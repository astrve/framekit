# Quick Start

Complete walkthrough from installation to your first uploaded release.

---

## 1. Verify external tools

```bash
fk doctor
```

Fix any red items before continuing.

---

## 2. Set your TMDb token

```bash
fk metadata --set-token
```

Paste your TMDb Read Access Token when prompted. See [Installation](Installation.md) for how to get one.

---

## 3. Inspect a release folder

```bash
fk inspect /path/to/Movie.2024.1080p.BluRay
```

Shows detected files, track info, and what the pipeline will process.

---

## 4. Run the full pipeline

```bash
fk pipeline /path/to/Movie.2024.1080p.BluRay
```

The pipeline runs each module in order, prompting at interactive steps:

```
folder → renamer → cleanmkv → metadata → nfo → prez → torrent → upload
```

### Fully automatic (no prompts)

```bash
fk pipeline /path/to/release --auto --pipeline-preset multi_fr
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
fk pipeline /path/to/release --pipeline-preset multi_fr
```

---

## 6. Run individual modules

Every pipeline step is also an independent command:

```bash
fk renamer /path/to/release          # rename files
fk cleanmkv /path/to/release         # strip unwanted tracks
fk metadata /path/to/release         # fetch TMDb metadata
fk nfo /path/to/release              # generate NFO
fk prez /path/to/release             # build BBCode/HTML presentation
fk torrent /path/to/release          # create .torrent
fk upload /path/to/release           # upload to trackers
```

---

## 7. Dry run

Preview what any command will do without making changes:

```bash
fk pipeline /path/to/release --dry-run
fk cleanmkv /path/to/release --dry-run
```

---

## 8. Day-to-day commands

```bash
fk batch /path/to/releases/          # process multiple releases
fk watch /path/to/watch/dir          # auto-process new arrivals
fk validate /path/to/release         # check release quality
fk screenshot /path/to/release       # extract screenshots
fk encode /path/to/file.mkv          # re-encode with preset
```

---

## Next steps

- [Configuration](Configuration.md) — all settings
- [Pipeline](Pipeline.md) — deep dive on the pipeline
- [Presets](Presets.md) — create custom presets
- [CLI Reference](CLI-Reference.md) — every option for every command
