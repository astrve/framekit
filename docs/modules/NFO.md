# NFO Module

The NFO module generates `.nfo` files for media releases using Jinja2 templates populated with scan data and optional TMDb metadata.

---

## Basic usage

```bash
fk nfo /path/to/release
fk nfo /path/to/release --template detailed --locale fr
fk nfo /path/to/release --write --with-metadata
```

## Options

| Option | Default | Purpose |
|--------|---------|---------|
| `--template / -t STR` | `default` | Template name |
| `--locale` | `auto` | Output language (`auto`, `en`, `fr`, `es`) |
| `--write / -w` | off | Write immediately (non-interactive) |
| `--with-metadata / -m` | on | Enrich with TMDb metadata |
| `--metadata-auto-accept / -y` | off | Accept top metadata candidate |
| `--mode` | `global` | Output mode (`global`, `per_file`, `both`) |
| `--list-templates / -L` | off | List available templates |
| `--import-template / -it PATH` | — | Import a `.jinja2` template |
| `--import-name / -in STR` | — | Display name for imported template |
| `--import-scope / -is` | — | Scope: `movie`, `single_episode`, `season_pack`, `universal` |
| `--import-logo / -ig PATH` | — | Import a text logo file (`.txt`, `.nfo`, `.asc`) |
| `--set-logo / -sl STR` | — | Set active logo by internal name |
| `--list-logos / -lg` | off | List available logos |
| `--clear-logo / -cl` | off | Disable active logo |

---

## Output modes

| Mode | Behavior |
|------|---------|
| `global` | Single `<release>.nfo` for the entire release |
| `per_file` | One `<filename>.nfo` per `.mkv` file |
| `both` | Global + per-file in one run |

The pipeline uses a media-kind-aware policy:

| Media kind | Pipeline mode |
|------------|--------------|
| movie | sidecar NFO + global NFO |
| single_episode | sidecar NFO + global NFO |
| season_pack | per_file + global NFO |
| special_pack | per_file + global NFO |

---

## Template system

Templates live in `src/framekit/templates/nfo/`. Built-in templates:

| Template | Scope | Style |
|----------|-------|-------|
| `movie_default` | movie | default |
| `movie_detailed` | movie | detailed |
| `series_default` | series | default |
| `series_detailed` | series | detailed |
| `single_episode_default` | single_episode | default |
| `single_episode_detailed` | single_episode | detailed |

Import a custom template:

```bash
fk nfo --import-template /path/to/my.jinja2 \
       --import-name "Custom" \
       --import-scope movie
```

User-imported templates take precedence over bundled ones.

---

## Logos

A logo is a text art file (`.txt`, `.nfo`, `.asc`) prepended to the NFO output.

```bash
fk nfo --import-logo /path/to/logo.txt --logo-name "MyGroup"
fk nfo --set-logo "MyGroup"
fk nfo --list-logos
fk nfo --clear-logo
```

---

## Configuration

```yaml
modules:
  nfo:
    active_template: default
    locale: fr
    active_logo: MyGroup
    with_metadata: true
    mode: global
```

---

## Available variables in templates

See [Templates — NFO variables](../Templates.md#template-variables) for the full variable reference.
