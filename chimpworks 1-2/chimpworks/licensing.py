"""Client-side licence state. Verifies signed entitlement objects **offline**
against bundled public keys; no network on the hot path.

Files under ``~/.config/chimpworks/licence/`` (written by the activate/refresh
calls):

    lease         compact EdDSA token, short-lived  -> proves an active subscription / OTP
    cert          compact EdDSA token, no expiry     -> proves perpetual ownership of a major version
    revocations   compact EdDSA token (signed list)  -> honoured only while fresh (online)
    install_id    random UUID, generated once

Precedence at startup: valid lease -> valid certificate -> Free.

The private keys live in the licensing Worker and the offline signer, never
here. Nothing in the transcription engine imports this module yet -- see
LICENSING.md for the (deliberately deferred) enforcement wiring.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from . import __version__
from .paths import CONFIG_DIR

LICENCE_DIR = CONFIG_DIR / "licence"

# --- deployment switches ---------------------------------------------------- #
# The URL of the deployed licensing Worker. Until this points at a real
# deployment, licensing is considered UNCONFIGURED and enforcement stays off no
# matter what ENFORCE says (so a dev/self build is never gated).
_PLACEHOLDER_URL = "https://chimpwriter-licensing.example.workers.dev"
BASE_URL = os.environ.get("CHIMPWORKS_LICENCE_URL", _PLACEHOLDER_URL)

# Flip to True in the same commit that sets a real BASE_URL to start gating Pro
# features. `CHIMPWORKS_LICENCE_DEV=1` in the environment always bypasses.
ENFORCE = False

# kid -> raw ed25519 public key (32 bytes, base64). Populate from `npm run gen-keys`.
# ADD-ONLY for cert-* kids: a key that has signed any certificate must stay here
# forever so old certificates keep validating.
TRUSTED_KEYS: dict[str, str] = {
    # "lease-2026a": "…base64…",
    # "cert-2026a":  "…base64…",
}

FEATURES = frozenset({"diarize", "cleanup", "packet", "batch"})
FEATURE_LABELS = {
    "diarize": "Speaker diarization",
    "cleanup": "LLM cleanup pass",
    "packet": "Research packet (article + citation)",
    "batch": "Batch queue",
}
_REVOCATION_MAX_AGE = 30 * 86400
_DEV_ENV = "CHIMPWORKS_LICENCE_DEV"


class LicenceError(RuntimeError):
    """Raised by :func:`require` when a Pro feature is used without entitlement."""


@dataclass(frozen=True)
class Entitlement:
    plan: str          # "pro" | "free"
    source: str        # "lease" | "perpetual" | "dev" | "free"
    features: frozenset[str]
    perpetual_major: int | None
    detail: str

    def has(self, feature: str) -> bool:
        return feature in self.features

    def require(self, feature: str) -> None:
        if not enforcing():
            return
        if feature not in self.features:
            label = FEATURE_LABELS.get(feature, feature)
            raise LicenceError(
                f"{label} needs Chimpwriter Pro. Add a licence in Settings → Licence."
            )


# --------------------------------------------------------------------------- #
#  Verification (offline)                                                      #
# --------------------------------------------------------------------------- #
def _b64u_dec(s: str) -> bytes:
    return __import__("base64").urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _verify(token: str) -> dict | None:
    """Verify a compact ``header.payload.sig`` EdDSA token. Returns payload or None."""
    if not token or token.count(".") != 2:
        return None
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

    h_b64, p_b64, s_b64 = token.split(".")
    try:
        header = json.loads(_b64u_dec(h_b64))
    except Exception:
        return None
    pub_b64 = TRUSTED_KEYS.get(header.get("kid", ""))
    if not pub_b64:
        return None
    try:
        pub = Ed25519PublicKey.from_public_bytes(__import__("base64").b64decode(pub_b64))
        pub.verify(_b64u_dec(s_b64), f"{h_b64}.{p_b64}".encode())
    except (InvalidSignature, ValueError):
        return None
    try:
        return json.loads(_b64u_dec(p_b64))
    except Exception:
        return None


def _ver_tuple(v: str) -> tuple[int, int, int]:
    core = v.split("+")[0].split("-")[0]
    parts = (core.split(".") + ["0", "0", "0"])[:3]
    return tuple(int(x) for x in parts)  # type: ignore[return-value]


def _in_range(version: str, rng: str) -> bool:
    """Tiny semver-range check: space-separated comparators, e.g. '>=1.0.0 <2.0.0'."""
    if not rng:
        return False
    vt = _ver_tuple(version)
    for term in rng.split():
        for op in (">=", "<=", "==", "!=", ">", "<"):
            if term.startswith(op):
                bound = _ver_tuple(term[len(op):])
                ok = {
                    ">=": vt >= bound, "<=": vt <= bound, ">": vt > bound,
                    "<": vt < bound, "==": vt == bound, "!=": vt != bound,
                }[op]
                if not ok:
                    return False
                break
        else:
            return False
    return True


def _read(name: str) -> str:
    try:
        return (LICENCE_DIR / name).read_text("utf-8").strip()
    except OSError:
        return ""


def _revoked() -> set[str]:
    payload = _verify(_read("revocations"))
    if not payload or payload.get("kind") != "revocations":
        return set()
    if time.time() - payload.get("iat", 0) > _REVOCATION_MAX_AGE:
        return set()  # stale -> don't enforce
    return set(payload.get("revoked", []))


# --------------------------------------------------------------------------- #
#  Public API                                                                 #
# --------------------------------------------------------------------------- #
def entitlement() -> Entitlement:
    """Current entitlement. Pure/offline; safe to call on every launch."""
    if os.environ.get(_DEV_ENV):
        return Entitlement("pro", "dev", FEATURES, None, "developer override")

    revoked = _revoked()

    lease = _verify(_read("lease"))
    if (
        lease
        and lease.get("kind") == "lease"
        and lease.get("plan") == "pro"
        and lease.get("exp", 0) > time.time()
        and lease.get("license_key") not in revoked
        and _in_range(__version__, lease.get("version_range", ""))
    ):
        feats = frozenset(lease.get("features", [])) or FEATURES
        return Entitlement("pro", "lease", feats, None, "active subscription")

    cert = _verify(_read("cert"))
    if (
        cert
        and cert.get("kind") == "perpetual"
        and cert.get("license_key") not in revoked
        and _in_range(__version__, cert.get("version_range", ""))
    ):
        major = int(cert.get("major_version", 0)) or None
        return Entitlement(
            "pro", "perpetual", FEATURES, major, f"perpetual licence for {major}.x"
        )

    return Entitlement("free", "free", frozenset(), None, "no active licence")


@lru_cache(maxsize=1)
def cached() -> Entitlement:
    """Process-lifetime cache for the common read-only callers."""
    return entitlement()


def configured() -> bool:
    """True once BASE_URL points at a real deployment (not the placeholder)."""
    return bool(BASE_URL) and BASE_URL != _PLACEHOLDER_URL


def enforcing() -> bool:
    """Gate Pro features? Only when explicitly enabled, configured, and not a dev box."""
    return ENFORCE and configured() and not os.environ.get(_DEV_ENV)


def has(feature: str) -> bool:
    """Is `feature` available? True for everything while enforcement is off."""
    if not enforcing():
        return True
    return cached().has(feature)


def require(feature: str) -> None:
    cached().require(feature)


def status_line() -> str:
    """One-line entitlement summary for the Settings → Licence pane."""
    e = cached()
    if e.source == "dev":
        return "Developer override — all Pro features unlocked"
    if not enforcing():
        return "Licensing not enforced in this build — all features available"
    if e.plan == "free":
        return "Free tier — Pro features locked"
    if e.source == "perpetual":
        return f"Chimpwriter Pro — perpetual licence for {e.perpetual_major}.x"
    return "Chimpwriter Pro — active subscription"


def save_certificate(dest: str | Path) -> Path:
    """Copy the perpetual certificate file out for safekeeping. Raises if none held."""
    src = LICENCE_DIR / "cert"
    if not src.exists():
        raise LicenceError("No perpetual certificate on this machine yet.")
    dest = Path(dest).expanduser()
    dest.write_text(src.read_text("utf-8"), "utf-8")
    return dest


# --------------------------------------------------------------------------- #
#  Network (Settings -> Licence pane only)                                     #
# --------------------------------------------------------------------------- #
def install_id() -> str:
    LICENCE_DIR.mkdir(parents=True, exist_ok=True)
    f = LICENCE_DIR / "install_id"
    val = _read("install_id")
    if not val:
        val = str(uuid.uuid4())
        f.write_text(val + "\n", "utf-8")
    return val


def _post(path: str, body: dict) -> dict:
    req = urllib.request.Request(
        BASE_URL.rstrip("/") + path,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:300]
        raise LicenceError(f"{exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise LicenceError(f"cannot reach licence server: {exc.reason}") from exc


def _store_bundle(bundle: dict) -> None:
    LICENCE_DIR.mkdir(parents=True, exist_ok=True)
    for name in ("lease", "cert", "revocations"):
        val = bundle.get(name)
        p = LICENCE_DIR / name
        if val:
            p.write_text(val + "\n", "utf-8")
            try:
                p.chmod(0o600)
            except OSError:
                pass
        elif name == "cert" and p.exists():
            pass  # never delete a perpetual cert we already hold
    cached.cache_clear()


def activate(license_key: str, label: str = "") -> Entitlement:
    bundle = _post(
        "/activate",
        {"license_key": license_key.strip(), "install_id": install_id(), "label": label},
    )
    (LICENCE_DIR / "license_key").write_text(license_key.strip() + "\n", "utf-8")
    _store_bundle(bundle)
    return entitlement()


def refresh() -> Entitlement:
    key = _read("license_key")
    if not key:
        return entitlement()
    bundle = _post("/refresh", {"license_key": key, "install_id": install_id()})
    _store_bundle(bundle)
    return entitlement()


def deactivate() -> None:
    key = _read("license_key")
    if key:
        try:
            _post("/deactivate", {"license_key": key, "install_id": install_id()})
        except LicenceError:
            pass
    for name in ("lease", "cert", "revocations", "license_key"):
        (LICENCE_DIR / name).unlink(missing_ok=True)
    cached.cache_clear()
