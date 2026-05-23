# Pipeline

The `pipeline` command orchestrates the full release workflow, running multiple modules in sequence with shared context.

```bash
fk pipeline [PATH] [OPTIONS]
```

---

## Module execution order

```
renamer → cleanmkv → nfo → torrent → prez → upload → encoder
```

- `encoder` is opt-in — excluded from the default set
- `upload` requires both `upload.enabled: true` and `upload.auto_upload: true`

Default module set: `renamer`, `cleanmkv`, `nfo`, `torrent`, `prez`

---

## All options

| Option | Purpose |
|--------|---------|
| `PATH` | Release folder (optional, prompts if omitted) |
| `-l / --nfo-locale STR` | NFO output locale |
| `-a / --announce STR` | Torrent announce URL |
| `--skip-renamer` / `--skip-cleanmkv` / `--skip-nfo` / `--skip-torrent` / `--skip-prez` / `--skip-upload` / `--skip-encoder` | Skip specific modules |
| `--ren` / `--cmk` / `--nfo` / `--tor` / `--prez` / `--up` / `--enc` | Opt-in only those modules |
| `--all` | Run default module set without interactive prompt |
| `-P / --preset STR` | Prez preset name |
| `-p / --preview` | Show preview and exit |
| `-d / --dry-run` | Execute without writing output files |
| `-e / --explain` | Show module explanations and exit |
| `--with-metadata / --no-metadata` | Enable/disable metadata fetching |
| `--remove-term STR` | Terms to remove from filenames (repeatable) |
| `-S / --select-modules` | Interactively select modules |
| `--select-templates` | Interactively select templates |
| `--select-terms` | Interactively select terms to remove |
| `--nfo-mode` | NFO output mode (`global`, `per_file`, `both`) |
| `--pipeline-preset STR` | Pipeline preset name |
| `--auto` | Fully autonomous mode |
| `--batch` | Switch to batch mode |
| `--batch-auto` | Auto-scan parent folder in batch mode |
| `--create-preset` | Launch interactive preset creation wizard |

---

## Execution flow

When you run `fk pipeline`:

1. Load settings via `SettingsStore`; resolve `PathResolver`
2. Validate the path argument; confirm folder exists
3. Apply `--skip-*` flags to filter the module list
4. Load and apply pipeline preset if `--pipeline-preset` provided
5. Resolve metadata enable/disable state
6. Resolve module selection — configured defaults → interactive selector (if TTY and not auto) → preset override
7. If TMDb token missing and metadata needed and interactive: prompt to add token, skip, or disable reminder
8. Determine `work_folder`: checks for `Release/{release}/`, CleanMKV output dir, `Release/` child, legacy `clean/`, then falls back to root
9. Handle preview / confirmation (interactive or headless)
10. Resolve terms to remove
11. Execute each enabled step in order via `PipelineContext`

---

## Pipeline context

Framekit shares data between steps via `PipelineContext`:

| Field | Type | Contains |
|-------|------|---------|
| `release` | `ReleaseNfoData` | Cached release scan (shared across NFO / Prez / Upload) |
| `metadata_context` | `dict` | Cached metadata fetch result |
| `nfo_path` | `Path` | Written NFO path (used by upload step) |
| `torrent_path` | `Path` | Written `.torrent` path |
| `prez_outputs` | `tuple[Path, ...]` | Written presentation file paths |
| `dry_run` | `bool` | Dry-run flag |

---

## Step details

### Renamer step

Calls `run_renamer_command` with `apply_changes=True`. Normalizes filenames before any other processing.

### CleanMKV step

Calls `run_cleanmkv_command`. In auto mode, applies immediately. In interactive mode, shows a confirmation before remuxing.

### NFO step

Uses `NfoService`. Media-kind-aware:

| Media kind | Behavior |
|------------|---------|
| movie / single_episode | Sidecar NFO + global NFO |
| season_pack / special_pack | Per-file NFO + global NFO |

### Torrent step

Derives the torrent name from `torrent_name_from_payload()`. Output goes to the configured output folder or `work_folder.parent`.

### Prez step

Uses `PrezService.build()`. Resolves banner URLs from the banner design index and template choices from settings or interactive picker.

### Encoder step

Opt-in. Loads encoder preset from `modules.encoder.preset`. Encodes in place (replaces originals). Use with care.

### Upload step

Requires `upload.enabled + auto_upload`. Parses the release name with `ReleaseParser`, reads the NFO with `NFOParser`, uploads screenshots to the configured image host, builds a BBCode description, then calls `UploadService.upload_to_multiple()`.

---

## Pipeline presets

Presets save your module selection, per-module options, and prez template choices so you can reuse them in one flag:

```bash
fk pipeline --create-preset                          # wizard
fk pipeline /release --pipeline-preset multi_fr
fk pipeline /release --auto --pipeline-preset vf_only
```

See [Presets](Presets.md) for the full format and shipped preset list.

---

## Auto mode

```bash
fk pipeline /release --auto
```

Disables all interactive prompts. Reads module list and options from settings / preset. Returns non-zero exit code on any module failure.

---

## Dry run

```bash
fk pipeline /release --dry-run
```

Executes all steps but writes no output files. Use to validate a run plan.

---

## Rollback

```bash
fk rollback
```

Every pipeline run is tracked in a run ledger. `rollback` lists runs and lets you revert all file operations from a selected run.
