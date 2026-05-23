# Templates

Framekit uses Jinja2 templates for NFO files and presentations.

---

## NFO templates

Location: `src/framekit/templates/nfo/`

### Jinja2 environment

- `trim_blocks=False`, `lstrip_blocks=False`
- `SandboxedEnvironment` (no arbitrary code execution)
- Auto-escaping disabled (NFO output is plain text)

### Available variables

| Variable | Type | Description |
|----------|------|-------------|
| `release` | `Release` | Scanned release object |
| `metadata` | `MetadataContext \| None` | TMDb metadata |
| `title` | `str` | Resolved display title |
| `year` | `str \| None` | Release year |
| `quality` | `str` | Detected quality string |
| `codec` | `str` | Video codec |
| `audio_tracks` | `list[AudioTrack]` | All audio tracks |
| `subtitle_tracks` | `list[SubtitleTrack]` | All subtitle tracks |
| `mediainfo_text` | `str` | Raw MediaInfo output |
| `nfo_version` | `str` | Framekit version |

### Macros

| Macro | Description |
|-------|-------------|
| `audio_table(tracks)` | Render a text-art audio track table |
| `subtitle_table(tracks)` | Render a text-art subtitle track table |
| `separator(char, width)` | Draw a horizontal rule |

### Custom templates

Place a `.j2` or `.jinja2` file in `~/.config/framekit/nfo_templates/` and reference it with `--template <name>`.

---

## BBCode templates (Prez)

Location: `src/framekit/templates/prez/bbcode/`

Naming convention: `{template}.{language}.jinja2`

Available: `classic.en`, `classic.fr`, `classic.es`, `detailed.en`, `detailed.fr`, `detailed.es`, `tracker.en`, `tracker.fr`, `tracker.es`

### Jinja2 environment

- `trim_blocks=True`, `lstrip_blocks=True`
- Note: `trim_blocks` eats the newline after `{% %}` tags. When you need a blank line after a conditional block, add an extra blank line in the template.

### Template variables

All under the `data` object:

| Variable | Description |
|----------|-------------|
| `data.title` | Release title |
| `data.year` | Release year |
| `data.season_label` | Season label for series, or `'-'` |
| `data.heading_subtitle` | Subtitle or `'-'` |
| `data.season_episode_range` | Episode range or `'-'` |
| `data.poster_url` | Poster image URL or `'-'` |
| `data.technical_summary` | One-line technical summary |
| `data.video_fields` | List of `LabeledField` for video section |
| `data.audio_tracks` | List of audio track objects |
| `data.subtitle_tracks` | List of subtitle track objects |
| `data.info_fields` | List of `LabeledField` for information section |
| `data.metadata_fields` | List of `LabeledField` for metadata section |
| `data.release_fields` | List of `LabeledField` for release section |
| `data.synopsis` | Overview text |
| `data.mediainfo_text` | Raw MediaInfo output |
| `data.banner_*` | Banner URL for each section (empty string = no banner) |

Banner variables:

| Variable | Section |
|----------|---------|
| `data.banner_audio` | Audio section header |
| `data.banner_information` | Information section header |
| `data.banner_metadata` | Metadata section header |
| `data.banner_release` | Release section header |
| `data.banner_subtitles` | Subtitles section header |
| `data.banner_synopsis` | Synopsis section header |
| `data.banner_technical` | Technical section header |

### Jinja2 functions

| Function | Description |
|----------|-------------|
| `bb(value)` | Escape BBCode-unsafe characters |
| `bbcode_banner(url)` | Render `[img]url[/img]` or empty string |
| `field_url_bbcode(field)` | Render a field value with URL if present |
| `audio_table_bbcode(tracks)` | Render BBCode audio table |
| `subtitle_table_bbcode(tracks)` | Render BBCode subtitle table |
| `mediainfo_spoiler(text)` | Wrap MediaInfo in a `[spoiler]` block |
| `tr(key, default, **kwargs)` | Internationalized string |

### Banner pattern

Use this pattern in templates to support both image and text-only modes:

```jinja2
{% if data.banner_audio %}{{ bbcode_banner(data.banner_audio) }}{% else %}[size=14][b]{{ tr('prez.section.audio', default='Audio') }}[/b][/size]{% endif %}
```

---

## HTML templates (Prez)

Location: `src/framekit/templates/prez/html/`

Over 140 template variants organized by design and color.

### Structure

```
html/
  {design}/
    {color}/
      index.html.jinja2
      style.css
```

### Available designs

`astro`, `cinema`, `dark-fantasy`, `diagonal`, `digital`, `folder`, `gold-frame`, `iron-man`, `large-basic`, `leaf`, `linear`, `metal-frame`, `military`, `minimal`, `mojave`, `movie-custom`, `old-label`, `ores`, `oval`, `palace`, `patterns`, `robotic`, `spectral`, `wavy`, `white-steel`

### Color aliases

Many designs ship multiple color variants:

| Design | Colors |
|--------|--------|
| `cinema` | `pink`, `purple` |
| `gold-frame` | `black`, `green` |
| `robotic` | `grey`, `purple` |
| `spectral` | `blue_and_purple` |

### Template variables (HTML)

Same as BBCode `data` object, plus:

| Variable | Description |
|----------|-------------|
| `data.screenshots` | List of screenshot paths/URLs |
| `data.design` | Active design name |
| `data.color` | Active color variant |
