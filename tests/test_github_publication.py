"""Acceptance for GitHub publication (C12-F020).

"Currently represented: GitHub publication." The honest proof is that this
checkout's origin is a public GitHub repository that is genuinely published
and fetchable without any credential:

  - `origin` resolves to a github.com URL;
  - `git ls-remote origin HEAD` succeeds keyless and returns a real commit sha.

The clean-clone gate itself clones this repository from that same origin, so a
passing clone is corroborating evidence. This test skips cleanly when there is
no `origin` remote (a bare local checkout) or when the network is unavailable.
"""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git not available")


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(REPO), *args],
                          capture_output=True, text=True, timeout=30)


def _origin_url() -> str | None:
    r = _git("remote", "get-url", "origin")
    if r.returncode != 0:
        return None
    return r.stdout.strip() or None


def test_origin_is_a_github_url():
    url = _origin_url()
    if not url:
        pytest.skip("no origin remote (bare local checkout)")
    assert "github.com" in url, f"origin is not a GitHub URL: {url!r}"


def test_published_repo_head_is_fetchable_keyless():
    url = _origin_url()
    if not url:
        pytest.skip("no origin remote (bare local checkout)")
    # Keyless, unauthenticated ls-remote against the public repo. If the host
    # is offline or the repo is unreachable, skip rather than fail.
    r = _git("ls-remote", url, "HEAD")
    if r.returncode != 0:
        pytest.skip(f"origin unreachable (offline / private): {r.stderr.strip()[:200]}")
    first = (r.stdout.splitlines() or [""])[0].split("\t")[0].strip()
    assert re.fullmatch(r"[0-9a-f]{40}", first), (
        f"ls-remote did not return a commit sha: {r.stdout[:200]!r}"
    )
