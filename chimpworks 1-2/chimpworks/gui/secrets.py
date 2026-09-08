"""Hugging Face token storage for the GUI.

The headless CLI reads the token from ``$CHIMPWORKS_HF_TOKEN`` only (see
``chimpworks.config``). The GUI has no shell, so it persists the token here --
OS keyring when one is available, otherwise a ``secrets.toml`` in the config dir
locked to 0600 -- and injects it when it launches a job.

Nothing here is imported by the engine; a headless install never touches it.
"""
from __future__ import annotations

import os
import stat
from pathlib import Path

from ..paths import CONFIG_DIR

_SERVICE = "chimpworks"
_ENTRY = "hf_token"
SECRETS_FILE = CONFIG_DIR / "secrets.toml"

_GATED_REPO = "pyannote/speaker-diarization-community-1"


def _keyring():
    """Return the keyring module iff a real, persisting backend is active."""
    try:
        import keyring
        from keyring.backends.fail import Keyring as FailKeyring
    except Exception:
        return None
    try:
        if isinstance(keyring.get_keyring(), FailKeyring):
            return None
    except Exception:
        return None
    return keyring


def load_token() -> str:
    kr = _keyring()
    if kr is not None:
        try:
            val = kr.get_password(_SERVICE, _ENTRY)
            if val:
                return val.strip()
        except Exception:
            pass
    if SECRETS_FILE.exists():
        try:
            import tomllib

            data = tomllib.loads(SECRETS_FILE.read_text("utf-8"))
            val = str(data.get("hf_token", "")).strip()
            if val:
                return val
        except Exception:
            pass
    return os.environ.get("CHIMPWORKS_HF_TOKEN", "").strip()


def save_token(token: str) -> str:
    """Persist (or clear) the token. Returns where it landed for the UI to show."""
    token = (token or "").strip()
    kr = _keyring()
    if kr is not None:
        try:
            if token:
                kr.set_password(_SERVICE, _ENTRY, token)
            else:
                try:
                    kr.delete_password(_SERVICE, _ENTRY)
                except Exception:
                    pass
            return "system keyring"
        except Exception:
            pass  # fall through to file

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if token:
        SECRETS_FILE.write_text(f'hf_token = "{token}"\n', encoding="utf-8")
        try:
            SECRETS_FILE.chmod(stat.S_IRUSR | stat.S_IWUSR)
        except OSError:
            pass
    elif SECRETS_FILE.exists():
        SECRETS_FILE.unlink()
    return str(SECRETS_FILE)


def storage_kind() -> str:
    return "system keyring" if _keyring() is not None else f"{SECRETS_FILE} (0600)"


def verify_token(token: str) -> dict:
    """Network check. Returns {ok, user, gated_ok, detail}."""
    token = (token or "").strip()
    if not token:
        return {"ok": False, "user": "", "gated_ok": False, "detail": "No token entered."}

    # this call must reach the network even if the launcher set offline mode
    prev = {k: os.environ.pop(k, None) for k in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE")}
    try:
        try:
            from huggingface_hub import HfApi

            who = HfApi(token=token).whoami()
            user = who.get("name") or who.get("fullname") or "?"
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "user": "", "gated_ok": False,
                    "detail": f"Token rejected by Hugging Face ({exc})."}

        try:
            from huggingface_hub import hf_hub_download

            hf_hub_download(_GATED_REPO, "config.yaml", token=token)
            return {"ok": True, "user": user, "gated_ok": True,
                    "detail": f"Signed in as {user}. Diarization model access: OK."}
        except Exception:
            return {"ok": True, "user": user, "gated_ok": False,
                    "detail": (f"Signed in as {user}, but this account has not accepted "
                               f"the terms for {_GATED_REPO}.")}
    finally:
        for k, v in prev.items():
            if v is not None:
                os.environ[k] = v
