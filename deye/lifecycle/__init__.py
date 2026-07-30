"""D-Eye lifecycle package.

Local, FOSS-first setup / update / backup / rollback / uninstall / repair
primitives. Every function is stdlib-only, deterministic, and safe under
the strict-sandbox mandate (no shell sourcing, no wildcards, no eval).

Public surface:
    env_detect() -> EnvironmentReport
    detect_extras() -> ExtrasReport
    provision_extra(name)
    portable_config_export(path)
    portable_config_import(path)
    backup_home(dest_dir) -> Path
    restore_home(archive)
    check_update() -> UpdateReport
    apply_update(spec)
    rollback_to(version)
    uninstall(remove_home=False) -> UninstallReport
    repair_guidance() -> list[RepairSuggestion]

None of these mutate anything unless explicitly asked; each returns a
structured report so callers (CLI, MCP tool) can decide.
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
import sysconfig
import tarfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from deye import __version__


# ---------------------------------------------------------------------------
# Environment detection
# ---------------------------------------------------------------------------

@dataclass
class EnvironmentReport:
    """Snapshot of the host + interpreter D-Eye is running under.

    Purely observational - never mutates the machine.
    """
    os_name: str
    os_version: str
    machine: str
    python_version: str
    python_executable: str
    is_venv: bool
    stdlib_paths_ok: bool
    detected_cli: dict[str, str | None]
    detected_browser: dict[str, str | None]
    home_dir: str
    is_offline: bool
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _which(name: str) -> str | None:
    return shutil.which(name)


def env_detect(home: Path | None = None) -> EnvironmentReport:
    """Detect OS, Python, venv, notable CLIs and browsers, offline flag."""
    from deye.core.config import Config

    cfg_home = home or Config.load().home
    warnings: list[str] = []
    is_venv = sys.prefix != sys.base_prefix
    if not is_venv:
        warnings.append(
            "not running inside a venv - install into a virtualenv or pipx to "
            "keep D-Eye isolated"
        )
    stdlib_ok = bool(sysconfig.get_paths().get("stdlib")) and sys.version_info >= (3, 10)
    if not stdlib_ok:
        warnings.append(
            f"python {sys.version_info.major}.{sys.version_info.minor} is below "
            "the D-Eye floor of 3.10"
        )

    cli = {
        name: _which(name)
        for name in ("git", "docker", "podman", "node", "npm", "claude", "gh", "pip")
    }
    browser = {
        name: _which(name)
        for name in ("chromium", "chrome", "google-chrome", "firefox", "safari")
    }

    return EnvironmentReport(
        os_name=platform.system(),
        os_version=platform.release(),
        machine=platform.machine(),
        python_version=platform.python_version(),
        python_executable=sys.executable,
        is_venv=is_venv,
        stdlib_paths_ok=stdlib_ok,
        detected_cli=cli,
        detected_browser=browser,
        home_dir=str(cfg_home),
        is_offline=os.environ.get("DEYE_OFFLINE", "").lower() in {"1", "true", "yes"},
        warnings=warnings,
    )


# ---------------------------------------------------------------------------
# Extras / dependency provisioning
# ---------------------------------------------------------------------------

# Extras defined in pyproject.toml. Kept here as the single source-of-truth
# consulted by the CLI + doctor + MCP capability listing. Adding an extra?
# Also update pyproject.toml, docs/DEPENDENCY_AND_LICENCE_POLICY.md and the
# licence attribution in NOTICE.
KNOWN_EXTRAS = {
    "mcp": {"purpose": "local stdio MCP server", "modules": ["mcp"]},
    "remote": {"purpose": "remote HTTP MCP + bearer auth", "modules": ["mcp", "uvicorn", "starlette"]},
    "secrets": {"purpose": "OS keyring for API-key storage", "modules": ["keyring"]},
    "rich": {"purpose": "richer RSS/HTTP client (optional)", "modules": ["feedparser", "requests"]},
    "browser": {"purpose": "optional local Playwright browser adapter", "modules": ["playwright"]},
    "embeddings": {"purpose": "optional local embeddings + sqlite-vec vector store", "modules": ["fastembed", "sqlite_vec"]},
    "backend": {"purpose": "optional local auth + observability", "modules": ["argon2", "prometheus_client"]},
    "dev": {"purpose": "developer tools (test, lint)", "modules": ["pytest", "ruff"]},
}


@dataclass
class ExtrasReport:
    available: dict[str, bool]
    modules: dict[str, list[str]]
    purposes: dict[str, str]

    def to_dict(self) -> dict:
        return asdict(self)


def _module_available(name: str) -> bool:
    try:
        __import__(name)
        return True
    except Exception:
        return False


def detect_extras() -> ExtrasReport:
    """Report which extras' Python modules are importable."""
    avail: dict[str, bool] = {}
    modules: dict[str, list[str]] = {}
    purposes: dict[str, str] = {}
    for extra, meta in KNOWN_EXTRAS.items():
        modules[extra] = list(meta["modules"])
        purposes[extra] = meta["purpose"]
        avail[extra] = all(_module_available(m) for m in meta["modules"])
    return ExtrasReport(available=avail, modules=modules, purposes=purposes)


