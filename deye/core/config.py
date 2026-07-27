"""Configuration + secret-reference resolution.

Secrets are NEVER stored inline. Config holds *references* like
``env:EXA_API_KEY`` or ``keychain:deye/exa``; the value is resolved at execution
time and never persisted, logged, or handed to the model.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from deye.core.policy import Limits

DEFAULT_HOME = Path(os.environ.get("DEYE_HOME", str(Path.home() / ".deye")))


def resolve_secret(ref: str | None) -> str | None:
    """Resolve a secret *reference* to its value at call time.

    Supported: ``env:NAME`` and ``keychain:SERVICE/ACCOUNT`` (via the OS
    keyring if installed). A raw non-prefixed value is treated as already
    resolved but discouraged.
    """
    if not ref:
        return None
    if ref.startswith("env:"):
        return os.environ.get(ref[4:])
    if ref.startswith("keychain:"):
        try:
            import keyring  # optional dependency
        except Exception:
            return None
        target = ref[len("keychain:"):]
        service, _, account = target.partition("/")
        return keyring.get_password(service, account or "deye")
    return ref


@dataclass
class Config:
    home: Path = field(default_factory=lambda: DEFAULT_HOME)
    limits: Limits = field(default_factory=Limits)
    # provider/adapter secret *references* only:
    search_provider: str = "duckduckgo"  # FOSS-first default, no key required
    exa_api_key_ref: str = "env:EXA_API_KEY"
    read_only: bool = True

    def ensure_home(self) -> Path:
        self.home.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(self.home, 0o700)  # owner-only, per hardening guidance
        except OSError:
            pass
        return self.home

    @property
    def evidence_db(self) -> Path:
        return self.home / "evidence.db"

    @classmethod
    def load(cls, path: Path | None = None) -> Config:
        path = path or (DEFAULT_HOME / "config.json")
        cfg = cls()
        if path.exists():
            data = json.loads(path.read_text())
            cfg.search_provider = data.get("search_provider", cfg.search_provider)
            cfg.read_only = data.get("read_only", cfg.read_only)
            cfg.exa_api_key_ref = data.get("exa_api_key_ref", cfg.exa_api_key_ref)
        return cfg
