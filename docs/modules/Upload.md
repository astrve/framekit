# Upload

> **Status: Beta.** The Upload module is functional but API contracts may evolve. Use `--dry-run` before real uploads.

Uploads a release (`.torrent` + description) to one or more configured trackers.

---

## Usage

```bash
fk upload run /path/to/release.torrent --tracker "BeyondHD (BHD)"
fk upload run /path/to/release-folder --dry-run
fk upload assistant --name "my-tracker" --base-url "https://tracker.example"
```

---

## Supported tracker engines

| Engine | Description | Typical trackers |
|--------|-------------|------------------|
| `unit3d` | UNIT3D API | BHD, BLU, ATH, RFX, STT, HWK, OTW |
| `gazelle` | Gazelle API | OPS, RED |
| `custom_json_api_v1` | Bearer-token custom JSON upload API | Private tracker APIs exposing `/api/torrents` |
| `custom` | User-defined adapter/config | Any custom endpoint |

---

## Built-in profile shortcuts

| Name | URL | Engine |
|------|-----|--------|
| BeyondHD (BHD) | beyond-hd.me | unit3d |
| Blutopia (BLU) | blutopia.cc | unit3d |
| Aither (ATH) | aither.cc | unit3d |
| ReelFliX (RFX) | reelflix.xyz | unit3d |
| SkipTheTrailers (STT) | skipthetrailers.xyz | unit3d |
| Hawke-One (HWK) | hawke.uno | unit3d |
| OldToons World (OTW) | oldtoons.world | unit3d |
| Orpheus Network (OPS) | orpheus.network | gazelle |
| Redacted (RED) | redacted.ch | gazelle |

---

## Configuration

```yaml
upload:
  trackers:
    - name: BeyondHD (BHD)
      type: unit3d
      url: https://beyond-hd.me
      api_key: ""
      categories:
        Movies: 1

    - name: my-tracker
      type: custom_json_api_v1
      url: https://tracker.example
      api_key: ""
      defaults:
        custom_api_category_id: 1
        custom_api_subcategory_id: 6
```

For safer local setup, generate tracker files with:

```bash
fk upload assistant
```

This creates `trackers/*.yaml` using `token_env` (no secret stored in repo config).

---

## In pipeline

`upload` runs last in pipeline. It consumes:
- `PipelineContext.torrent_path`
- generated prez output as description source

With `--dry-run`, upload payload is previewed only.
