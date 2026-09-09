"""Offline verification + precedence for chimpworks.licensing."""
from __future__ import annotations

import base64
import json
import time

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from chimpworks import licensing


def _b64u(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _token(typ: str, kid: str, key: Ed25519PrivateKey, payload: dict) -> str:
    header = _b64u(json.dumps({"alg": "EdDSA", "typ": typ, "kid": kid}).encode())
    body = _b64u(json.dumps(payload).encode())
    sig = _b64u(key.sign(f"{header}.{body}".encode()))
    return f"{header}.{body}.{sig}"


@pytest.fixture
def rig(tmp_path, monkeypatch):
    lease_key = Ed25519PrivateKey.generate()
    cert_key = Ed25519PrivateKey.generate()

    def pub(k: Ed25519PrivateKey) -> str:
        from cryptography.hazmat.primitives import serialization

        raw = k.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw
        )
        return base64.b64encode(raw).decode()

    monkeypatch.setattr(
        licensing, "TRUSTED_KEYS", {"lease-t": pub(lease_key), "cert-t": pub(cert_key)}
    )
    monkeypatch.setattr(licensing, "LICENCE_DIR", tmp_path)
    monkeypatch.setattr(licensing, "__version__", "1.5.0")
    monkeypatch.delenv("CHIMPWORKS_LICENCE_DEV", raising=False)
    licensing.cached.cache_clear()

    def write(name: str, content: str) -> None:
        (tmp_path / name).write_text(content, "utf-8")

    return {"lease_key": lease_key, "cert_key": cert_key, "write": write}


def test_no_files_is_free(rig):
    assert licensing.entitlement().plan == "free"


def test_valid_lease_grants_pro(rig):
    tok = _token(
        "chimp-lease", "lease-t", rig["lease_key"],
        {
            "kind": "lease", "plan": "pro", "license_key": "K1",
            "features": ["diarize", "cleanup", "packet", "batch"],
            "version_range": ">=1.0.0 <2.0.0",
            "exp": int(time.time()) + 3600,
        },
    )
    rig["write"]("lease", tok)
    e = licensing.entitlement()
    assert e.plan == "pro" and e.source == "lease"
    assert e.has("cleanup")


def test_expired_lease_is_ignored(rig):
    tok = _token(
        "chimp-lease", "lease-t", rig["lease_key"],
        {"kind": "lease", "plan": "pro", "license_key": "K1",
         "version_range": ">=1.0.0 <2.0.0", "exp": int(time.time()) - 10},
    )
    rig["write"]("lease", tok)
    assert licensing.entitlement().plan == "free"


def test_lease_out_of_version_range_is_ignored(rig):
    tok = _token(
        "chimp-lease", "lease-t", rig["lease_key"],
        {"kind": "lease", "plan": "pro", "license_key": "K1",
         "version_range": ">=2.0.0 <3.0.0", "exp": int(time.time()) + 3600},
    )
    rig["write"]("lease", tok)
    assert licensing.entitlement().plan == "free"


def test_tampered_signature_rejected(rig):
    tok = _token(
        "chimp-lease", "lease-t", rig["lease_key"],
        {"kind": "lease", "plan": "pro", "license_key": "K1",
         "version_range": ">=1.0.0 <2.0.0", "exp": int(time.time()) + 3600},
    )
    h, b, _s = tok.split(".")
    forged = _token(
        "chimp-lease", "lease-t", Ed25519PrivateKey.generate(),
        {"kind": "lease", "plan": "pro", "license_key": "K1",
         "version_range": ">=1.0.0 <2.0.0", "exp": int(time.time()) + 3600},
    )
    rig["write"]("lease", f"{h}.{b}.{forged.split('.')[2]}")
    assert licensing.entitlement().plan == "free"


def test_perpetual_cert_when_no_lease(rig):
    tok = _token(
        "chimp-cert", "cert-t", rig["cert_key"],
        {"kind": "perpetual", "license_key": "K1", "major_version": 1,
         "version_range": ">=1.0.0 <2.0.0"},
    )
    rig["write"]("cert", tok)
    e = licensing.entitlement()
    assert e.plan == "pro" and e.source == "perpetual" and e.perpetual_major == 1


