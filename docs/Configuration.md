# Configuration

## Config file location

Framekit resolves `framekit.yaml` in this order:

1. `FRAMEKIT_CONFIG` environment variable (absolute path)
2. Nearest `framekit.yaml` found walking upward from CWD (stops before home directory)
3. Global path stored in `~/.config/framekit/settings-path.txt`
4. `~/.config/framekit/framekit.yaml` (platform default)

Create a starter config:

```bash
fk init          # creates framekit.yaml in CWD
fk setup         # interactive wizard
```

> `framekit.yaml` is git-ignored — it may contain local paths or credentials.

---

## Environment variable overrides

| Variable | Purpose |
|----------|---------|
| `FRAMEKIT_CONFIG` | Override config file path |
| `FRAMEKIT_CONFIG_DIR` | Override config directory |
| `FRAMEKIT_CACHE_DIR` | Override cache directory |
| `FRAMEKIT_LOCALE` | Override UI locale (`en`, `fr`, `es`) |
| `FRAMEKIT_TMDB_READ_ACCESS_TOKEN` | Override TMDb token (bypasses vault) |
| `FRAMEKIT_DISABLE_PLUGINS` | Set to `1` to disable plugin loading |

---

## Key reference

### `general`

| Key | Type | Default | Purpose |
|-----|------|---------|---------|
| `locale` | string | `"en"` | UI language (`en`, `fr`, `es`) |
| `default_folder` | string | `""` | Default working folder (empty = CWD) |
| `report_output_folder` | string | `""` | Where to write operation reports |

### `logging`

| Key | Type | Default | Purpose |
|-----|------|---------|---------|
| `max_size_mb` | int | `100` | Max log file size before rotation |
| `max_backups` | int | `30` | Rotated log files to keep |
| `compress_old_logs` | bool | `true` | Gzip old log files |
| `retention_days` | int | `5` | Delete logs older than N days |
| `cleanup_on_startup` | bool | `true` | Run log cleanup at startup |

### `tools`

| Key | Type | Default | Purpose |
|-----|------|---------|---------|
| `mkvmerge` | string | `""` | Path to mkvmerge (empty = search PATH) |
| `ffmpeg` | string | `""` | Path to ffmpeg |
| `ffprobe` | string | `""` | Path to ffprobe |
| `mediainfo` | string | `""` | Path to mediainfo |

### `security`

| Key | Type | Default | Purpose |
|-----|------|---------|---------|
| `enabled` | bool | `true` | Use encrypted vault for secrets |
| `vault_path` | string | `""` | Custom vault file path |
| `key_storage` | string | `"keyring"` | Key storage backend (`keyring` or `file`) |
| `auto_migrate` | bool | `true` | Auto-migrate vault on schema changes |
| `backup_before_changes` | bool | `true` | Backup vault before modifications |

See [Security](Security.md) for details.

### `metadata`

| Key | Type | Default | Purpose |
|-----|------|---------|---------|
| `provider` | string | `"tmdb"` | Primary metadata provider |
| `fallback_providers` | list | `[]` | Ordered fallback providers |
| `interactive_confirmation` | bool | `true` | Show candidate selection UI |
| `cache_ttl_hours` | int | `168` | Metadata cache TTL (7 days) |
| `language` | string | `"en-US"` | Fetch language (BCP-47) |
| `tmdb_read_access_token` | string | `""` | TMDb v4 read access token |
| `tvdb_api_key` | string | `""` | TVDb API key |
| `tvdb_language` | string | `"eng"` | TVDb language code |
| `anilist_enabled` | bool | `true` | Enable AniList provider |
| `anilist_language` | string | `"en"` | AniList preferred language |
| `enabled_by_default` | bool | `true` | Fetch metadata by default |
| `prompt_missing_token_in_pipeline` | bool | `true` | Prompt to add TMDb token if missing |

Default `content_type_hints`:

```yaml
metadata:
  content_type_hints:
    anime: [anilist, tmdb]
    tv: [tvdb, tmdb]
    movie: [tmdb]
```

### `cache`

| Key | Type | Default | Purpose |
|-----|------|---------|---------|
| `enabled` | bool | `true` | Global cache on/off |
| `directory` | string | `""` | Custom cache directory |
| `auto_cleanup` | bool | `true` | Auto-evict expired entries |

Per-provider sub-keys (`tmdb`, `tvdb`, `anilist`, `mediainfo`, `release`):

| Key | Type | Default |
|-----|------|---------|
| `enabled` | bool | `true` |
| `ttl_days` | int | `7` (`mediainfo`: 30) |
| `max_size_mb` | int | `50` |

### `modules.renamer`

| Key | Type | Default | Purpose |
|-----|------|---------|---------|
| `default_folder` | string | `""` | Default folder |
| `default_language_tag` | string | `"MULTI.VFF"` | Language tag when none detected |

### `modules.cleanmkv`