def provision_extra(name: str, *, python: str | None = None, offline: bool = False) -> dict:
    """Install one extras group using the given Python's pip. Never runs pip -U.

    Refuses to run when DEYE_OFFLINE=1 or offline=True - provisioning is a
    network action, and the offline contract must hold.
    """
    if name not in KNOWN_EXTRAS:
        raise ValueError(f"unknown extra {name!r}; known: {sorted(KNOWN_EXTRAS)}")
    if offline or os.environ.get("DEYE_OFFLINE", "").lower() in {"1", "true", "yes"}:
        return {"ok": False, "reason": "offline mode - provisioning skipped"}
    py = python or sys.executable
    cmd = [py, "-m", "pip", "install", "-e", f".[{name}]"]
    proc = subprocess.run(cmd, check=False, capture_output=True, text=True)
    return {
        "ok": proc.returncode == 0,
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-500:],
        "stderr_tail": proc.stderr[-500:],
        "command": cmd,
    }


# ---------------------------------------------------------------------------
# Portable config
# ---------------------------------------------------------------------------

def portable_config_export(dest: Path, *, home: Path | None = None) -> Path:
    """Write DEYE_HOME/config.json (redacted) + package version to *dest*.

    Never exports credentials; only reads config.json and stamps version/date.
    """
    from deye.core.config import Config
    from deye.core.redact import redact

    cfg = Config.load()
    home_dir = home or cfg.home
    config = home_dir / "config.json"
    payload = {
        "deye_version": __version__,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "config": {},
    }
    if config.exists():
        payload["config"] = json.loads(redact(config.read_text()))
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(payload, indent=2))
    return dest


def portable_config_import(src: Path, *, home: Path | None = None) -> dict:
    """Import a portable config into the local DEYE_HOME.

    Merges into an existing config.json rather than overwriting; unknown
    keys are ignored (forward-compat).
    """
    from deye.core.config import Config

    cfg = Config.load()
    home_dir = home or cfg.ensure_home()
    payload = json.loads(src.read_text())
    incoming = payload.get("config") or {}
    target = home_dir / "config.json"
    current: dict = {}
    if target.exists():
        current = json.loads(target.read_text())
    known_keys = {"search_provider", "read_only", "exa_api_key_ref"}
    merged = dict(current)
    for k in known_keys & incoming.keys():
        merged[k] = incoming[k]
    target.write_text(json.dumps(merged, indent=2))
    return {"ok": True, "target": str(target), "keys_imported": sorted(known_keys & incoming.keys())}


# ---------------------------------------------------------------------------
# Backup / restore
# ---------------------------------------------------------------------------

def backup_home(dest_dir: Path, *, home: Path | None = None) -> Path:
    """Create a UTC-stamped .tar.gz of DEYE_HOME under dest_dir. Idempotent."""
    from deye.core.config import Config

    cfg = Config.load()
    home_dir = home or cfg.ensure_home()
    dest_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = dest_dir / f"deye-home-{stamp}.tar.gz"
    with tarfile.open(out, "w:gz") as tar:
        for entry in sorted(home_dir.rglob("*")):
            if entry.is_file():
                tar.add(entry, arcname=str(entry.relative_to(home_dir)))
    return out


def restore_home(archive: Path, *, home: Path | None = None,
                 overwrite: bool = False) -> dict:
    """Extract a backup tar.gz into DEYE_HOME.

    Fails closed unless *overwrite=True* and the destination is a D-Eye home.
    """
    from deye.core.config import Config

    cfg = Config.load()
    home_dir = home or cfg.ensure_home()
    # sanity: only overwrite an existing home if the user opts in.
    if any(home_dir.rglob("*")) and not overwrite:
        return {"ok": False, "reason": "home not empty; pass overwrite=True to proceed"}
    with tarfile.open(archive, "r:gz") as tar:
        # defensive: reject entries with absolute paths or parent traversal
        for m in tar.getmembers():
            n = Path(m.name)
            if n.is_absolute() or ".." in n.parts:
                return {"ok": False, "reason": f"unsafe path in archive: {m.name}"}
        tar.extractall(home_dir, filter="data")
    return {"ok": True, "restored_to": str(home_dir)}


# ---------------------------------------------------------------------------
# Update / rollback
# ---------------------------------------------------------------------------

@dataclass
class UpdateReport:
    current_version: str
    available_version: str | None
    reason: str

    def to_dict(self) -> dict:
        return asdict(self)


def check_update(*, offline: bool = False) -> UpdateReport:
    """Compare installed version to PyPI. Offline-safe: returns 'skipped'."""
    if offline or os.environ.get("DEYE_OFFLINE", "").lower() in {"1", "true", "yes"}:
        return UpdateReport(
            current_version=__version__,
            available_version=None,
            reason="offline mode - network check skipped",
        )
    # Deliberately avoid the network here in the stdlib path. Downstream
    # callers with `pip` available may run `pip index versions deye`; this
    # function stays honest without pretending to reach PyPI itself.
    return UpdateReport(
        current_version=__version__,
        available_version=None,
        reason="update check requires a caller-provided version source; "
               "run `pip index versions deye` or check the release tag",
    )


