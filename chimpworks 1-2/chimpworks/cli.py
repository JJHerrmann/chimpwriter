"""chimpworks CLI - the headless entrypoint the v1 GUI never had.

    chimpworks transcribe <url|file> [options]
    chimpworks batch <playlist-url | @urls.txt> [options]
    chimpworks render <transcript.json> [options]     # re-render, no re-transcribe
    chimpworks doctor                                  # check ffmpeg / faster-whisper / pyannote
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

from . import __version__
from .config import hf_token, load_config, resolve_model, with_overrides
from .core import asr, audio
from .core import diarize as diar
from .core.pipeline import TranscribeOptions, build_transcript
from .core.sources import expand_playlist, read_url_list
from .log import get_logger, setup_logging
from .models import Transcript
from .render.packet import PacketOptions, write_packet

log = get_logger("chimpworks.cli")


def _progress(stage: str, fraction: float | None) -> None:
    if fraction is None:
        print(f"  {stage}...", file=sys.stderr)
    elif stage == "transcribe":
        pct = int(fraction * 100)
        end = "\n" if fraction >= 1.0 else "\r"
        print(f"  transcribe {pct:3d}%", file=sys.stderr, end=end, flush=True)


def _packet_opts(args, cfg) -> PacketOptions:
    formats = args.formats.split(",") if args.formats else cfg.formats
    return PacketOptions(
        topic=args.topic or cfg.default_topic,
        formats=[f.strip() for f in formats if f.strip()],
        make_article=args.article or cfg.make_article,
        make_citation=not args.no_citation and cfg.make_citation,
        citation_style=args.citation_style or cfg.citation_style,
        digest=args.digest or cfg.digest,
    )


def _transcribe_opts(args, cfg) -> TranscribeOptions:
    if getattr(args, "no_terms", False):
        lexicon_path: str | None = None
    else:
        lexicon_path = getattr(args, "terms", None) or cfg.lexicon or ""
    cleanup = cfg.cleanup or getattr(args, "cleanup", False)
    if getattr(args, "no_cleanup", False):
        cleanup = False
    return TranscribeOptions(
        model=resolve_model(args.model or cfg.model),
        language=args.language or cfg.language,
        device=args.device or cfg.device,
        compute_type=cfg.compute_type,
        word_timestamps=cfg.word_timestamps,
        diarize=args.diarize or cfg.diarize,
        diarize_model=cfg.diarize_model,
        hf_token=hf_token(),
        cookies_from_browser=cfg.yt_cookies_from_browser,
        lexicon_path=lexicon_path,
        cleanup=cleanup,
        cleanup_endpoint=getattr(args, "cleanup_endpoint", None) or cfg.cleanup_endpoint,
        cleanup_model=getattr(args, "cleanup_model", None) or cfg.cleanup_model,
        cleanup_max_chars=cfg.cleanup_max_chars,
    )


def _run_one(inp: str, out_root: Path, t_opts: TranscribeOptions, p_opts: PacketOptions) -> list[Path]:
    started = time.time()
    transcript = build_transcript(inp, t_opts, progress=_progress)
    written = write_packet(transcript, out_root, p_opts)
    log.info("%s -> %s (%d files, %.1fs)",
             transcript.meta.display_name(), written[0].parent, len(written), time.time() - started)
    return written


def cmd_transcribe(args) -> int:
    cfg = load_config(args.config)
    out_root = Path(args.out).expanduser() if args.out else cfg.resolved_output_dir()
    written = _run_one(args.input, out_root, _transcribe_opts(args, cfg), _packet_opts(args, cfg))
    for p in written:
        print(p)
    return 0


def cmd_batch(args) -> int:
    cfg = load_config(args.config)
    out_root = Path(args.out).expanduser() if args.out else cfg.resolved_output_dir()
    t_opts, p_opts = _transcribe_opts(args, cfg), _packet_opts(args, cfg)

    target = args.input
    if target.startswith("@"):
        inputs = read_url_list(target[1:])
    elif Path(target).exists() and Path(target).suffix in {".txt", ".list"}:
        inputs = read_url_list(target)
    else:
        inputs = expand_playlist(target, cookies_from_browser=cfg.yt_cookies_from_browser)

    log.info("batch: %d inputs", len(inputs))
    ok = fail = 0
    for i, inp in enumerate(inputs, 1):
        log.info("[%d/%d] %s", i, len(inputs), inp)
        try:
            _run_one(inp, out_root, t_opts, p_opts)
            ok += 1
        except Exception as exc:  # noqa: BLE001 - keep going through the batch
            fail += 1
            log.error("failed: %s", exc)
    print(f"batch done: {ok} ok, {fail} failed")
    return 0 if fail == 0 else 1


def cmd_render(args) -> int:
    cfg = load_config(args.config)
    transcript = Transcript.load(args.transcript)
    out_root = Path(args.out).expanduser() if args.out else Path(args.transcript).resolve().parents[3]
    written = write_packet(transcript, out_root, _packet_opts(args, cfg))
    for p in written:
        print(p)
    return 0


def cmd_cleanup(args) -> int:
    """Run the LLM cleanup pass on an existing transcript.json, in place + re-render."""
    from .core.cleanup import CleanupOptions, clean_segments
    from .core.lexicon import load_lexicon

    cfg = load_config(args.config)
    tpath = Path(args.transcript).expanduser()
    transcript = Transcript.load(tpath)

    lex = load_lexicon(None if args.no_terms else (args.terms or cfg.lexicon or ""))
    opts = CleanupOptions(
        enabled=True,
        endpoint=args.cleanup_endpoint or cfg.cleanup_endpoint,
        model=args.cleanup_model or cfg.cleanup_model,
        max_chars=cfg.cleanup_max_chars,
        glossary=lex.terms,
    )
    ok, why = opts.ready()
    if not ok:
        log.error("cleanup: %s", why)
        return 1

    changed = clean_segments(transcript.segments, opts, progress=_progress)
    transcript.save(tpath)
    print(f"{changed} segment(s) changed -> {tpath}")

    if args.out:
        out_root = Path(args.out).expanduser()
    else:
        parents = tpath.resolve().parents
        # packet lives at <root>/Research/<topic>/<name>/x.transcript.json
        out_root = parents[3] if len(parents) > 3 else tpath.resolve().parent
    for p in write_packet(transcript, out_root, _packet_opts(args, cfg)):
        print(p)
    return 0


def cmd_doctor(args) -> int:  # noqa: ARG001
    rows = [
        ("ffmpeg", audio.available(), "sudo pacman -S ffmpeg / brew install ffmpeg / pip install imageio-ffmpeg"),
        ("faster-whisper", asr.available(), "pip install faster-whisper"),
        ("pyannote.audio (diarization)", diar.available(), 'pip install "chimpworks[diarize]"'),
    ]
    ok = True
    for name, present, hint in rows:
        mark = "OK " if present else "MISSING"
        print(f"  [{mark}] {name}" + ("" if present else f"   -> {hint}"))
        ok = ok and (present or "diariz" in name.lower())
    print(f"HF token ({'set' if hf_token() else 'not set'}) - only needed for gated pyannote models")
    return 0 if ok else 1


def cmd_terms(args) -> int:
    from .core.lexicon import load_lexicon, read_raw, save_lexicon

    path = getattr(args, "terms", None)
    sub = getattr(args, "terms_cmd", None)

    if sub in (None, "list"):
        lex = load_lexicon(path)
        print(f"# {lex.source}")
        print("terms:", ", ".join(lex.terms) or "(none)")
        if lex.fixes:
            print("fixes:")
            for _pat, repl, key in lex.fixes:
                print(f"  {key!r} -> {repl!r}")
        else:
            print("fixes: (none)")
        return 0

    if sub == "path":
        _terms, _fixes, p = read_raw(path)
        print(p)
        return 0

    terms, fixes, p = read_raw(path)
    if sub == "add":
        terms.extend(args.term)
        save_lexicon(terms, fixes, p)
        print(f"added {len(args.term)} term(s) -> {p}")
    elif sub == "fix":
        key = args.bad
        if args.regex and not key.startswith("re:"):
            key = f"re:{key}"
        fixes[key] = args.good
        save_lexicon(terms, fixes, p)
        print(f"{key!r} -> {args.good!r}  ({p})")
    elif sub == "remove":
        before = (len(terms), len(fixes))
        terms = [t for t in terms if t.lower() != args.key.lower()]
        fixes = {k: v for k, v in fixes.items() if k != args.key}
        save_lexicon(terms, fixes, p)
        removed = before[0] - len(terms) + before[1] - len(fixes)
        print(f"removed {removed} entr{'y' if removed == 1 else 'ies'} -> {p}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="chimpworks", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--version", action="version", version=f"chimpworks {__version__}")
    p.add_argument("-v", "--verbose", action="store_true")
    p.add_argument("--config", help="path to config.toml")
    sub = p.add_subparsers(dest="command")

    def add_render_opts(sp):
        sp.add_argument("--topic")
        sp.add_argument("--out", help="output root (default: config output_dir)")
        sp.add_argument("--formats", help="comma list: txt,srt,vtt,article,summary,quotes,json")
        sp.add_argument("--article", action="store_true")
        sp.add_argument("--no-citation", action="store_true")
        sp.add_argument("--citation-style", choices=["apa", "mla", "chicago"])
        sp.add_argument("--digest", choices=["heuristic", "off"])

    def add_transcribe_opts(sp):
        sp.add_argument("--model", help="tiny|base|small|medium|large-v3 (or cheetah/dolphin/whale)")
        sp.add_argument("--language", help="ISO code or 'auto'")
        sp.add_argument("--device", choices=["auto", "cpu", "cuda"])
        sp.add_argument("--diarize", action="store_true")
        sp.add_argument("--terms", metavar="PATH", help="terminology lexicon (default: <config>/lexicon.toml)")
        sp.add_argument("--no-terms", action="store_true", help="ignore the terminology lexicon")
        sp.add_argument("--cleanup", action="store_true", help="LLM terminology-aware cleanup pass")
        sp.add_argument("--no-cleanup", action="store_true", help="skip the cleanup pass")
        sp.add_argument("--cleanup-model", metavar="NAME", help="model for the cleanup pass")
        sp.add_argument("--cleanup-endpoint", metavar="URL", help="OpenAI-compatible endpoint for cleanup")

    t = sub.add_parser("transcribe", help="one URL or file -> research packet")
    t.add_argument("input")
    add_transcribe_opts(t)
    add_render_opts(t)
    t.set_defaults(func=cmd_transcribe)

    b = sub.add_parser("batch", help="playlist URL / @urls.txt -> a packet per item")
    b.add_argument("input")
    add_transcribe_opts(b)
    add_render_opts(b)
    b.set_defaults(func=cmd_batch)

    r = sub.add_parser("render", help="re-render an existing transcript.json (no re-transcribe)")
    r.add_argument("transcript")
    add_render_opts(r)
    r.set_defaults(func=cmd_render)

    cl = sub.add_parser("cleanup", help="LLM cleanup pass on an existing transcript.json (in place)")
    cl.add_argument("transcript")
    cl.add_argument("--cleanup-model", metavar="NAME")
    cl.add_argument("--cleanup-endpoint", metavar="URL")
    cl.add_argument("--terms", metavar="PATH")
    cl.add_argument("--no-terms", action="store_true")
    add_render_opts(cl)
    cl.set_defaults(func=cmd_cleanup)

    d = sub.add_parser("doctor", help="check optional dependencies")
    d.set_defaults(func=cmd_doctor)

    tm = sub.add_parser("terms", help="manage the terminology lexicon (hotwords + fixes)")
    tm.add_argument("--terms", metavar="PATH", help="lexicon file (default: <config>/lexicon.toml)")
    tsub = tm.add_subparsers(dest="terms_cmd")
    tsub.add_parser("list", help="print the current lexicon")
    tsub.add_parser("path", help="print the lexicon file path")
    ta = tsub.add_parser("add", help="add one or more hotword terms")
    ta.add_argument("term", nargs="+")
    tf = tsub.add_parser("fix", help="add a substitution: <bad> -> <good>")
    tf.add_argument("bad")
    tf.add_argument("good")
    tf.add_argument("--regex", action="store_true", help="treat <bad> as a regex")
    tr = tsub.add_parser("remove", help="remove a term or a fix key")
    tr.add_argument("key")
    tm.set_defaults(func=cmd_terms)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    setup_logging(logging.DEBUG if getattr(args, "verbose", False) else logging.INFO)
    if not getattr(args, "command", None):
        build_parser().print_help()
        return 2
    try:
        return args.func(args)
    except KeyboardInterrupt:
        return 130
    except Exception as exc:  # noqa: BLE001
        log.error("%s", exc)
        if getattr(args, "verbose", False):
            raise
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
