# Configuration

All configuration lives in `~/.config/ouro/ouro.yaml`. Create the file and a skeleton config with:

```bash
ouro init
```

---

## File layout

```yaml
metadata:
  tmdb_read_access_token: ""
  provider: tmdb
  language: fr-FR
  interactive_confirmation: true
  cache_ttl_hours: 168

nfo:
  template: classic
  output_dir_name: ""

prez:
  template: classic
  language: fr
  banner_design: textual
  output_dir_name: ""

torrent:
  announce_url: ""
  announce_urls: []
  piece_length: auto
  output_dir_name: ""
  include_release_folder: true

cleanmkv:
  default_preset: ""
  output_dir_name: ""

encoder:
  default_preset: ""
  output_dir_name: encoded

upload:
  trackers: []

seedbox:
  seedboxes: []

security:
  enabled: false
  key_backend: keyring

paths:
  start_folder: ""
```

---

## Section reference

### `metadata`

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `tmdb_read_access_token` | string | `""` | TMDb v4 Read Access Token. Store with `ouro metadata --set-token` |
| `provider` | string | `tmdb` | Metadata provider. Currently `tmdb` only |
| `language` | string | `fr-FR` | BCP-47 locale for metadata (titles, overview). E.g. `en-US`, `fr-FR` |
| `interactive_confirmation` | bool | `true` | Prompt to confirm the matched title before continuing |
| `cache_ttl_hours` | int | `168` | How long to cache API responses (hours). `0` disables caching |

### `nfo`

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `template` | string | `classic` | NFO template name |
| `output_dir_name` | string | `""` | Subdirectory for NFO output. Empty = same folder as release |

### `prez`

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `template` | string | `classic` | Presentation template (`classic`, `detailed`, `tracker`) |
| `language` | string | `fr` | Language for section labels (`en`, `fr`, `es`) |
| `banner_design` | string | `textual` | Default banner design name, or `textual` for text-only headers |
| `output_dir_name` | string | `""` | Subdirectory for prez output |

### `torrent`

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `announce_url` | string | `""` | Primary announce URL |
| `announce_urls` | list | `[]` | Additional announce URLs (multi-tracker) |
| `piece_length` | string/int | `auto` | Piece size in KiB, or `auto` |
| `output_dir_name` | string | `""` | Subdirectory for .torrent output |
| `include_release_folder` | bool | `true` | Include the top-level folder in torrent payload |

### `cleanmkv`

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `default_preset` | string | `""` | Auto-apply this CleanMKV preset instead of prompting |
| `output_dir_name` | string | `""` | Output directory name. Empty = in-place |

### `encoder`

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `default_preset` | string | `""` | Encoder preset to use when none specified on CLI |
| `output_dir_name` | string | `encoded` | Subdirectory name for encoded files |

### `upload`

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `trackers` | list | `[]` | List of tracker profile objects (see [Upload](modules/Upload.md)) |

### `seedbox`

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `seedboxes` | list | `[]` | Named seedbox profiles (see [Seedbox](modules/Seedbox.md)) |

### `security`

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `enabled` | bool | `false` | Encrypt secrets in the vault |
| `key_backend` | string | `keyring` | Key storage backend: `keyring` or `file` |

See [Security](Security.md) for full details.

### `paths`

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `start_folder` | string | `""` | Default root folder when no path is given on the CLI |

---

## Environment overrides

All config keys can be overridden with environment variables using the pattern `OURO_<SECTION>_<KEY>` (uppercase, underscores):

```bash
OURO_METADATA_LANGUAGE=en-US ouro metadata /path/to/release
```

---

## Viewing current config

```bash
ouro settings show
ouro settings get metadata.language
ouro settings set metadata.language fr-FR
```
