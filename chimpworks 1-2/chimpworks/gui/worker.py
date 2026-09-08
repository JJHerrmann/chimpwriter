"""One transcription job, off the UI thread.

``build_transcript`` has no cancel hook of its own, so we co-opt the progress
callback: raising from it aborts the run at the next progress tick (mid-ASR is
the common case). Model load / diarization can't be interrupted -- same
limitation the v1 GUI had.
"""
from __future__ import annotations

import os
from pathlib import Path

from PySide6 import QtCore

from ..core.pipeline import TranscribeOptions, build_transcript
from ..render.packet import PacketOptions, write_packet


class _Cancelled(Exception):
    pass


class JobWorker(QtCore.QThread):
    # stage name, fraction in [0,1] or -1 when unknown
    progressed = QtCore.Signal(str, float)
    logged = QtCore.Signal(str)
    finished_ok = QtCore.Signal(list)   # list[str] of written paths
    failed = QtCore.Signal(str)

    def __init__(
        self,
        *,
        source: str,
        out_root: str,
        t_opts: TranscribeOptions,
        p_opts: PacketOptions,
        hf_token: str = "",
        parent: QtCore.QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._source = source
        self._out_root = Path(out_root).expanduser()
        self._t_opts = t_opts
        self._p_opts = p_opts
        self._hf_token = hf_token
        self._cancel = False

    def cancel(self) -> None:
        self._cancel = True

    # progress callback handed to the pipeline
    def _progress(self, stage: str, fraction: float | None) -> None:
        if self._cancel:
            raise _Cancelled()
        self.progressed.emit(stage, -1.0 if fraction is None else float(fraction))

    def run(self) -> None:  # noqa: D401 - QThread entry point
        try:
            if self._hf_token:
                os.environ["CHIMPWORKS_HF_TOKEN"] = self._hf_token
            self.logged.emit(f"Source: {self._source}")
            transcript = build_transcript(self._source, self._t_opts, progress=self._progress)
            n_spk = len({s.speaker for s in transcript.segments if s.speaker})
            self.logged.emit(
                f"Transcribed {transcript.word_count()} words"
                + (f", {n_spk} speaker(s)" if n_spk else "")
                + " -- writing packet..."
            )
            written = write_packet(transcript, self._out_root, self._p_opts)
            self.finished_ok.emit([str(p) for p in written])
        except _Cancelled:
            self.failed.emit("cancelled")
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))
