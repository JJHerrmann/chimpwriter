"""Configuration (``config.toml``) + secret lookup.

v1 kept ``hf_token`` in plaintext ``settings.json`` and duplicated the
speed-preset list/normaliser across ``presets.py`` and ``settings.py``. Here the
token comes from the environment only, and the cutesy Cheetah/Dolphin/Whale
names survive as thin aliases for real whisper model sizes.
"""
from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from .paths import CONFIG_FILE, default_output_dir

# alias -> faster-whisper model size
SPEED_ALIASES = {
    "cheetah": "tiny",
    "cheeta": "tiny",
    "dolphin": "small",
    "whale": "large-v3",
}
VALID_MODELS = {"tiny", "base", "small", "medium", "large-v2", "large-v3"}

HF_TOKEN_ENV = "CHIMPWORKS_HF_TOKEN"


def resolve_model(value: str | None) -> str:
    if not value:
        return "small"
    v = value.strip().lower()
    v = SPEED_ALIASES.get(v, v)
    return v if v in VALID_MODELS else "small"


@dataclass
class Config:
    output_dir: str = ""                     # "" => platform Documents/Chimpworks
    default_topic: str = "General"
    model: str = "small"
    language: str = "auto"
    device: str = "auto"                     # auto | cpu | cuda
    compute_type: str = "auto"               # auto | int8 | float16 | ...
    word_timestamps: bool = True
    formats: list[str] = field(default_factory=lambda: ["txt", "srt", "vtt", "json"])
    make_article: bool = False
    make_citation: bool = True
    citation_style: str = "apa"              # apa | mla | chicago
    digest: str = "heuristic"                # heuristic | off
    diarize: bool = False
    diarize_model: str = "pyannote/speaker-diarization-3.1"
    yt_cookies_from_browser: str = ""        # e.g. "firefox" - passed to yt-dlp
    source_path: str | None = None

    def resolved_output_dir(self) -> Path:
        return Path(self.output_dir).expanduser() if self.output_dir else default_output_dir()


def _overlay(cfg: Config, data: dict[str, Any]) -> None:
    for key, value in data.items():
        if key in cfg.__dataclass_fields__ and not isinstance(value, dict):
            setattr(cfg, key, value)


def load_config(path: str | Path | None = None) -> Config:
    if path is None:
        env = os.environ.get("CHIMPWORKS_CONFIG")
        path = Path(env) if env else CONFIG_FILE
    cfg = Config()
    path = Path(path)
    if not path.exists():
        return cfg
    with path.open("rb") as fh:
        raw = tomllib.load(fh)
    cfg.source_path = str(path)
    _overlay(cfg, raw)
    cfg.model = resolve_model(cfg.model)
    return cfg


def with_overrides(cfg: Config, **overrides: Any) -> Config:
    clean = {k: v for k, v in overrides.items() if v is not None}
    if "model" in clean:
        clean["model"] = resolve_model(clean["model"])
    return replace(cfg, **clean)


def hf_token() -> str:
    return os.environ.get(HF_TOKEN_ENV, "")
