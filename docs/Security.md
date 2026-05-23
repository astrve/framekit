# Security

Framekit can encrypt sensitive values (API tokens, credentials) using an AES-GCM vault. The vault is optional — without it, secrets are stored as plain text in `framekit.yaml`.

---

## Enabling the vault

```bash
fk settings set security.enabled true
```

On first use, a random 256-bit key is generated and stored via the configured `key_backend`.

---

## Key backends

| Backend | Config value | Where the key lives |
|---------|-------------|---------------------|
| OS keyring (default) | `keyring` | System keychain (macOS Keychain, GNOME Keyring, Windows Credential Locker) |
| File | `file` | `~/.config/framekit/.vault_key` (chmod 600) |

Set the backend:

```bash
fk settings set security.key_backend keyring   # or: file
```

The file backend is useful on headless servers where no keyring daemon is available.

---

## What gets encrypted

When security is enabled, the following values are stored encrypted in the vault rather than plain text in `framekit.yaml`:

- `metadata.tmdb_read_access_token`
- `upload.trackers[*].api_key`
- Any value stored with `fk metadata --set-token`

All other config values remain in plain text.

---

## VaultKeyMismatchError

If Framekit cannot decrypt the vault (e.g. the key was rotated or the keyring was wiped), it raises `VaultKeyMismatchError`. Resolution:

1. Clear the encrypted value: `fk metadata --set-token` (then re-enter your token)
2. Or disable security: `fk settings set security.enabled false`

---

## Subprocess safety

Framekit never passes secrets as CLI arguments to child processes. API tokens are passed via environment variables or temporary files with restricted permissions. The `subprocess_safe` module ensures no secret appears in process listings.

---

## Secret masking

All log output and console tables mask secrets: only the first 4 and last 4 characters are shown, with `...` in between. Example:

```
eyJh...xNiJ
```

---

## Audit log

Every pipeline run and upload attempt is appended to:

```
~/.local/share/framekit/logs/audit.ndjson
```

Entries include timestamp, command, path, and outcome — but never raw secret values.

```bash
fk audit-log           # view recent entries
fk audit-log --tail 20
```
