from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from filelock import FileLock

from framekit.core.models.metadata import MetadataCandidate
from framekit.core.models.nfo import ReleaseNfoData
from framekit.core.paths import get_lock_dir, get_metadata_choice_store_file


@dataclass(slots=True)
class StoredMetadataChoice:
    provider_name: str
    provider_id: str
    kind: str
    title: str
    year: str | None
    season_number: int | None = None
    episode_number: int | None = None
    imdb_id: str | None = None
    external_url: str | None = None


def build_release_signature(release: ReleaseNfoData) -> str:
    if release.media_kind == "movie":
        return " | ".join(
            [
                "movie",
                (release.title_display or "").strip().lower(),
                (release.year or "").strip(),
            ]
        )

    if release.media_kind == "single_episode":
        episode = release.episodes[0] if release.episodes else None
        episode_code = episode.episode_code if episode else ""
        return " | ".join(
            [
                "single_episode",
                (release.series_title or "").strip().lower(),
                (release.year or "").strip(),
                (episode_code or "").strip().upper(),
            ]
        )

    if release.media_kind == "season_pack":
        episode_codes = sorted(
            episode.episode_code.strip().upper()
            for episode in release.episodes
            if episode.episode_code
        )
        season_hint = episode_codes[0][:3] if episode_codes else ""
        return " | ".join(
            [
                "season_pack",
                (release.series_title or "").strip().lower(),
                (release.year or "").strip(),
                season_hint,
                ",".join(episode_codes),
            ]
        )

    return " | ".join(
        [
            release.media_kind,
            (release.release_title or "").strip().lower(),
        ]
    )


class MetadataChoiceStore:
    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path else get_metadata_choice_store_file()
        self.lock = FileLock(str(get_lock_dir() / f"{self.path.name}.lock"))

    def _load_raw(self) -> dict:
        with self.lock:
            if not self.path.exists():
                return {}

            try:
                return json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:
                return {}

    def _save_raw(self, data: dict) -> None:
        with self.lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(
                json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )

    def get(self, release: ReleaseNfoData) -> StoredMetadataChoice | None:
        data = self._load_raw()
        signature = build_release_signature(release)
        raw = data.get(signature)
        if not raw:
            return None
        return StoredMetadataChoice(**raw)

    def set(self, release: ReleaseNfoData, candidate: MetadataCandidate) -> None:
        data = self._load_raw()
        signature = build_release_signature(release)

        data[signature] = asdict(
            StoredMetadataChoice(
                provider_name=candidate.provider_name,
                provider_id=candidate.provider_id,
                kind=candidate.kind,
                title=candidate.title,
                year=candidate.year,
                season_number=candidate.season_number,
                episode_number=candidate.episode_number,
                imdb_id=candidate.imdb_id,
                external_url=candidate.external_url,
            )
        )
        self._save_raw(data)

    def clear(self, release: ReleaseNfoData) -> None:
        data = self._load_raw()
        signature = build_release_signature(release)
        if signature in data:
            del data[signature]
            self._save_raw(data)
