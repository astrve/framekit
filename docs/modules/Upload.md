# Upload

> **Status: Beta.** The Upload module is functional but the API may change between releases. Test with `--dry-run` before real uploads.

Uploads a release (torrent file + presentation) to one or more configured trackers.

---

## Usage

```bash
fk upload /path/to/release [OPTIONS]
fk upload /path/to/release --tracker BHD
fk upload /path/to/release --dry-run
```

---

## Options

| Option | Description |
|--------|-------------|
| `--tracker NAME` | Upload to a specific tracker profile by name |
| `--dry-run` | Print upload payload without sending |
| `--json` | Emit upload result as JSON |

---

## Supported tracker types

| Type | Description | Known trackers |
|------|-------------|----------------|
| `c411` | C411 private tracker API | C411 |
| `unit3d` | UNIT3D tracker engine | BHD, BLU, ATH, RFX, STT, HWK, OTW |
| `gazelle` | Gazelle-based trackers | OPS, RED |

---

## Known tracker profiles

| Name | URL | Type |
|------|-----|------|
| C411 | c411.org | c411 |
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
    - name: BHD
      type: unit3d
      url: https://beyond-hd.me
      api_key: ""          # stored encrypted when security.enabled = true
      category: movies
      auto_approve: false

    - name: C411
      type: c411
      url: https://c411.org
      api_key: ""
      category_id: 1
      subcategory_id: 6
      language_id: 2
```

### C411 category IDs

| ID | Category |
|----|---------|
| 1 | Films & Videos |
| 2 | Ebook |
| 3 | Audio |

### C411 subcategory IDs (Films, category 1)

| ID | Subcategory |
|----|------------|
| 1 | Animation |
| 2 | Animation Serie |
| 4 | Documentaire |
| 6 | Film |
| 7 | Serie TV |

### C411 language IDs

| ID | Language |
|----|---------|
| 1 | Anglais |
| 2 | Francais (VFF) |
| 3 | Muet |

---

## In the pipeline

The `upload` step is the last in the pipeline. It reads `PipelineContext.torrent_path` and `prez_outputs` (for the BBCode description), then POSTs to each configured tracker.

The step is skipped in `--dry-run` mode. When no trackers are configured, the step exits cleanly with an info message.
