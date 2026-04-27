# Changelog

All notable changes to Framekit are documented in this file.

Framekit currently follows an internal versioning approach focused on CLI stability, media release preparation, and UX quality.

## [1.1.1] - Hotfix release

### Fixed

- `fk --version` and `framekit --version` no longer create a user `settings.json`
  file.
- Fresh installs and settings resets now consistently use English (`en`) as the
  default UI locale.
- `tests/test_settings_command.py` now expects `general.locale` to reset to
  English, matching `DEFAULT_UI_LOCALE`.
- The pipeline payload workflow test now avoids creating Windows-invalid file
  names while still checking release-name sanitisation separately.

### Changed

- Updated the project version to `1.1.1` in package metadata and runtime version
  reporting.
- Clarified in the README that `mediainfo` and `mkvmerge` are external tools
  required for the full workflow and are not bundled with Framekit.
- Kept the public PyPI distribution name as `framekit-cli`, with `fk` and
  `framekit` as CLI entry points.

### Documentation

- Added clearer external-tool guidance for users installing Framekit from PyPI.
- Cleaned up licensing wording so README, package metadata and `LICENSE` all
  point to GPL-3.0.
- Documented this release as a small corrective hotfix after the first public
  `1.1.0` release.

---

## [1.1.0] - Release v1.1.0

### Added
- A clickable link to the official Framekit repository (`https://github.com/astrve/framekit`) and a credit line for the author in the main CLI banner.
- Added project license metadata and repository information in `pyproject.toml`.
- Added a README introduction with a clickable GitHub link, installation instructions, a quickstart, and a license notice.
- Added project URLs (`Homepage`, `Repository`, `Issues`) and author metadata to `pyproject.toml` to improve PyPI metadata.

### Changed
- Updated the README structure to provide clearer guidance on installation and usage.
- Extended the CLI banner to include repository and author information when displayed at the top‑level.

### Fixed
- Ensured translations are complete for all preview summaries and error messages (pass 4) and that secrets are always redacted and headless behaviour is explicit (pass 3).
- Resolved minor documentation inconsistencies and improved formatting across the README and CHANGELOG.

### Security
- No additional changes in this pass beyond what was delivered in passes 3 and 4.

### Tests
- Added tests in prior passes to verify secret redaction, headless behaviour and translation completeness. No new tests were required in this pass.

### Documentation
- The README now includes installation and quickstart guides, a link to the repository, and license information.

### Finalised
- Version numbers are synchronised to `1.1.0` across project metadata and package code.
- The GitHub link and author credit now appear directly under the CLI subtitle.
- Release-candidate housekeeping is complete; no further breaking changes are planned.

---

## [1.0.14] - Documentation and hygiene

### Added
- Added a concise section in the README describing the recommended workflow, the `Release/{release}` folder structure, torrent content modes (`auto`, `media`, `folder`, `select`) and how to operate Framekit in headless environments.
- Added guidance on storage of local settings and the redaction of secrets when printing settings or diagnostics.

### Changed
- Bumped the internal version number to `1.0.14` to start a three-part stability release.
- Updated `.gitignore` to exclude additional development artefacts such as `uv.lock` and `pyrightconfig.json`.
- Updated the README with information on headless vs interactive operation and important CLI flags (`--preview`, `--apply`, `--details`, `--no-metadata`, `--content`, `--select-content`).
- Started structuring the changelog into planned work across multiple passes. Further changes around security and payload workflow will follow in subsequent releases.

### Fixed
- No functional changes in this pass. This release focuses solely on documentation and project hygiene. Bug fixes and new tests are planned for the next passes.

### Security
- No changes in this pass. Security hardening and secret redaction tests will be implemented in upcoming releases.

### Tests
- No new tests in this pass.

### Documentation
- See the “Added” and “Changed” sections above.

### Planned
- Future passes (2/3 and 3/3) will address secret redaction, headless ambiguity handling, torrent payload resolution, release naming consistency, and more comprehensive tests.
---

