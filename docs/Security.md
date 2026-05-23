# Security

Framekit stores sensitive values (API tokens, announce URLs, tracker credentials) in an **encrypted vault** backed by AES-GCM encryption.

---

## Encrypted vault

When `security.enabled: true` (the default), the vault is an encrypted JSON file. The encryption key is stored separately via the OS keyring (`keyring` backend) or a key file (`file` backend).

Vault contents include:

- TMDb / TVDb / AniList / Trakt tokens
- Tracker API keys and passkeys
- Torrent announce URLs
- Image host API keys
- Torrent client credentials

### Key storage backends

| Backend | Config value | Where key is stored |
|---------|-------------|---------------------|
| OS keyring | `keyring` (default) | System credential store (Keychain / Secret Service / DPAPI) |
| File | `file` | `~/.config/framekit/vault.key` with mode `600` |

Configure in `framekit.yaml`:

```yaml
security:
  enabled: true
  key_storage: keyring   # or "file"
```

### Vault file location

Default: platform data directory (e.g., `~/.local/share/framekit/vault.enc`).

Override:

```yaml
security:
  vault_path: /secure/location/framekit.vault
```

---

## Disable the vault

If you prefer to store tokens in plaintext `framekit.yaml` (not recommended):

```yaml
security:
  enabled: false
```

Sensitive values then live directly under their config keys (e.g., `metadata.tmdb_read_access_token`).

---

## VaultKeyMismatchError

If the OS keyring is wiped (e.g., after a password reset) while the vault file still exists, Framekit raises `VaultKeyMismatchError` at startup.

Recovery options:

```bash
fk setup              # re-run setup to reconfigure credentials
```

Or manually delete the vault file and re-enter all credentials:

```bash
rm ~/.local/share/framekit/vault.enc   # Linux
```

---

## Subprocess safety

Framekit enforces a rule: **all subprocess calls must go through `run_safe()` or `popen_safe()`** from `framekit.core.subprocess_safe`. Direct use of `subprocess.run()` with shell strings is blocked by a ruff `TID251` rule.

---

## Secret masking

Tokens and API keys are masked in logs and terminal output using `mask_secret()` from `framekit.modules.metadata.config`. Raw secret values are never written to JSONL logs.

---

## Running the security check

```bash
fk doctor
```

The `doctor` command runs a **Security** section that checks:

- Vault status (initialized / locked / missing)
- Key storage backend availability
- File permissions on vault and key files
- TMDb token presence and format
