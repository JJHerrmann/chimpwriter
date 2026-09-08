"""User terminology library.

Whisper spells domain jargon and proper nouns however it likes ("n8n" becomes
"N10", "neighten", "N8 N"). Two levers fix that:

* **terms**  -- fed to faster-whisper as ``hotwords``, biasing the decode toward
  the right spelling in the first place;
* **fixes**  -- literal / regex substitutions applied to the transcript text
  afterwards, for the ones the bias misses.

Both live in one TOML file the user owns (``<config>/lexicon.toml`` by default),
so it can grow per project without touching code.

Format::

    terms = ["n8n", "LangChain", "Pinecone", "Make.com"]

    [fixes]
    "neighten"          = "n8n"
    "N8 N"              = "n8n"
    "re:\\bN[ -]?10\\b" = "n8n"

A ``[fixes]`` key is a case-insensitive whole-word match, unless it starts with
``re:`` -- then the rest is a regex (also case-insensitive). Order is preserved.
"""
from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from ..log import get_logger
from ..paths import CONFIG_DIR

log = get_logger(__name__)

DEFAULT_LEXICON = CONFIG_DIR / "lexicon.toml"


@dataclass
class Lexicon:
    terms: list[str] = field(default_factory=list)
    # (compiled pattern, replacement, original-key) in file order
    fixes: list[tuple[re.Pattern[str], str, str]] = field(default_factory=list)
    source: str = ""

    def __bool__(self) -> bool:
        return bool(self.terms or self.fixes)

    def hotwords(self) -> str:
        """Comma-joined string for faster-whisper's ``hotwords=``."""
        return ", ".join(t.strip() for t in self.terms if t.strip())

    def apply(self, text: str) -> str:
        if not text:
            return text
        for pat, repl, _key in self.fixes:
            text = pat.sub(repl, text)
        return text


def _compile(key: str) -> re.Pattern[str] | None:
    key = key.strip()
    if not key:
        return None
    try:
        if key.startswith("re:"):
            return re.compile(key[3:], re.IGNORECASE)
        return re.compile(rf"\b{re.escape(key)}\b", re.IGNORECASE)
    except re.error as exc:  # noqa: BLE001
        log.warning("lexicon: bad pattern %r (%s) - skipped", key, exc)
        return None


def parse_lexicon(data: dict, *, source: str = "") -> Lexicon:
    terms = [str(t) for t in (data.get("terms") or []) if str(t).strip()]
    fixes: list[tuple[re.Pattern[str], str, str]] = []
    for key, repl in (data.get("fixes") or {}).items():
        pat = _compile(str(key))
        if pat is not None:
            fixes.append((pat, str(repl), str(key)))
    return Lexicon(terms=terms, fixes=fixes, source=source)


def load_lexicon(path: str | Path | None = None) -> Lexicon:
    """Load the lexicon, or an empty one if the file is missing/broken."""
    p = Path(path).expanduser() if path else DEFAULT_LEXICON
    if not p.exists():
        return Lexicon(source=str(p))
    try:
        with p.open("rb") as fh:
            data = tomllib.load(fh)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        log.warning("lexicon: could not read %s (%s)", p, exc)
        return Lexicon(source=str(p))
    return parse_lexicon(data, source=str(p))


# --- editing (used by `chimpworks terms` and the GUI dialog) ----------------

def _toml_str(s: str) -> str:
    """A TOML string literal that survives round-trip.

    Prefer a single-quoted *literal* string (no escape processing) so regex
    backslashes (``\\b``) are kept verbatim. Fall back to a basic string only
    when the value itself contains a single quote.
    """
    if "'" not in s and "\n" not in s:
        return f"'{s}'"
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _dump(lex_terms: list[str], lex_fixes: dict[str, str]) -> str:
    lines: list[str] = ["# chimpworks terminology library. See chimpworks/core/lexicon.py.", ""]
    lines.append("terms = [")
    for t in lex_terms:
        lines.append(f"    {_toml_str(t)},")
    lines.append("]")
    if lex_fixes:
        lines.append("")
        lines.append("[fixes]")
        for k, v in lex_fixes.items():
            lines.append(f"{_toml_str(k)} = {_toml_str(v)}")
    return "\n".join(lines) + "\n"


def save_lexicon(terms: list[str], fixes: dict[str, str], path: str | Path | None = None) -> Path:
    p = Path(path).expanduser() if path else DEFAULT_LEXICON
    p.parent.mkdir(parents=True, exist_ok=True)
    # de-dup terms, keep order, strip blanks
    seen: set[str] = set()
    clean_terms = []
    for t in terms:
        t = t.strip()
        if t and t.lower() not in seen:
            seen.add(t.lower())
            clean_terms.append(t)
    clean_fixes = {k.strip(): v for k, v in fixes.items() if k.strip()}
    p.write_text(_dump(clean_terms, clean_fixes), encoding="utf-8")
    return p


def read_raw(path: str | Path | None = None) -> tuple[list[str], dict[str, str], Path]:
    """Return (terms, fixes, path) as plain editable data."""
    p = Path(path).expanduser() if path else DEFAULT_LEXICON
    if not p.exists():
        return [], {}, p
    try:
        with p.open("rb") as fh:
            data = tomllib.load(fh)
    except (OSError, tomllib.TOMLDecodeError):
        return [], {}, p
    terms = [str(t) for t in (data.get("terms") or [])]
    fixes = {str(k): str(v) for k, v in (data.get("fixes") or {}).items()}
    return terms, fixes, p
