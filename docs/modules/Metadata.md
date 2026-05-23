# Metadata

Fetches release metadata (title, year, poster, rating, overview, IMDb ID) from TMDb. Results are cached locally to avoid repeated API calls.

---

## Usage

```bash
fk metadata /path/to/release [OPTIONS]
fk metadata /path/to/release --language fr-FR
fk metadata /path/to/release --refresh
fk metadata --set-token
fk metadata --status
```

---

## Options

| Option | Description |
|--------|-------------|
| `--set-token` | Store TMDb Read Access Token interactively |
| `--set-token-value TOKEN` | Store token non-interactively (CI/scripting) |
| `--status` | Print current metadata configuration |
| `--refresh` | Bypass cache and re-fetch |
| `--language LANG` | BCP-47 locale override (e.g. `fr-FR`, `en-US`) |
| `--json` | Emit resolved metadata as JSON |

---

## Setup

Get a free Read Access Token from [themoviedb.org/settings/api](https://www.themoviedb.org/settings/api).

Store it:

```bash
fk metadata --set-token
```

When the security vault is enabled, the token is stored encrypted. Otherwise it is stored as plain text in `framekit.yaml`.

---

## How it works

1. Parses the release folder name to extract title and year
2. Searches TMDb for matching movies or series
3. If multiple results, shows an interactive confirmation prompt (unless `interactive_confirmation: false`)
4. Fetches detail page: year, rating, overview, poster URL, IMDb ID
5. Caches the full response for `cache_ttl_hours` hours (default: 168 = 1 week)

---

## Providers

| Provider | Config value | Notes |
|---------|-------------|-------|
| TMDb | `tmdb` | Default. Supports movies and TV series |

Additional providers may be added in future releases.

---

## Cache

Responses are cached in `~/.cache/framekit/metadata/`. Clear with:

```bash
fk metadata /path/to/release --refresh
```

Or adjust TTL:

```yaml
metadata:
  cache_ttl_hours: 0   # disable caching
```

---

## Configuration

```yaml
metadata:
  tmdb_read_access_token: ""
  provider: tmdb
  language: fr-FR
  interactive_confirmation: true
  cache_ttl_hours: 168
```

---

## Status output

```bash
fk metadata --status
```

Shows current token (masked), provider, language, and cache TTL.

---

## In the pipeline

The `metadata` step runs after `cleanmkv`. The resolved `MetadataContext` object (title, year, poster URL, IMDb ID, overview) is stored in `PipelineContext.metadata_context` and used by `nfo` and `prez`.

If metadata fetch fails (network error, no token), the pipeline continues without metadata — NFO and prez are built from release scan data only.