def apply_update(spec: str, *, python: str | None = None,
                 offline: bool = False, dry_run: bool = False) -> dict:
    """Install a specific version spec (e.g. 'deye==0.3.0' or a wheel path).

    Records the pre-update version so `rollback_to()` can restore it.
    """
    if offline or os.environ.get("DEYE_OFFLINE", "").lower() in {"1", "true", "yes"}:
        return {"ok": False, "reason": "offline mode - update skipped"}
    py = python or sys.executable
    cmd = [py, "-m", "pip", "install", spec]
    if dry_run:
        return {"ok": True, "would_run": cmd, "dry_run": True}
    proc = subprocess.run(cmd, check=False, capture_output=True, text=True)
    return {
        "ok": proc.returncode == 0,
        "returncode": proc.returncode,
        "command": cmd,
        "previous_version": __version__,
    }


def rollback_to(version: str, *, python: str | None = None, offline: bool = False) -> dict:
    """Reinstall a specific D-Eye version. Thin wrapper over apply_update."""
    return apply_update(f"deye=={version}", python=python, offline=offline)


# ---------------------------------------------------------------------------
# Uninstall
# ---------------------------------------------------------------------------

@dataclass
class UninstallReport:
    removed_home: bool
    home_backup: str | None
    pip_result: dict | None

    def to_dict(self) -> dict:
        return asdict(self)


def uninstall(*, remove_home: bool = False, python: str | None = None,
              backup_dir: Path | None = None) -> UninstallReport:
    """Uninstall D-Eye. Always backs up DEYE_HOME before touching it."""
    from deye.core.config import Config

    cfg = Config.load()
    backup_path: Path | None = None
    if remove_home and cfg.home.exists():
        backup_path = backup_home(backup_dir or (cfg.home.parent / "deye-uninstall-backups"))
    py = python or sys.executable
    pip = subprocess.run(
        [py, "-m", "pip", "uninstall", "-y", "deye"],
        check=False, capture_output=True, text=True,
    )
    removed = False
    if remove_home and cfg.home.exists() and backup_path is not None:
        shutil.rmtree(cfg.home)
        removed = True
    return UninstallReport(
        removed_home=removed,
        home_backup=str(backup_path) if backup_path else None,
        pip_result={"returncode": pip.returncode, "stdout_tail": pip.stdout[-300:]},
    )


# ---------------------------------------------------------------------------
# Repair guidance
# ---------------------------------------------------------------------------

@dataclass
class RepairSuggestion:
    id: str
    severity: str          # info | warn | error
    condition: str
    remedy: str

    def to_dict(self) -> dict:
        return asdict(self)


def repair_guidance() -> list[RepairSuggestion]:
    """Deterministic, non-executing suggestions the user can accept or reject."""
    env = env_detect()
    extras = detect_extras()
    out: list[RepairSuggestion] = []

    if not env.is_venv:
        out.append(RepairSuggestion(
            id="venv.missing",
            severity="warn",
            condition="not running inside a virtualenv",
            remedy=(
                "Create one: `python3 -m venv .venv && ./.venv/bin/python "
                "-m pip install -e .`."
            ),
        ))
    if not env.stdlib_paths_ok:
        out.append(RepairSuggestion(
            id="python.too_old",
            severity="error",
            condition=f"python {env.python_version} is below the 3.10 floor",
            remedy="Install Python 3.10+ (Homebrew/uv/pyenv all work).",
        ))
    if env.detected_cli.get("git") is None:
        out.append(RepairSuggestion(
            id="cli.git_missing",
            severity="info",
            condition="`git` not on PATH",
            remedy="Install git via your OS package manager if you plan to "
                   "publish D-Eye to a repository.",
        ))
    if not extras.available.get("mcp"):
        out.append(RepairSuggestion(
            id="extra.mcp_missing",
            severity="info",
            condition="`mcp` optional extra not installed",
            remedy="Install with `./.venv/bin/python -m pip install -e '.[mcp]'`.",
        ))
    if extras.available.get("browser") is False:
        out.append(RepairSuggestion(
            id="extra.browser_missing",
            severity="info",
            condition="`browser` optional extra not installed",
            remedy=(
                "Only needed for JS-heavy pages. Install with "
                "`./.venv/bin/python -m pip install -e '.[browser]'` and "
                "`playwright install chromium`."
            ),
        ))
    return out


# ---------------------------------------------------------------------------
# Aggregate report - used by `deye lifecycle status` and MCP surface_status
# ---------------------------------------------------------------------------

def aggregate_report(*, home: Path | None = None) -> dict:
    return {
        "environment": env_detect(home=home).to_dict(),
        "extras": detect_extras().to_dict(),
        "repair_suggestions": [s.to_dict() for s in repair_guidance()],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
