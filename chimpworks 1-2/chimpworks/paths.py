"""Platform-correct locations. No more hardcoded ``C:\\Users\\jjzeg\\Chimpwriter``.

v1 special-cased ``LOCALAPPDATA``/``APPDATA`` and baked an ``R:\\Rookworks\\...``
model path into the defaults. Everything routes through ``platformdirs`` now.
"""
from __future__ import annotations

from pathlib import Path

from platformdirs import (
    user_cache_dir,
    user_config_dir,
    user_data_dir,
    user_documents_dir,
    user_log_dir,
)

APP = "chimpworks"

CONFIG_DIR = Path(user_config_dir(APP))
DATA_DIR = Path(user_data_dir(APP))
CACHE_DIR = Path(user_cache_dir(APP))
LOG_DIR = Path(user_log_dir(APP))

CONFIG_FILE = CONFIG_DIR / "config.toml"
LIBRARY_DB = DATA_DIR / "library.db"
MODELS_DIR = DATA_DIR / "models"


def default_output_dir() -> Path:
    return Path(user_documents_dir()) / "Chimpworks"


def ensure_dirs() -> None:
    for d in (CONFIG_DIR, DATA_DIR, CACHE_DIR, LOG_DIR, MODELS_DIR):
        d.mkdir(parents=True, exist_ok=True)
