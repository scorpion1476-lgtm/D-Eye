"""C09-F007 / C12-F033 signed-release and bundle verification (FOSS toolchain).

Two layers:
  * integrity (stdlib SHA256SUMS) - always runs, detects any tampered file;
  * authenticity (OpenSSL Ed25519 signature over the manifest) - runs where the
    FOSS `openssl` tool is present, detects a tampered manifest.
"""
from __future__ import annotations

import pytest

from deye import release


def _bundle(tmp_path):
    d = tmp_path / "bundle"
    d.mkdir()
    (d / "wheel.whl").write_bytes(b"fake wheel bytes")
    (d / "sdist.tar.gz").write_bytes(b"fake sdist bytes")
    (d / "sub").mkdir()
    (d / "sub" / "extra.txt").write_text("nested artifact")
    return d


# -- integrity layer (stdlib, always) ---------------------------------------

def test_manifest_verifies_clean_bundle(tmp_path):
    d = _bundle(tmp_path)
    release.write_manifest(d)
    result = release.verify_manifest(d)
    assert result["ok"] is True
    assert result["checked"] == 3


def test_manifest_detects_a_flipped_byte(tmp_path):
    d = _bundle(tmp_path)
    release.write_manifest(d)
    (d / "wheel.whl").write_bytes(b"fake wheel bytez")   # one byte changed
    result = release.verify_manifest(d)
    assert result["ok"] is False
    assert "wheel.whl" in result["mismatches"]


def test_manifest_detects_missing_and_extra(tmp_path):
    d = _bundle(tmp_path)
    release.write_manifest(d)
    (d / "sdist.tar.gz").unlink()                        # removed
    (d / "surprise.txt").write_text("unexpected")        # added
    result = release.verify_manifest(d)
    assert result["ok"] is False
    assert "sdist.tar.gz" in result["missing"]
    assert "surprise.txt" in result["extra"]


def test_verify_bundle_unsigned_is_integrity_only(tmp_path):
    d = _bundle(tmp_path)
    release.write_manifest(d)
    result = release.verify_bundle(d)
    assert result["ok"] is True
    assert result["signature_ok"] is None               # no signature present


# -- authenticity layer (OpenSSL Ed25519) -----------------------------------

@pytest.mark.skipif(not release.openssl_available(),
                    reason="openssl (the FOSS signing toolchain) not installed")
def test_ed25519_sign_and_verify_roundtrip(tmp_path):
    d = _bundle(tmp_path)
    priv, pub = release.generate_keypair(tmp_path / "keys")
    release.write_manifest(d)
    release.sign_manifest(d, priv, public_key=pub)
    assert release.verify_signature(d) is True
    full = release.verify_bundle(d)
    assert full["ok"] is True and full["signature_ok"] is True


@pytest.mark.skipif(not release.openssl_available(),
                    reason="openssl (the FOSS signing toolchain) not installed")
def test_ed25519_signature_rejects_tampered_manifest(tmp_path):
    d = _bundle(tmp_path)
    priv, pub = release.generate_keypair(tmp_path / "keys")
    release.write_manifest(d)
    release.sign_manifest(d, priv, public_key=pub)
    # tamper the manifest itself: the signature must no longer verify
    (d / release.MANIFEST_NAME).write_text("0" * 64 + "  wheel.whl\n")
    assert release.verify_signature(d) is False


@pytest.mark.skipif(not release.openssl_available(),
                    reason="openssl (the FOSS signing toolchain) not installed")
def test_ed25519_signature_rejects_wrong_key(tmp_path):
    d = _bundle(tmp_path)
    priv, _pub = release.generate_keypair(tmp_path / "keys")
    _priv2, pub2 = release.generate_keypair(tmp_path / "keys2")
    release.write_manifest(d)
    release.sign_manifest(d, priv)                       # signed with key 1
    assert release.verify_signature(d, public_key=pub2) is False   # verified with key 2
