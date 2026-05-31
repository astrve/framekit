# Changelog

## [2.0.0]

### Breaking

- Python 3.12+ required
- `settings.json` → `swirrl.yaml` (schema 14, auto-migrated on first start)
- Secrets moved to encrypted vault by default (`security.enabled: true`)

### Added

**New commands**

- `swirrl init` — create starter config
- `swirrl alias` — custom command aliases
- `swirrl logs` — view structured logs
- `swirrl rollback` — undo tracked file operations
- `swirrl validate` — pre-upload release checks
- `swirrl batch` — process multiple releases
- `swirrl encode` — ffmpeg encoding with presets
- `swirrl screenshot` — capture release screenshots
- `swirrl rename-parent` — rename parent folder from metadata
- `swirrl browse` — browse folders in terminal
- `swirrl sort` — sort release folders
- `swirrl profile` — manage settings profiles
- `swirrl seedbox` — seedbox transfer helpers
- `swirrl examples` — show usage examples
- `swirrl extract` *(beta)* — extract streams
- `swirrl upload` *(beta)* — upload to tracker APIs
- `swirrl watch` *(beta)* — folder monitoring automation

**Pipeline**

- `--auto` — fully unattended run
- `--dry-run` — execute without writing files
- `--pipeline-preset <name>` — load saved YAML preset
- `--create-preset` — interactive preset wizard
- `--skip-renamer`, `--skip-cleanmkv`, `--skip-nfo`, `--skip-torrent`, `--skip-prez`, `--skip-upload`, `--skip-encoder`
- `upload` and `encode` added as pipeline modules (opt-in)

**Infrastructure**

- Encrypted vault (`cryptography` + `keyring`)
- Structured JSONL logging (Loguru)
- Rollback ledger
- Pydantic v2 data models
- Plugin system via `swirrl.modules` entry-points
- Desktop notifications
- httpx + HTTP/2, retry via tenacity
- `py.typed` marker (PEP 561)
- Standalone binaries: Windows, Linux, macOS (PyInstaller)

**Presets & providers**

- Package-embedded presets: CleanMKV, Pipeline, Encoder, Prez
- Metadata providers: TVDb, AniList, Trakt (alongside TMDb)
- Per-provider metadata cache (TTL + size limits)
- Encoder presets: h264↔h265, by content type

### Changed

- `ffmpeg` and `ffprobe` added as required external tools
- `swirrl settings` outputs YAML
- All dependencies use bounded version ranges
- ruff target: `py312`

### Security

- `cryptography>=46.0.7` — CVE-2026-26007, CVE-2026-34073, CVE-2026-39892
- All subprocess calls via `swirrl.core.subprocess_safe` wrappers
- Bandit + pip-audit in CI

---

## [1.1.2]

### Added

- Renamer term picker (`--select-terms`)
- NFO output mode: `global` / `per_file` / `both` (`--mode`)
- `Encode Settings` field in detailed NFO templates (EN/FR/ES)
- Single-file support for `swirrl md` and `swirrl nfo`
- CleanMKV: pre-checked track selector
- CleanMKV: explicit "no default" track flag (`audio_default_explicit`, `subtitle_default_explicit`)
- Translation keys: `cleanmkv.error.invalid_file_type`, `cleanmkv.warning.different_bitrates`

### Changed

- CleanMKV: audio dedup by language + codec + channels only (bitrate and title ignored)

### Fixed

- Single MKV path to `swirrl md` / `swirrl nfo` raised "Folder not found"
- `swirrl doctor` launched MediaInfo GUI on macOS `.app` installs
- CleanMKV ignored explicit "no default subtitle" choice

---

## [1.1.1]

### Fixed

- `swirrl --version` created `settings.json` on first run
- Fresh install defaulted to wrong locale (now always `en`)

### Changed

- Version `1.1.1`

---

## [1.1.0]

### Added

- GitHub link and author credit in CLI banner
- README: installation, quickstart, license

### Changed

- Version `1.1.0`

---

## [1.0.14]

### Changed

- README: headless vs interactive, `Release/{release}` workflow, torrent content modes, flags reference
- Version `1.0.14`

---

## [1.0.13]

### Added

