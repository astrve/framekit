# Prez Module

The Prez module generates BBCode and HTML presentation files for release threads on trackers and forums.

---

## Basic usage

```bash
fk prez /path/to/release
fk prez /path/to/release --preset detailed --locale fr
fk prez /path/to/release --format bbcode --bbcode-template tracker
```

## Options

| Option | Default | Purpose |
|--------|---------|---------|
| `--format / -f` | `both` | Output: `html`, `bbcode`, or `both` |
| `--preset / -P STR` | `default` | Prez preset name |
| `--html-template STR` | — | HTML template name |
| `--bbcode-template STR` | — | BBCode template name |
| `--with-metadata / --no-metadata` | on | Enrich with TMDb data |
| `--locale STR` | `auto` | Output language |
| `--mediainfo-mode` | `none` | MediaInfo inclusion: `none`, `inline`, `spoiler` |
| `--select-templates` | off | Interactive template picker |
| `--list-templates` | off | List templates and presets |
| `--output-dir / -o PATH` | — | Custom output directory |
| `--dry-run` | off | Preview only |

---

## Presets

| Preset | Format | HTML template | BBCode template | MediaInfo |
|--------|--------|---------------|-----------------|-----------|
| `default` | both | `minimal_dark` | `classic` | none |
| `tracker` | bbcode | — | `tracker` | none |
| `compact` | bbcode | — | `compact` | none |
| `detailed` | both | `magazine_dark` | `detailed` | none |
| `premium` | both | `cinematic_dark` | `cinematic` | none |
| `technical` | both | `minimal_dark` | `technical` | inline |

---

## BBCode templates

| Template | Description |
|----------|-------------|
| `classic` | Standard layout: info, synopsis, metadata, release, technical, audio, subtitles |
| `detailed` | Expanded with full per-track details |
| `compact` | Condensed bullet-point format |
| `technical` | Technical specs focused |
| `cinematic` | Technical summary + synopsis |
| `tracker` | Minimal tracker-upload format |
| `spoiler` | Sections inside `[spoiler=...]` tags |
| `boxed` | Sections inside `[quote]` boxes |

---

## HTML templates

140 templates = 10 designs × 14 color variants.

Designs: `cinematic`, `magazine`, `minimal`, `card`, `timeline`, `glassmorphism`, `brutalist`, `neon_cyberpunk`, `vintage_retro`, `neumorphism`

Colors: `dark`, `forest`, `sunset`, `ocean`, `sepia`, `rainbow`, `midnight`, `cherry`, `lavender`, `mint`, `amber`, `slate`, `coral`, `teal`

Examples: `cinematic_dark`, `magazine_ocean`, `brutalist_amber`, `neon_cyberpunk_rainbow`

---

## Banner images

Banner images are section headers fetched from the online catalog. Select interactively:

```bash
fk prez /release --select-templates
```

The banner catalog is cached for 24 hours. To force a refresh, use `--select-templates` which always fetches the latest index.

---

## Configuration

```yaml
modules:
  prez:
    locale: fr
    format: both
    preset: default
    html_template: minimal_dark
    bbcode_template: classic
    mediainfo_mode: none
    with_metadata: true
```

---

## Template variables

See [Templates — Prez BBCode variables](../Templates.md#template-variables-prezdata) for the full reference.
