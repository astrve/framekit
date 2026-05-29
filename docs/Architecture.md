# Architecture

High-level overview of Ouro's codebase structure and design decisions.

---

## Repository layout

```
ouro/
├── src/ouro/
│   ├── commands/         CLI command definitions (Click)
│   ├── core/             Shared infrastructure
│   │   ├── settings.py   Config read/write
│   │   ├── i18n.py       Translation layer (tr())
│   │   ├── paths.py      Path resolution helpers
│   │   ├── security.py   AES-GCM vault
│   │   └── subprocess_safe.py  Secret-safe subprocess wrapper
│   ├── modules/          Business logic, one package per module
│   │   ├── batch/
│   │   ├── cleanmkv/
│   │   ├── encoder/
│   │   ├── extract/
│   │   ├── metadata/
│   │   ├── nfo/
│   │   ├── prez/
│   │   ├── renamer/
│   │   ├── screenshot/
│   │   ├── torrent/
│   │   ├── upload/
│   │   ├── validate/
│   │   └── watch/
│   ├── templates/        Jinja2 templates
│   │   ├── nfo/
│   │   └── prez/
│   │       ├── bbcode/
│   │       └── html/
│   └── ui/               Rich-based console components
│       ├── console.py
│       ├── branding.py
│       ├── timeline.py
│       └── unified_selector.py
├── tests/
├── docs/
├── pyproject.toml
└── mkdocs.yml
```

---

## Core layer

The `core/` package provides shared infrastructure with no business logic:

| Module | Purpose |
|--------|---------|
| `settings.py` | Read/write `ouro.yaml`; environment var overrides |
| `i18n.py` | `tr(key, default, **kwargs)` — returns translated string or default |
| `paths.py` | `PathResolver` — resolves start folder, output dirs |
| `security.py` | AES-GCM vault, OS keyring and file backends |
| `subprocess_safe.py` | `run_safe()` — wraps `subprocess.run`, masks secrets |
| `json_output.py` | `emit_json()` — machine-readable envelope |
| `cli_helpers.py` | Shared Click helpers and error formatting |

---

## Module layer

Each module under `modules/` follows a consistent layout:

```
modules/cleanmkv/
├── __init__.py      Public API exports
├── config.py        Config dataclass and resolution
├── service.py       Core business logic
├── models.py        Data models
└── presets.py       Built-in presets
```

Modules never import from `commands/`. The `commands/` layer only imports from `modules/`.

---

## Data flow

```
CLI args
  └─► commands/pipeline.py
        └─► PipelineContext (shared state)
              ├─► modules/nfo/scanner.py   → Release object
              ├─► modules/metadata/        → MetadataContext
              ├─► modules/nfo/builder.py   → .nfo file
              ├─► modules/prez/service.py  → BBCode, HTML
              ├─► modules/torrent/         → .torrent file
              └─► modules/upload/          → HTTP upload
```

---

## UI layer

All terminal output goes through `ui/console.py` (`console`, `print_info`, `print_error`, etc.). Rich is the only output mechanism — `print()` is not used directly.

Interactive prompts use `ui/unified_selector.py`:

- `select_one()` — single-choice arrow selector
- `select_many()` — multi-choice selector
- `confirm_choice()` — Yes/No prompt
- `text_input()` — free text prompt

---

## CI/CD

| Workflow | Trigger | What it does |
|---------|---------|--------------|
| `tests.yml` | push / PR | pytest, ruff, mypy |
| `build.yml` | push to main | PyInstaller standalone binaries |
| `docs.yml` | push to main | MkDocs build → GitHub Pages |
| `release.yml` | tag `v*` | Build + publish to PyPI + GitHub Releases |

---

## Extension points

### Custom templates

Drop `.jinja2` files in:
- `~/.config/ouro/nfo_templates/` for NFO
- `~/.config/ouro/prez_templates/` for Prez

### Plugin system (experimental)

```bash
ouro plugin list
ouro plugin install <package>
```

Plugins are Python packages that register Click commands under the `ouro.plugins` entry point group.
