"""Second stage: terminology-aware transcript cleanup via an LLM.

    chimpworks STT  ->  lexicon fixes  ->  LLM cleanup  ->  final transcript

The STT keeps meaning but fumbles cleanup-class details: brand/tool names,
jargon, homophones, punctuation, paragraph breaks, fast compounds ("missed
lead" -> "mislead"). This pass hands the LLM a small glossary and asks it to
correct *only* obvious transcription errors while preserving wording and order.

Segments are sent as numbered lines and must come back one-for-one; any chunk
whose reply doesn't line up is left untouched, so a flaky model degrades to
"no change" rather than to a scrambled transcript.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..log import Progress, get_logger, noop_progress
from ..models import Segment
from . import llm

log = get_logger(__name__)

_SYSTEM = (
    "You correct speech-to-text transcription errors. You will get numbered "
    "lines, one per transcript segment. Return the SAME number of lines with the "
    "SAME numbers, in order, each line being the corrected text of that segment.\n"
    "Fix ONLY clear transcription mistakes: misheard words and homophones, "
    "wrong brand/tool/product names (use the glossary), run-together compounds, "
    "and obviously wrong punctuation or sentence boundaries.\n"
    "PRESERVE the speaker's wording, filler words, tone, and meaning. Do NOT "
    "summarize, paraphrase, translate, reorder, merge, split, add, or delete "
    "content. If a line is already correct, return it unchanged. Output only the "
    "numbered lines, nothing else."
)

_LINE_RE = re.compile(r"^\s*(\d+)[.)\]:\t ]+(.*)$")


@dataclass
class CleanupOptions:
    enabled: bool = False
    endpoint: str = "http://localhost:11434/v1"
    model: str = ""
    max_chars: int = 4000
    temperature: float = 0.0
    glossary: list[str] = field(default_factory=list)

    def ready(self) -> tuple[bool, str]:
        if not self.enabled:
            return False, "disabled"
        if not self.model:
            return False, "no cleanup model set (config [cleanup] model / --cleanup-model)"
        if not self.endpoint:
            return False, "no cleanup endpoint set"
        return True, ""


def _chunks(indexed: list[tuple[int, str]], max_chars: int) -> list[list[tuple[int, str]]]:
    out: list[list[tuple[int, str]]] = []
    cur: list[tuple[int, str]] = []
    size = 0
    for i, text in indexed:
        add = len(text) + 8
        if cur and size + add > max_chars:
            out.append(cur)
            cur, size = [], 0
        cur.append((i, text))
        size += add
    if cur:
        out.append(cur)
    return out


def _user_msg(chunk: list[tuple[int, str]], glossary: list[str]) -> str:
    gloss = ", ".join(dict.fromkeys(g.strip() for g in glossary if g.strip()))
    head = f"Glossary (correct spellings): {gloss}\n\n" if gloss else ""
    body = "\n".join(f"{n}. {text}" for n, text in chunk)
    return f"{head}Correct these {len(chunk)} lines:\n{body}"


def _parse(reply: str, expected: list[int]) -> dict[int, str] | None:
    got: dict[int, str] = {}
    for line in reply.splitlines():
        m = _LINE_RE.match(line)
        if not m:
            continue
        got[int(m.group(1))] = m.group(2).strip()
    if set(got) != set(expected):
        return None
    if any(not v for v in got.values()):
        return None
    return got


def clean_segments(
    segments: list[Segment],
    opts: CleanupOptions,
    *,
    progress: Progress = noop_progress,
) -> int:
    """Rewrite ``segment.text`` in place. Returns the number of segments changed."""
    ok, why = opts.ready()
    if not ok:
        log.info("cleanup: skipped (%s)", why)
        return 0

    indexed = [(i, s.text.strip()) for i, s in enumerate(segments) if s.text.strip()]
    if not indexed:
        return 0

    chunks = _chunks(indexed, opts.max_chars)
    log.info("cleanup: %d segment(s) in %d chunk(s) via %s (%s)",
             len(indexed), len(chunks), opts.model, opts.endpoint)

    changed = 0
    for ci, chunk in enumerate(chunks):
        progress("cleanup", ci / len(chunks))
        nums = [n for n, _ in chunk]
        try:
            reply = llm.chat(
                [
                    {"role": "system", "content": _SYSTEM},
                    {"role": "user", "content": _user_msg(chunk, opts.glossary)},
                ],
                endpoint=opts.endpoint,
                model=opts.model,
                temperature=opts.temperature,
            )
        except llm.LlmError as exc:
            log.warning("cleanup: chunk %d/%d failed, left as-is (%s)",
                        ci + 1, len(chunks), exc)
            continue

        parsed = _parse(reply, nums)
        if parsed is None:
            log.warning("cleanup: chunk %d/%d reply did not line up, left as-is",
                        ci + 1, len(chunks))
            continue

        for n, new_text in parsed.items():
            if new_text != segments[n].text.strip():
                segments[n].text = new_text
                changed += 1

    progress("cleanup", 1.0)
    log.info("cleanup: %d segment(s) changed", changed)
    return changed
