# CLI Reference

All commands are invoked as `fk <command>` or `framekit <command>`.

## Global flags

These flags work on every command:

| Flag | Purpose |
|------|---------|
| `--version` | Print installed version |
| `-h / --help` | Show help for the command |
| `--yes / -y` | Skip confirmations |
| `--dry-run` | Preview changes without writing |
| `--debug` | Show full tracebacks and write debug logs |
| `--log-file PATH` | Write JSONL logs to a custom path |
| `--no-color` | Disable terminal colors |

---

## Configuration commands

### `fk about` (alias: `license`)

Print version, copyright, license type, and repository URL.

### `fk init`

Create a starter `framekit.yaml` in the current directory.

### `fk setup`

Run the guided interactive setup wizard. Covers credentials, tool paths, NFO defaults, and vault configuration.

### `fk language <code>` (alias: `lang`)

Switch the UI language. Supported codes: `en`, `fr`, `es`.

```bash
fk language fr
```

---

## Tools commands

### `fk settings` (aliases: `cfg`, `set`)

View and edit settings. Shows a multi-table overview of all sections. Sensitive keys are redacted.

```bash
fk settings
fk settings set modules.nfo.locale fr
fk settings get security.enabled
fk settings reset
```

### `fk alias`

Manage command aliases.

```bash
fk alias list                       # list all aliases
fk alias add myalias "pipeline --auto --pipeline-preset multi_fr"
fk alias remove myalias
```

Aliases are stored in `aliases.user` in `framekit.yaml`. Max chain depth is configurable via `aliases.max_chain_depth` (default: 5).

### `fk doctor` (aliases: `doc`, `diag`)

Full environment health check. Checks Python version, settings file, external tools (mkvmerge, ffmpeg, ffprobe, mediainfo), TMDb credentials, vault, disk space, template registry, and NFO/torrent config. Outputs a Rich table with OK / Warning / Error per check.

```bash
fk doctor
```

### `fk logs`

Inspect Framekit structured JSONL logs. Supports filtering by level, date range, and command.

### `fk rollback`

Roll back tracked file operations using the run ledger. Lists available runs; you select which to revert.

### `fk validate PATH`

Validate a release folder against a ruleset.

| Option | Default | Purpose |
|--------|---------|---------|
| `--ruleset / -r` | `default` | Ruleset: `default` or `strict` |
| `--strict` | off | Force strict ruleset |
| `--require-nfo / --no-require-nfo` | — | Override NFO requirement |
| `--require-subs / --no-require-subs` | — | Override subtitle requirement |
| `--min-resolution INT` | — | Minimum video width in pixels |
| `--max-size-gb FLOAT` | — | Maximum file size in GB |

Exits with code `1` if any check fails.

### `fk profile`

Manage settings profiles (list, create, switch, delete, show).

### `fk inspect PATH` (alias: `ins`)

Scan a release folder and print a summary table: title, media kind, year, episode count, completeness, size, duration, codec, audio, resolution.

### `fk examples` (alias: `ex`)

Show command examples in the terminal.

---

## Media processing commands

### `fk renamer [PATH]` (alias: `ren`)

Normalize filenames by detecting and removing release tags, inserting language codes.

| Option | Default | Purpose |
|--------|---------|---------|
| `--lang STR` | — | Language tag to insert (e.g., `MULTI.VFF`) |
| `--apply / -a` | off | Apply renames immediately |
| `--dry-run` | off | Preview only |
| `--force-lang` | off | Override detected language |
| `--remove-term STR` | — | Terms to strip (repeatable) |
| `--select-terms` | off | Interactive term picker |
| `--profile STR` | — | Named renamer profile |

### `fk cleanmkv [PATH]` (alias: `cmk`)

Interactively clean MKV track selection (audio + subtitle tracks).

| Option | Default | Purpose |
|--------|---------|---------|
| `--apply / -a` | off | Apply without confirmation |
| `--preset / -p STR` | `multi` | Built-in preset (`multi`, `keep_all`, `en_only`, ...) |
| `--preset-file / -pf PATH` | — | Load preset from JSON file |
| `--external-preset / -ep STR` | — | Load saved preset by name |
| `--wizard / -w` | off | Open interactive preset wizard |
| `--save-preset / -sp STR` | — | Save wizard preset under this name |
| `--list-presets / -L` | off | List available presets |
| `--diff` | off | Show before/after track comparison |
| `--dry-run` | off | Preview only |

Output goes to `Release/{release}/` by default (configured via `modules.cleanmkv.output_dir_name`).

### `fk metadata [PATH]` (aliases: `meta`, `md`)

Fetch and manage metadata.

| Option | Default | Purpose |
|--------|---------|---------|
| `--set-token` | off | Interactively set the TMDb read access token |
| `--token-value STR` | — | Set token non-interactively |
| `--clear` | off | Remove stored credentials |
| `--doctor` | off | Show credential and provider status |
| `--auto-accept / -y` | off | Accept top candidate automatically |
| `--language STR` | — | Metadata language override (e.g., `fr-FR`) |

Providers: `tmdb` (primary), `tvdb`, `anilist`, `trakt`.

### `fk nfo [PATH]` (alias: `nf`)

Generate NFO files for a release.

