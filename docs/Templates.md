# Templates

Framekit uses Jinja2 templates to generate NFO files and presentation files (BBCode and HTML).

---

## NFO templates

**Location:** `src/framekit/templates/nfo/`
**Naming:** `{scope}_{style}.{locale}.jinja2`

### Available templates

| Scope | Style | Locales |
|-------|-------|---------|
| `movie` | `default`, `detailed` | `en`, `fr`, `es` |
| `series` | `default`, `detailed` | `en`, `fr`, `es` |
| `single_episode` | `default`, `detailed` | `en`, `fr`, `es` |

Framekit auto-selects the scope based on the detected media kind. You can override the style:

```bash
fk nfo /release --template detailed
```

### Template variables

**`release` object (`ReleaseNfoData`):**

| Variable | Type | Contains |
|----------|------|---------|
| `release.release_title` | string | Full release name |
| `release.title_display` | string | Clean display title |
| `release.series_title` | string | Series name (if applicable) |
| `release.year` | string | Year |
| `release.source` | string | Source tag (e.g., `BluRay`, `WEB-DL`) |
| `release.resolution` | string | Resolution (e.g., `1080p`) |
| `release.video_tag` | string | Video codec tag |
| `release.audio_tag` | string | Primary audio tag |
| `release.language_tag` | string | Language tag (e.g., `MULTI.VFF`) |
| `release.audio_languages_display` | string | Human-readable audio languages |
| `release.hdr_display` | string | HDR format string |
| `release.team` | string | Release group name |
| `release.episodes` | list | List of `EpisodeNfoData` |
| `release.total_size_bytes` | int | Total release size |
| `release.total_duration_ms` | int | Total duration in milliseconds |
| `release.media_kind` | string | `movie`, `single_episode`, `season_pack`, `special_pack`, `anime` |
| `release.subtitle_summary_lines` | list | Subtitle track summary lines |

**Per-episode (`EpisodeNfoData`):**

| Variable | Contains |
|----------|---------|
| `.file_name` | Filename |
| `.size_bytes` | File size |
| `.duration_ms` | Duration in ms |
| `.overall_bitrate_kbps` | Overall bitrate |
| `.resolution` | Resolution string |
| `.aspect_ratio_display` | Aspect ratio |
| `.video_codec` | Video codec |
| `.hdr_display` | HDR format |
| `.audio_tracks` | List of `TrackNfoData` |
| `.subtitle_summary` | Subtitle track summary |

**Metadata (injected when metadata fetching succeeds):**

| Variable | Contains |
|----------|---------|
| `metadata_movie` | Movie object: `.title`, `.imdb_id`, `.external_url`, `.genres`, `.runtime_minutes`, `.overview` |
| `metadata_episode` | Episode object |
| `metadata_season` | Season object |
| `metadata_episode_map` | `{episode_code: episode_metadata}` |
| `logo_text` | Contents of the active logo file |

### Built-in macros (`_macros.jinja2`)

| Macro | Renders |
|-------|---------|
| `ui.section(title)` | Section header separator |
| `ui.line(label, value)` | Key-value line |
| `ui.yesno(bool)` | "Yes" / "No" string |
| `filesize` filter | Human-readable file size |
| `duration_ms` filter | Human-readable duration |
| `bitrate_kbps` filter | Human-readable bitrate |

### Importing custom templates

```bash
fk nfo --import-template /path/to/my.jinja2 --import-name "My Template" --import-scope movie
fk nfo --list-templates
fk nfo --template "My Template"
```

User-imported templates take precedence over bundled ones.

---

## Prez BBCode templates

**Location:** `src/framekit/templates/prez/bbcode/`
**Naming:** `{name}.{locale}.jinja2`
**Locales:** `en`, `fr`, `es`

### Available templates

| Template | Style |
|----------|-------|
| `classic` | Standard with all sections: info, synopsis, metadata, release, technical, audio, subtitles |
| `detailed` | Expanded, with full per-track details |
| `compact` | Condensed single-block format with bullet points |
| `technical` | Technical specs focused, with video fields |
| `cinematic` | Technical summary + synopsis in a cinematic layout |
| `tracker` | Minimal tracker-upload format |
| `spoiler` | Content inside `[spoiler=...]` tags |
| `boxed` | Sections in `[quote]` boxes |

