"""Signed-release and bundle verification with a FOSS signing toolchain.

Two layers, both FOSS and offline:

1. Integrity (standard library, always available):
   a ``SHA256SUMS`` manifest lists the SHA-256 of every file in a bundle.
   ``verify_manifest`` recomputes each digest and reports any mismatch, so a
   single flipped byte in any artifact is detected. No external tool needed.

2. Authenticity (OpenSSL Ed25519, a ubiquitous FOSS toolchain):
   ``sign_manifest`` signs the ``SHA256SUMS`` file with an Ed25519 private key
   (``SHA256SUMS.sig``); ``verify_signature`` checks it against the public key.
   Tampering with the manifest breaks the signature. This needs no hosted
   identity or account - the keypair is generated locally with ``openssl``.

The signature covers the manifest and the manifest covers every artifact, so
verifying both proves the whole bundle is authentic and untampered. The public
key can be shipped alongside the bundle (``PUBKEY.pem``) for convenience; trust
is anchored by publishing that key's fingerprint out of band.

This module shells out to ``openssl`` only for the asymmetric signature; if
``openssl`` is absent the integrity layer still works and the signing calls
raise a clear error rather than degrading silently.
"""
from __future__ import annotations

import hashlib
import shutil
import subprocess
from pathlib import Path

MANIFEST_NAME = "SHA256SUMS"
SIG_NAME = "SHA256SUMS.sig"
PUBKEY_NAME = "PUBKEY.pem"

# Files that describe/sign the bundle are never part of the hashed payload.
_EXCLUDED = {MANIFEST_NAME, SIG_NAME, PUBKEY_NAME}


class ReleaseError(RuntimeError):
    pass


# ---------------------------------------------------------------------------
# Integrity layer (stdlib only)
# ---------------------------------------------------------------------------

def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _iter_files(bundle_dir: Path):
    root = Path(bundle_dir)
    for p in sorted(root.rglob("*")):
        if p.is_file() and p.name not in _EXCLUDED:
            yield p


def build_manifest(bundle_dir: Path) -> str:
    """Return a deterministic ``<sha256>  <relpath>`` manifest for the bundle."""
    root = Path(bundle_dir)
    lines = []
    for p in _iter_files(root):
        rel = p.relative_to(root).as_posix()
        lines.append(f"{sha256_of(p)}  {rel}")
    return "\n".join(lines) + ("\n" if lines else "")


def write_manifest(bundle_dir: Path) -> Path:
    root = Path(bundle_dir)
    out = root / MANIFEST_NAME
    out.write_text(build_manifest(root), encoding="utf-8")
    return out


def _parse_manifest(text: str) -> dict[str, str]:
    entries: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        digest, _, rel = line.partition("  ")
        if rel:
            entries[rel] = digest
    return entries


def verify_manifest(bundle_dir: Path, manifest_text: str | None = None) -> dict:
    """Recompute every digest and compare to the manifest.

    Returns {ok, checked, mismatches, missing, extra}. ``ok`` is True only when
    every listed file is present with a matching digest and no unexpected file
    was added to the bundle.
    """
    root = Path(bundle_dir)
    if manifest_text is None:
        mpath = root / MANIFEST_NAME
        if not mpath.exists():
            raise ReleaseError(f"no {MANIFEST_NAME} in {bundle_dir}")
        manifest_text = mpath.read_text(encoding="utf-8")
    expected = _parse_manifest(manifest_text)
    present = {p.relative_to(root).as_posix() for p in _iter_files(root)}

    mismatches, missing = [], []
    for rel, digest in expected.items():
        fp = root / rel
        if not fp.exists():
            missing.append(rel)
        elif sha256_of(fp) != digest:
            mismatches.append(rel)
    extra = sorted(present - set(expected))
    ok = not mismatches and not missing and not extra
    return {"ok": ok, "checked": len(expected), "mismatches": mismatches,
            "missing": missing, "extra": extra}


# ---------------------------------------------------------------------------
# Authenticity layer (OpenSSL Ed25519)
# ---------------------------------------------------------------------------

def openssl_available() -> bool:
    return shutil.which("openssl") is not None


def _openssl(*args: str, **kw) -> subprocess.CompletedProcess:
    if not openssl_available():
        raise ReleaseError("openssl not found; the FOSS signing toolchain is required "
                           "for the authenticity layer (integrity still works without it)")
    return subprocess.run(["openssl", *args], capture_output=True, **kw)


def generate_keypair(dest_dir: Path, *, name: str = "deye-release") -> tuple[Path, Path]:
    """Generate a local Ed25519 keypair. Returns (private_key, public_key)."""
    dest = Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)
    priv = dest / f"{name}.key"
    pub = dest / f"{name}.pub"
    r = _openssl("genpkey", "-algorithm", "ed25519", "-out", str(priv))
    if r.returncode != 0:
        raise ReleaseError(f"key generation failed: {r.stderr.decode(errors='replace')}")
    r = _openssl("pkey", "-in", str(priv), "-pubout", "-out", str(pub))
    if r.returncode != 0:
        raise ReleaseError(f"public-key export failed: {r.stderr.decode(errors='replace')}")
    try:
        priv.chmod(0o600)
    except OSError:
        pass
    return priv, pub


def sign_manifest(bundle_dir: Path, private_key: Path, *,
                  public_key: Path | None = None) -> Path:
    """Sign the bundle's SHA256SUMS with an Ed25519 key. Writes SHA256SUMS.sig.

    If *public_key* is given, a copy is placed in the bundle as PUBKEY.pem so
    the bundle can be self-verified; trust is anchored by that key's published
    fingerprint, not by its mere presence.
    """
    root = Path(bundle_dir)
    manifest = root / MANIFEST_NAME
    if not manifest.exists():
        raise ReleaseError(f"nothing to sign: no {MANIFEST_NAME} in {bundle_dir}")
    sig = root / SIG_NAME
    r = _openssl("pkeyutl", "-sign", "-inkey", str(private_key), "-rawin",
                 "-in", str(manifest), "-out", str(sig))
    if r.returncode != 0:
        raise ReleaseError(f"signing failed: {r.stderr.decode(errors='replace')}")
    if public_key is not None:
        shutil.copyfile(public_key, root / PUBKEY_NAME)
    return sig


def verify_signature(bundle_dir: Path, public_key: Path | None = None) -> bool:
    """Verify SHA256SUMS.sig against the public key (bundle PUBKEY.pem if unset)."""
    root = Path(bundle_dir)
    manifest = root / MANIFEST_NAME
    sig = root / SIG_NAME
    pub = Path(public_key) if public_key is not None else (root / PUBKEY_NAME)
    if not (manifest.exists() and sig.exists() and pub.exists()):
        raise ReleaseError("need SHA256SUMS, SHA256SUMS.sig, and a public key to verify")
    r = _openssl("pkeyutl", "-verify", "-pubin", "-inkey", str(pub), "-rawin",
                 "-in", str(manifest), "-sigfile", str(sig))
    return r.returncode == 0


def verify_bundle(bundle_dir: Path, public_key: Path | None = None) -> dict:
    """Full verification: integrity always, signature when signing material is present."""
    result = verify_manifest(bundle_dir)
    root = Path(bundle_dir)
    has_sig = (root / SIG_NAME).exists()
    if has_sig:
        try:
            result["signature_ok"] = verify_signature(bundle_dir, public_key)
        except ReleaseError as exc:
            result["signature_ok"] = False
            result["signature_error"] = str(exc)
        result["ok"] = bool(result["ok"] and result.get("signature_ok"))
    else:
        result["signature_ok"] = None  # unsigned bundle: integrity only
    return result
