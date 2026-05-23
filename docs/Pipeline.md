# Pipeline

The pipeline is Framekit's core orchestration layer. It chains every processing module into a single, composable command that can run unattended.

---

## Module order

```
inspect → renamer → cleanmkv → metadata → nfo → prez → torrent → upload
```

Each step can be skipped, paused after, or started from.

---

## Basic usage

```bash
# Interactive (prompts at each step)
fk pipeline /path/to/release

# Fully automatic
fk pipeline /path/to/release --auto

# Dry run (preview only)
fk pipeline /path/to/release --dry-run

# Use a preset
fk pipeline /path/to/release --pipeline-preset multi_fr

# Start from a specific step
fk pipeline /path/to/release --start-at prez

# Skip steps
fk pipeline /path/to/release --skip-step torrent --skip-step upload
```

---

## Pipeline presets

Presets bundle all step options into a named configuration.

| Preset | Description |
|--------|-------------|
| `single_fr` | Single-audio French film |
| `multi_fr` | Multi-audio with French track |
| `series_fr` | TV series, French tracks |

```bash
fk pipeline /path/to/release --pipeline-preset multi_fr --auto
```

See [Presets](Presets.md) for the full format and how to create custom presets.

---

## Step reference

### inspect

Read-only scan. Detects:
- MKV files and their tracks
- Existing NFO / torrent files
- Release type (movie / series / episode)

### renamer

Renames files to a structured format. Interactive by default — shows proposed names and asks for confirmation.

### cleanmkv

Removes unwanted audio and subtitle tracks from MKV files. Prompts for preset selection or uses `cleanmkv.default_preset` from config.

### metadata

Fetches title, year, rating, overview, poster URL, and IMDb ID from TMDb. Caches responses for `metadata.cache_ttl_hours` hours. Prompts for confirmation when multiple matches exist.

### nfo

Generates `.nfo` files from the Jinja2 templates in `src/framekit/templates/nfo/`.

### prez

Builds BBCode and HTML presentations. In interactive mode, prompts for:
- Template (`classic` / `detailed` / `tracker`)
- Language (`en` / `fr` / `es`)
- Banner design (fetched from GitHub, or `textual`)

In the pipeline, **text-only banners are pre-selected by default** to avoid accidental selections.

### torrent

Creates a `.torrent` file with the configured announce URLs and piece length.

### upload

Uploads the torrent and presentation to configured trackers. **Beta** — requires `upload.trackers` in config.

---

## PipelineContext

Steps share state via a `PipelineContext` dataclass:

| Field | Type | Description |
|-------|------|-------------|
| `release` | `Release` | Scanned release object (set by inspect) |
| `metadata_context` | `MetadataContext \| None` | Resolved TMDb metadata |
| `nfo_path` | `Path \| None` | Path to generated NFO file |
| `prez_outputs` | `dict` | BBCode and HTML output paths |
| `torrent_path` | `Path \| None` | Path to generated .torrent |
| `dry_run` | `bool` | Global dry-run flag |

---

## Auto mode

With `--auto`, all interactive prompts are answered with their defaults:

- CleanMKV: uses `cleanmkv.default_preset` (skips if not set)
- Prez: uses `prez.template`, `prez.language`, `prez.banner_design` from config (default: `textual`)
- Torrent: uses `torrent.announce_url` from config
- Upload: uses all configured tracker profiles

---

## Rollback

Every step that modifies files records a rollback entry:

```bash
fk rollback /path/to/release
```

Restores the release folder to its pre-pipeline state. Rollback data is stored in `~/.local/share/framekit/rollback/`.
