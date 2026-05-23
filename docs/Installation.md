# Installation

## Requirements

- **Python 3.12 or newer** (3.13 and 3.14 are tested in CI)
- External media tools on `PATH` (see below)

---

## Option A — Pre-built binary (recommended)

Download the standalone binary for your platform from the [Releases page](https://github.com/astrve/framekit/releases):

| Platform | File |
|----------|------|
| Linux x86-64 | `framekit-linux-x86_64` |
| macOS Apple Silicon | `framekit-macos-arm64` |
| Windows x86-64 | `framekit-windows-x86_64.exe` |

The binary bundles Python and all Python dependencies. External media tools are **not** bundled.

```bash
# Linux / macOS
chmod +x framekit-linux-x86_64
mv framekit-linux-x86_64 /usr/local/bin/fk
fk doctor
```

---

## Option B — From source (scripted)

### Linux / macOS

```bash
git clone https://github.com/astrve/framekit.git
cd framekit
bash install.sh
```

`install.sh` verifies Python 3.12+, creates `.venv`, runs `pip install -e .`, and prints PATH instructions.

### Windows

```bat
git clone https://github.com/astrve/framekit.git
cd framekit
install.bat
```

`install.bat` additionally offers to install MKVToolNix and FFmpeg via **winget** or **Chocolatey**.

---

## Option C — Manual install

```bash
git clone https://github.com/astrve/framekit.git
cd framekit
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .
fk --version
```

Both `fk` and `framekit` are registered as entry points and are interchangeable.

---

## External tools

Run `fk doctor` after install — it will report any missing tools.

### MKVToolNix — CleanMKV, Extract

- **Linux**: `sudo apt install mkvtoolnix`
- **macOS**: `brew install mkvtoolnix`
- **Windows**: `winget install MKVToolNix.MKVToolNix`

Required binaries: `mkvmerge`, `mkvextract`, `mkvpropedit`

### MediaInfo — NFO, Prez, Inspect

- **Linux**: `sudo apt install mediainfo`
- **macOS**: `brew install mediainfo`
- **Windows**: `winget install MediaArea.MediaInfo`

### FFmpeg — Encode, Screenshot, Extract

- **Linux**: `sudo apt install ffmpeg`
- **macOS**: `brew install ffmpeg`
- **Windows**: `winget install Gyan.FFmpeg`

Required binaries: `ffmpeg`, `ffprobe`

---

## Custom tool paths

If tools are not on `PATH`, set their paths in `framekit.yaml`:

```yaml
tools:
  mkvmerge: /opt/mkvtoolnix/bin/mkvmerge
  ffmpeg: /usr/local/bin/ffmpeg
  ffprobe: /usr/local/bin/ffprobe
  mediainfo: /usr/local/bin/mediainfo
```

---

## Development install

```bash
pip install -e ".[dev,docs,build-binary]"
pre-commit install
```

See [Contributing](Contributing.md) for the full development setup.
