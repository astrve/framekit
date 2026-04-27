# Framekit

[Framekit](https://github.com/astrve/framekit) is a CLI‑first, headless‑friendly toolkit for preparing media releases. Created by **astrve**.

## License

Framekit is distributed under the terms of the GNU General Public License v3.0.

Copyright (C) 2026 astrve

See the [LICENSE](LICENSE) file for details.

## Installation

Framekit requires **Python 3.11** or newer. Install the latest release from PyPI with:

```bash
pip install framekit-cli
```

If you want to use the latest development version directly from GitHub, install with:

```bash
pip install git+https://github.com/astrve/framekit.git
```

## Quickstart

1. Inspect your release folder to detect missing files and see what would be changed:

    ```bash
    fk inspect "Release folder"
    ```
2. Run the full pipeline in preview mode to see planned changes without modifying anything:

    ```bash
    fk pipe "Release folder" --preview
    ```
3. When satisfied, run the pipeline to apply the changes and generate NFO/Prez/Torrent artifacts:

    ```bash
    fk pipe "Release folder"
    ```

These quickstart commands orchestrate all modules. You can also call individual modules (e.g. ``fk ren``, ``fk cmk``, ``fk nfo``, ``fk prez``, ``fk torrent``) as shown below.

## Core workflow

```bash
fk inspect "Release folder"
fk ren "Release folder"
fk cmk "Release folder"
fk nfo "Release folder"
fk prez "Release folder"
fk torrent "Release folder"
fk pipe "Release folder"
```

## Recommended pipeline

```bash
fk setup
fk pipe "Release folder" --preview
fk pipe "Release folder"
```

The pipeline can run all modules or a subset:

```bash
fk pipe "Release folder" --modules cleanmkv,nfo,prez,torrent
fk pipe "Release folder" -nm
```

## CleanMKV

CleanMKV prepares a payload folder under `Release/<release-name>/`. The release name is derived from the MKV filename. For season packs, the episode token is removed from the first MKV name.

```bash
fk cmk "Release folder"
fk cmk "Release folder" --details
fk cmk "Release folder" --apply --preset multi
```

CleanMKV writes cleaned MKV files into a dedicated subfolder named `Release/<release>` where
`<release>` is derived from the first MKV name and sanitised to remove any characters
illegal on your platform (colons, question marks, etc.). For season packs, the episode
token (for example, `E03`) is removed from the name. The same sanitisation helper is used
throughout the pipeline so that NFO, Prez and Torrent always operate on the same
payload folder. You can override the output folder name pattern via the
`modules.cleanmkv.output_dir_name` setting; the placeholder `{release}` will be
replaced with the sanitised release name.

## Renamer

```bash
fk ren "Release folder"
fk ren "Release folder" --details
fk ren "Release folder" --apply
```

## Torrent

Configure one or more announce URLs:

```bash
fk torrent --add-announce https://tracker.example/announce
fk torrent --list-announces
fk torrent --select-announce
```

Create a torrent:

```bash
fk torrent "Release/Release.Name"
```
### Content modes

Framekit detects the media payload to include in a torrent so that sidecar files (NFO,
TXT, Prez HTML/BBCode, screenshots) are ignored by default. You can control this via
the `--content` option:

- `auto` (default) – detect the payload automatically: include only the MKV files from
  the detected release or season pack;
- `media` – include only recognised media files (MKV, MP4, M4V, AVI);
- `folder` – include everything in the folder, including sidecars (except existing `.torrent` files);
- `select` – interactively choose one of several detected media groups when multiple
  candidates exist.

You can also override the default mode by configuring `modules.torrent.content_mode` in
`settings.json` or by passing `--content` on the CLI. When running in headless mode,
ambiguous payloads will cause an error instead of silently selecting a default.

Torrent filenames are derived from the payload name using the same sanitisation logic
as CleanMKV and never keep the `.mkv` suffix.

## Prez

```bash
fk prez "Release folder"
fk prez "Release folder" --list-templates
fk prez "Release folder" --html-template timeline --bbcode-template tracker
```

Metadata is enabled by default. Disable it with:

```bash
fk prez "Release folder" -nm
fk nfo "Release folder" -nm
fk pipe "Release folder" -nm
```

## Diagnostics

```bash
fk doctor
fk settings
fk inspect "Release folder"
```

## External tools

Required for the full workflow:

- `mediainfo`
- `mkvmerge`

Framekit does not require `ffmpeg`, `ffprobe`, `aria2c`, or `n_m3u8dl_re`.


## Settings and security

Framekit stores user-specific configuration and metadata in a settings file located in your platform's user config directory (for example, `~/.config/framekit/settings.json` on Linux).
Do **not** commit this file to version control, as it may contain API keys and private torrent announce URLs. When printing settings via `fk settings` or diagnostics via `fk doctor`,
secret values are redacted so that API keys and tokens are never displayed in plain text.
Logs and debug output follow the same redaction rules.

**Headless vs interactive**: When running commands in a non-interactive environment (such as in a CI pipeline), Framekit operates in headless mode. In headless mode, any operation that would normally prompt the user to make a selection (such as choosing between multiple detected payloads or selecting a template) will instead raise a clear error. To avoid ambiguity, you can explicitly choose the payload detection mode with `--content` (`auto`, `media` or `folder`) or enable interactive selection with `--select-content`. Use `--preview` to see planned changes without writing files, and `--apply` to commit the changes.

## License

Framekit is distributed under the terms of the **MIT License**. See the [LICENSE](LICENSE) file for the full license text.

### Important flags

- `--preview`: Show what would be done without applying changes.
- `--apply`: Perform the operation and write files.
- `--details`: Show detailed per-file information.
- `--dry-run`: For the renamer, shows the planned renames without renaming any files.
- `--no-metadata`: Skip metadata downloading and embedding for NFO and Prez.
- `--content <mode>`: Choose the payload detection mode for torrent creation (`auto`, `media`, `folder`).
- `--select-content`: Interactively choose one of several detected payloads when multiple candidates exist.
