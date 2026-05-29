# Encode

Re-encodes video files using FFmpeg presets. Supports single-file and batch (directory) modes.

---

## Usage

```bash
ouro encode /path/to/file.mkv --preset hevc_crf20
ouro encode /path/to/folder/ --preset hevc_crf20
ouro encode /path/to/folder/ --preset hevc_crf20 --recursive
ouro encode /path/to/file.mkv --preset-file /path/to/preset.yaml
```

---

## Options

| Option | Description |
|--------|-------------|
| `--preset NAME` | Named encoder preset |
| `--preset-file FILE` | Load preset from a YAML file |
| `--output PATH` | Output file (single-file mode) |
| `--output-dir DIR` | Output directory (batch mode) |
| `--recursive` | Recurse subdirectories in batch mode |
| `--dry-run` | Show what would be encoded without running FFmpeg |
| `--json` | Emit encode results as JSON |

---

## Preset format

```yaml
name: hevc_crf20
description: "HEVC CRF 20, 10-bit, AAC stereo"

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

Store presets in `~/.config/ouro/encoder_presets/` or `./encoder_presets/`.

---

## Output naming

Single file:
```
input.mkv → <output-dir>/input_encoded.mkv
```

With `--output`:
```
input.mkv → /specified/path.mkv
```

---

## Configuration

```yaml
encoder:
  default_preset: hevc_crf20
  output_dir_name: encoded
```

---

## External dependency

Requires `ffmpeg` on `PATH`.
