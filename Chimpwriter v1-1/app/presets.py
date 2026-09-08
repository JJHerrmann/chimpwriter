from __future__ import annotations

import random
import string

SPEED_PRESET_ORDER = ["Cheetah", "Dolphin", "Whale"]
SPEED_PRESETS = {
    "Cheetah": {"label": "Very fast, less accurate", "model": "tiny"},
    "Dolphin": {"label": "Balanced speed and accuracy", "model": "small"},
    "Whale": {"label": "Slow, most accurate", "model": "large-v3"},
}


def resolve_speed_preset(value: str) -> str:
    if not value:
        return "Dolphin"
    val = value.strip().lower()
    if val in ("cheeta", "cheetah"):
        return "Cheetah"
    if val == "dolphin":
        return "Dolphin"
    if val == "whale":
        return "Whale"
    return "Dolphin"


def resolve_model_size(speed_preset: str) -> str:
    preset = resolve_speed_preset(speed_preset)
    return SPEED_PRESETS[preset]["model"]


def make_monkey_wall(cols: int = 48, rows: int = 3, seed: int = 1337) -> str:
    rng = random.Random(seed)
    alphabet = string.ascii_letters + string.digits + ".,;:!?/\\()[]{}"
    lines = []
    for _ in range(rows):
        lines.append("".join(rng.choice(alphabet) for _ in range(cols)))
    return "\n".join(lines)
