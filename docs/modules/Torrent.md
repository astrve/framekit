# Torrent Module

The Torrent module creates `.torrent` files from release folders using the bencode-open library.

---

## Basic usage

```bash
fk torrent /path/to/release
fk torrent /path/to/release --announce https://tracker.example.com/announce
fk torrent /path/to/release --content auto --piece-length 1m
```

## Options

| Option | Default | Purpose |
|--------|---------|---------|
| `--output / -o PATH` | — | Output `.torrent` path |
| `--announce / -a STR` | — | Announce URL |
| `--private / --no-private` | private | Private torrent flag |
| `--piece-length STR` | `auto` | Piece length (`auto`, `512k`, `1m`, `2m`, `4m`, ...) |
| `--content` | `auto` | Payload mode: `auto`, `media`, `folder`, `select` |
| `--dry-run` | off | Preview only |

---

## Payload modes

| Mode | Includes |
|------|---------|
| `auto` | Detected MKV release or season pack only |
| `media` | All recognized media files (MKV, MP4, M4V, AVI) |
| `folder` | Everything except existing `.torrent` files |
| `select` | Interactive multi-group picker |

---

## Announce URL management

Framekit can save announce URLs to the vault for reuse:

```yaml
modules:
  torrent:
    announce: ""                   # default announce URL
    announce_urls: []              # multiple URLs
    private: true
    piece_length: auto
    prompt_save_announce: true     # prompt to save new URLs
```

The first time you use a new announce URL, Framekit offers to save it. Disable the prompt with `prompt_save_announce: false`.

---

## Piece length selection

| Option | Best for |
|--------|---------|
| `auto` | Let Framekit choose based on release size |
| `512k` | Small releases |
| `1m` | Standard releases (recommended for 1–10 GB) |
| `2m` | Large releases |
| `4m` | Very large multi-disc releases |
