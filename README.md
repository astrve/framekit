# Ouro

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/downloads/)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![Type-checked: pyright](https://img.shields.io/badge/type--checked-pyright-2A6DB2.svg)](https://github.com/microsoft/pyright)

Ouro is a CLI-first media release toolkit for local, headless-friendly workflows:
rename files, clean MKV tracks, fetch metadata, build NFO and presentation files, create
torrents, validate releases, encode video, process batches, and automate repeatable pipelines.

Application auto-hébergée pour le traitement de fichiers vidéo.  
Self-hosted media workflow automation.

## Status

Ouro `2.0.0` is the first public v2 release.

Beta modules — available and tested, but their command surfaces may change faster than the
stable core workflow:

- `ouro upload`
- `ouro extract`
- `ouro watch`

## Requirements

- Python `3.12` or newer
- `mkvmerge`, `mkvextract`, `mkvpropedit` from [MKVToolNix](https://mkvtoolnix.download/) — for MKV cleanup and subtitle extraction
- `mediainfo` from [MediaInfo](https://mediaarea.net/en/MediaInfo) — for release inspection and technical metadata
- `ffmpeg` and `ffprobe` — for encoding, screenshots, and stream extraction

Ouro GitHub Release binaries package Ouro itself. External tools are not bundled;
install them separately and make sure they are available on `PATH`.

## Installation

### From GitHub Release

Download the binary for your platform from the GitHub Release page:

- `ouro-windows-x86_64.exe`
- `ouro-linux-x86_64`
- `ouro-macos-arm64`

Then run:

```bash
ouro --version
ouro doctor
```

### From PyPI

```bash
pip install ouro-auto
ouro --version
```

### From Source

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
pip install -e .
ouro --version
```

## Migration from Framekit

- Product/app renamed to `Ouro`.
- CLI command renamed to `ouro` (no `framekit` compatibility alias in v2).
- Config defaults moved to:
  - settings: `~/.config/ouro/ouro.yaml`
  - cache: `~/.cache/ouro/`
  - service state: platform app-data under `ouro/`
- Old `framekit` files/folders are **not** deleted automatically.
- Manual migration: copy old config/cache content into new `ouro` paths if needed.

## Quick Start

```bash
ouro setup                                  # guided wizard: credentials, tools, presets
ouro doctor                                 # verify external tools and configuration
ouro inspect "Release folder"               # scan release structure
ouro pipeline "Release folder" --preview    # see planned actions before running
ouro pipeline "Release folder"              # run the full pipeline
```

Batch mode (multiple releases):

```bash
ouro batch "Parent folder"
ouro batch "Parent folder" --auto           # unattended
```

## Core Workflow

| Step | Command | What it does |
|------|---------|-------------|
| Inspect | `ouro inspect` | Scan release structure, detect missing files and completeness |
| Rename | `ouro renamer` | Normalize filenames and release tags |
| Clean | `ouro cleanmkv` | Remux MKV files, remove unwanted audio and subtitle tracks |
| Metadata | `ouro metadata` | Resolve title, year, cast from TMDb, TVDb, AniList, or Trakt |
| NFO | `ouro nfo` | Generate tracker-ready NFO files (global, per-file, or both) |
| Presentation | `ouro prez` | Generate BBCode and HTML presentation files |
| Torrent | `ouro torrent` | Build private or public `.torrent` files |
| Validate | `ouro validate` | Run pre-upload release checks |
| Pipeline | `ouro pipeline` | Orchestrate all of the above in one command |

CleanMKV writes cleaned MKV files to `Release/<release-name>/` — the release name is
derived from the first MKV filename. NFO, Prez, and Torrent all operate on that same
payload folder so outputs are always consistent.

## Commands

| Command | Alias(es) | Description |
|---------|-----------|-------------|
| `about` | `license` | Show version, license, and repository information |
| `init` | — | Create a starter `ouro.yaml` in the current directory |
| `setup` | — | Run the guided setup wizard |
| `language` | `lang` | Manage CLI language preferences |
| `settings` | `cfg`, `set` | View and edit local settings |
| `alias` | — | Manage custom command aliases |
| `doctor` | `doc`, `diag` | Check the local environment and toolchain |
| `logs` | — | Inspect Ouro structured logs |
| `rollback` | — | Roll back tracked file operations |
| `examples` | `ex` | Show command examples |
| `rename-parent` | `rp` | Rename a parent folder from release metadata |
| `validate` | — | Run pre-upload release checks |
| `profile` | — | Manage settings profiles |
| `inspect` | `ins` | Inspect a release folder |
| `browse` | — | Browse release folders from the terminal |
| `sort` | — | Sort release folders |
| `extract` | `ext` | *(beta)* Extract subtitle, audio, and video streams |
| `screenshot` | `sc`, `screens` | Capture screenshots and image sets |
| `encode` | `enc` | Encode video files with presets |
| `watch` | — | *(beta)* Monitor folders and trigger pipeline presets |
| `seedbox` | — | Seedbox transfer helpers |
| `renamer` | `ren` | Normalize file and folder names |
| `cleanmkv` | `cmk` | Clean and remux MKV files |
| `metadata` | `meta`, `md` | Resolve metadata from configured providers |
| `nfo` | `nf` | Generate tracker-ready NFO files |
| `torrent` | `tor` | Create torrent files |
| `prez` | — | Generate BBCode and HTML presentations |
| `upload` | `up` | *(beta)* Upload releases to tracker APIs |
| `pipeline` | `pipe`, `pr` | Orchestrate the full workflow |
| `batch` | `bat` | Process multiple releases |

Common global flags:

```text
--yes / -y        Skip confirmations where supported
--dry-run         Preview changes without writing any files
--debug           Show tracebacks and write debug logs
--log-file PATH   Write JSONL logs to a custom path
--no-color        Disable terminal colors
-h / --help       Show command help
--version         Show installed version
```

## Configuration

Run the setup wizard to configure credentials, external tool paths, and default presets:

```bash
ouro setup
```

Or start from the bundled example:

```bash
cp ouro.example.yaml ouro.yaml
```

`ouro.yaml` is ignored by Git because it may contain local paths, tracker URLs, or
secrets. Use the `OURO_CONFIG` environment variable to point to a config file in a
non-standard location:

```bash
OURO_CONFIG=/path/to/ouro.yaml ouro doctor
```

## Credentials

Ouro uses [The Movie Database (TMDb)](https://www.themoviedb.org/) and optionally
TVDb, AniList, and Trakt for metadata. To enable metadata fetching:

1. Create a free TMDb account at [themoviedb.org](https://www.themoviedb.org/) and go to
   account settings → **API**.
2. Copy your **API Read Access Token (v4 auth)** or **API Key (v3 auth)**.
3. Run `ouro setup` or `ouro metadata --set-token` and paste the token when prompted.
   Ouro stores it in the encrypted vault.

To remove stored credentials:

```bash
ouro metadata --clear
```

## Secrets

Ouro stores sensitive values in an encrypted local vault when `security.enabled: true`
(the default):

- TMDb, TVDb, AniList, and Trakt tokens
- Tracker API keys
- Announce URLs and passkeys
- Torrent client credentials
- Image host API keys

Secret values are redacted from `ouro settings`, `ouro doctor`, logs, and error messages.

To opt out of the encrypted vault, set `security.enabled: false` in `ouro.yaml`. This
is not recommended for shared machines.

## Torrent Content Modes

Ouro detects the media payload automatically so sidecar files (NFO, Prez HTML/BBCode,
screenshots, `.txt`) are excluded by default. Control this with `--content`:

| Mode | Behaviour |
|------|-----------|
| `auto` (default) | Include only the detected MKV release or season pack |
| `media` | Include all recognized media files (MKV, MP4, M4V, AVI) |
| `folder` | Include everything in the folder, except existing `.torrent` files |
| `select` | Interactively pick from multiple detected media groups |

```bash
ouro torrent "Release/Release.Name" --content auto
ouro torrent "Release/Release.Name" --content folder
```

In headless mode, an ambiguous payload raises an error instead of silently selecting a
default. Torrent filenames follow the same sanitization logic as CleanMKV and never keep
the `.mkv` suffix.

## Pipeline Options

```bash
ouro pipeline "Release folder"                              # interactive: choose modules, confirm
ouro pipeline "Release folder" --auto                       # fully unattended
ouro pipeline "Release folder" --preview                    # show planned actions, confirm or cancel
ouro pipeline "Release folder" --dry-run                    # execute without writing any files
ouro pipeline "Release folder" --pipeline-preset multi_fr   # load a saved preset
ouro pipeline "Release folder" --skip-prez --skip-upload    # skip specific modules
ouro pipeline "Release folder" --nfo-mode per_file          # one NFO per MKV
ouro pipeline "Release folder" --no-metadata                # skip metadata fetching
ouro pipeline --create-preset                               # interactive wizard to save a new preset
```

Pipeline modules (in execution order): `renamer` → `cleanmkv` → `nfo` → `torrent` →
`prez` → `upload`. `encode` is opt-in and excluded from the default set.

## Automation

Ouro is designed for repeatable workflows:

- **Presets** are discovered from `Presets/Pipeline/`, `Presets/CleanMKV/`,
  `Presets/Encoder/`, and package-bundled resources.
- **Prez** templates and NFO logos are scanned from bundled resources and user imports.
- **Pipeline presets** can be reused in `ouro batch` and `ouro watch` workflows.
- **`ouro batch`** processes a parent folder containing multiple release subfolders.
- **`ouro watch`** *(beta)* monitors a folder and triggers a pipeline preset when new
  content appears.

## Development

```bash
python -m venv .venv
pip install -e ".[dev,docs,build-binary]"
pre-commit install
```

Quality checks:

```bash
ruff format --check src tests
ruff check src tests
pyright
pytest
bandit -r src
pip-audit
detect-secrets scan
python -m build
twine check dist/*
```

## License

Ouro is released under the GNU General Public License v3.0.

Copyright (C) 2026 astrve. See [LICENSE](LICENSE).

