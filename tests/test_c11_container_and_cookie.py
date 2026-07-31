"""Category-11 evidence: C11-F016 Non-root container.

Parses the shipped docker/Dockerfile and asserts it declares a
non-root USER directive after the account is created. Static
assertion; no docker daemon required.

C11-F002 (Local cookie protection) is covered by the existing
tests/test_browser.py::test_cookie_boundary_records_and_reports_zero_uploads
and tests/test_new_connectors_batch2.py::test_browser_profile_lifecycle;
this file does not duplicate that coverage.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# C11-F016
# ---------------------------------------------------------------------------


def test_c11_f016_dockerfile_declares_non_root_user():
    dockerfile = REPO / "docker" / "Dockerfile"
    assert dockerfile.exists(), (
        "docker/Dockerfile must exist for the remote-MCP container"
    )
    text = dockerfile.read_text()
    # A USER directive is present.
    user_lines = [ln.strip() for ln in text.splitlines()
                  if ln.strip().upper().startswith("USER ")]
    assert user_lines, "Dockerfile must declare a USER directive"
    # And the last USER is not root.
    last_user = user_lines[-1].split(None, 1)[1].strip()
    assert last_user.lower() not in ("root", "0", "0:0"), (
        f"final USER must not be root; got {last_user!r}"
    )


def test_c11_f016_dockerfile_creates_the_user_before_switching():
    dockerfile = (REPO / "docker" / "Dockerfile").read_text()
    # useradd or adduser must appear before the last USER line so we do
    # not switch to a non-existent user.
    lines = dockerfile.splitlines()
    user_idx = max(i for i, ln in enumerate(lines)
                   if ln.strip().upper().startswith("USER "))
    before = "\n".join(lines[:user_idx])
    assert re.search(r"\b(useradd|adduser|addgroup)\b", before), (
        "Dockerfile must create the account before the USER switch"
    )
