# Validate

Checks a release against quality rules before uploading. Reports errors and warnings by category.

---

## Usage

```bash
ouro validate /path/to/release [OPTIONS]
ouro validate /path/to/release --ruleset strict
ouro validate /path/to/release --ruleset anime --require-subs
```

---

## Options

| Option | Description |
|--------|-------------|
| `--ruleset NAME` | Ruleset to apply (default: `default`) |
| `--strict` | Apply strict rules |
| `--require-nfo / --no-require-nfo` | Override NFO requirement |
| `--require-subs / --no-require-subs` | Override subtitle requirement |
| `--json` | Emit results as JSON |

---

## Built-in rulesets

| Ruleset | NFO | Subs | Min resolution | Containers |
|---------|-----|------|----------------|-----------|
| `default` | No | No | None | Any |
| `strict` | Yes | No | 1280px | `.mkv` only |
| `anime` | No | Yes | 720px | `.mkv` only |
| `music-video` | No | No | 720px | `.mkv`, `.mp4` |

---

## Checks performed

| Category | What is checked |
|----------|----------------|
| Video | Codec, resolution, bitrate |
| Audio | Codec, channel count |
| Container | File extension |
| NFO | Presence and size |
| Subtitles | Presence, language tags |
| Files | File size limits, file count |
| Naming | Folder and file name structure |

---

## Output

```
Severity  Category  Issue                            Suggestion
────────────────────────────────────────────────────────────────
ERROR     Video     No video track found             Check MKV integrity
WARNING   NFO       NFO file missing                 Run: ouro nfo /path/to/release
INFO      Audio     No language tag on track 2       Edit with mkvpropedit
```

Exit codes:
- `0` — passed (no errors)
- `1` — failed (one or more errors)

---

## Integrating in CI

```bash
ouro validate /path/to/release --ruleset strict --json
# Check exit code; parse JSON for structured results
```

---

## In the pipeline

Validate is not a default pipeline step. Run it explicitly before or after the pipeline:

```bash
ouro validate /path/to/release && ouro pipeline /path/to/release --auto
```
