# Framekit 2.0.0

Framekit 2.0.0 is the first public v2 release: a CLI-first media release toolkit for repeatable local workflows.

## GitHub Release Text

Framekit 2.0.0 is now available.

This release focuses on a stable terminal-first workflow for preparing media releases: inspect, rename, clean MKV tracks, fetch metadata, build NFO and presentation files, create torrents, validate outputs, and run repeatable pipelines or batches.

Highlights:

- End-to-end `fk pipeline` workflow
- Batch mode for multi-release processing
- Package-embedded presets
- Automatic preset, template, logo, and banner discovery
- Encrypted local vault for tokens, announce URLs, and tracker credentials
- Structured logs, audit trail, rollback ledger, and diagnostics
- GitHub Release binaries for Windows, Linux, and macOS

Beta modules:

- `fk upload`
- `fk extract`
- `fk watch`

These modules are available in 2.0.0, but their command surfaces may change faster than the stable core workflow.

External tools are not bundled in the binaries. Install `ffmpeg`, `ffprobe`, `mkvtoolnix`, and `mediainfo` separately.

## Short Announcement

Framekit 2.0.0 is out: CLI-first media release automation with pipeline, batch, MKV cleanup, metadata, NFO/Prez, torrents, validation, encrypted secrets, and standalone GitHub binaries.

Beta in 2.0.0: `upload`, `extract`, `watch`.

External tools still required: `ffmpeg`, `mkvtoolnix`, `mediainfo`.
