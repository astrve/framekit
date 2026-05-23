# CleanMKV

Removes unwanted audio and subtitle tracks from MKV files. Operates in-place or to a separate output directory.

---

## Usage

```bash
fk cleanmkv /path/to/release [OPTIONS]
fk cleanmkv /path/to/release --preset multi_fr
fk cleanmkv /path/to/release --output-dir /tmp/cleaned --dry-run
```

---

## Options

| Option | Description |
|--------|-------------|
| `--preset NAME` | Apply a named CleanMKV preset |
| `--preset-file FILE` | Load preset from a specific YAML file |
| `--output-dir DIR` | Write cleaned MKVs to a different directory |
| `--in-place` | Overwrite source files |
| `--dry-run` | Show which tracks would be removed |
| `--json` | Emit results as JSON |

---

## How it works

1. Scans all `.mkv` files in the release folder
2. For each file, lists audio and subtitle tracks with language tags
3. Applies the preset rules to determine which tracks to keep
4. Calls `mkvmerge` to write a new MKV with only the selected tracks
5. If `--in-place`, replaces the original file

Tracks without a language tag (`und`) are kept by default.

---

## Interactive wizard

Without `--preset`, CleanMKV shows a track picker:

```
Audio tracks:
  [x] Track 1 — fra (French) — DTS-HD MA 7.1
  [x] Track 2 — eng (English) — AC-3 5.1
  [ ] Track 3 — spa (Spanish) — AC-3 2.0

Subtitle tracks:
  [x] Track 4 — fra (French) — PGS
  [x] Track 5 — fra.forced (French Forced) — PGS
  [ ] Track 6 — eng (English) — SRT
```

---

## Built-in presets

| Name | Audio kept | Subtitles kept |
|------|-----------|---------------|
| `single_fr` | French only | French, forced |
| `multi_fr` | French + English | French, forced |
| `series_fr` | French + English | French, forced |
| `en_only` | English only | English |

---

## Preset format

```yaml
name: my_preset
description: "Keep French and English, French subs"

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

Store presets in `~/.config/framekit/cleanmkv_presets/` or `./cleanmkv_presets/`.

---

## Configuration

```yaml
cleanmkv:
  default_preset: multi_fr   # auto-applied without prompting
  output_dir_name: ""        # empty = in-place
```

---

## External dependency

Requires `mkvmerge` on `PATH` (from [MKVToolNix](https://mkvtoolnix.download/)).
