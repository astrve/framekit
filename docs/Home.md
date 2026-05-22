# Framekit

Framekit is a CLI-first toolkit for preparing media releases from local folders.

Core workflow:

- inspect release folders
- rename files
- clean MKV tracks
- fetch metadata
- build NFO files
- build BBCode and HTML presentation files
- create torrents
- validate releases
- run pipelines and batches

Beta modules:

- `upload`
- `extract`
- `watch`

## Install

From source:

```bash
python -m venv .venv
pip install -e .
fk doctor
```

From GitHub Release:

```bash
framekit --version
framekit doctor
```

GitHub Release binaries include Framekit itself. External media tools remain separate system dependencies.

## External Tools

Install these and keep them on `PATH`:

- `ffmpeg`
- `ffprobe`
- `mkvmerge`
- `mkvextract`
- `mkvpropedit`
- `mediainfo`

## Configuration

```bash
fk setup
```

Or copy `framekit.example.yaml` to `framekit.yaml`.

`framekit.yaml` is ignored by Git because it may contain local paths or secrets.

## Security

Keep `security.enabled: true` to store sensitive values in the encrypted vault.

Run:

```bash
fk doctor
```

before release work or automation runs.
