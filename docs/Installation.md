# Installation

## Requirements

- **Python 3.12+** (CPython)
- External tools on `PATH` — see [External tools](#external-tools)

---

## Install options

### Pre-built binary (recommended)

Download the standalone binary for your platform from the [Releases page](https://github.com/astrve/ouro/releases). No Python installation required.

| Platform | File |
|----------|------|
| Linux x86-64 | `ouro-linux-x86_64` |
| macOS arm64 | `ouro-macos-arm64` |
| Windows x86-64 | `ouro-windows-x86_64.exe` |

Rename to `ouro` (or `ouro.exe`) and place on your `PATH`.

### pip / pipx

```bash
# Isolated install (recommended)
pipx install ouro

# Or standard pip
pip install ouro-auto
```

### From source

```bash
git clone https://github.com/astrve/ouro.git
cd ouro
pip install -e ".[dev]"
```

---

## External tools

Ouro shells out to these — install them and ensure they are on `PATH`:

| Tool | Package | Required by |
|------|---------|-------------|
| `mkvmerge`, `mkvextract`, `mkvpropedit` | [MKVToolNix](https://mkvtoolnix.download/) | CleanMKV, Extract |
| `mediainfo` | [MediaInfo CLI](https://mediaarea.net/en/MediaInfo) | NFO, Prez |
| `ffmpeg`, `ffprobe` | [FFmpeg](https://ffmpeg.org/) | Encode, Screenshot, Extract |
| `rclone` | [rclone](https://rclone.org/) | Seedbox |
| `mktorrent` or `torrentool` | system / pip | Torrent (optional) |

Verify your setup:

```bash
ouro doctor
```

---

## First-time setup

```bash
ouro init
```

This creates `~/.config/ouro/ouro.yaml` with defaults and prompts for your TMDb token.

Set your TMDb token at any time:

```bash
ouro metadata --set-token
```

Get a free TMDb Read Access Token at [themoviedb.org/settings/api](https://www.themoviedb.org/settings/api).

---

## Custom paths

| Env var | Default | Purpose |
|---------|---------|---------|
| `OURO_CONFIG_DIR` | `~/.config/ouro` | Config and settings |
| `OURO_CACHE_DIR` | `~/.cache/ouro` | API response cache, banner index |
| `OURO_LOG_DIR` | `~/.local/share/ouro/logs` | Audit and run logs |

---

## Dev install

```bash
git clone https://github.com/astrve/ouro.git
cd ouro
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pre-commit install
```

Run tests:

```bash
pytest
```
