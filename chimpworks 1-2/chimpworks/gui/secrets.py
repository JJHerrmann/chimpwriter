"""Secret storage for the GUI: Hugging Face token + LLM cleanup API key.

The headless CLI reads these from the environment only -- ``$CHIMPWORKS_HF_TOKEN``
and ``$CHIMPWORKS_LLM_API_KEY`` (see ``chimpworks.config`` / ``chimpworks.core.llm``).
The GUI has no shell, so it persists them here -- OS keyring when a real backend
is available, otherwise a ``secrets.toml`` in the config dir locked to 0600 --
and injects them into the environment when it launches a job.

Nothing here is imported by the engine; a headless install never touches it.
"""
from __future__ import annotations

import os
import stat

from ..paths import CONFIG_DIR

_SERVICE = "chimpworks"
SECRETS_FILE = CONFIG_DIR / "secrets.toml"

# logical name -> (keyring entry, secrets.toml key, env var)
_SECRETS = {
    "hf": ("hf_token", "hf_token", "CHIMPWORKS_HF_TOKEN"),
    "llm": ("llm_api_key", "llm_api_key", "CHIMPWORKS_LLM_API_KEY"),
}

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


def _read_file() -> dict:
    if not SECRETS_FILE.exists():
        return {}
    try:
        import tomllib

        return tomllib.loads(SECRETS_FILE.read_text("utf-8"))
    except Exception:
        return {}


def _write_file(data: dict) -> None:
    """Persist the non-empty entries in ``data`` (or remove the file)."""
    lines = [f'{k} = "{v}"' for k, v in sorted(data.items()) if v]
    if not lines:
        if SECRETS_FILE.exists():
            SECRETS_FILE.unlink()
        return
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    SECRETS_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    try:
        SECRETS_FILE.chmod(stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass


def load_secret(name: str) -> str:
    """Keyring, then ``secrets.toml``, then the env var. Empty string if unset."""
    entry, filekey, envvar = _SECRETS[name]
    kr = _keyring()
    if kr is not None:
        try:
            val = kr.get_password(_SERVICE, entry)
            if val:
                return val.strip()
        except Exception:
            pass
    val = str(_read_file().get(filekey, "")).strip()
    if val:
        return val
    return os.environ.get(envvar, "").strip()


def save_secret(name: str, value: str) -> str:
    """Persist (or clear) one secret. Returns where it landed, for the UI."""
    entry, filekey, _ = _SECRETS[name]
    value = (value or "").strip()
    kr = _keyring()
    if kr is not None:
        try:
            if value:
                kr.set_password(_SERVICE, entry, value)
            else:
                try:
                    kr.delete_password(_SERVICE, entry)
                except Exception:
                    pass
            return "system keyring"
        except Exception:
            pass  # fall through to file
    data = _read_file()
    data[filekey] = value
    _write_file(data)  # preserves the sibling secret
    return str(SECRETS_FILE)


# -- named wrappers (back-compat + call-site clarity) ----------------------
def load_token() -> str:
    return load_secret("hf")


def save_token(token: str) -> str:
    return save_secret("hf", token)


def load_llm_key() -> str:
    return load_secret("llm")


def save_llm_key(key: str) -> str:
    return save_secret("llm", key)


def storage_kind() -> str:
    return "system keyring" if _keyring() is not None else f"{SECRETS_FILE} (0600)"


def verify_token(token: str) -> dict:
    """Network check of the HF token. Returns {ok, user, gated_ok, detail}."""
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


def verify_cleanup_endpoint(endpoint: str, model: str, key: str) -> dict:
    """Network check of the LLM cleanup endpoint. Returns {ok, detail}."""
    endpoint = (endpoint or "").strip()
    if not endpoint:
        return {"ok": False, "detail": "No endpoint entered."}

    from ..core import llm

    prev = os.environ.get(_SECRETS["llm"][2])
    if key:
        os.environ[_SECRETS["llm"][2]] = key
    else:
        os.environ.pop(_SECRETS["llm"][2], None)
    try:
        if not llm.reachable(endpoint):
            return {"ok": False, "detail": (
                f"No usable response from {endpoint} -- check the URL, the API key, "
                "and that the server is running.")}
        models = llm.list_models(endpoint)
        if not model:
            hint = f" {len(models)} model(s) available." if models else ""
            return {"ok": True, "detail": f"Endpoint reachable.{hint} Now set a cleanup model."}
        if models and model not in models:
            shown = ", ".join(models[:12]) + ("  …" if len(models) > 12 else "")
            return {"ok": False, "detail": (
                f"Reached the server, but '{model}' is not in its model list.\n"
                f"Available: {shown}  (with Ollama: `ollama pull {model}`)")}
        if not models:
            return {"ok": True, "detail": (
                f"Endpoint reachable, but it returned no model list -- the cleanup "
                f"call will still fail if '{model}' isn't pulled / loaded on the server.")}
        return {"ok": True, "detail": f"Endpoint reachable, model '{model}' is served."}
    finally:
        if prev is not None:
            os.environ[_SECRETS["llm"][2]] = prev
        else:
            os.environ.pop(_SECRETS["llm"][2], None)
