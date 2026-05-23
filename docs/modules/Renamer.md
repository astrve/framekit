# Renamer

Renames release files and folders to a structured, consistent format. Works on MKV files, subtitles, and the release folder itself.

---

## Usage

```bash
fk renamer /path/to/release [OPTIONS]
fk renamer /path/to/release --auto
fk renamer /path/to/release --dry-run
```

---

## Options

| Option | Description |
|--------|-------------|
| `--auto` | Apply proposed names without confirmation |
| `--dry-run` | Show proposed names without renaming |
| `--json` | Emit proposed renames as JSON |

---

## What it renames

- Main MKV files → structured filename with title, year, quality, codec, group
- Subtitle files → matched to their MKV with language suffix
- Release folder → matches the main MKV stem

### Example

Before:
```
Movie.2024.1080p.WEB-DL.DD5.1.H.264-GROUP/
  Movie.2024.1080p.WEB-DL.DD5.1.H.264-GROUP.mkv
  Movie.2024.1080p.WEB-DL.DD5.1.H.264-GROUP.fra.srt
```

After (with metadata fetched):
```
The.Movie.2024.1080p.WEB-DL.DD5.1.H264-GROUP/
  The.Movie.2024.1080p.WEB-DL.DD5.1.H264-GROUP.mkv
  The.Movie.2024.1080p.WEB-DL.DD5.1.H264-GROUP.fra.srt
```

---

## Interactive term picker

In interactive mode, Renamer shows the parsed components of the detected filename and lets you correct individual terms:

```
Detected:
  Title   : Movie
  Year    : 2024
  Quality : 1080p
  Source  : WEB-DL
  Codec   : H264
  Group   : GROUP

Accept? [Y/n]
```

---

## Configuration

No dedicated config section. Renamer uses:

- `metadata.language` for title lookup
- `paths.start_folder` as fallback root

---

## In the pipeline

The `renamer` step runs first, before CleanMKV. The renamed paths are passed to subsequent steps via `PipelineContext.release`.
