"""Chimpwriter -- the GUI face on the chimpworks engine (v1.3).

A thin PySide6 shell: it collects a source + options, runs
``chimpworks.core.pipeline.build_transcript`` on a worker thread, and writes the
same research packet the CLI does. The only thing it adds over the CLI is a
place to store the Hugging Face token (keyring, falling back to a 0600
secrets.toml) so a mouse-only user can enable diarization.
"""
