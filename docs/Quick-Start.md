# Quick Start

This guide walks through the first-run experience from install to a complete pipeline run.

---

## 1. Verify install

```bash
fk doctor
```

All items should show **OK**. Fix any **Warning** or **Error** before continuing.

---

## 2. Run setup

```bash
fk setup
```

The setup wizard configures:

- UI language (English, French, Spanish)
- TMDb read access token (for metadata enrichment)
- Default folders per module
- NFO template and logo preferences
- Vault and security settings

You can re-run `fk setup` at any time to update any setting.

---

## 3. Inspect a release

```bash
fk inspect /path/to/MyRelease.2024.BluRay.1080p
```

Prints a summary: detected title, media kind (movie / series / single episode), file count, total size, resolution, codec, audio languages, episode completeness.

---

## 4. Run the pipeline

The `pipeline` command is the primary way to process a release:

```bash
fk pipeline /path/to/release
```

Framekit will interactively:

1. Ask which modules to enable (renamer, cleanmkv, nfo, torrent, prez, ...)
2. Ask for a torrent announce URL if none is configured
3. Ask whether to enrich with TMDb metadata
4. Execute each enabled module in order
5. Write outputs to `Release/{release}/` inside the folder

To run fully automatically with a saved preset:

```bash
fk pipeline /path/to/release --auto --pipeline-preset multi_fr
```

---

## 5. Run modules individually

Each module can be run standalone:

```bash
fk renamer /path/to/release          # rename files
fk cleanmkv /path/to/release         # clean MKV tracks interactively
fk nfo /path/to/release              # generate NFO
fk prez /path/to/release             # build BBCode + HTML presentation
fk torrent /path/to/release          # create .torrent file
fk validate /path/to/release         # validate release structure
```

---

## 6. Batch mode

Process multiple releases at once:

```bash
fk batch /path/to/parent/folder
```

Framekit scans subfolders, builds a queue, and shows an interactive dashboard. Use `--auto` for fully unattended batch processing.

---

## 7. Pipeline presets

Save a preset once, reuse everywhere:

```bash
fk pipeline --create-preset              # interactive preset wizard
fk pipeline /release --pipeline-preset multi_fr
fk batch /parent --pipeline-preset anime_multi_fr
```

Shipped presets: `multi_fr`, `multi_en`, `multi_es`, `vf_only`, `ve_only`, `en_only`, `anime_multi_fr`, `anime_vo_multi`, and more.

See [Presets](Presets.md) for the full list and format reference.

---

## 8. Useful day-to-day commands

```bash
fk settings                # view all settings (sensitive values redacted)
fk alias list              # list all command aliases
fk logs                    # inspect JSONL operation logs
fk rollback                # undo the last pipeline run
fk language fr             # switch UI to French
fk about                   # version, copyright, and license info
fk doctor                  # full environment health check
```
