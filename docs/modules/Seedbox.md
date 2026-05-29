# Seedbox

Transfers releases to remote seedboxes via rclone. Supports multiple named seedbox profiles and keeps a transfer history.

---

## Usage

```bash
ouro seedbox list
ouro seedbox send /path/to/release --to my-seedbox
ouro seedbox history
ouro seedbox history --seedbox my-seedbox
ouro seedbox add
```

---

## Sub-commands

| Sub-command | Description |
|------------|-------------|
| `list` | List all configured seedbox profiles |
| `send PATH --to NAME` | Transfer a release to a named seedbox |
| `history` | Show recent transfer history |
| `add` | Add a seedbox profile interactively |

---

## Setup

Seedbox profiles are stored in `ouro.yaml`. Credentials (remote paths, auth) are managed by rclone — Ouro only stores seedbox metadata.

### 1. Configure rclone

```bash
rclone config
```

Add a remote for your seedbox (SFTP, FTP, WebDAV, etc.).

### 2. Add a seedbox profile to Ouro

```bash
ouro seedbox add
```

Or edit `ouro.yaml` directly:

```yaml
seedbox:
  seedboxes:
    - name: my-seedbox
      rclone_remote: "myseedbox"        # rclone remote name
      remote_path: "/downloads/complete"
      bandwidth_limit: "10M"            # optional rclone --bwlimit value
      post_upload_command: ""           # optional shell command after upload
```

---

## Sending a release

```bash
ouro seedbox send /path/to/Movie.2024.1080p.BluRay --to my-seedbox
```

Calls `rclone copy` with the configured remote and path. Transfer timeout is 24 hours.

---

## History

Transfer history is stored as newline-delimited JSON in:

```
~/.config/ouro/seedbox/history.ndjson
```

```bash
ouro seedbox history              # last 50 transfers
ouro seedbox history --limit 20   # limit entries
ouro seedbox history --seedbox my-seedbox  # filter by profile
```

---

## Configuration

```yaml
seedbox:
  seedboxes:
    - name: my-seedbox
      rclone_remote: myseedbox
      remote_path: /downloads
      bandwidth_limit: ""
      post_upload_command: ""
```

---

## External dependency

Requires `rclone` on `PATH`. Install from [rclone.org](https://rclone.org/).
