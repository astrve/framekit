# Prez

Builds BBCode and HTML presentations for a release. Supports multiple templates, three languages, and online banner images.

---

## Usage

```bash
fk prez /path/to/release [OPTIONS]
fk prez /path/to/release --template classic --language fr
fk prez /path/to/release --banner-design minimal_blue --language en
fk prez /path/to/release --no-html
```

---

## Options

| Option | Description |
|--------|-------------|
| `--template NAME` | Presentation template: `classic`, `detailed`, `tracker` |
| `--language LANG` | Section label language: `en`, `fr`, `es` |
| `--banner-design NAME` | Banner design name, or `textual` for text-only headers |
| `--output-dir DIR` | Write output to this directory |
| `--no-bbcode` | Skip BBCode generation |
| `--no-html` | Skip HTML generation |
| `--dry-run` | Print to stdout, do not write files |

---

## Templates

| Template | Description |
|----------|-------------|
| `classic` | Standard layout with synopsis, technical, audio, subtitles, metadata, information, release sections |
| `detailed` | Extended layout with more fields |
| `tracker` | Compact single-block layout for tracker posts |

---

## Languages

| Code | Labels in |
|------|-----------|
| `en` | English |
| `fr` | French |
| `es` | Spanish |

---

## Banner images

Banners are PNG section header images hosted on the `feature/banners` GitHub branch. The module fetches an index of available designs on first run and caches it for 24 hours.

### Selecting a banner

In interactive mode, `fk prez` (standalone) asks whether to fetch banners, then shows a design selector. In the pipeline, the default is **text-only** (`textual`) to avoid accidental selections.

### Banner sections

| Section | Banner variable |
|---------|----------------|
| Audio | `data.banner_audio` |
| Information | `data.banner_information` |
| Metadata | `data.banner_metadata` |
| Release | `data.banner_release` |
| Subtitles | `data.banner_subtitles` |
| Synopsis | `data.banner_synopsis` |
| Technical | `data.banner_technical` |

### Fallback

When GitHub is unreachable and no cache exists, a static list of 30 design names is used. Banner URLs are built to the same pattern but may 404 if a design does not have all sections.

---

## Output

Writes to the release folder (or `--output-dir`):

- `<release-name>.bbcode.txt` — BBCode for tracker posts
- `<release-name>.html` — Standalone HTML file

---

## Configuration

```yaml
prez:
  template: classic
  language: fr
  banner_design: textual
  output_dir_name: ""
```

---

## In the pipeline

The `prez` step runs after `nfo`. Banner selection uses `prez.banner_design` from config (default: `textual`) when running in `--auto` mode.
