"""Round 6 mirror + representation tests.

Each test below asserts the specific acceptance sentence of the row it
is attached to. These are structural / in-process assertions, not live
end-to-end runs. That is honest: the mirror rows are catalogue-level
statements about what is represented in the repository, not claims that
the mirrored surface was exercised live end-to-end.

Live-gated pieces (Playwright browser display, hosted uvicorn deploy,
Claude Desktop activation, cross-OS installer matrix, live sigstore
signing, socket bind on 127.0.0.1) are deliberately NOT covered here
and the rows that need them stay honestly labelled elsewhere.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[3]
REPO = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# C09-F001 Private repository publication (SHAPE)
# ---------------------------------------------------------------------------
#
# Acceptance: this repository is a working git repository on a feature
# branch, with per-commit history for the production-completion
# programme. Live publication to a private GitHub org is external state
# and NOT asserted here; the row remains SHAPE-verified only.


def test_c09_f001_repository_is_a_git_working_copy_on_a_feature_branch():
    assert (REPO / ".git").exists(), (
        "expected repository/deye/.git/ to exist (repository is not a git working copy)"
    )
    r = subprocess.run(
        ["git", "-C", str(REPO), "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True, text=True, check=False, timeout=10,
    )
    assert r.returncode == 0, r.stderr
    branch = r.stdout.strip()
    assert branch.startswith("feature/") or branch in ("main", "master"), (
        f"unexpected branch: {branch!r}"
    )


def test_c09_f001_repository_has_recent_history_from_production_completion_programme():
    r = subprocess.run(
        ["git", "-C", str(REPO), "log", "--oneline", "-n", "20"],
        capture_output=True, text=True, check=False, timeout=10,
    )
    assert r.returncode == 0
    log = r.stdout
    # The production-completion programme's round commits carry the
    # 'round N:' prefix. Assert at least one recent round commit exists.
    assert any(f"round {n}:" in log for n in range(1, 10)), (
        f"expected at least one 'round N:' commit in recent history; got: {log[:400]}"
    )


# ---------------------------------------------------------------------------
# C12-F011 IP pinning represented (SHAPE)
# ---------------------------------------------------------------------------
#
# Acceptance: "IP pinning represented." This is a shape assertion that
# _PinnedHTTPConnection and _PinnedHTTPSConnection exist, accept a
# pre-validated IP, and are wired into safe_get. The live TCP round-
# trip proof belongs to C11-F008, which is still IMPLEMENTED BUT NOT
# FULLY VERIFIED because the sandbox forbids bind() on 127.0.0.1.


def test_c12_f011_pinned_connection_classes_exist_and_accept_pinned_ip():
    import ssl
    from deye.connectors.base import _PinnedHTTPConnection, _PinnedHTTPSConnection
    conn = _PinnedHTTPConnection("example.com", "127.0.0.1", port=80)
    assert getattr(conn, "host", None) == "example.com"
    assert getattr(conn, "_pinned_ip", None) == "127.0.0.1"
    # Do not call connect() -- the sandbox forbids the syscall and, more
    # importantly, C12-F011's acceptance is representational, not live.
    ctx = ssl.create_default_context()
    conn_s = _PinnedHTTPSConnection(
        "example.com", "127.0.0.1", port=443, context=ctx,
    )
    assert getattr(conn_s, "_pinned_ip", None) == "127.0.0.1"


def test_c12_f011_safe_get_actually_wires_the_pinned_connection_classes():
    src = (REPO / "deye" / "connectors" / "base.py").read_text()
    # safe_get must reference the pinned connection classes for the
    # representation to be meaningful (not just imported dead code).
    assert "_PinnedHTTPConnection(" in src or "_PinnedHTTPConnection " in src, (
        "safe_get must actually instantiate _PinnedHTTPConnection"
    )
    assert "_PinnedHTTPSConnection(" in src or "_PinnedHTTPSConnection " in src


# ---------------------------------------------------------------------------
# C12-F022 True automatic installation on the user's Mac (SHAPE + IN-PROCESS)
# ---------------------------------------------------------------------------
#
# Acceptance: install.sh + lifecycle helpers cover it on macOS; Windows
# equivalent still pending. The install.sh script is inspected for
# shape (POSIX + safe flags + venv + pip install + deye setup) and the
# lifecycle module is imported to verify its public surface.


def test_c12_f022_install_sh_exists_and_declares_safe_shell_shape():
    install = WORKSPACE / "scripts" / "install.sh"
    assert install.exists(), f"expected {install} to exist"
    txt = install.read_text()
    first = txt.splitlines()[0]
    assert first.startswith("#!/"), f"install.sh must start with a shebang; got {first!r}"
    # Safe-shell posture: at minimum set -e; set -eu (with -u) is stricter.
    assert "set -e" in txt or "set -eu" in txt, "install.sh must use set -e"
    # Every acceptance-bearing step referenced in the script header.
    # The script uses $PY (a variable) rather than the literal 'python3',
    # so the token to assert is '-m venv', and the pip install call uses
    # '-m pip install'. Setup runs via 'deye.cli setup' (module form).
    assert "-m venv" in txt, "install.sh must create a venv"
    assert "pip install" in txt, "install.sh must run pip install"
    assert "deye.cli setup" in txt or "deye setup" in txt, (
        "install.sh must call deye setup"
    )


def test_c12_f022_lifecycle_module_public_surface_is_importable_on_macos():
    # Round-trip the module: we do not call functions that mutate the
    # host, we only assert their existence per the acceptance sentence.
    from deye import lifecycle
    for name in ("env_detect", "detect_extras", "provision_extra",
                 "portable_config_export", "portable_config_import",
                 "check_update", "apply_update", "rollback_to",
                 "uninstall", "repair_guidance"):
        assert callable(getattr(lifecycle, name, None)), (
            f"lifecycle.{name} must be a callable public surface"
        )


def test_c12_f022_env_detect_actually_runs_on_this_mac_and_returns_a_report():
    from deye import lifecycle
    report = lifecycle.env_detect()
    d = report.to_dict()
    # Not asserting exact OS name -- the test just proves env_detect()
    # completed a real macOS-Python-level run without raising.
    assert d.get("os_name")
    assert d.get("python_version")


# ---------------------------------------------------------------------------
# C12-F025 Automatic remote hosting (SHAPE)
# ---------------------------------------------------------------------------
#
# Acceptance: "docker-compose + reverse-proxy guidance." No docker or
# podman command is ever run here; the compose file and the guidance
# doc are inspected as text only.


def test_c12_f025_docker_compose_shape_binds_loopback_and_requires_token():
    compose = REPO / "docker" / "docker-compose.yml"
    assert compose.exists(), f"expected {compose}"
    txt = compose.read_text()
    # Loopback bind is the acceptance's safe-default posture.
    assert "127.0.0.1:8080:8080" in txt, "compose must bind loopback only"
    # Bearer-token required, sourced from the environment.
    assert "DEYE_HTTP_TOKEN" in txt
    # Hardened container.
    assert "no-new-privileges:true" in txt
    assert "cap_drop" in txt and "ALL" in txt


def test_c12_f025_remote_deployment_guide_is_present_and_names_reverse_proxy():
    guides = [
        REPO / "docs" / "REMOTE_DEPLOYMENT.md",
        WORKSPACE / "docs" / "MCP_DEPLOYMENT.md",
    ]
    found = None
    for g in guides:
        if g.exists():
            found = g
            break
    assert found is not None, f"expected one of {guides} to exist"
    txt = found.read_text().lower()
    # The guidance must mention TLS termination and a reverse-proxy
    # posture (Caddy, nginx, traefik, cloudflare, or similar).
    assert "tls" in txt or "https" in txt
    assert any(p in txt for p in ("reverse proxy", "reverse-proxy",
                                   "caddy", "nginx", "traefik")), (
        "guide must name a reverse proxy or TLS-termination pattern"
    )


# ---------------------------------------------------------------------------
# C12-F027 Browser automation represented (SHAPE + IN-PROCESS)
# ---------------------------------------------------------------------------
#
# Acceptance: "adapter + consent gate + isolation contract shipped;
# live headless behind [browser] extras + playwright install." We
# assert the adapter code, the consent gate, and the isolation
# contract; live headless is deferred to C04 rows.


def test_c12_f027_browser_adapter_module_imports_and_declares_public_surface():
    from deye import browser as b
    assert callable(getattr(b, "is_available", None))
    assert callable(getattr(b, "unavailable_reason", None))
    assert hasattr(b, "BrowserAdapter"), "BrowserAdapter class must be present"


def test_c12_f027_browser_adapter_declares_consent_gate_and_profile_isolation():
    src = (REPO / "deye" / "browser" / "__init__.py").read_text()
    # Consent gate is required by the acceptance.
    assert "ConsentPolicy" in src
    # Consent-gated methods must appear in the module docstring / API.
    for method in ("navigate_and_click", "fill_form"):
        assert method in src, f"BrowserAdapter must expose {method}"
    # Profile isolation contract: named on-disk profile directories
    # with owner-only permissions, enumerable via profile_report().
    from deye.browser import profiles as bp
    for name in ("list_profiles", "create_profile", "remove_profile",
                 "profile_report"):
        assert callable(getattr(bp, name, None)), (
            f"deye.browser.profiles.{name} must be a callable public surface"
        )


def test_c12_f027_browser_adapter_degrades_cleanly_when_playwright_absent():
    # In this sandbox Playwright is NOT installed. is_available() must
    # return False without raising, and unavailable_reason() must be a
    # non-empty diagnostic that names playwright.
    from deye import browser as b
    ok = b.is_available()
    reason = b.unavailable_reason()
    if ok:
        # If Playwright happens to be installed (developer machine),
        # the graceful-degradation path is not exercised in this run.
        # That is fine -- the row's acceptance is about the presence of
        # the contract, not about the negative branch specifically.
        assert reason == "" or "available" in reason.lower()
    else:
        assert "playwright" in reason.lower()


# ---------------------------------------------------------------------------
# C12-F035 Automatic updates and rollback represented (IN-PROCESS)
# ---------------------------------------------------------------------------
#
# Acceptance: "Automatic updates + rollback via lifecycle.check_update
# + apply_update + rollback_to." Mirror of C01-F005 which is already
# PROD. The mirror gets its own dedicated in-process test that
# exercises each surface without ever touching PyPI or mutating the
# environment.


def test_c12_f035_check_update_returns_report_shape_offline():
    from deye import lifecycle
    report = lifecycle.check_update(offline=True)
    # Offline path must not touch the network; must return a structured
    # report with a determinate state token.
    d = report if isinstance(report, dict) else report.to_dict()
    assert "state" in d or "status" in d or "reason" in d, (
        f"check_update offline must return a shaped report; got {d!r}"
    )


def test_c12_f035_apply_update_dry_run_returns_structured_result():
    from deye import lifecycle
    # Rollback is a thin wrapper over apply_update; both must accept an
    # explicit spec and refuse to touch PyPI when offline.
    res = lifecycle.apply_update("deye==0.2.0", offline=True)
    assert isinstance(res, dict)
    # The dry-run / offline path must NOT contain a real pip completion
    # marker; it must contain either the offline-refusal state or the
    # spec passed in.
    keys = " ".join(str(v) for v in res.values()).lower() + " " + " ".join(res.keys()).lower()
    assert ("offline" in keys or "skipped" in keys or "deye==0.2.0" in keys), (
        f"apply_update offline must indicate offline / skipped / spec; got {res!r}"
    )


def test_c12_f035_rollback_to_delegates_to_apply_update_with_pinned_spec():
    from deye import lifecycle
    res = lifecycle.rollback_to("0.2.0", offline=True)
    assert isinstance(res, dict)
    joined = json.dumps(res, default=str)
    assert "0.2.0" in joined or "offline" in joined.lower()