## [1.0.13] - Internal development build

### Added
- Introduced a centralised release naming helper to generate safe folder and torrent names from MKV file names. This helper sanitises illegal filesystem characters and unifies naming logic across modules.
- Enhanced the torrent payload resolver to better detect the intended media payload from a folder. Added support for multiple content modes (`auto`, `media`, `folder`, `select-content`).
- Added a `--select-content` flag to the torrent command to enable interactive payload selection.
- Added preliminary support for removing terms in the Renamer via `--remove-term`, including support for multiple terms.
- Added internal tests for the torrent payload resolver and release naming helper.

### Changed
- CleanMKV, Renamer and Torrent summaries were refined with clearer labelling and progress information.
- CleanMKV output folder naming switched to use the new release naming helper to avoid invalid characters on Windows and other filesystems.
- Preview summaries were made less noisy and renamed to “Planned changes” to avoid implying that modifications had already been applied.

### Fixed
- The torrent resolver no longer includes sidecar files (NFO, TXT, Prez HTML/BBCode, screenshots) in auto or media modes.
- The torrent command now properly detects when multiple payloads are present and prompts the user (or errors in headless mode).
- CleanMKV no longer implies that files were modified in preview mode.
- Several inconsistencies in translation keys were corrected.

---

## [1.0.12] - Torrent resolver, CleanMKV/Renamer summaries & release workflow polish

### Added
- Added a safer Torrent payload resolver with multiple content modes:
  - `auto`;
  - `media`;
  - `folder`;
  - `select`.
- Added `--select-content` for interactive Torrent payload selection.
- Added explicit full-folder torrent mode through `--content folder`.
- Added clearer Torrent payload detection for:
  - single MKV files;
  - movie releases;
  - single episode releases;
  - season packs;
  - already structured `Release/{release}` folders.
- Added better handling for ambiguous Torrent sources:
  - multiple media groups;
  - mixed seasons;
  - several releases in the same folder.
- Added `--remove-term` groundwork for Renamer.
- Added more tests around Torrent payload selection and release naming.

### Changed
- `fk tor "folder"` no longer blindly torrents every file in the folder by default.
- Torrent generation now prefers the detected media payload instead of sidecar files.
- Sidecar files are ignored by default in Torrent auto/media mode:
  - `.nfo`;
  - `.txt`;
  - Prez HTML;
  - Prez BBCode;
  - screenshots or unrelated files where applicable.
- Torrent output naming is more consistently based on the detected release name.
- CleanMKV preview summary improved:
  - clearer global summary;
  - more useful audio/subtitle kept-track information;
  - improved distinction between preview and actual apply mode.
- Renamer preview summary improved:
  - clearer global summary;
  - more explicit planned rename examples;
  - less noisy default output.
- `--details` output for CleanMKV and Renamer was introduced or expanded to keep detailed per-item views available without cluttering the default summary.
- Changelog and documentation updated for the new Torrent behavior.

### Fixed
- Torrent could previously include unwanted files when run on a folder containing NFO, Prez, TXT, screenshots, or other sidecars.
- Torrent could target the parent `Release` folder instead of the real media payload folder.
- Torrent naming could still be too dependent on technical or intermediate folder names.
- CleanMKV preview wording incorrectly implied that files had already been modified.
- Renamer preview wording incorrectly implied that files had already been modified.
- Some preview summary labels were not translated consistently.
- Some CleanMKV/Renamer detail views were too compressed or hard to read.

### Known issue
- `--remove-term` was added as a Renamer feature, but in the current tested build it does not correctly affect the final generated name in all cases. This should be treated as a follow-up hotfix item.

---

## [1.0.11.1] - Renamer remove-term hotfix

### Fixed
- Fixed `fk ren --remove-term TERM` so requested tokens are removed from preview and apply outputs.
- Fixed repeated `--remove-term` handling after name normalization.
- Added pipeline propagation with `fk pipe --remove-term TERM`.

