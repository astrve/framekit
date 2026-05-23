# Presets

Framekit has three preset systems: **Pipeline presets**, **CleanMKV presets**, and **Encoder presets**. Each is a YAML or JSON file that encodes a reusable configuration.

---

## Discovery order

For each module, presets are discovered in this priority:

1. Project-level `Presets/<Module>/` (e.g., `./Presets/Pipeline/`)
2. User config dir `~/.config/framekit/Presets/<Module>/`
3. Bundled package presets (shipped with Framekit)

---

## Pipeline presets

### Format

```yaml
name: Multi FR                        # display name (required)
description: French multi audio + metadata

modules: [renamer, cleanmkv, nfo, torrent, prez]

renamer:
  auto_detect: true
  rules: []

cleanmkv:
  preset: multi_fr
  apply_changes: true
  output_dir_name: "Release/{release}"

nfo:
  template: default
  locale: fr
  auto_metadata: true
  mode: global

torrent:
  private: true
  piece_length: auto

prez:
  preset: default
  format: both
  html_template: minimal_dark
  bbcode_template: classic
  banner_design: textual
  mediainfo_mode: none
```

### Creating a preset

```bash
fk pipeline --create-preset          # interactive wizard
```

Saves to `Presets/Pipeline/{slug}.yaml`.

### Using a preset

```bash
fk pipeline /release --pipeline-preset multi_fr
fk batch /parent --pipeline-preset anime_multi_fr
```

### Shipped presets

| File | Description |
|------|-------------|
| `multi_fr.yaml` | Multi audio, French as default |
| `multi_en.yaml` | Multi audio, English as default |
| `multi_es.yaml` | Multi audio, Spanish as default |
| `multi_en_compact.yaml` | Multi audio EN, compact BBCode prez |
| `vf_only.yaml` | French audio only (VF) |
| `ve_only.yaml` | English audio only (VE) |
| `en_only.yaml` | English audio and subtitles only |
| `anime_multi_fr.yaml` | Anime, multi audio, French preferred |
| `anime_multi_en.yaml` | Anime, multi audio, English preferred |
| `anime_multi_es.yaml` | Anime, multi audio, Spanish preferred |
| `anime_vo_multi.yaml` | Anime, original Japanese voice with multi subs |
| `multi_jp.yaml` | Japanese audio, multi subtitles |
| `example.yaml` | Annotated reference with all available fields |

---

## CleanMKV presets

### Format

```yaml
name: Multi FR
keep_audio_filters:
  - "french"
  - "english:us"
default_audio_filter: "french"
keep_subtitle_filters:
  - "french"
  - "english"
keep_subtitle_variants:
  - full
  - forced
  - sdh
default_subtitle_filter: "french"
default_subtitle_variant: forced
```

### Key fields

| Field | Type | Purpose |
|-------|------|---------|
| `keep_audio_filters` | list | Language filters for audio tracks |
| `default_audio_filter` | string | Which audio filter is set as default |
| `keep_subtitle_filters` | list | Language filters for subtitles |
| `keep_subtitle_variants` | list | Subtitle types to keep: `forced`, `full`, `sdh` |
| `default_subtitle_filter` | string | Which subtitle is set as default |
| `default_subtitle_variant` | string | Variant to prefer as default |
| `audio_default_explicit` | bool | `true` = no default is deliberate, not a fallback |

### Using CleanMKV presets

```bash
fk cleanmkv /release --preset multi_fr        # built-in preset
fk cleanmkv /release --preset-file my.json    # custom JSON file
fk cleanmkv /release --external-preset saved  # user-saved preset
fk cleanmkv /release --wizard                 # build interactively
fk cleanmkv /release --list-presets           # show available presets
```

### Shipped CleanMKV presets

| File | Description |
|------|-------------|
| `multi_fr.yaml` | Multi audio, French default |
| `multi_en.yaml` | Multi audio, English default |
| `multi_es.yaml` | Multi audio, Spanish default |
| `vf_only.yaml` | French audio only |
| `ve_only.yaml` | English audio only |
| `en_only.yaml` | English audio + English subtitles only |
| `multi_jp.yaml` | Japanese audio with multi subtitles |
| `anime_multi_fr.yaml` | Anime, multi audio, French preferred |
| `anime_multi_en.yaml` | Anime, multi audio, English preferred |
| `anime_multi_es.yaml` | Anime, multi audio, Spanish preferred |
| `anime_vo_multi.yaml` | Anime original voice with multi subs |

---

## Encoder presets

### Format

```yaml
name: Films (H.265)
description: High-quality movie encode, CRF 19
aliases: [f265, film265, movie265]
source_codec: h264
target_codec: h265
encoder: libx265
video:
  crf: 19
  preset: slow
  profile: main10
audio:
  copy: true
subtitles:
  copy: true
metadata:
  preserve: true
chapters:
  preserve: true
```

### Using encoder presets

```bash
fk encode run /release --preset films
fk encode run /release --preset f265        # alias
fk encode list                              # list all presets
```

### Shipped H.264 → H.265 presets

| Preset name | Aliases | Description |
|-------------|---------|-------------|
| `films` | `f265`, `film265`, `movie265` | CRF 19, slow, main10 |
| `series` | `s265`, `serie265`, `tv265` | CRF 21, medium, main10 |
| `animes_japonais` | `a265`, `anime265`, `jp265` | CRF 19, veryslow, tune animation |
| `documentaires` | `d265`, `doc265`, `docu265` | CRF 22, medium, main |
| `series_animees` | `sa265`, `anim265`, `cartoon265` | CRF 20, slow, tune animation |

### Shipped H.265 → H.264 presets

| Preset name | Aliases | Description |
|-------------|---------|-------------|
| `films` | `f264`, `film264`, `movie264` | CRF 19, slow, high |
| `series` | `s264`, `serie264`, `tv264` | CRF 21, medium, high |
| `animes_japonais` | `a264`, `anime264`, `jp264` | CRF 19, veryslow, tune animation |
| `documentaires` | `d264`, `doc264`, `docu264` | CRF 22, medium, main |
| `series_animees` | `sa264`, `anim264`, `cartoon264` | CRF 20, slow, tune animation |

See `Presets/Encoder/ALIASES.md` in the repository for the full alias list.