| Key | Type | Default | Purpose |
|-----|------|---------|---------|
| `default_folder` | string | `""` | Default folder |
| `output_dir_name` | string | `"Release/{release}"` | Output subdirectory pattern |
| `default_preset` | string | `"multi"` | Default preset name |
| `copy_unchanged_files` | bool | `true` | Copy MKVs that need no track changes |

### `modules.nfo`

| Key | Type | Default | Purpose |
|-----|------|---------|---------|
| `default_folder` | string | `""` | Default folder |
| `active_template` | string | `"default"` | Active template name |
| `locale` | string | `"auto"` | NFO output language |
| `active_logo` | string | `""` | Internal name of active logo |
| `with_metadata` | bool | `true` | Enrich NFO with metadata |
| `mode` | string | `"global"` | Output mode (`global`, `per_file`, `both`) |

### `modules.torrent`

| Key | Type | Default | Purpose |
|-----|------|---------|---------|
| `default_folder` | string | `""` | Default folder |
| `announce` | string | `""` | Default announce URL |
| `announce_urls` | list | `[]` | Multiple announce URLs |
| `private` | bool | `true` | Create private torrents |
| `piece_length` | string | `"auto"` | Piece length (`auto`, `512k`, `1m`, ...) |
| `prompt_save_announce` | bool | `true` | Prompt to save new announce URLs |

### `modules.prez`

| Key | Type | Default | Purpose |
|-----|------|---------|---------|
| `default_folder` | string | `""` | Default folder |
| `locale` | string | `"auto"` | Output language |
| `format` | string | `"both"` | Output format (`html`, `bbcode`, `both`) |
| `preset` | string | `"default"` | Prez preset name |
| `html_template` | string | `"minimal_dark"` | HTML template name |
| `bbcode_template` | string | `"classic"` | BBCode template name |
| `mediainfo_mode` | string | `"none"` | MediaInfo mode (`none`, `inline`, `spoiler`) |
| `with_metadata` | bool | `true` | Enrich with TMDb metadata |

### `modules.pipeline`

| Key | Type | Default | Purpose |
|-----|------|---------|---------|
| `default_folder` | string | `""` | Default folder |
| `stop_on_error` | bool | `false` | Stop on first module error |
| `enabled_modules` | list | `[renamer,cleanmkv,nfo,torrent,prez]` | Default module set |
| `with_metadata` | bool | `true` | Enable metadata fetching |
| `auto_mode` | bool | `false` | Run non-interactively |

### `modules.encoder`

| Key | Type | Default | Purpose |
|-----|------|---------|---------|
| `output_dir_name` | string | `"encoded"` | Output subdirectory name |
| `preset` | string | `""` | Preset name for pipeline encoder step |
| `ffmpeg_path` | string | `"ffmpeg"` | FFmpeg binary path |
| `ffprobe_path` | string | `"ffprobe"` | FFprobe binary path |

### `upload`

| Key | Type | Default | Purpose |
|-----|------|---------|---------|
| `enabled` | bool | `false` | Enable upload module |
| `auto_upload` | bool | `false` | Auto-upload without confirmation |
| `max_parallel_uploads` | int | `3` | Max concurrent uploads |
| `image_host` | string | `""` | Image host (`imgbb`, `imgbox`, `ptpimg`, `freeimage`) |
| `image_host_api_key` | string | `""` | Image host API key |
| `torrent_client` | string | `""` | Client (`qbittorrent` or empty) |
| `torrent_client_host` | string | `"localhost"` | Client hostname |
| `torrent_client_port` | int | `8080` | Client port |
| `torrent_client_category` | string | `"framekit"` | Category for added torrents |

### `seedbox`

| Key | Type | Default | Purpose |
|-----|------|---------|---------|
| `default` | string | `""` | Default seedbox name |
| `history_enabled` | bool | `true` | Track transfer history |
| `seedboxes` | list | `[]` | Seedbox configurations |

### `watch`

| Key | Type | Default | Purpose |
|-----|------|---------|---------|
| `enabled` | bool | `false` | Enable folder watcher |
| `folders` | list | `[]` | Folders to monitor |
| `notifications.enabled` | bool | `true` | Enable desktop notifications |
| `notifications.on_error` | bool | `true` | Notify on pipeline error |
| `notifications.on_success` | bool | `false` | Notify on pipeline success |

### `aliases`

| Key | Type | Default | Purpose |
|-----|------|---------|---------|
| `enabled` | bool | `true` | Enable alias resolution |
| `max_chain_depth` | int | `5` | Max alias chain depth |
| `user` | dict | `{}` | User-defined aliases (name -> command string) |

---

## Editing settings

```bash
fk settings           # view all current settings (sensitive keys redacted)
fk setup              # interactive guided wizard
```

Framekit uses `ruamel.yaml` — comments in `framekit.yaml` are preserved across edits.