| Option | Default | Purpose |
|--------|---------|---------|
| `--template / -t STR` | — | Template name |
| `--locale` | `auto` | NFO output language (`auto`, `en`, `fr`, `es`) |
| `--write / -w` | off | Write NFO immediately (non-interactive) |
| `--with-metadata / -m` | on | Enable metadata enrichment |
| `--metadata-auto-accept / -y` | off | Accept top metadata candidate |
| `--mode` | `global` | Output mode (`global`, `per_file`, `both`) |
| `--list-templates / -L` | off | List available templates |
| `--import-template / -it PATH` | — | Import a `.jinja2` template |
| `--import-name / -in STR` | — | Display name for imported template |
| `--import-scope / -is` | — | `movie`, `single_episode`, `season_pack`, `universal` |
| `--import-logo / -ig PATH` | — | Import a text logo file |
| `--set-logo / -sl STR` | — | Set active logo by internal name |
| `--list-logos / -lg` | off | List available logos |
| `--clear-logo / -cl` | off | Disable active logo |

**NFO output modes:**

| Mode | Behavior |
|------|----------|
| `global` | Single NFO for the entire release |
| `per_file` | One `.nfo` per `.mkv` file |
| `both` | Global + per-file in one run |

### `fk screenshot VIDEOS...` (aliases: `sc`, `screens`)

Extract screenshots from video files using FFmpeg.

| Option | Default | Purpose |
|--------|---------|---------|
| `--count / -n INT` | `6` | Number of screenshots |
| `--width / -w INT` | — | Screenshot width (aspect ratio preserved) |
| `--quality / -q INT` | `2` | JPEG quality (1–31, lower = better) |
| `--format / -f` | `png` | Output format (`png`, `jpg`, `jpeg`) |
| `--output / -o PATH` | — | Output directory |
| `--timestamps / -t STR` | — | Comma-separated timestamps in seconds |
| `--skip-start-percent FLOAT` | `5.0` | Skip N% from start |
| `--skip-end-percent FLOAT` | `5.0` | Skip N% from end |
| `--no-black-detection` | off | Disable black frame detection |
| `--all` | off | Process all MKV files without interaction |
| `--recursive` | off | Scan subdirectories |

### `fk encode run [PATH]` (alias: `enc`)

Encode video files with a preset.

| Option | Default | Purpose |
|--------|---------|---------|
| `--preset / -p STR` | — | Preset name (e.g., `films`, `series`, `f265`) |
| `--preset-file PATH` | — | Custom preset YAML file |
| `--output / -o PATH` | — | Output file path |
| `--output-dir PATH` | — | Output directory for batch encoding |
| `--recursive / -r` | off | Process directories recursively |
| `--dry-run` | off | Show plan without encoding |

```bash
fk encode list                   # list available presets
fk encode check                  # verify FFmpeg installation
fk encode validate --preset-file custom.yaml
```

---

## Workflow commands

### `fk torrent [PATH]` (alias: `tor`)

Create a `.torrent` file from a release folder.

| Option | Default | Purpose |
|--------|---------|---------|
| `--output / -o PATH` | — | Output `.torrent` path |
| `--announce / -a STR` | — | Announce URL |
| `--private / --no-private` | private | Private torrent flag |
| `--piece-length STR` | `auto` | Piece length (`auto`, `512k`, `1m`, ...) |
| `--content` | `auto` | Payload mode (`auto`, `media`, `folder`, `select`) |
| `--dry-run` | off | Preview only |

**Payload modes:**

| Mode | Includes |
|------|---------|
| `auto` | Detected MKV release or season pack |
| `media` | All recognized media files (MKV, MP4, M4V, AVI) |
| `folder` | Everything except existing `.torrent` files |
| `select` | Interactive multi-group picker |

### `fk prez [PATH]`

Build BBCode and/or HTML presentation files for a release.

| Option | Default | Purpose |
|--------|---------|---------|
| `--format / -f` | `both` | Output format (`html`, `bbcode`, `both`) |
| `--preset / -P STR` | `default` | Prez preset name |
| `--html-template STR` | — | HTML template name |
| `--bbcode-template STR` | — | BBCode template name |
| `--with-metadata / --no-metadata` | on | Enrich with TMDb data |
| `--locale STR` | `auto` | Output language |
| `--mediainfo-mode` | `none` | MediaInfo inclusion (`none`, `inline`, `spoiler`) |
| `--select-templates` | off | Interactive template picker |
| `--list-templates` | off | List available templates and presets |
| `--output-dir / -o PATH` | — | Custom output directory |
| `--dry-run` | off | Preview only |

See [Prez module](modules/Prez.md) for template reference.

### `fk pipeline [PATH]` (aliases: `pipe`, `pr`)

Orchestrate the full release workflow. See [Pipeline](Pipeline.md) for the complete reference.

### `fk batch [PATH]` (alias: `bat`)

Process multiple releases in a parent folder.

| Option | Default | Purpose |
|--------|---------|---------|
| `--auto` | off | Unattended mode |
| `--pipeline-preset STR` | — | Pipeline preset for every item |
| `--nfo-locale STR` | — | NFO locale override |
| `--announce STR` | — | Torrent announce URL override |
| `--with-metadata / --no-metadata` | on | Enable/disable metadata |

See [Batch module](modules/Batch.md).

### `fk seedbox` (alias: `seed`)

Seedbox transfer helpers. See [Seedbox module](modules/Seedbox.md).

### `fk watch` (beta)

Monitor a folder and trigger a pipeline preset when new content appears.

### `fk extract [PATH]` (alias: `ext`) — beta

Extract subtitle, audio, and video streams from MKV files.

### `fk upload` (alias: `up`) — beta

Upload releases to tracker APIs. Requires `upload.enabled: true` and `upload.auto_upload: true`.