---

## [1.0.11] - Torrent payload resolver & summary polish

### Added
- Added torrent content resolution modes:
  - `--content auto`;
  - `--content media`;
  - `--content folder`;
  - `--select-content`.
- Added a release-aware torrent payload resolver.
- Added interactive torrent payload selection by detected media groups.
- Added `--remove-term` to Renamer to remove unwanted tokens before normalization.
- Added tests for torrent payload detection and Renamer remove-term plumbing.

### Changed
- `fk tor` now defaults to a media-aware `auto` mode instead of blindly torrenting every file in the selected folder.
- Torrent creation now ignores sidecar files in media mode:
  - `.nfo`;
  - `.txt`;
  - Prez HTML / BBCode;
  - other non-media files.
- CleanMKV preview summary now shows kept/default tracks as readable labels instead of only counts.
- CleanMKV and Renamer summaries now use “Planned changes” in preview mode instead of misleading “Modified” wording.
- CleanMKV and Renamer `--details` output now uses readable item tables.
- Renamer preview now shows an example planned rename.

### Fixed
- Prevented accidental inclusion of NFO, Prez, notes, and unrelated sidecar files in torrents by default.
- Fixed untranslated CleanMKV preview labels.
- Fixed untranslated Renamer preview labels.
- Improved CleanMKV/Renamer details readability.

---

## [1.0.10] - UX polish, naming & documentation

### Added
- Added `CHANGELOG.md`.
- Added a new updated `README.md`.
- Added `--details` for CleanMKV to display full per-item details.
- Added `--details` for Renamer to display full per-item details.
- Added tests for:
  - release/torrent naming;
  - progress bar scaling;
  - release naming based on source MKV names.

### Changed
- Fixed progress bar unit scaling:
  - a `14.49 GB` file no longer appears as `14.49 TB`.
- Multi-file progress bars now display processed file count:
  - example: `8/20 files`.
- User-facing sizes are now converted more consistently to readable units:
  - `KB`, `MB`, `GB`, `TB`.
- Torrent piece size is displayed in a readable format.
- Removed default pre-checked boxes from selectors:
  - CleanMKV;
  - NFO;
  - Prez;
  - Pipeline;
  - Setup;
  - Torrent.
- CleanMKV now uses a more reliable folder name for `Release/{release}`:
  - based on the MKV filename for movies and single episodes;
  - based on the first MKV filename for season packs;
  - removes the episode suffix `E**` for season packs.
- Torrent naming now follows the same logic as CleanMKV:
  - removes `.mkv` from final names;
  - prevents names such as `Release.mkv.torrent`.
- CleanMKV default output is now more concise and summary-focused.
- Renamer default output is now more concise and summary-focused.

### Fixed
- Incorrect torrent naming based on technical folders instead of the actual release name.
- Excessively verbose default output in CleanMKV and Renamer.
- Raw byte values shown in some user-facing areas.

---

## [1.0.9.2] - Audit hotfix

### Changed
- CleanMKV:
  - removed the misleading progress bar that started during module initialization;
  - progress now reflects actual MKV processing;
  - progress is based on real processed file size.
- Pipeline:
  - improved detection of the `Release/{release}` payload folder after CleanMKV;
  - better alignment of NFO / Prez / Torrent outputs with the `Release` folder.
- Progress bars:
  - now display `MB` / `GB` instead of raw bytes.

### Fixed
- Cases where `Release/{release}` was not correctly propagated to the rest of the pipeline.
- `.torrent` still being based on the wrong folder in some cases.
- Aspect ratio `2.000` is now recognized as `2:1`.
- Prez release date is now formatted as a localized literal date:
  - example: `March 26, 2026`.

---

## [1.0.9] - Audit fixes & UX hardening

### Added
- Initial progress bars for long-running steps:
  - CleanMKV;
  - torrent hashing;
  - Prez when relevant.
