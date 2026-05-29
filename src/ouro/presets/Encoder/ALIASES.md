# Encoder Preset Aliases

Ouro encoder presets can be loaded by file name or by alias.

## h264 to h265

| Preset file | Aliases | Description |
| --- | --- | --- |
| `films.yaml` | `f265`, `film265`, `movie265`, `f264-265`, `film264-265` | Movies, CRF 19, slow, main10 |
| `series.yaml` | `s265`, `serie265`, `tv265`, `s264-265`, `serie264-265` | TV series, CRF 21, medium, main10 |
| `animes_japonais.yaml` | `a265`, `anime265`, `jp265`, `a264-265`, `anime264-265` | Japanese anime, CRF 19, veryslow, tune animation, main10 |
| `documentaires.yaml` | `d265`, `doc265`, `docu265`, `d264-265`, `doc264-265` | Documentaries, CRF 22, medium, main |
| `series_animees.yaml` | `sa265`, `anim265`, `cartoon265`, `sa264-265`, `anim264-265` | Western animated series, CRF 20, slow, tune animation, main10 |

## h265 to h264

| Preset file | Aliases | Description |
| --- | --- | --- |
| `films.yaml` | `f264`, `film264`, `movie264` | Movies, CRF 19, slow, high |
| `series.yaml` | `s264`, `serie264`, `tv264` | TV series, CRF 21, medium, high |
| `animes_japonais.yaml` | `a264`, `anime264`, `jp264` | Japanese anime, CRF 19, veryslow, tune animation, high |
| `documentaires.yaml` | `d264`, `doc264`, `docu264` | Documentaries, CRF 22, medium, main |
| `series_animees.yaml` | `sa264`, `anim264`, `cartoon264` | Western animated series, CRF 20, slow, tune animation, high |

## Usage

```bash
ouro encode --preset f265 input.mkv
ouro encode --preset serie264 input.mkv
ouro encode --preset anime265 input.mkv
ouro encode --preset films input.mkv
```

Aliases are case-insensitive. The preset file name without extension always works.
