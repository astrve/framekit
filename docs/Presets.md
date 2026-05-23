# Presets

Framekit has three independent preset systems: Pipeline presets, CleanMKV presets, and Encoder presets.

---

## Pipeline presets

Bundle all per-step options into a named configuration. Stored in `~/.config/framekit/pipeline_presets/` or `./pipeline_presets/`.

### Format

```yaml
# pipeline_presets/my_preset.yaml
name: my_preset
description: "French multi-audio film release"

steps:
  cleanmkv:
    preset: multi_fr
  metadata:
    language: fr-FR
  nfo:
    template: classic
  prez:
    template: classic
    language: fr
    banner_design: textual
  torrent:
    announce_url: "https://tracker.example.com/announce"
    piece_length: 4096
```

### Shipped presets

| Name | Metadata lang | CleanMKV preset | Prez lang |
|------|--------------|-----------------|-----------|
| `single_fr` | `fr-FR` | `single_fr` | `fr` |
| `multi_fr` | `fr-FR` | `multi_fr` | `fr` |
| `series_fr` | `fr-FR` | `series_fr` | `fr` |

### Usage

```bash
fk pipeline /path/to/release --pipeline-preset my_preset
fk pipeline /path/to/release --pipeline-preset my_preset --auto
```

---

## CleanMKV presets

Control which audio and subtitle tracks to keep or remove. Stored in `~/.config/framekit/cleanmkv_presets/` or `./cleanmkv_presets/`.

### Format

```yaml
# cleanmkv_presets/my_clean.yaml
name: my_clean
description: "Keep French and English audio, French subs only"

audio:
  keep_languages: ["fra", "fre", "eng"]
  keep_commentary: false
  keep_descriptive: false

subtitles:
  keep_languages: ["fra", "fre"]
  keep_forced: true
  keep_sdh: false
  remove_all: false
```

### Shipped presets

| Name | Audio kept | Subtitles kept |
|------|-----------|---------------|
| `single_fr` | French only | French only |
| `multi_fr` | French + English | French |
| `series_fr` | French + English | French, forced |
| `en_only` | English only | English |

### Usage

```bash
fk cleanmkv /path/to/release --preset my_clean
```

Or set the default in config:

```yaml
cleanmkv:
  default_preset: multi_fr
```

---

## Encoder presets

Define FFmpeg encoding parameters. Stored in `~/.config/framekit/encoder_presets/` or `./encoder_presets/`.

### Format

```yaml
# encoder_presets/hevc_crf20.yaml
name: hevc_crf20
description: "HEVC CRF 20, AAC stereo audio"

video:
  codec: libx265
  crf: 20
  preset: slow
  profile: main10
  pix_fmt: yuv420p10le

audio:
  codec: aac
  bitrate: 192k
  channels: 2

container: mkv
extra_args: ["-map", "0:v:0", "-map", "0:a:0"]
```

### Usage

```bash
fk encode /path/to/file.mkv --preset hevc_crf20
fk encode /path/to/folder/ --preset hevc_crf20
```

Or set the default:

```yaml
encoder:
  default_preset: hevc_crf20
```