- More explicit CLI messages when an option expects a value.
- Prez template selection inside the pipeline.
- Stricter cancellation through `Esc` / user interruption.

### Changed
- CleanMKV:
  - introduced a `Release/{release}` workflow;
  - clearer separation between content folder and output folder.
- Pipeline:
  - improved preview;
  - better path summary;
  - better handling of source, payload, and output folders.
- Torrent:
  - name based on the release rather than the `clean` folder.
- Prez:
  - improved BBCode spacing at the top of the presentation;
  - corrected `h1`, `h2`, `h3` header layout.
- CLI:
  - fixed `fk pipe -h` to avoid duplicated `--with-metadata`.

### Fixed
- Torrent being named `clean.torrent` in some workflows.
- Improved HDR10 and HDR10+ detection.
- Episode completeness being displayed incorrectly for movies.
- Pipeline preview not behaving as a true non-destructive mode.
- Cancellation issues where some modules continued after `Esc`.

---

## [1.0.8] - Inspect, preview & metadata defaults

### Added
- Added the new release inspection command:
  - `fk inspect "folder"`
- Added pipeline preview and explanation modes:
  - `fk pipe --preview`
  - `fk pipe --explain`
- Added `--no-metadata` / `-nm` to disable TMDb metadata for a run.
- Enabled metadata by default for:
  - NFO;
  - Prez;
  - Pipeline.
- Added centralized episode completeness detection.
- Added episode completeness visibility in:
  - Inspect;
  - Pipeline;
  - Prez;
  - NFO.
- Added centralized warnings groundwork.
- Added additional tests for:
  - movie releases;
  - single episode releases;
  - complete season packs;
  - incomplete season packs;
  - releases without metadata.
- Added support for improved headless usage across key commands.

### Changed
- `fk settings` now displays a readable doctor-style overview instead of a raw JSON dump.
- Setup was simplified for Prez configuration:
  - default BBCode template selection;
  - default HTML template selection.
- Prez selector improved:
  - HTML templates grouped by families;
  - template descriptions displayed;
  - cleaner navigation for large template lists.
- Timeline HTML templates improved:
  - corrected poster layout;
  - better handling of long titles;
  - better handling of long release names;
  - improved responsive behavior;
  - improved visual balance between poster and content.
- Timeline template variants improved:
  - `timeline`;
  - `timeline_noir`;
  - `timeline_amber`;
  - `timeline_ocean`.
- Poster handling improved:
  - hidden placeholder when no poster is available;
  - no visible “No poster” / localized placeholder in HTML output.
- Subtitle format display improved:
  - `SRT`;
  - `ASS`;
  - `WebVTT`;
  - `TTML`;
  - `PGS`.
- Pipeline preview made safer and clearer:
  - shows planned modules;
  - shows metadata state;
  - shows selected preset;
  - shows selected output templates;
  - shows expected outputs;
  - avoids destructive operations.
- CLI behavior improved for metadata:
  - metadata is ON by default;
  - `-nm` / `--no-metadata` disables it explicitly.
- Settings defaults updated for metadata behavior:
  - global metadata default;
  - NFO metadata default;
  - Prez metadata default;
  - Pipeline metadata default.
- Main CLI help updated to expose `inspect`.

### Fixed
- Fixed HTML poster being too large or cropped in timeline templates.
- Fixed visible “No poster” / localized poster placeholders in some HTML templates.
- Fixed subtitles being displayed with technical values such as `UTF-8` instead of logical subtitle formats.
- Fixed empty fields remaining visible in some Prez outputs.
- Fixed metadata being inconsistently enabled or disabled across NFO / Prez / Pipeline.
- Fixed episode completeness being unavailable from some output contexts.
- Fixed selectors showing grouped HTML templates without enough context.
- Fixed CLI help and headless mode inconsistencies.
- Fixed Prez timeline layout issues with long metadata and release names.
- Fixed several translation key alignment issues across:
  - English;
  - French;
  - Spanish.

