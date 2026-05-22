# Changelog

Framekit release notes stay short, public-facing, and limited to user-visible changes.

## [2.0.0] - 2026-05-22

- Public v2 release.
- Rebuilt CLI-first workflow around `fk pipeline`.
- Added release inspection, renaming, MKV cleanup, metadata lookup, NFO generation, presentation generation, torrent creation, validation, screenshots, encoding, batch processing, and diagnostics.
- Added encrypted vault storage for tokens, announce URLs, tracker credentials, and other sensitive values.
- Added package-embedded presets and project/user preset discovery.
- Added automatic template, logo, and banner discovery for presentation workflows.
- Added English, Spanish, and French CLI localization.
- Added structured logs, audit log, rollback ledger, cache management, and doctor checks.
- Added strict linting, type checking, security scanning, coverage gates, fuzz tests, and benchmarks.
- Added GitHub Release build pipeline for wheel, source archive, signed artifacts, and standalone binaries.
- Marked `upload`, `extract`, and `watch` as beta modules.
- Required Python `3.12+`.
- Replaced legacy `settings.json` configuration with `framekit.yaml`.
- Moved bundled presets into package resources.
- Reworked secret handling to prefer encrypted local vault storage.
