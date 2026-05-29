# Quick Start

Complete walkthrough from installation to your first uploaded release.

---

## 1. Verify external tools

```bash
ouro doctor
```

Fix any red items before continuing.

---

## 2. Set your TMDb token

```bash
ouro metadata --set-token
```

Paste your TMDb Read Access Token when prompted. See [Installation](Installation.md) for how to get one.

---

## 3. Inspect a release folder

```bash
ouro inspect /path/to/Movie.2024.1080p.BluRay
```

Shows detected files, track info, and what the pipeline will process.

---

## 4. Run the full pipeline

```bash
ouro pipeline /path/to/Movie.2024.1080p.BluRay
```

The pipeline runs each module in order, prompting at interactive steps:

```
folder → renamer → cleanmkv → metadata → nfo → prez → torrent → upload
```

### Fully automatic (no prompts)

```bash
ouro pipeline /path/to/release --auto --pipeline-preset multi_fr
```

---

## 5. Use a preset

Built-in pipeline presets:

| Preset | Description |
|--------|-------------|
| `single_fr` | Single French-language film |
| `multi_fr` | Multi-audio film with French |
| `series_fr` | TV series, French tracks |

```bash
ouro pipeline /path/to/release --pipeline-preset multi_fr
```

---

## 6. Run individual modules

Every pipeline step is also an independent command:

```bash
ouro renamer /path/to/release          # rename files
ouro cleanmkv /path/to/release         # strip unwanted tracks
ouro metadata /path/to/release         # fetch TMDb metadata
ouro nfo /path/to/release              # generate NFO
ouro prez /path/to/release             # build BBCode/HTML presentation
ouro torrent /path/to/release          # create .torrent
ouro upload /path/to/release           # upload to trackers
```

---

## 7. Dry run

Preview what any command will do without making changes:

```bash
ouro pipeline /path/to/release --dry-run
ouro cleanmkv /path/to/release --dry-run
```

---

## 8. Day-to-day commands

```bash
ouro batch /path/to/releases/          # process multiple releases
ouro watch /path/to/watch/dir          # auto-process new arrivals
ouro validate /path/to/release         # check release quality
ouro screenshot /path/to/release       # extract screenshots
ouro encode /path/to/file.mkv          # re-encode with preset
```

---

## Next steps

- [Configuration](Configuration.md) — all settings
- [Pipeline](Pipeline.md) — deep dive on the pipeline
- [Presets](Presets.md) — create custom presets
- [CLI Reference](CLI-Reference.md) — every option for every command
