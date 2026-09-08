from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict

SPEED_PRESET_ORDER = ["Cheetah", "Dolphin", "Whale"]


def _default_output_dir() -> str:
    home = os.path.expanduser("~")
    return os.path.join(home, "Documents", "Chimpwriter")


def _settings_path() -> str:
    base = os.getenv("LOCALAPPDATA") or os.getenv("APPDATA") or os.path.expanduser("~")
    return os.path.join(base, "Chimpwriter", "settings.json")


def _speed_from_model(model_size: str) -> str:
    model = (model_size or "").lower()
    if model in {"large", "large-v2", "large-v3"}:
        return "Whale"
    if model in {"medium", "small"}:
        return "Dolphin"
    if model in {"base", "tiny"}:
        return "Cheetah"
    return "Dolphin"


def _normalize_speed(value: str) -> str:
    if not value:
        return "Dolphin"
    val = value.strip().lower()
    if val in {"cheeta", "cheetah"}:
        return "Cheetah"
    if val == "dolphin":
        return "Dolphin"
    if val == "whale":
        return "Whale"
    return "Dolphin"


@dataclass
class AppSettings:
    output_dir: str
    topic: str
    speed_preset: str
    language: str
    make_article: bool
    make_citation: bool
    diarize_enabled: bool
    diarize_model: str
    hf_token: str


def load_settings() -> AppSettings:
    path = _settings_path()
    data = {}
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}

    raw_speed = data.get("speed_preset") or data.get("speed")
    if raw_speed:
        speed = _normalize_speed(str(raw_speed))
    else:
        speed = _speed_from_model(data.get("model_size", "small"))

    return AppSettings(
        output_dir=data.get("output_dir", _default_output_dir()),
        topic=data.get("topic", "General"),
        speed_preset=speed,
        language=data.get("language", "auto"),
        make_article=bool(data.get("make_article", False)),
        make_citation=bool(data.get("make_citation", False)),
        diarize_enabled=bool(data.get("diarize_enabled", False)),
        diarize_model=data.get(
            "diarize_model",
            r"R:\Rookworks\011_AI_Operations\03_Audio\models\pyannote\speaker-diarization-3.1",
        ),
        hf_token=data.get("hf_token", ""),
    )


def save_settings(settings: AppSettings) -> None:
    path = _settings_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(asdict(settings), f, indent=2)
