"""GUI-only preferences: gui.json in the platform config dir.

Job *defaults* still come from ``chimpworks.config`` (the shared ``config.toml``)
so the CLI and GUI agree; this only remembers what the user last picked in the
window plus the diarization model path.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass

from ..config import load_config
from ..paths import CONFIG_DIR

PREFS_FILE = CONFIG_DIR / "gui.json"

# UI speed labels -> faster-whisper sizes (kept from Chimpwriter v1)
SPEED_TO_MODEL = {"Cheetah": "tiny", "Dolphin": "small", "Whale": "large-v3"}
MODEL_TO_SPEED = {v: k for k, v in SPEED_TO_MODEL.items()}


@dataclass
class GuiPrefs:
    output_dir: str = ""
    topic: str = "General"
    model: str = "small"          # tiny|base|small|medium|large-v2|large-v3
    language: str = "auto"
    diarize: bool = False
    make_article: bool = False
    make_citation: bool = True
    diarize_model: str = "pyannote/speaker-diarization-3.1"
    last_input: str = ""

    def speed_label(self) -> str:
        return MODEL_TO_SPEED.get(self.model, "Dolphin")


def load_prefs() -> GuiPrefs:
    cfg = load_config()
    p = GuiPrefs(
        output_dir=str(cfg.resolved_output_dir()),
        topic=cfg.default_topic,
        model=cfg.model,
        language=cfg.language,
        diarize=cfg.diarize,
        make_article=cfg.make_article,
        make_citation=cfg.make_citation,
        diarize_model=cfg.diarize_model,
    )
    if PREFS_FILE.exists():
        try:
            data = json.loads(PREFS_FILE.read_text("utf-8"))
            for key, value in data.items():
                if key in p.__dataclass_fields__:
                    setattr(p, key, value)
        except Exception:
            pass
    return p


def save_prefs(p: GuiPrefs) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    PREFS_FILE.write_text(json.dumps(asdict(p), indent=2), encoding="utf-8")
