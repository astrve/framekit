# CLI Reference

All commands follow the pattern `fk <command> [OPTIONS] [ARGS]`.

Global options available on every command:

| Option | Description |
|--------|-------------|
| `--dry-run` | Preview changes without writing anything |
| `--json` | Emit machine-readable JSON output |
| `--no-color` | Disable Rich color output |
| `--help` | Show help and exit |

---

## Pipeline

```
fk pipeline PATH [OPTIONS]
```

Run the full release pipeline.

| Option | Description |
|--------|-------------|
| `--auto` | Skip all interactive prompts |
| `--pipeline-preset NAME` | Apply a named pipeline preset |
| `--dry-run` | Preview steps without executing |
| `--skip-step STEP` | Skip one pipeline step (repeatable) |
| `--start-at STEP` | Resume from a specific step |
| `--stop-after STEP` | Stop after a specific step |

Steps: `inspect`, `renamer`, `cleanmkv`, `metadata`, `nfo`, `prez`, `torrent`, `upload`

---

## Inspect

```
fk inspect PATH
```

Show release structure, detected tracks, and pipeline readiness. Read-only.

---

## Renamer

```
fk renamer PATH [OPTIONS]
```

Rename files to a structured format.

| Option | Description |
|--------|-------------|
| `--auto` | Apply rename without confirmation |
| `--dry-run` | Show proposed names only |

---

## CleanMKV

```
fk cleanmkv PATH [OPTIONS]
```

Remove unwanted audio/subtitle tracks from MKV files.

| Option | Description |
|--------|-------------|
| `--preset NAME` | Apply a named CleanMKV preset |
| `--output-dir DIR` | Write output to a different directory |
| `--dry-run` | Preview track removal |
| `--in-place` | Overwrite source files |

---

## Metadata

```
fk metadata [PATH] [OPTIONS]
```

Fetch and cache release metadata from TMDb.

| Option | Description |
|--------|-------------|
| `--set-token` | Store TMDb Read Access Token interactively |
| `--set-token-value TOKEN` | Store token non-interactively |
| `--status` | Show current metadata configuration |
| `--refresh` | Force re-fetch, ignoring cache |
| `--language LANG` | Override metadata language (e.g. `fr-FR`) |

---

## NFO

```
fk nfo PATH [OPTIONS]
```

Generate NFO files for the release.

| Option | Description |
|--------|-------------|
| `--template NAME` | NFO template to use |
| `--output-dir DIR` | Write NFO to this directory |
| `--no-logo` | Omit logo from NFO |

---

## Prez

```
fk prez PATH [OPTIONS]
```

Build BBCode and HTML presentations.

| Option | Description |
|--------|-------------|
| `--template NAME` | Presentation template (`classic`, `detailed`, `tracker`) |
| `--language LANG` | Presentation language (`en`, `fr`, `es`) |
| `--banner-design NAME` | Banner design name, or `textual` |
| `--output-dir DIR` | Write output to this directory |
| `--no-bbcode` | Skip BBCode output |
| `--no-html` | Skip HTML output |

---

## Torrent

```
fk torrent PATH [OPTIONS]
```

Create a `.torrent` file.

| Option | Description |
|--------|-------------|
| `--announce URL` | Primary announce URL |
| `--add-announce URL` | Add extra announce URL (repeatable) |
| `--piece-length SIZE` | Piece size in KiB, or `auto` |
| `--output-dir DIR` | Write torrent to this directory |
| `--no-folder` | Do not include top-level folder in payload |

---

## Upload

```
fk upload PATH [OPTIONS]
```

Upload a release to configured trackers. **Beta.**

| Option | Description |
|--------|-------------|
| `--tracker NAME` | Upload to a specific tracker profile |
| `--dry-run` | Preview upload payload without sending |

---

## Validate

```
fk validate PATH [OPTIONS]
```

Check a release against quality rules.

| Option | Description |
|--------|-------------|
| `--ruleset NAME` | Ruleset: `default`, `strict`, `anime`, `music-video` |
| `--strict` | Apply strict rules |
| `--require-nfo / --no-require-nfo` | Override NFO requirement |
| `--require-subs / --no-require-subs` | Override subtitle requirement |

---

## Encode

```
fk encode PATH [OPTIONS]
```

Re-encode video files using a preset.

| Option | Description |
|--------|-------------|
| `--preset NAME` | Named encoder preset |
| `--preset-file FILE` | Load preset from a YAML file |
| `--output PATH` | Output file path (single file mode) |
| `--output-dir DIR` | Output directory (batch mode) |
| `--recursive` | Recurse into subdirectories |
| `--dry-run` | Preview without encoding |

---

## Screenshot

```
fk screenshot PATH [OPTIONS]
```

Extract screenshots from video files.

| Option | Description |
|--------|-------------|
| `--count N` | Number of screenshots (default: 6) |
| `--output-dir DIR` | Screenshot output directory |
| `--timestamps LIST` | Comma-separated HH:MM:SS positions |

---

## Batch

```
fk batch PATH [OPTIONS]
```

Run the pipeline on multiple release folders.

| Option | Description |
|--------|-------------|
| `--auto` | No prompts; fully automatic |
| `--pipeline-preset NAME` | Apply preset to every release |
| `--workers N` | Parallel workers (default: 1) |
| `--no-dashboard` | Plain progress output |
| `--dry-run` | Preview without processing |

---

## Watch

```
fk watch PATH [OPTIONS]
```

Monitor a folder and auto-process new releases. **Beta.**

| Option | Description |
|--------|-------------|
| `--pipeline-preset NAME` | Preset applied to each detected release |
| `--poll-interval SECS` | Check interval in seconds (default: 30) |

---

## Seedbox

```
fk seedbox COMMAND [OPTIONS]
```

Manage seedbox transfers via rclone.

| Sub-command | Description |
|------------|-------------|
| `list` | List configured seedboxes |
| `send PATH --to NAME` | Transfer a release to a seedbox |
| `history` | Show transfer history |
| `add` | Add a seedbox profile interactively |

---

## Extract

```
fk extract PATH [OPTIONS]
```

Extract audio/subtitle streams from MKV files. **Beta.**

---

## Settings

```
fk settings COMMAND
```

| Sub-command | Description |
|------------|-------------|
| `show` | Print current config |
| `get KEY` | Get a single config value |
| `set KEY VALUE` | Set a config value |
| `reset` | Reset to defaults |

---

## Utility commands

| Command | Description |
|---------|-------------|
| `fk init` | First-time setup wizard |
| `fk doctor` | Check external tools and config |
| `fk inspect PATH` | Inspect release structure |
| `fk audit-log` | View audit log |
| `fk logs` | View run logs |
| `fk rollback PATH` | Rollback last operation on a path |
| `fk language` | Switch UI language |
| `fk alias` | Manage command aliases |
| `fk browse` | Open release in file browser |
| `fk sort` | Sort release files |
| `fk profile` | Show performance profiles |
| `fk benchmark` | Run performance benchmark |
| `fk examples` | Show usage examples |
