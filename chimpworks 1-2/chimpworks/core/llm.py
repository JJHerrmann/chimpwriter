"""Tiny OpenAI-compatible chat client (stdlib only).

Works against anything that speaks ``POST {endpoint}/chat/completions`` -- Ollama
(``http://localhost:11434/v1``), llama.cpp / LM Studio, vLLM, or a hosted API if
you point it there and set ``CHIMPWORKS_LLM_API_KEY``. No SDK dependency; the
cleanup stage is the only caller today.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

API_KEY_ENV = "CHIMPWORKS_LLM_API_KEY"


class LlmError(RuntimeError):
    pass


def api_key() -> str:
    return os.environ.get(API_KEY_ENV, "")


def chat(
    messages: list[dict],
    *,
    endpoint: str,
    model: str,
    temperature: float = 0.0,
    max_tokens: int | None = None,
    timeout: float = 120.0,
) -> str:
    """Return the assistant message content for a chat completion."""
    if not endpoint:
        raise LlmError("no LLM endpoint configured")
    if not model:
        raise LlmError("no LLM model configured")

    url = endpoint.rstrip("/") + "/chat/completions"
    payload: dict = {"model": model, "messages": messages, "temperature": temperature}
    if max_tokens:
        payload["max_tokens"] = max_tokens

    headers = {"Content-Type": "application/json"}
    key = api_key()
    if key:
        headers["Authorization"] = f"Bearer {key}"

    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:500]
        raise LlmError(f"{exc.code} {exc.reason} from {url}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise LlmError(f"cannot reach {url}: {exc.reason}") from exc
    except (TimeoutError, OSError) as exc:  # noqa: BLE001
        raise LlmError(f"LLM request failed: {exc}") from exc

    try:
        return body["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise LlmError(f"unexpected response shape from {url}: {body!r}"[:500]) from exc


def reachable(endpoint: str, *, timeout: float = 3.0) -> bool:
    """Best-effort ping of the models list -- for a GUI 'Test' button."""
    if not endpoint:
        return False
    url = endpoint.rstrip("/") + "/models"
    headers = {}
    if api_key():
        headers["Authorization"] = f"Bearer {api_key()}"
    try:
        with urllib.request.urlopen(
            urllib.request.Request(url, headers=headers), timeout=timeout
        ) as resp:
            return resp.status == 200
    except Exception:  # noqa: BLE001
        return False