def test_perpetual_cert_does_not_cover_next_major(rig, monkeypatch):
    monkeypatch.setattr(licensing, "__version__", "2.0.0")
    tok = _token(
        "chimp-cert", "cert-t", rig["cert_key"],
        {"kind": "perpetual", "license_key": "K1", "major_version": 1,
         "version_range": ">=1.0.0 <2.0.0"},
    )
    rig["write"]("cert", tok)
    assert licensing.entitlement().plan == "free"


def test_revocation_list_blocks_cert(rig):
    cert = _token(
        "chimp-cert", "cert-t", rig["cert_key"],
        {"kind": "perpetual", "license_key": "K1", "major_version": 1,
         "version_range": ">=1.0.0 <2.0.0"},
    )
    revs = _token(
        "chimp-revocations", "lease-t", rig["lease_key"],
        {"kind": "revocations", "revoked": ["K1"], "iat": int(time.time())},
    )
    rig["write"]("cert", cert)
    rig["write"]("revocations", revs)
    assert licensing.entitlement().plan == "free"


def test_stale_revocation_list_not_enforced(rig):
    cert = _token(
        "chimp-cert", "cert-t", rig["cert_key"],
        {"kind": "perpetual", "license_key": "K1", "major_version": 1,
         "version_range": ">=1.0.0 <2.0.0"},
    )
    revs = _token(
        "chimp-revocations", "lease-t", rig["lease_key"],
        {"kind": "revocations", "revoked": ["K1"],
         "iat": int(time.time()) - 40 * 86400},  # older than _REVOCATION_MAX_AGE
    )
    rig["write"]("cert", cert)
    rig["write"]("revocations", revs)
    assert licensing.entitlement().plan == "pro"


def test_dev_override(rig, monkeypatch):
    monkeypatch.setenv("CHIMPWORKS_LICENCE_DEV", "1")
    licensing.cached.cache_clear()
    assert licensing.entitlement().source == "dev"


# --- enforcement switch --------------------------------------------------------
def _enforce_on(monkeypatch):
    monkeypatch.setattr(licensing, "ENFORCE", True)
    monkeypatch.setattr(licensing, "BASE_URL", "https://real.example.workers.dev")
    licensing.cached.cache_clear()


def test_require_is_noop_by_default(rig):
    # ENFORCE defaults False -> no licence, still no error, has() is permissive
    licensing.require("cleanup")
    assert licensing.has("diarize") is True


def test_require_raises_when_enforcing_and_unlicensed(rig, monkeypatch):
    _enforce_on(monkeypatch)
    assert licensing.has("cleanup") is False
    with pytest.raises(licensing.LicenceError):
        licensing.require("cleanup")


def test_not_enforced_until_configured(rig, monkeypatch):
    monkeypatch.setattr(licensing, "ENFORCE", True)  # but BASE_URL is still the placeholder
    licensing.cached.cache_clear()
    assert licensing.enforcing() is False
    licensing.require("cleanup")  # no raise


def test_dev_env_disables_enforcement(rig, monkeypatch):
    _enforce_on(monkeypatch)
    monkeypatch.setenv("CHIMPWORKS_LICENCE_DEV", "1")
    assert licensing.enforcing() is False
    licensing.require("cleanup")


def test_enforcing_allows_licensed_feature(rig, monkeypatch):
    _enforce_on(monkeypatch)
    tok = _token(
        "chimp-lease", "lease-t", rig["lease_key"],
        {"kind": "lease", "plan": "pro", "license_key": "K1",
         "features": ["diarize", "cleanup", "packet", "batch"],
         "version_range": ">=1.0.0 <2.0.0", "exp": int(time.time()) + 3600},
    )
    rig["write"]("lease", tok)
    licensing.cached.cache_clear()
    licensing.require("cleanup")  # no raise
    assert licensing.has("packet") is True
