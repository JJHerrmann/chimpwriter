# chimpworks 1-2

The production rebuild of **Chimpwriter v1-1**. Same job — turn a YouTube URL or
a local audio/video file into a clean, citable research packet — but the pieces
are pulled apart so it can be tested, scripted, batched, and shipped.

`../Chimpwriter v1-1/` is the frozen original (PySide6 tray app). This folder is
a **copy-and-refactor**, not a move: nothing in v1-1 was changed.

## What changed vs v1-1

| v1-1 | 1-2 |
|---|---|
| `run_job()` — 150 lines inside a Qt `QThread` | `chimpworks/core/pipeline.py::build_transcript()` — plain function, `progress` callback |
| Output = a pile of lossy `.txt` files | Output = **`transcript.json`** (source of truth) + renders derived from it |
| GUI only | `chimpworks` CLI: `transcribe`, `batch`, `render`, `doctor` |
| `C:\Users\jjzeg\Chimpwriter` + `R:\Rookworks\...` hardcoded | `platformdirs`; nothing hardcoded |
| `hf_token` in plaintext `settings.json` | `CHIMPWORKS_HF_TOKEN` env only |
| `pyannote` (drags torch) always required | optional extra `chimpworks[diarize]` |
| model reloaded every job | model + diarization pipeline cached |
| segment timestamps only | **word-level timestamps** on by default |
| APA7 only, from filename guessing | APA / MLA / Chicago + BibTeX; metadata-first |
| "summary" / "quotes" = longest sentences, shipped as features | same heuristic, behind a `Digest` protocol, **named honestly**, LLM-ready |
| no tests | 9 test modules, run offline |

## Layout

```
chimpworks/
  models.py            Transcript / Segment / Word / SpeakerTurn / SourceMeta (+ JSON)
  config.py            config.toml overlay; Cheetah/Dolphin/Whale -> model sizes
  paths.py             platformdirs locations
  cli.py               transcribe / batch / render / doctor
  core/
    sources.py         yt-dlp: resolve, probe metadata, fetch audio, expand playlist (retries, cookies, bot-check msg)
    audio.py           ffmpeg locate + decode to 16k mono WAV
    asr.py             faster-whisper (lazy import, cached model, word timestamps, progress)
    diarize.py         pyannote (lazy import, cached pipeline, max-overlap speaker assignment)
    pipeline.py        build_transcript(): input string -> Transcript
  render/
    text.py            joined / paragraphized / speaker-labelled
    subtitles.py       SRT / VTT + timestamp helpers
    article.py         "no grunts" readable pass
    digest.py          Digest protocol; HeuristicDigest, NullDigest
    citation.py        APA7 / MLA9 / Chicago / BibTeX / in-text
    packet.py          Transcript + options -> Research/<Topic>/<Source>/ tree
config/config.example.toml
tests/
```

## Install

```bash
cd "chimpworks 1-2"
python -m pip install -e ".[dev]"        # or: pipx install ".[diarize]"
# system ffmpeg required (pacman -S ffmpeg / brew install ffmpeg), or: pip install "chimpworks[ffmpeg]"
chimpworks doctor
```

`platformdirs` is the only non-stdlib import the *tests* need; `faster-whisper`
and `pyannote` are imported lazily at run time.

## Use

```bash
chimpworks transcribe "https://youtu.be/VIDEOID" --topic "Thermodynamics" --model dolphin --diarize
chimpworks transcribe ./lecture-07.mp4 --formats txt,srt,vtt,article,json --citation-style chicago
chimpworks batch "https://www.youtube.com/playlist?list=PLxxxx" --topic "PHYS 451"
chimpworks batch @urls.txt --model whale
chimpworks render "~/Documents/Chimpworks/Research/PHYS 451/Lecture 7/Lecture 7.transcript.json" --formats srt,vtt --article
```

`render` re-emits from an existing `transcript.json` — add formats, switch
citation style, run the article pass — **without re-downloading or
re-transcribing.**

## Tests

```bash
python -m unittest discover -s tests -v
```

Everything is stubbed (a hand-built `Transcript` fixture, mocked `subprocess` for
yt-dlp) so the suite runs with no models, no ffmpeg, and no network.

## Not in this pass (next phases)

- **Library**: SQLite + FTS5 index over the `Research/` tree, `chimpworks library search`, content-hash dedup so a re-run of the same video is skipped.
- **LLM digest**: real summaries/quotes via a local endpoint, behind the existing `Digest` protocol.
- **GUI shell (v1-3)**: a thin PySide6 tray/dropzone that calls `build_transcript` + `write_packet` — the `[gui]` extra is reserved.
- **Packaging**: PyInstaller/Briefcase for Windows + macOS, bundled ffmpeg.