### Notes
- `1.0.8` focused on making Framekit easier to audit and safer to run before generation.
- This version introduced the first stronger inspection/preview layer:
  - `fk inspect` for release understanding;
  - `fk pipe --preview` for planned pipeline output;
  - `fk pipe --explain` for workflow explanation.
- It also established metadata as an enabled-by-default feature while keeping `-nm` / `--no-metadata` available for fully local or headless runs.

---

## [1.0.7] - Pipeline modules, torrent config & cleanup

### Added
- Added module selection at pipeline startup.
- Added Torrent configuration support:
  - saved announce URLs;
  - interactive announce selection;
  - announce URL validation.
- Added Torrent status to `fk doctor`.
- Added `fk prez --list-templates`.
- Added Prez dry-run / preview support.
- Added Prez template descriptions.
- Added localized title suggestion support in Renamer:
  - example: `The Simpsons` → `Les Simpsons`.

### Changed
- Improved `fk settings` with a clearer global overview.
- Expanded setup with configuration for:
  - Prez;
  - Torrent.
- Improved `fk doctor` output.
- Made the pipeline more modular.
- Prez:
  - grouped selector by template families;
  - average video bitrate for season packs;
  - improved H1 / H2 / H3 hierarchy;
  - improved TMDb crew / creator information.
- CleanMKV:
  - simplified displayed information;
  - logical subtitle deduplication for season packs.
- Updated README documentation.

### Fixed
- Fixed “Complete season” badge being displayed when episodes were missing.
- Fixed incorrect title hierarchy in some Prez outputs.
- Fixed Prez selector being too flat for HTML templates.
- Fixed settings still referencing unused external tools.
- Fixed several inconsistencies in Prez templates and localized output.

---

## [1.0.6] - Prez polish

### Added
- Added a new HTML style: `timeline`.
- Added additional visual Prez variants.
- Added additional tests for selectors and templates.

### Changed
- Fixed BBCode season pack header structure:
  - main title;
  - season;
  - episode range;
  - poster.
- Added `(Complete season)` / localized equivalent when applicable.
- Added average video bitrate display for season packs.
- Aligned Prez selector UX with the NFO selector style.
- Removed `[hr]` immediately below the BBCode poster.
- Improved Prez template consistency across:
  - English;
  - French;
  - Spanish.

### Fixed
- Fixed incorrect display order in BBCode season pack headers.
- Fixed duplicate `[hr]` markers when metadata was missing.
- Fixed empty fields leaving visible spacing.
- Fixed rendering inconsistencies across Prez templates.
- Fixed season pack BBCode hierarchy and spacing issues.

---

## [1.0.5] - PrezData, TMDb & data-aware pipeline

### Added
- Added dedicated `PrezData` model.
- Added maintainable Prez rendering helpers:
  - `_dash`;
  - `_join_list`;
  - `_format_runtime`;
  - `_format_average_runtime`;
  - `_format_technical_summary`;
  - `_render_audio_tracks_bbcode`;
  - `_render_subtitle_tracks_bbcode`;
  - `_render_mediainfo_spoiler`.
- Added MediaInfo modes:
  - `--mediainfo-mode none`;
  - `--mediainfo-mode spoiler`;
  - `--mediainfo-mode only`.
- Added `.mediainfo.txt` output for `mediainfo-mode only`.
- Added raw MediaInfo spoiler integration for `mediainfo-mode spoiler`.
- Added template name to Prez output filenames:
  - `Release.tracker.bbcode.txt`;
  - `Release.editorial.html`.
- Added `PipelineContext`:
  - release;
  - metadata context;
  - NFO path;
  - torrent path;
  - Prez outputs.
- Added expanded Prez presets:
  - `default`;
  - `tracker`;
  - `compact`;
  - `detailed`;
  - `technical`;
  - `premium`.
- Added more HTML template organizations.
- Added FlagCDN flags in BBCode audio and subtitle tables.

