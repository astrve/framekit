# Architecture

This page describes the internal structure of Framekit for contributors and advanced users.

---

## Repository layout

```
framekit/
├── src/framekit/
│   ├── __main__.py             # Entry point
│   ├── commands/               # CLI command implementations
│   │   ├── main.py             # Root CLI group, alias registration
│   │   ├── pipeline.py         # Pipeline command + PipelineContext
│   │   ├── pipeline_steps.py   # Per-module step functions
│   │   ├── pipeline_orchestrator.py
│   │   ├── pipeline_presets.py
│   │   ├── pipeline_preview.py
│   │   └── ...                 # One file per command group
│   ├── core/                   # Shared infrastructure
│   │   ├── settings/           # Config store, schema, migration
│   │   ├── security/           # Encrypted vault, keyring
│   │   ├── models/             # Core data transfer objects
│   │   ├── paths.py            # Path resolution
│   │   ├── i18n.py             # tr() translation function
│   │   ├── aliases.py          # Alias resolution
│   │   ├── cache/              # Multi-backend cache
│   │   ├── runs/               # Run ledger + rollback
│   │   ├── subprocess_safe.py  # run_safe() / popen_safe()
│   │   └── ...
│   ├── modules/                # Business logic
│   │   ├── batch/
│   │   ├── cleanmkv/
│   │   ├── encoder/
│   │   ├── extract/
│   │   ├── metadata/
│   │   ├── nfo/
│   │   ├── prez/
│   │   ├── renamer/
│   │   ├── screenshot/
│   │   ├── setup/
│   │   ├── torrent/
│   │   ├── upload/
│   │   ├── validate/
│   │   └── watch/
│   ├── templates/              # Jinja2 templates
│   │   ├── nfo/                # NFO templates + macros
│   │   └── prez/
│   │       ├── bbcode/         # BBCode templates
│   │       └── html/           # HTML templates (generated)
│   ├── locales/                # Translation catalogs
│   │   ├── en.json
│   │   ├── fr.json
│   │   └── es.json
│   └── ui/                     # Terminal UI components
├── tests/                      # pytest test suite
├── Presets/                    # Shipped presets
│   ├── Pipeline/
│   ├── CleanMKV/
│   ├── Encoder/
│   └── Prez/
├── docs/                       # MkDocs wiki source
└── .github/workflows/          # CI/CD pipelines
```

---

## Core layer

### Settings store (`core/settings/`)

- **`store.py`** — `SettingsStore.load()`: reads YAML, runs migration, returns dict. `save()`: writes with `ruamel.yaml` (preserves comments).
- **`schema.py`** — `DEFAULT_SETTINGS` dict (schema v14), `SECRET_KEY_PARTS` list.
- **`normalize.py`** — Input sanitization functions.
- **`migration.py`** — Schema version upgrade logic.
- **`high_level.py`** — `Settings` class: `get_tmdb_token()`, `set_tmdb_token()`, `get_vault()`.

### Path resolution (`core/paths.py`)

- `get_settings_path()` — Active config file path.
- `get_config_dir()` — User config directory (overridable via `FRAMEKIT_CONFIG_DIR`).
- `get_cache_dir()` — User cache directory (overridable via `FRAMEKIT_CACHE_DIR`).
- `get_vault_path()` — Encrypted vault file path.
- `PathResolver` — Resolves `default_folder` per module, falls back to CWD.

### i18n (`core/i18n.py`)

- `tr(key, default, **kwargs)` — Returns translated string from JSON catalog; falls back to `default`.
- `get_locale()` — Reads from `FRAMEKIT_LOCALE`, `LC_ALL`, `LC_MESSAGES`, `LANG`.
- `set_locale(code)` — Switches locale at runtime.
- `temporary_locale(code)` — Context manager for locale override.

### Security (`core/security/`)

- **`vault.py`** — `SecureVault`: AES-GCM encrypted JSON; `store()`, `retrieve()`, `delete()`.
- **`encryption.py`** — `EncryptionManager`: wraps `cryptography` library for key derivation and encryption.
- **`keyring.py`** — `KeyStorage`: abstracts OS keyring vs file-based key storage.

### Subprocess safety (`core/subprocess_safe.py`)

All subprocess calls in Framekit **must** go through:

- `run_safe(cmd, ...)` — Validated `subprocess.run()` wrapper.
- `popen_safe(cmd, ...)` — Validated `subprocess.Popen()` wrapper.

Direct use of `subprocess.run()` with shell strings is blocked by a ruff `TID251` lint rule.

### Run ledger (`core/runs/`)

Every pipeline run is recorded in a run ledger (JSONL). Each entry tracks which files were created, moved, or modified. `rollback.py` reads the ledger and reverses operations.

### Cache (`core/cache/`)

Multi-backend cache with per-provider TTL, max size, and auto-cleanup. Backends are configured per-provider in `cache.*` settings.

---

## Module layer

Each module lives in `modules/<name>/` and follows a common pattern:

- **`models.py`** — Pydantic/dataclass models for inputs and outputs.
- **`service.py`** — `<Module>Service` class with a `run()` or `build()` method.
- **`scanner.py`** — Discovers files in the release folder.
- **`planner.py`** — Computes what operations would be performed (without side effects).

The command layer (`commands/<name>.py`) wires CLI flags to service calls.

---

## Data flow in the pipeline

```
ReleaseNfoData (scan once, share via PipelineContext)
     │
     ├─► NfoService.build()           → writes .nfo
     │         └─ uses metadata_context
     │
     ├─► PrezService.build()          → writes .bbcode + .html
     │         └─ uses ReleaseNfoData + metadata_context
     │
     └─► UploadService.upload_to_multiple()
               └─ uses nfo_path + torrent_path + prez_outputs
```

---

## CI/CD

GitHub Actions workflows in `.github/workflows/`:

| Workflow | File | Trigger |
|----------|------|---------|
| CI (lint + type + test + coverage) | `ci.yml` | push / PR |
| Docs (MkDocs build + deploy) | `docs.yml` | push to main |
| Release (build + sign + publish) | `release.yml` | version tag |
| Security (Semgrep + pip-audit) | `security.yml` | push / schedule |

### CI quality gates

| Gate | Tool | Threshold |
|------|------|-----------|
| Lint | `ruff check` | zero findings |
| Format | `ruff format --check` | zero diffs |
| Type check | `pyright` (strict) | zero errors |
| Tests | `pytest -n auto` | all pass |
| Coverage | `coverage report` | >= 80% |
| Security lint | `bandit -r src -ll` | no Medium/High |
| Dependency audit | `pip-audit` | no Critical/High |
| SAST | `semgrep scan` | no blocking |
| Docstring coverage | `interrogate` | >= 80% |

---

## Plugins

Framekit supports third-party plugins via Python entry points (`framekit.modules` group). Plugins are loaded at startup unless `FRAMEKIT_DISABLE_PLUGINS=1` is set.

Allowed plugin distributions are listed in `plugins.allowed` in `framekit.yaml`.
