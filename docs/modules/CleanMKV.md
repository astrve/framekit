# CleanMKV Module

CleanMKV remuxes MKV files to keep only the desired audio and subtitle tracks, removing unwanted languages and track variants.

---

## Basic usage

```bash
fk cleanmkv /path/to/release
fk cleanmkv /path/to/release --preset multi_fr --apply
fk cleanmkv /path/to/release --wizard
```

## Options

| Option | Default | Purpose |
|--------|---------|---------|
| `--apply / -a` | off | Apply changes without confirmation |
| `--preset / -p STR` | `multi` | Built-in preset name |
| `--preset-file / -pf PATH` | — | Load preset from JSON file |
| `--external-preset / -ep STR` | — | Load saved external preset by name |
| `--wizard / -w` | off | Open interactive preset wizard |
| `--save-preset / -sp STR` | — | Save wizard preset under this name |
| `--list-presets / -L` | off | List available presets |
| `--dry-run` | off | Preview only |
| `--diff` | off | Show before/after track comparison |
| `--details` | off | Show per-file details |

Preset resolution priority: `--wizard` → `--preset-file` → `--external-preset` → `--preset` → settings default

---

## Output directory

By default, remuxed files are written to `Release/{release}/` inside the release folder. Configure via:

```yaml
modules:
  cleanmkv:
    output_dir_name: "Release/{release}"   # {release} = derived release name
```

---

## Interactive wizard

```bash
fk cleanmkv /release --wizard
fk cleanmkv /release --wizard --save-preset "my_preset"
```

The wizard lets you pick audio and subtitle languages, set defaults, and choose subtitle variants (forced, full, SDH). The result can be saved as a named preset.

---

## Built-in presets

| Preset | Description |
|--------|-------------|
| `multi` | Keep all detected languages |
| `keep_all` | Keep all tracks without filtering |
| `multi_fr` | Multi audio, French as default |
| `multi_en` | Multi audio, English as default |
| `multi_es` | Multi audio, Spanish as default |
| `vf_only` | French audio only |
| `ve_only` | English audio only |
| `en_only` | English audio + English subtitles only |

See [Presets — CleanMKV](../Presets.md#cleanmkv-presets) for the full format and shipped preset list.

---

## Preset format (JSON / YAML)

```yaml
name: Multi FR
keep_audio_filters:
  - "french"
  - "english:us"
default_audio_filter: "french"
keep_subtitle_filters:
  - "french"
  - "english"
keep_subtitle_variants: [full, forced, sdh]
default_subtitle_filter: "french"
default_subtitle_variant: forced
```

---

## Configuration

```yaml
modules:
  cleanmkv:
    default_preset: multi_fr
    output_dir_name: "Release/{release}"
    copy_unchanged_files: true
```
