# Packaging

Freezes the **Chimpwriter GUI** (`chimpworks.gui.app`) into a standalone app with
PyInstaller. The diarization stack (torch / pyannote / scipy / sklearn, ~600 MB)
is **not** bundled — the frozen app downloads it on first use.

## What ships

GUI + CLI engine, faster-whisper (CPU), yt-dlp, a bundled ffmpeg (`imageio-ffmpeg`),
licensing. Whisper models download to the HF cache on first run.

Unpacked ≈ 700 MB; compressed download ≈ 200 MB.

## Local build (Linux/macOS/Windows)

From the repo root, in a venv with the GUI deps + PyInstaller:

```bash
python -m pip install "./chimpworks 1-2[gui]" pyinstaller imageio-ffmpeg
python packaging/write_build_config.py          # inert dev config unless env vars set
pyinstaller packaging/chimpwriter.spec --noconfirm
./dist/Chimpwriter/Chimpwriter --selfcheck      # imports the runtime, no display needed
```

Output: `dist/Chimpwriter/` (a one-folder bundle; the launcher is `Chimpwriter[.exe]`).

## Release config

`chimpworks/_build.py` is the DEV posture (unconfigured, `ENFORCE=False`) and is
what's committed. `packaging/write_build_config.py` rewrites it from env vars
before a real build:

| env | meaning |
|---|---|
| `CHIMPWRITER_LICENCE_URL` | deployed Worker URL, e.g. `https://chimpwriter-licensing.<acct>.workers.dev` |
| `CHIMPWRITER_ENFORCE` | `1` to gate Pro features |
| `CHIMPWRITER_TRUSTED_KEYS` | JSON `{"lease-2026a":"<b64>","cert-2026a":"<b64>"}` from `npm run gen-keys` |

## CI

`.github/workflows/build.yml` — matrix (Linux / Windows / macOS-arm). Runs on
`workflow_dispatch` and on `v*` tags; a tag build attaches the archives to the
GitHub Release. The three env vars above come from repo **Secrets** — until they
are set, CI still builds, just unenforced.

Tag a release:

```bash
git tag v1.6.0 && git push origin v1.6.0
```

## TODO (v1.1)

- Proper installers: Inno Setup (`.exe`), `.dmg` + codesign/notarize, AppImage.
- First-run "install speaker diarization" flow (pip-install torch-CPU + pyannote
  into a user dir, add to `sys.path`).
- macOS Intel (`macos-13`) matrix row.
- Bundle the small whisper model for a fully-offline first run (optional).
