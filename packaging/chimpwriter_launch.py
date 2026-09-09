"""Frozen-app entry point for the Chimpwriter GUI.

PyInstaller needs a script, not a module path. This also pins the package dir
on sys.path so the editable-install redirect is not relied on inside the freeze.

`Chimpwriter --selfcheck` imports the heavy runtime deps and exits — a fast
smoke test for CI that needs no display.
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.join(os.path.dirname(_HERE), "chimpworks 1-2")
if os.path.isdir(_SRC) and _SRC not in sys.path:
    sys.path.insert(0, _SRC)


def _selfcheck() -> int:
    import importlib

    mods = [
        "faster_whisper", "ctranslate2", "av", "onnxruntime", "yt_dlp",
        "PySide6.QtWidgets", "cryptography.hazmat.primitives.asymmetric.ed25519",
        "chimpworks.gui.app", "chimpworks.core.pipeline", "chimpworks.licensing",
    ]
    for m in mods:
        importlib.import_module(m)
    from chimpworks import __version__
    print(f"selfcheck OK — Chimpwriter {__version__}")
    return 0


if __name__ == "__main__":
    if "--selfcheck" in sys.argv:
        sys.exit(_selfcheck())
    from chimpworks.gui.app import main
    sys.exit(main())
