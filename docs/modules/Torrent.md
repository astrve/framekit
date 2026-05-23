# Torrent

Creates a `.torrent` file for the release. Supports single announce URL, multi-tracker lists, and automatic piece-length calculation.

---

## Usage

```bash
fk torrent /path/to/release [OPTIONS]
fk torrent /path/to/release --announce https://tracker.example.com/announce
fk torrent /path/to/release --piece-length 4096
fk torrent /path/to/release --output-dir /tmp/torrents
```

---

## Options

| Option | Description |
|--------|-------------|
| `--announce URL` | Primary announce URL |
| `--add-announce URL` | Add extra announce URL (repeatable) |
| `--piece-length SIZE` | Piece size in KiB, or `auto` |
| `--output-dir DIR` | Write .torrent to this directory |
| `--no-folder` | Exclude the top-level folder from the torrent payload |
| `--dry-run` | Show torrent metadata without creating the file |
| `--json` | Emit torrent metadata as JSON |

---

## Payload modes

| Mode | Config | Behavior |
|------|--------|----------|
| Folder (default) | `include_release_folder: true` | Top-level folder + all files inside |
| Files only | `include_release_folder: false` | Files at the root of the torrent, no folder |

---

## Piece length guide

| Release size | Recommended piece length |
|-------------|-------------------------|
| < 1 GB | 512 KiB |
| 1–4 GB | 1024 KiB |
| 4–8 GB | 2048 KiB |
| 8–16 GB | 4096 KiB |
| > 16 GB | 8192 KiB |

`auto` (default) selects based on total release size.

---

## Multi-tracker

```yaml
torrent:
  announce_url: "https://primary.tracker.com/announce"
  announce_urls:
    - "https://secondary.tracker.com/announce"
    - "udp://backup.tracker.com:6969/announce"
```

Or on the CLI:

```bash
fk torrent /path/to/release \
  --announce https://primary.tracker.com/announce \
  --add-announce https://secondary.tracker.com/announce
```

---

## Configuration

```yaml
torrent:
  announce_url: ""
  announce_urls: []
  piece_length: auto
  output_dir_name: ""
  include_release_folder: true
```

---

## In the pipeline

The `torrent` step runs after `prez`. The torrent path is stored in `PipelineContext.torrent_path` and passed to the `upload` step.