### Template variables (`data: PrezData`)

| Variable | Contains |
|----------|---------|
| `data.title` | Release title |
| `data.year` | Year |
| `data.season_label` | Season label (e.g., `Season 2`) |
| `data.heading_subtitle` | Episode heading subtitle |
| `data.season_episode_range` | Episode range (e.g., `S01E01-E12`) |
| `data.poster_url` | Poster image URL |
| `data.banner_information` | Banner URL for the Information section |
| `data.banner_synopsis` | Banner URL for the Synopsis section |
| `data.banner_metadata` | Banner URL for the Metadata section |
| `data.banner_release` | Banner URL for the Release section |
| `data.banner_technical` | Banner URL for the Technical section |
| `data.banner_audio` | Banner URL for the Audio section |
| `data.banner_subtitles` | Banner URL for the Subtitles section |
| `data.info_fields` | List of `PrezField` (label + value) |
| `data.overview` | Synopsis text |
| `data.metadata_fields` | Metadata fields |
| `data.cast` | Cast string |
| `data.crew` | Crew string |
| `data.release_fields` | Release fields |
| `data.video_fields` | Video detail fields |
| `data.audio_tracks` | List of `PrezTrack` |
| `data.subtitle_tracks` | List of `PrezTrack` |
| `data.technical_summary` | One-line technical summary |
| `data.mediainfo_text` | Raw MediaInfo output (when enabled) |
| `data.has_metadata_section` | `true` if metadata is available |

### Jinja2 functions in BBCode templates

| Function | Returns |
|----------|---------|
| `bb(text)` | BBCode-escaped text |
| `bbcode_banner(url)` | `[img]url[/img]` banner tag |
| `field_url_bbcode(field)` | Field value with optional URL |
| `audio_table_bbcode(tracks)` | Formatted audio track table |
| `subtitle_table_bbcode(tracks)` | Formatted subtitle track table |
| `mediainfo_spoiler(text)` | Content wrapped in spoiler tags |
| `tr(key, default)` | I18n translated string |

### Banner images

Banners are image headers for each section. They are fetched from the online catalog on the `feature/banners` branch. Select a design interactively:

```bash
fk prez /release --select-templates
```

Or configure in `framekit.yaml`:

```yaml
modules:
  prez:
    preset: default    # banner_design is part of the preset
```

---

## Prez HTML templates

**Location:** `src/framekit/templates/prez/html/generated/`
**Count:** 140 templates (10 designs × 14 color variants)

### Designs

`cinematic`, `magazine`, `minimal`, `card`, `timeline`, `glassmorphism`, `brutalist`, `neon_cyberpunk`, `vintage_retro`, `neumorphism`

### Color variants

`dark`, `forest`, `sunset`, `ocean`, `sepia`, `rainbow`, `midnight`, `cherry`, `lavender`, `mint`, `amber`, `slate`, `coral`, `teal`

Full template name: `{design}_{color}` — e.g., `cinematic_dark`, `magazine_ocean`, `brutalist_amber`.

### Common aliases

| Alias | Resolves to |
|-------|-------------|
| `cinema` | `cinematic_dark` |
| `magazine` | `magazine_dark` |
| `minimal` | `minimal_dark` |
| `neon` | `neon_cyberpunk_dark` |
| `poster` | `card_dark` |
| `timeline` | `timeline_dark` |

### Prez presets

Presets bundle a format, HTML template, BBCode template, and mediainfo mode:

| Preset | Format | HTML | BBCode | MediaInfo |
|--------|--------|------|--------|-----------|
| `default` | both | `minimal_dark` | `classic` | none |
| `tracker` | bbcode | `magazine_dark` | `tracker` | none |
| `compact` | bbcode | `minimal_dark` | `compact` | none |
| `detailed` | both | `magazine_dark` | `detailed` | none |
| `premium` | both | `cinematic_dark` | `cinematic` | none |
| `technical` | both | `minimal_dark` | `technical` | inline |

```bash
fk prez /release --preset premium
fk prez /release --preset technical
```
