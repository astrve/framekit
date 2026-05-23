# NFO

Generates `.nfo` files describing the release. Uses Jinja2 templates and merges data from the release scan, MediaInfo, and fetched metadata.

---

## Usage

```bash
fk nfo /path/to/release [OPTIONS]
fk nfo /path/to/release --template classic
fk nfo /path/to/release --output-dir /some/other/dir
```

---

## Options

| Option | Description |
|--------|-------------|
| `--template NAME` | NFO template to use (default: from config) |
| `--output-dir DIR` | Write NFO to this directory instead of the release folder |
| `--no-logo` | Omit the ASCII logo from the NFO header |
| `--dry-run` | Print the NFO to stdout without writing a file |
| `--json` | Emit output path and metadata as JSON |

---

## Output

Writes `<release-name>.nfo` in the release folder (or `--output-dir`).

The NFO contains:
- Release title, year, and quality line
- Video track information (codec, resolution, bitrate, HDR)
- Audio tracks table (language, codec, channels, bitrate)
- Subtitles table (language, format, flags)
- Full MediaInfo block (in a collapsible section where supported)
- Release group and encode notes

---

## Template system

Templates live in `src/framekit/templates/nfo/` and use a `SandboxedEnvironment` with `trim_blocks=False`.

### Built-in templates

| Name | Description |
|------|-------------|
| `classic` | Standard ASCII-art NFO |

### Custom templates

Place `.jinja2` files in `~/.config/framekit/nfo_templates/`. Reference by filename stem:

```bash
fk nfo /path/to/release --template my_template
```

### Variables

| Variable | Type | Description |
|----------|------|-------------|
| `release` | `Release` | Full release scan result |
| `title` | `str` | Display title |
| `year` | `str \| None` | Year string |
| `quality` | `str` | Quality tag (e.g. `1080p`, `4K HDR`) |
| `codec` | `str` | Video codec name |
| `audio_tracks` | `list` | Audio track objects |
| `subtitle_tracks` | `list` | Subtitle track objects |
| `mediainfo_text` | `str` | Raw MediaInfo CLI output |
| `metadata` | `MetadataContext \| None` | TMDb metadata |
| `nfo_version` | `str` | Framekit version string |

### Macros

| Macro | Output |
|-------|--------|
| `audio_table(tracks)` | Text-art table of audio tracks |
| `subtitle_table(tracks)` | Text-art table of subtitle tracks |
| `separator(char, width)` | Horizontal rule |
| `logo()` | ASCII logo block |

---

## Configuration

```yaml
nfo:
  template: classic
  output_dir_name: ""   # empty = same folder as release
```

---

## In the pipeline

The `nfo` step runs after `metadata`. If metadata fetch failed or was skipped, the NFO is built from release scan data only (no title, year, or poster from TMDb).

The generated NFO path is stored in `PipelineContext.nfo_path` and passed to `prez` and `torrent`.
