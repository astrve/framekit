# Framekit

**Framekit** is a CLI-first toolkit for preparing and publishing media releases from local folders. It automates the full release workflow — renaming, MKV track cleaning, metadata fetching, NFO generation, BBCode/HTML presentations, torrent creation, and tracker uploads — with a composable pipeline that can run fully unattended.

---

## Core workflow

```
folder → renamer → cleanmkv → metadata → nfo → prez → torrent → upload
```

Run the full pipeline interactively or in a single command:

```bash
fk pipeline /path/to/release
fk pipeline /path/to/release --auto --pipeline-preset multi_fr
```

---

## Quick links

| Topic | Page |
|-------|------|
| Install Framekit | [Installation](Installation.md) |
| First-run walkthrough | [Quick Start](Quick-Start.md) |
| All config keys | [Configuration](Configuration.md) |
| All CLI commands | [CLI Reference](CLI-Reference.md) |
| Pipeline deep-dive | [Pipeline](Pipeline.md) |
| Presets system | [Presets](Presets.md) |
| Template system | [Templates](Templates.md) |
| Encrypted vault / security | [Security](Security.md) |
| Module reference | [Modules →](modules/NFO.md) |
| Contributing | [Contributing](Contributing.md) |
| Architecture internals | [Architecture](Architecture.md) |

---

## Modules at a glance

| Module | Command | Status |
|--------|---------|--------|
| Inspect release | `fk inspect` | Stable |
| Rename files | `fk renamer` | Stable |
| Clean MKV tracks | `fk cleanmkv` | Stable |
| Fetch metadata | `fk metadata` | Stable |
| Generate NFO | `fk nfo` | Stable |
| Build presentation | `fk prez` | Stable |
| Create torrent | `fk torrent` | Stable |
| Validate release | `fk validate` | Stable |
| Screenshot extraction | `fk screenshot` | Stable |
| Video encoding | `fk encode` | Stable |
| Batch processing | `fk batch` | Stable |
| Upload to trackers | `fk upload` | Beta |
| Stream extraction | `fk extract` | Beta |
| Folder watcher | `fk watch` | Beta |

---

## External tools

Framekit shells out to these — install them and keep them on `PATH`:

| Tool | Package | Used by |
|------|---------|---------|
| `mkvmerge`, `mkvextract`, `mkvpropedit` | MKVToolNix | CleanMKV, Extract |
| `mediainfo` | MediaInfo | NFO, Prez |
| `ffmpeg`, `ffprobe` | FFmpeg | Encode, Screenshot, Extract |

---

## Supported platforms

Python **3.12+** on Linux, macOS, and Windows. Pre-built standalone binaries for `linux-x86_64`, `macos-arm64`, and `windows-x86_64` are published on the [Releases page](https://github.com/astrve/framekit/releases).
