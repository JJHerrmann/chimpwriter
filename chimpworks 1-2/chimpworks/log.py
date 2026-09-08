"""Logging + a small progress-callback type shared by core and CLI."""
from __future__ import annotations

import logging
import sys
from typing import Callable

# progress(stage, fraction|None): fraction in [0, 1] when known, else None
Progress = Callable[[str, "float | None"], None]

_CONFIGURED = False


def get_logger(name: str = "chimpworks") -> logging.Logger:
    return logging.getLogger(name)


def setup_logging(level: int = logging.INFO, *, stream=None) -> None:
    global _CONFIGURED
    logger = logging.getLogger("chimpworks")
    logger.setLevel(level)
    if _CONFIGURED:
        return
    handler = logging.StreamHandler(stream or sys.stderr)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(message)s", "%H:%M:%S"))
    logger.addHandler(handler)
    logger.propagate = False
    _CONFIGURED = True


def noop_progress(stage: str, fraction: float | None = None) -> None:  # noqa: ARG001
    return None
