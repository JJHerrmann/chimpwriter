# PyInstaller spec — base Chimpwriter app (no diarization stack).
# Build:  pyinstaller packaging/chimpwriter.spec --noconfirm
# Run from the repo root, inside a venv that has the [gui] deps + pyinstaller
# + imageio-ffmpeg installed. torch / pyannote / scipy / sklearn are DELIBERATELY
# excluded — diarization is a first-run download in the frozen app.
import os
from PyInstaller.utils.hooks import collect_all, collect_submodules

APP = "Chimpwriter"
ROOT = os.path.abspath(os.getcwd())
SRC = os.path.join(ROOT, "chimpworks 1-2")
LAUNCH = os.path.join(ROOT, "packaging", "chimpwriter_launch.py")

datas, binaries, hiddenimports = [], [], []
for pkg in (
    "faster_whisper", "ctranslate2", "av", "onnxruntime", "tokenizers",
    "huggingface_hub", "yt_dlp", "keyring", "imageio_ffmpeg",
    "platformdirs", "cryptography",
):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

hiddenimports += collect_submodules("keyring.backends")
hiddenimports += ["chimpworks._build"]

EXCLUDES = [
    # diarization stack — pulled in on first use, never shipped
    "torch", "torchaudio", "torchvision", "pyannote", "pyannote.audio",
    "pyannote.core", "pyannote.database", "pyannote.metrics", "pyannote.pipeline",
    "scipy", "sklearn", "scikit_learn", "lightning", "pytorch_lightning",
    "asteroid_filterbanks", "speechbrain", "nvidia", "triton",
    # not used by the GUI
    "pandas", "matplotlib", "IPython", "notebook", "jupyter", "jupyterlab",
    "pytest", "_pytest", "tkinter", "test", "unittest",
    "transformers", "datasets",
    # heavy Qt modules the GUI never touches
    "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineQuick",
    "PySide6.QtWebChannel", "PySide6.QtWebSockets", "PySide6.Qt3DCore",
    "PySide6.Qt3DRender", "PySide6.Qt3DAnimation", "PySide6.QtCharts",
    "PySide6.QtDataVisualization", "PySide6.QtMultimedia", "PySide6.QtMultimediaWidgets",
    "PySide6.QtQuick", "PySide6.QtQuick3D", "PySide6.QtQml", "PySide6.QtQuickWidgets",
    "PySide6.QtPdf", "PySide6.QtPdfWidgets", "PySide6.QtSensors", "PySide6.QtSql",
    "PySide6.QtDesigner", "PySide6.QtHelp", "PySide6.QtTest", "PySide6.QtOpenGLFunctions",
    "PySide6.QtSpatialAudio", "PySide6.QtBluetooth", "PySide6.QtNfc", "PySide6.QtPositioning",
    "PySide6.QtRemoteObjects", "PySide6.QtScxml", "PySide6.QtSerialPort", "PySide6.QtSerialBus",
]

a = Analysis(
    [LAUNCH],
    pathex=[SRC],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    excludes=EXCLUDES,
    noarchive=False,
    optimize=1,
)

pyz = PYZ(a.pure)

# strip() is a no-op on Windows; saves ~40-80 MB of debug symbols on Linux/macOS.
_STRIP = os.name != "nt"

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP,
    debug=False,
    strip=_STRIP,
    upx=False,
    console=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=_STRIP,
    upx=False,
    name=APP,
)
