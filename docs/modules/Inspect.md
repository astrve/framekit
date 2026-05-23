# Inspect

Read-only release scanner. Reports detected files, MKV track details, and pipeline readiness without modifying anything.

---

## Usage

```bash
fk inspect /path/to/release
fk inspect /path/to/release --json
```

---

## Options

| Option | Description |
|--------|-------------|
| `--json` | Emit structured JSON output |

---

## What it reports

- **Release type** — movie, TV episode, episode pack, or unknown
- **MKV files** — list of all `.mkv` files with size and track counts
- **Video tracks** — codec, resolution, color space, HDR metadata
- **Audio tracks** — language, codec, channels, bitrate
- **Subtitle tracks** — language, format, forced/SDH flags
- **Existing outputs** — whether NFO, `.torrent`, BBCode/HTML files already exist
- **External tools** — which required tools are available on `PATH`

---

## Example output

```
Release: Movie.2024.1080p.BluRay.x265-GROUP
Type   : Movie
Files  : 1 MKV (28.4 GB)

Video
  Track 1 — HEVC, 1920×1080, YUV 4:2:0 10-bit

Audio
  Track 1 — fra (French)  — DTS-HD MA 7.1
  Track 2 — eng (English) — AC-3 5.1

Subtitles
  Track 3 — fra (French)  — PGS
  Track 4 — fra (Forced)  — PGS

Existing outputs
  NFO     : not found
  Torrent : not found

External tools
  mkvmerge   : ✓ found
  mediainfo  : ✓ found
  ffmpeg     : ✓ found
```

---

## In the pipeline

`inspect` is the first step in the pipeline. It populates `PipelineContext.release` — the `Release` object used by all subsequent steps.
