"""chimpworks 1-2 - the Qt-free core extracted from Chimpwriter v1-1.

Turns a YouTube URL or a local audio/video file into a structured ``Transcript``
(the single source of truth) and renders it into a research packet: clean text,
SRT/VTT, speaker-labelled transcript, article pass, digest, and citations.

The v1 GUI logic lived tangled inside ``app/transcribe.py`` behind a Qt
``QThread``. Here the pipeline is plain Python with a ``progress`` callback, so
it runs from the CLI, from tests, and (later) from a thin GUI shell.
"""

__version__ = "1.2.0"