- Release naming helper (sanitizes filesystem-illegal characters)
- Torrent payload resolver: `auto`, `media`, `folder`, `select-content` modes
- `--remove-term` groundwork for Renamer

### Fixed

- Torrent included sidecar files in auto/media mode
- CleanMKV preview implied files were already modified

---

## [1.0.12]

### Added

- Torrent content modes: `auto`, `media`, `folder`, `select`
- `--select-content` for interactive payload selection

### Changed

- `swirrl tor` defaults to media-aware `auto` mode
- Sidecars excluded from torrent by default (NFO, Prez, TXT, screenshots)
- CleanMKV and Renamer `--details` output

### Fixed

- Torrent included sidecars, targeted wrong folder, used wrong name
- CleanMKV and Renamer preview wording implied changes were applied

---

## [1.0.11.1]

### Fixed

- `--remove-term` not applied to final rename output
- Pipeline propagation of `--remove-term`

---

## [1.0.11]

### Added

- Torrent content modes: `auto`, `media`, `folder`, `select-content`
- `--remove-term` for Renamer

### Changed

- `swirrl tor` defaults to `auto` mode
- CleanMKV and Renamer summaries: "Planned changes" in preview mode

### Fixed

- Sidecars included in torrents by default
- Untranslated CleanMKV and Renamer labels

---

## [1.0.10]

### Added

- `CHANGELOG.md` and updated `README.md`
- `--details` for CleanMKV and Renamer

### Changed

- Progress bar units fixed (GB not TB)
- CleanMKV and Renamer summaries more concise
- CleanMKV and Torrent naming from MKV filename

### Fixed

- Incorrect torrent naming from technical folders
- Raw byte values in UI

---

## [1.0.9.2]

### Fixed

- `Release/{release}` not propagated through pipeline
- Progress bars showed raw bytes
- Prez release date format

---

## [1.0.9]

### Added

- Progress bars: CleanMKV, torrent hashing, Prez

### Changed

- CleanMKV: `Release/{release}` workflow
- Torrent: name from release, not `clean` folder
- Prez: BBCode spacing and header layout

### Fixed

- Torrent named `clean.torrent`
- HDR10/HDR10+ detection
- Pipeline preview not truly non-destructive

---

## [1.0.8]

### Added

- `swirrl inspect`
- `swirrl pipe --preview` and `--explain`
- `--no-metadata` / `-nm`
- Episode completeness detection

### Changed

- `swirrl settings`: doctor-style overview instead of raw JSON
- Metadata enabled by default for NFO, Prez, Pipeline
- Prez: template selector, poster fallback, subtitle format labels
- Timeline HTML templates

### Fixed

- NFO/Prez metadata consistency
- Prez timeline layout
- Translation key alignment

---

## [1.0.7]

### Added

- Pipeline module selection
- Torrent: saved announce URLs, interactive selection
- `swirrl prez --list-templates`, dry-run, template descriptions
- Renamer: localized title suggestions

### Changed

- `swirrl settings` overview
- `swirrl doctor` output
- Prez: grouped selector, average bitrate for season packs

### Fixed

- "Complete season" badge on incomplete packs
- Prez selector too flat

---

## [1.0.6]

### Added

- HTML style `timeline`
- Visual Prez variants

### Fixed

- BBCode season pack header structure
- Duplicate `[hr]` markers
- Empty field spacing

---

## [1.0.5]

### Added

- `PrezData` model
- MediaInfo modes: `none`, `spoiler`, `only`
- `PipelineContext`
- Prez presets: `default`, `tracker`, `compact`, `detailed`, `technical`, `premium`
- FlagCDN flags in BBCode tables

### Changed

- Prez and pipeline data-aware (shared release/metadata context)
- TMDb links readable, IMDb removed
- Subtitles deduplicated across season packs
- Poster fallback: season → series → local

### Fixed

- TMDb links shown as numeric IDs
- Per-episode subtitle duplication in season packs
- Poster fallback behavior

---

## [1.0.4]

### Added

- HTML and BBCode Prez rendering
- Prez templates and presets
- MediaInfo support in Prez

---

## [1.0.3]

### Added

- Core modules: Renamer, CleanMKV, NFO, Metadata, Torrent, Prez, Pipeline, Settings, i18n, Doctor
- CLI-first / headless-first foundation
- pytest, ruff, pyright alignment