### Changed
- Prez now relies on shared structured data instead of large pre-rendered strings.
- HTML and BBCode now share `PrezData`.
- Pipeline made data-aware:
  - release scanned once;
  - metadata resolved once;
  - NFO and Prez reuse the same release data and metadata context.
- TMDb behavior:
  - movie links point to the movie page;
  - series / episode releases primarily link to the series page;
  - episode links are kept as secondary links;
  - TMDb links use readable clickable labels instead of numeric IDs.
- Removed IMDb link from Prez because it was not reliable.
- Prez title structure changed:
  - movie: title then year;
  - single episode: series title, episode title, season/episode;
  - season pack: series title, season, episode range.
- Subtitles are logically deduplicated across the whole release.
- Season packs now display average runtime per episode instead of long per-episode runtime lists.
- Poster fallback logic improved:
  - season poster first;
  - series poster fallback;
  - local poster fallback.
- BBCode:
  - improved title hierarchy;
  - title displayed above poster;
  - screenshots removed;
  - `source_name` removed.
- HTML:
  - improved release-field layout;
  - fixed text overflow in release cards;
  - empty fields hidden;
  - screenshots removed.

### Fixed
- Fixed TMDb links being displayed as numeric IDs.
- Fixed unreliable IMDb display by removing it.
- Fixed subtitles being repeated for every episode in season packs.
- Fixed long unreadable `runtime_by_episode` output.
- Fixed incorrect or weak season pack runtime display.
- Fixed poster fallback behavior.
- Fixed internal fields such as `nfo_path` and `torrent_path` appearing in Prez.
- Fixed several BBCode / HTML empty-field issues.

---

## [1.0.4] - Major Prez refactor

### Added
- Major Prez module refactor.
- Added HTML Prez rendering.
- Added BBCode Prez rendering.
- Added multiple Prez templates.
- Added Prez presets.
- Added optional MediaInfo support.
- Added early data-aware pipeline groundwork.
- Added support for multiple visual organizations in Prez outputs.

### Changed
- Prez became more structured and closer to the NFO model.
- Improved separation between:
  - data collection;
  - HTML rendering;
  - BBCode rendering;
  - CLI options.
- Prepared future integration with:
  - TMDb metadata;
  - pipeline reuse;
  - tracker-oriented presets;
  - MediaInfo spoiler output.
- Improved localization support for Prez output.

### Fixed
- Fixed early Prez rendering inconsistencies.
- Consolidated the first generation of Prez templates.
- Improved template organization and output naming foundations.

---

## [1.0.3] - Core stabilization

### Added
- Stabilized the main Framekit modules:
  - Renamer;
  - CleanMKV;
  - NFO;
  - TMDb Metadata;
  - Torrent;
  - Prez;
  - Pipeline;
  - Settings;
  - i18n;
  - HTTP wrapper;
  - Doctor.
- Added or consolidated test coverage for the main modules.
- Added the foundation for a CLI-first / headless-first workflow.
- Added early debug/log stabilization groundwork.

### Changed
- Project aligned with:
  - `pytest`;
  - `ruff`;
  - `pyright`.
- Improved doctor output.
- Improved internal module boundaries.
- Improved settings and localization foundations.

### Fixed
- General stabilization before the major Prez refactor.
- Fixed multiple module-level inconsistencies.
- Cleaned up core commands and workflows.
- Stabilized the project around a working internal baseline.

---

## Historical notes

Entries before `1.0.8` are summarized from Framekit stabilization notes and successive internal patches. Some internal fixes are grouped by topic rather than listed file by file.

The `1.0.3` to `1.0.7` cycle mainly focused on building and stabilizing the core Framekit workflow:

- local media release preparation;
- Renamer;
- CleanMKV;
- NFO;
- TMDb metadata;
- Torrent generation;
- Prez HTML / BBCode;
- pipeline reuse;
- settings and setup;
- doctor diagnostics;
- CLI-first and headless-first usage.