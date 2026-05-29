# Contributing

---

## Dev setup

```bash
git clone https://github.com/astrve/ouro.git
cd ouro
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pre-commit install
```

---

## Branching model

| Branch | Purpose |
|--------|---------|
| `main` | Stable, always deployable |
| `feature/*` | New features |
| `fix/*` | Bug fixes |
| `docs/*` | Documentation only |
| `feature/banners` | Banner image assets (kept separate) |

Open a PR against `main`. Squash-merge is preferred.

---

## Commit convention

```
type(scope): short description

body (optional)
```

Types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `ci`

Examples:
```
feat(prez): add default_textual parameter to banner selector
fix(bbcode): add blank line before info_fields loop to fix trim_blocks output
docs(wiki): add module reference pages
```

---

## Quality gates

All PRs must pass:

| Check | Command |
|-------|---------|
| Unit tests | `pytest` |
| Lint | `ruff check .` |
| Format | `ruff format --check .` |
| Type check | `mypy src/` |

Run all locally:

```bash
pre-commit run --all-files
pytest
```

---

## Adding a new module

1. Create `src/ouro/modules/<name>/` with `__init__.py`, `config.py`, `service.py`
2. Create `src/ouro/commands/<name>.py` with a Click command
3. Register the command in `src/ouro/commands/main.py`
4. Add a pipeline step in `src/ouro/commands/pipeline_steps.py`
5. Add documentation in `docs/modules/<Name>.md`
6. Update `docs/Home.md` module table
7. Update `mkdocs.yml` nav

---

## Adding a new BBCode template

1. Create `src/ouro/templates/prez/bbcode/<name>.en.jinja2`
2. Optionally add `<name>.fr.jinja2` and `<name>.es.jinja2`
3. Use the banner pattern for each section header:
   ```jinja2
   {% if data.banner_audio %}{{ bbcode_banner(data.banner_audio) }}{% else %}[size=14][b]{{ tr('prez.section.audio', default='Audio') }}[/b][/size]{% endif %}
   ```
4. Add a blank line after each `{% endif %}` that precedes a `{% for %}` loop (required for `trim_blocks=True`)

---

## Security rules

- Never commit secrets, tokens, or API keys
- Never pass secrets as CLI arguments to subprocesses — use env vars or temp files
- All user-facing output of secret-like values must go through `mask_secret()`
- New network calls must go through `httpx` with a timeout, never raw `urllib`
- Subprocess calls must use `run_safe()` from `core/subprocess_safe.py`

---

## Reporting issues

[GitHub Issues](https://github.com/astrve/ouro/issues)

Include:
- Ouro version (`ouro --version`)
- OS and Python version
- Full command run
- Complete error output (or `ouro logs --last`)
