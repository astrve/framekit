# Framekit

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/downloads/)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![Type-checked: pyright](https://img.shields.io/badge/type--checked-pyright-2A6DB2.svg)](https://github.com/microsoft/pyright)

Framekit is a CLI-first media release toolkit for local, headless-friendly workflows:
rename, clean MKV tracks, fetch metadata, build NFO and presentation files, create
torrents, validate releases, process batches, and automate repeatable pipelines.

## Status

Framekit `2.0.0` is the first public v2 release.

Beta modules:
- `fk upload`
- `fk extract`
- `fk watch`

These modules are usable, tested, and documented, but their command surfaces may still
change faster than the stable core workflow.

## Requirements

- Python `3.12` or newer
- `ffmpeg` and `ffprobe` for screenshots, extraction, and encoding
- `mkvtoolnix` (`mkvmerge`, `mkvextract`, `mkvpropedit`) for MKV cleanup and subtitle extraction
- `mediainfo` for release inspection and technical metadata

Framekit GitHub Release binaries package Framekit itself. They do not bundle these
external tools; install them separately and make sure they are available on `PATH`.

## Installation

### From GitHub Release

Download the binary matching your platform from the GitHub Release page:

- `framekit-windows-x86_64.exe`
- `framekit-linux-x86_64`
- `framekit-macos-arm64`

Then run:

```bash
framekit --version
framekit doctor
```

### From Source

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
pip install -e .
```

Short command alias:

```bash
fk --version
```

## Quick Start

```bash
fk setup
fk doctor
fk inspect "Release folder"
fk pipeline "Release folder" --preview
fk pipeline "Release folder"
```

Headless mode:

```bash
fk pipeline "Release folder" --auto
fk batch "Parent folder" --auto
```

## Core Workflow

- `fk inspect` checks release folder structure.
- `fk renamer` normalizes file names and release tags.
- `fk cleanmkv` remuxes MKV files and removes unwanted tracks.
- `fk metadata` resolves metadata from TMDb and optional fallback providers.
- `fk nfo` creates tracker-ready NFO files.
- `fk prez` creates BBCode and HTML presentation files.
- `fk torrent` builds private or public `.torrent` files.
- `fk validate` runs pre-upload release checks.
- `fk pipeline` orchestrates the full workflow.
- `fk batch` processes multiple releases.

Beta workflow modules:
- `fk upload` uploads torrents to supported tracker APIs.
- `fk extract` extracts subtitle, audio, and video streams.
- `fk watch` monitors folders and triggers pipeline presets.

## Automation

Framekit avoids project-directory assumptions where possible:

- Presets are discovered from package resources and project/user preset folders.
- Prez HTML and BBCode templates are discovered from packaged template files.
- NFO logos are scanned from bundled resources and user imports.
- Banner designs are discovered from the online banner catalog, cached locally, and backed by an offline fallback list.
- Pipeline presets can be reused in batch and watch workflows.

## Commands

| Command | Alias(es) | Description |
| --- | --- | --- |
| `about` | `license` | Show version, license, and repository information. |
| `init` | - | Create a starter local configuration. |
| `setup` | - | Run the guided setup wizard. |
| `language` | `lang` | Manage CLI language preferences. |
| `settings` | `cfg`, `set` | View and edit local settings. |
| `alias` | - | Manage custom command aliases. |
| `doctor` | `doc`, `diag` | Check the local environment and toolchain. |
| `logs` | - | Inspect Framekit logs. |
| `rollback` | - | Roll back tracked file operations. |
| `examples` | `ex` | Show command examples. |
| `rename-parent` | `rp` | Rename a parent folder from release metadata. |
| `validate` | - | Run pre-upload release checks. |
| `profile` | - | Manage settings profiles. |
| `inspect` | `ins` | Inspect a release folder. |
| `browse` | - | Browse release folders from the terminal. |
| `sort` | - | Sort release folders. |
| `extract` | `ext` | Beta stream extraction commands. |
| `screenshot` | `sc`, `screens` | Create screenshots and image sets. |
| `encode` | `enc` | Encode video files with presets. |
| `watch` | - | Beta folder watcher automation. |
| `seedbox` | - | Seedbox transfer helpers. |
| `renamer` | `ren` | Normalize file and folder names. |
| `cleanmkv` | `cmk` | Clean and remux MKV files. |
| `metadata` | `meta`, `md` | Resolve metadata from configured providers. |
| `nfo` | `nf` | Generate tracker-ready NFO files. |
| `torrent` | `tor` | Create torrent files. |
| `prez` | - | Generate BBCode and HTML presentations. |
| `upload` | `up` | Beta tracker upload commands. |
| `pipeline` | `pipe`, `pr` | Run the workflow pipeline. |
| `batch` | `bat` | Process multiple releases. |

Common global flags:

```text
--yes / -y       Skip confirmations where supported
--dry-run        Preview changes without writing
--debug          Show tracebacks and write debug logs
--log-file PATH  Write JSONL logs to a custom path
--no-color       Disable terminal colors
-h / --help      Show command help
--version        Show installed version
```

## Configuration

Run the setup wizard:

```bash
fk setup
```

Or start from the example:

```bash
cp framekit.example.yaml framekit.yaml
```

`framekit.yaml` is ignored by Git because it may contain local paths, tracker URLs,
or plaintext secrets if the encrypted vault is disabled.

## Secrets

Framekit stores sensitive values in an encrypted vault when `security.enabled` is true:

- TMDb tokens
- tracker API keys
- announce URLs and passkeys
- torrent client credentials
- image host API keys

Secret values are redacted from settings output, diagnostics, logs, and error messages.

Supported override pattern:

```bash
FRAMEKIT_CONFIG=/path/to/framekit.yaml fk doctor
```

## Documentation

Minimal docs live in [`docs/Home.md`](docs/Home.md).

The public wiki can reuse the same pages later without changing the CLI package.

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

Framekit is released under the GNU General Public License v3.0.

See [LICENSE](LICENSE).
