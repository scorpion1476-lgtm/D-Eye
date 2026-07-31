"""Category-9 script acceptance tests.

These tests use tmp_path git repos (initialised via subprocess) to
exercise the three round-2 scripts end-to-end:

- scripts/verify_repo.py   -> C09-F002, C09-F004, C09-F006
- scripts/gen_changelog.py -> C09-F008
- scripts/scan_secrets.py  -> C09-F005

Every test uses only Python stdlib plus the system 'git' binary; no
network, no bind, no browser. If 'git' is not available the test
module skips cleanly.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = REPO_ROOT / "scripts"

pytestmark = pytest.mark.skipif(
    shutil.which("git") is None,
    reason="git binary not available in this environment",
)


# ---------------------------------------------------------------------------
# tmp_path fixture: a real git repo with a couple of Conventional-Commit
# messages, a tag, extra branches, and a fake secret file.
# ---------------------------------------------------------------------------


def _git(cwd: Path, *args: str) -> str:
    env = os.environ.copy()
    env["GIT_AUTHOR_NAME"] = "Test"
    env["GIT_AUTHOR_EMAIL"] = "test@example.invalid"
    env["GIT_COMMITTER_NAME"] = "Test"
    env["GIT_COMMITTER_EMAIL"] = "test@example.invalid"
    r = subprocess.run(
        ["git", *args], cwd=str(cwd),
        capture_output=True, text=True, check=True, timeout=15,
        env=env,
    )
    return r.stdout.strip()


@pytest.fixture()
def tmp_repo(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "--initial-branch=feature/prod-complete", "--quiet")
    _git(root, "config", "commit.gpgsign", "false")
    _git(root, "config", "tag.gpgSign", "false")
    (root / "README.md").write_text("# test repo\n")
    _git(root, "add", "README.md")
    _git(root, "commit", "-m", "chore: initial commit")
    (root / "a.py").write_text("print('hello')\n")
    _git(root, "add", "a.py")
    _git(root, "commit", "-m", "feat(app): add greeting")
    _git(root, "tag", "v0.1.0")
    (root / "b.py").write_text("print('bye')\n")
    _git(root, "add", "b.py")
    _git(root, "commit", "-m", "fix(app): typo in bye message")
    (root / "SECURITY.md").write_text("# security\n")
    _git(root, "add", "SECURITY.md")
    _git(root, "commit", "-m", "security(policy): tighten CSP")
    (root / "deps.txt").write_text("requests==2.32.0\n")
    _git(root, "add", "deps.txt")
    _git(root, "commit", "-m", "deps: bump requests to 2.32.0")
    (root / "notes.md").write_text("random note\n")
    _git(root, "add", "notes.md")
    _git(root, "commit", "-m", "just a message without prefix")
    _git(root, "branch", "topic/other")
    return root


def _run_script(script: Path, *args: str, cwd: Path | None = None):
    r = subprocess.run(
        [sys.executable, str(script), *args],
        cwd=str(cwd) if cwd else None,
        capture_output=True, text=True, timeout=15,
    )
    return r


# ---------------------------------------------------------------------------
# C09-F004 / C09-F002 / C09-F006 -- verify_repo.py
# ---------------------------------------------------------------------------


class TestVerifyRepo:
    def test_reports_branch_and_head_json(self, tmp_repo):
        r = _run_script(SCRIPTS / "verify_repo.py", "--path", str(tmp_repo))
        assert r.returncode == 0, r.stderr
        data = json.loads(r.stdout)
        assert data["branch"] == "feature/prod-complete"
        assert len(data["head"]) == 40  # sha1
        assert data["on_default_branch"] is False

    def test_enumerates_multiple_branches(self, tmp_repo):
        # C09-F006 branch management: script must list every local branch.
        r = _run_script(SCRIPTS / "verify_repo.py", "--path", str(tmp_repo))
        assert r.returncode == 0, r.stderr
        data = json.loads(r.stdout)
        branches = set(data["branches"])
        assert "feature/prod-complete" in branches
        assert "topic/other" in branches

    def test_lists_tags(self, tmp_repo):
        r = _run_script(SCRIPTS / "verify_repo.py", "--path", str(tmp_repo))
        data = json.loads(r.stdout)
        assert "v0.1.0" in data["tags"]

    def test_refuses_when_on_main_without_flag(self, tmp_repo):
        _git(tmp_repo, "checkout", "-b", "main", "--quiet")
        r = _run_script(SCRIPTS / "verify_repo.py", "--path", str(tmp_repo))
        assert r.returncode == 1
        data = json.loads(r.stdout)
        assert data["branch"] == "main"
        assert data["on_default_branch"] is True

    def test_accepts_main_with_allow_flag(self, tmp_repo):
        _git(tmp_repo, "checkout", "-b", "master", "--quiet")
        r = _run_script(SCRIPTS / "verify_repo.py",
                        "--path", str(tmp_repo), "--allow-main")
        assert r.returncode == 0, r.stderr
        data = json.loads(r.stdout)
        assert data["branch"] == "master"
        assert data["allow_main"] is True

    def test_reports_error_when_not_a_repo(self, tmp_path):
        outside = tmp_path / "not-a-repo"
        outside.mkdir()
        r = _run_script(SCRIPTS / "verify_repo.py", "--path", str(outside))
        assert r.returncode == 2
        assert "error" in json.loads(r.stdout)


# ---------------------------------------------------------------------------
# C09-F008 -- gen_changelog.py
# ---------------------------------------------------------------------------


class TestGenChangelog:
    def test_buckets_by_conventional_commit_prefix(self, tmp_repo):
        # There are no commits AFTER the last tag except those we added,
        # so 'since last tag' picks up fix / security / deps / one un-
        # prefixed. Bucket into headings.
        r = _run_script(SCRIPTS / "gen_changelog.py", "--path", str(tmp_repo))
        assert r.returncode == 0, r.stderr
        out = r.stdout
        assert "## Fixed" in out
        assert "typo in bye message" in out
        assert "## Security" in out
        assert "tighten CSP" in out
        assert "## Dependencies" in out
        assert "bump requests" in out
        # Un-prefixed commit falls into Chore
        assert "## Chore" in out
        assert "without prefix" in out
        # feat is BEFORE the tag so should NOT be in this section
        assert "## Added" not in out

    def test_range_flag_takes_precedence_and_covers_feat(self, tmp_repo):
        r = _run_script(SCRIPTS / "gen_changelog.py",
                        "--path", str(tmp_repo), "--range", "HEAD")
        assert r.returncode == 0, r.stderr
        out = r.stdout
        # Now the tagged feat commit is included.
        assert "## Added" in out
        assert "add greeting" in out

    def test_output_is_deterministic(self, tmp_repo):
        r1 = _run_script(SCRIPTS / "gen_changelog.py", "--path", str(tmp_repo))
        r2 = _run_script(SCRIPTS / "gen_changelog.py", "--path", str(tmp_repo))
        assert r1.stdout == r2.stdout

    def test_no_commits_range_gives_empty_marker(self, tmp_repo):
        r = _run_script(SCRIPTS / "gen_changelog.py",
                        "--path", str(tmp_repo), "--range", "HEAD..HEAD")
        assert r.returncode == 0, r.stderr
        assert "_No commits in this range._" in r.stdout


# ---------------------------------------------------------------------------
# C09-F005 -- scan_secrets.py
# ---------------------------------------------------------------------------


class TestScanSecrets:
    def test_clean_repo_returns_zero(self, tmp_repo):
        r = _run_script(SCRIPTS / "scan_secrets.py", "--path", str(tmp_repo))
        assert r.returncode == 0, r.stderr
        assert "no secrets found" in r.stdout

    def test_detects_planted_github_token(self, tmp_repo):
        # Split the marker so this test file itself is not flagged.
        planted = "ghp_" + "A" * 25
        (tmp_repo / "leaked.env").write_text(f"TOKEN={planted}\n")
        r = _run_script(SCRIPTS / "scan_secrets.py", "--path", str(tmp_repo))
        assert r.returncode == 1
        assert "leaked.env" in r.stdout
        assert "github_token" in r.stdout

    def test_detects_planted_aws_access_key(self, tmp_repo):
        planted = "AKIA" + "B" * 16
        (tmp_repo / "aws.txt").write_text(f"key={planted}\n")
        r = _run_script(SCRIPTS / "scan_secrets.py", "--path", str(tmp_repo))
        assert r.returncode == 1
        assert "aws.txt" in r.stdout
        assert "aws_access_key_id" in r.stdout

    def test_output_is_deterministic_across_runs(self, tmp_repo):
        planted = "ghp_" + "C" * 25
        (tmp_repo / "leaked.env").write_text(f"TOKEN={planted}\n")
        r1 = _run_script(SCRIPTS / "scan_secrets.py", "--path", str(tmp_repo))
        r2 = _run_script(SCRIPTS / "scan_secrets.py", "--path", str(tmp_repo))
        assert r1.stdout == r2.stdout
        assert r1.returncode == r2.returncode == 1

    def test_not_a_directory_returns_two(self, tmp_path):
        f = tmp_path / "file.txt"
        f.write_text("hi")
        r = _run_script(SCRIPTS / "scan_secrets.py", "--path", str(f))
        assert r.returncode == 2
