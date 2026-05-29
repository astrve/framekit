# Security Policy

## Supported Version

Security fixes target the latest public release.

## Reporting

Open a private security advisory on GitHub when possible.

Do not publish working exploit details before a fix is available.

## Secret Handling

Ouro must not require secrets in committed files.

Sensitive values belong in the encrypted vault or environment variables:

- metadata tokens
- tracker API keys
- announce URLs and passkeys
- torrent client credentials
- image host API keys

`ouro.yaml` is intentionally ignored because it may contain local secrets when vault storage is disabled.

## Local Checks

Run these before a public release:

```bash
bandit -r src
pip-audit
detect-secrets scan
ruff check src tests
pyright
pytest
```
