# Installation

## Requirements

- **Python 3.12+** (CPython)
- External tools on `PATH` — see [External tools](#external-tools)

---

## Install options

### Pre-built binary (recommended)

Download the standalone binary for your platform from the [Releases page](https://github.com/astrve/framekit/releases). No Python installation required.

| Platform | File |
|----------|------|
| Linux x86-64 | `framekit-linux-x86_64` |
| macOS arm64 | `framekit-macos-arm64` |
| Windows x86-64 | `framekit-windows-x86_64.exe` |

Rename to `fk` (or `fk.exe`) and place on your `PATH`.

### pip / pipx

```bash
# Isolated install (recommended)
pipx install framekit

# Or standard pip
pip install framekit
```

### From source

```bash
git clone https://github.com/astrve/framekit.git
cd framekit
pip install -e ".[dev]"
```

---

## External tools

Framekit shells out to these — install them and ensure they are on `PATH`:

| Tool | Package | Required by |
|------|---------|-------------|
| `mkvmerge`, `mkvextract`, `mkvpropedit` | [MKVToolNix](https://mkvtoolnix.download/) | CleanMKV, Extract |
| `mediainfo` | [MediaInfo CLI](https://mediaarea.net/en/MediaInfo) | NFO, Prez |
| `ffmpeg`, `ffprobe` | [FFmpeg](https://ffmpeg.org/) | Encode, Screenshot, Extract |
| `rclone` | [rclone](https://rclone.org/) | Seedbox |
| `mktorrent` or `torrentool` | system / pip | Torrent (optional) |

Verify your setup:

```bash
fk doctor
```

---

## First-time setup

```bash
fk init
```

This creates `~/.config/framekit/framekit.yaml` with defaults and prompts for your TMDb token.

Set your TMDb token at any time:

```bash
fk metadata --set-token
```

Get a free TMDb Read Access Token at [themoviedb.org/settings/api](https://www.themoviedb.org/settings/api).

---

## Custom paths

| Env var | Default | Purpose |
|---------|---------|---------|
| `FRAMEKIT_CONFIG_DIR` | `~/.config/framekit` | Config and settings |
| `FRAMEKIT_CACHE_DIR` | `~/.cache/framekit` | API response cache, banner index |
| `FRAMEKIT_LOG_DIR` | `~/.local/share/framekit/logs` | Audit and run logs |

---

## Dev install

```bash
git clone https://github.com/astrve/framekit.git
cd framekit
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pre-commit install
```

Run tests:

```bash
pytest
```
