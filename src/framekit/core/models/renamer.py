from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class RenamePlanItem:
    source: Path
    target: Path
    reason: str
    changed: bool
    case_only: bool = False
    collision: bool = False

    inferred_video_tag: str | None = None
    inferred_audio_tag: str | None = None
    inferred_source: str | None = None
    inferred_resolution: str | None = None

    hdr_canonical: str | None = None
    hdr_release_label: str | None = None
    hdr_display_label: str | None = None

    existing_language_tag: str | None = None
    resulting_language_tag: str | None = None

    parsed_episode_code: str | None = None
    parsed_episode_title: str | None = None
