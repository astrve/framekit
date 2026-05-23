# Renamer Module

The Renamer module normalizes filenames by detecting release tags, removing unwanted terms, and inserting standardized language codes.

---

## Basic usage

```bash
fk renamer /path/to/release
fk renamer /path/to/release --apply
fk renamer /path/to/release --lang MULTI.VFF --apply
```

## Options

| Option | Default | Purpose |
|--------|---------|---------|
| `--lang STR` | — | Language tag to insert (e.g., `MULTI.VFF`, `FRENCH`) |
| `--apply / -a` | off | Apply renames immediately |
| `--dry-run` | off | Preview only |
| `--force-lang` | off | Override detected language |
| `--remove-term STR` | — | Terms to strip from filenames (repeatable) |
| `--select-terms` | off | Interactive term picker |
| `--profile STR` | — | Named renamer profile |

---

## What it does

1. Scans the release folder for `.mkv` files
2. Detects existing tags: resolution, source, codec, audio, language, HDR, release group
3. Normalizes tag capitalization and ordering
4. Removes configured unwanted terms
5. Inserts or replaces the language code
6. Presents a before/after preview

---

## Interactive term picker

```bash
fk renamer /release --select-terms
```

Shows all detected terms and lets you mark which to remove.

---

## Configuration

```yaml
modules:
  renamer:
    default_language_tag: "MULTI.VFF"
```
