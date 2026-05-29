# Contributing to Ouro

Thanks for considering a contribution. Ouro is a security-sensitive, headless-friendly CLI for media release preparation; the rules below exist to keep it that way.

## TL;DR

```bash
# 1. Fork + clone
git clone https://github.com/<you>/ouro && cd ouro

# 2. Install with dev extras (uv recommended)
uv venv && uv pip install -e ".[dev]"

# 3. Enable pre-commit so lint/format/type/security run on every commit
pre-commit install

# 4. Make a focused change, add tests, run the full suite
pytest --cov=src/ouro --cov-report=term-missing
ruff check src tests && ruff format --check src tests
pyright
bandit -r src
pip-audit

# 5. Open a PR against `develop` (not `main`)
```

## Development Environment

- **Python**: 3.12 minimum. CI matrix covers 3.12, 3.13, 3.14 on Ubuntu, macOS, Windows.
- **Package manager**: `uv` preferred (`uv pip install -e ".[dev]"`). Plain `pip install -e ".[dev]"` also works.
- **External tools** (only required for the features that use them):
  - `mkvmerge` from MKVToolNix (CleanMKV)
  - `ffmpeg` + `ffprobe` (encoder, screenshot, extract)
  - `mediainfo` / `libmediainfo` (technical metadata)

Run `ouro doctor` to verify your environment.

## Branching

| Branch    | Purpose                                                       |
| --------- | ------------------------------------------------------------- |
| `main`    | Tagged release tip; protected, no direct commits               |
| `develop` | Integration branch for the next minor                          |
| `feat/*`  | New user-visible feature                                       |
| `fix/*`   | Bug fix (regression test required)                             |
| `chore/*` | Tooling, docs, refactor with no user-visible change            |
| `sec/*`   | Security fix (coordinate via SECURITY.md before opening a PR)  |

Open PRs against `develop` unless the maintainer asks otherwise.

## Commit Style

```
<type>(<scope>): <imperative summary, <72 chars>

<wrap body at 80 chars. Explain the *why*, not the *what* — the diff
shows the what. Reference issues with #N.>

Refs: #123
```

Types: `feat`, `fix`, `sec`, `perf`, `refactor`, `docs`, `test`, `build`, `ci`, `chore`.

## Quality Gates

A PR is mergeable when **all** of the following are green:

| Gate                  | Command                                              | Threshold        |
| --------------------- | ---------------------------------------------------- | ---------------- |
| Lint                  | `ruff check src tests`                               | zero findings    |
| Format                | `ruff format --check src tests`                      | zero diffs       |
| Type (strict)         | `pyright`                                            | zero errors      |
| Unit + integration    | `pytest -n auto`                                     | all pass         |
| Coverage              | `coverage report --fail-under=80`                    | ≥ 80% (target 90)|
| Security lint         | `bandit -r src -ll`                                  | no Medium/High   |
| Dep vulnerabilities   | `pip-audit`                                          | no Critical/High |
| SAST                  | `semgrep scan --config auto`                         | no blocking      |
| Docstring coverage    | `interrogate src --fail-under=80`                    | ≥ 80%            |
| Spelling              | `codespell src tests docs`                           | zero (or `.codespellrc` allowlisted) |

`pre-commit run --all-files` runs a fast subset locally before push.

## Tests

- **Always** add a regression test alongside a bug fix. The test should fail without the fix and pass with it.
- Prefer `pytest` fixtures over global state.
- For subprocess and network code, use `respx` (httpx mocks) and `tmp_path` instead of real I/O.
- Tests live in `tests/`. Mirror the source tree: `src/ouro/modules/foo.py` → `tests/test_foo.py`.
- Security-sensitive paths (vault, keyring, redaction, template escape, subprocess, path validation) **must** have regression tests when modified.

## Code Style

- 100-char lines, 4-space indent (enforced by ruff).
- Google-style docstrings (configured in `pyproject.toml`).
- Type annotations required on public functions. Use `from __future__ import annotations` in module headers — Pyright runs in strict mode.
- Prefer `pathlib.Path` over `os.path`.
- Prefer dataclasses or pydantic models over raw dicts for structured data.
- Never use bare `except:` or `except Exception: pass`. Either log + re-raise, or convert to a typed exception. Silent swallow in security paths will be rejected at review.

## Security Rules

- Never log raw token, announce URL, password, or other secret material. Use `mask_secret()` from `ouro.modules.metadata.config`.
- Never call subprocess with a partial executable path. Resolve via `shutil.which` or hard-code the absolute path.
- Never set Jinja2 `autoescape=False` without a clear rationale in a comment.
- Vault changes must include a migration test (`tests/test_settings_migration.py`).
- New external HTTP calls must use the project `httpx` wrapper (`ouro.core.http`) so timeouts, retries, and TLS settings are uniform.

Coordinate vulnerability fixes via [SECURITY.md](SECURITY.md) before opening a public PR.

## CLI / UX Rules

- Every command must have a `--help` and a non-interactive path. Headless mode must not silently prompt.
- Destructive operations (writes, renames, deletes, uploads) must respect `--dry-run` / `--preview` and confirm in interactive mode.
- Localized strings go through `ouro.core.i18n.tr()` — never hard-code user-facing English.
- Selector calls go through `ouro.ui.unified_selector` (the consolidation target). Don't add new ad-hoc Click prompts.

## Documentation

- Update `README.md` and `docs/` when user-visible behaviour changes.
- For non-trivial design choices, add an ADR under `docs/decisions/` (see existing examples for format).
- Keep examples runnable: every code block in docs must work against the current public API.

## Pull Request Checklist

```
[ ] Branch is up to date with develop
[ ] Tests added / updated and all pass locally
[ ] `ruff check . && ruff format --check . && pyright` green
[ ] Coverage did not drop
[ ] CHANGELOG.md entry under "Unreleased"
[ ] Docs / ADR updated if behaviour or architecture changed
[ ] No secrets in diff (`detect-secrets scan`)
[ ] Security implications acknowledged or N/A
```

## Code of Conduct

We expect professional, kind communication. Disagreements are resolved with evidence (code, tests, benchmarks) — not authority.

## License

By contributing you agree your work is licensed under the project [LICENSE](LICENSE) (GPL-3.0-only).
