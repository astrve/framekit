# Contributing

Thank you for contributing to Framekit. This guide covers the development workflow, quality gates, and conventions.

---

## Development setup

```bash
git clone https://github.com/astrve/framekit.git
cd framekit
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev,docs,build-binary]"
pre-commit install
```

---

## Branching model

| Branch | Purpose |
|--------|---------|
| `main` | Tagged release tip — protected |
| `develop` | Integration branch — all PRs target this |
| `feat/*` | New features |
| `fix/*` | Bug fixes |
| `chore/*` | Maintenance, dependency bumps |
| `sec/*` | Security fixes |

---

## Commit convention

```
<type>(<scope>): <summary>
```

Types: `feat`, `fix`, `sec`, `perf`, `refactor`, `docs`, `test`, `build`, `ci`, `chore`

Examples:

```
feat(prez): add glassmorphism HTML template family
fix(cleanmkv): handle MKVs with no audio tracks
chore(deps): bump jinja2 to 3.1.6
```

---

## Quality gates

All gates must pass before a PR can be merged:

| Gate | Command | Threshold |
|------|---------|-----------|
| Lint | `ruff check src tests` | zero findings |
| Format | `ruff format --check src tests` | zero diffs |
| Type check | `pyright` | zero errors (strict mode) |
| Tests | `pytest -n auto` | all pass |
| Coverage | `coverage report --fail-under=80` | >= 80% (target: 90%) |
| Security lint | `bandit -r src -ll` | no Medium/High |
| Dependency audit | `pip-audit` | no Critical/High |
| SAST | `semgrep scan --config auto` | no blocking |
| Docstring coverage | `interrogate src --fail-under=80` | >= 80% |
| Spelling | `codespell src tests docs` | zero |

Run all checks locally:

```bash
ruff check src tests
ruff format --check src tests
pyright
pytest -n auto
```

---

## Security rules for contributors

- **Never log raw tokens or secrets.** Use `mask_secret()` from `framekit.modules.metadata.config`.
- **Never call subprocess directly.** Use `run_safe()` / `popen_safe()` from `framekit.core.subprocess_safe`. This is enforced by a ruff `TID251` lint rule.
- **Never set `autoescape=False`** in a Jinja2 `Environment` without a comment explaining why.
- **Vault schema changes** require a migration test in `tests/test_settings_migration.py`.
- **New HTTP calls** must use the `framekit.core.http` wrapper for uniform timeouts, retries, and TLS settings.

---

## Adding a module

1. Create `src/framekit/modules/<name>/` with `models.py`, `service.py`, `scanner.py` (if needed)
2. Add a command file `src/framekit/commands/<name>.py` with Click group
3. Register the command in `src/framekit/commands/main.py`
4. Add locale keys to `src/framekit/locales/*.json`
5. Add tests in `tests/test_<name>*.py`
6. Add module documentation in `docs/modules/<Name>.md`
7. Update `mkdocs.yml` nav

---

## Adding an NFO template

```bash
fk nfo --import-template /path/to/my.jinja2 \
       --import-name "My Template" \
       --import-scope movie
```

For bundled templates, add files to `src/framekit/templates/nfo/` following the naming convention `{scope}_{style}.{locale}.jinja2` and register them in `NfoTemplateRegistry`.

---

## Adding a CleanMKV preset

Add a YAML file to `Presets/CleanMKV/` following the format described in [Presets](Presets.md).

---

## Documentation

Docs live in `docs/` and are built with MkDocs + Material theme.

```bash
pip install -e ".[docs]"
mkdocs serve             # local preview at http://127.0.0.1:8000
```

Docs are deployed automatically to GitHub Pages on every push to `main`.
