import re, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[1]
# The exact leaked-token shape and other live-credential patterns must never appear.
PATTERNS = [
    re.compile(r"sk_user_[A-Za-z0-9]{16,}"),
    re.compile(r"sk-ant-[A-Za-z0-9]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9]{20,}"),
]
# Directories that are not source of truth: virtualenvs, VCS internals, caches
# and build output. Scanning their (often binary) contents yields false positives.
SKIP_DIRS = {
    ".venv", "venv", ".git", "__pycache__", "build", "dist",
    "node_modules", ".ruff_cache", ".pytest_cache", ".mypy_cache", ".eggs",
}
# Only scan text-like source files; binaries can coincidentally match a pattern.
TEXT_SUFFIXES = {
    ".py", ".md", ".txt", ".toml", ".cfg", ".ini", ".json", ".yaml", ".yml",
    ".sh", ".env", ".example", ".gitignore", ".dockerfile", "",
}


def test_repo_has_no_live_secrets():
    offenders = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or "/tests/" in str(path):
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.suffix not in TEXT_SUFFIXES:
            continue
        try:
            text = path.read_text(errors="ignore")
        except Exception:
            continue
        for pat in PATTERNS:
            if pat.search(text):
                offenders.append(f"{path}: {pat.pattern}")
    assert not offenders, offenders
