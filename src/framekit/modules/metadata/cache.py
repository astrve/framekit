from __future__ import annotations

import json
import time
from dataclasses import asdict
from pathlib import Path

from filelock import FileLock

from framekit.core.models.metadata import MetadataCandidate, MetadataLookupRequest
from framekit.core.paths import get_lock_dir, get_metadata_cache_file


class MetadataCache:
    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path else get_metadata_cache_file()
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

    def _key(self, provider_name: str, request: MetadataLookupRequest) -> str:
        bits = [
            provider_name.strip().lower(),
            request.media_kind.strip().lower(),
            (request.title or "").strip().lower(),
            (request.year or "").strip(),
            str(request.season_number or ""),
            str(request.episode_number or ""),
        ]
        return " | ".join(bits)

    def get(
        self,
        provider_name: str,
        request: MetadataLookupRequest,
        ttl_hours: int,
    ) -> list[MetadataCandidate] | None:
        data = self._load_raw()
        key = self._key(provider_name, request)

        entry = data.get(key)
        if not entry:
            return None

        created_at = entry.get("created_at", 0)
        age_seconds = time.time() - created_at
        if age_seconds > ttl_hours * 3600:
            return None

        candidates_raw = entry.get("candidates", [])
        return [MetadataCandidate(**item) for item in candidates_raw]

    def set(
        self,
        provider_name: str,
        request: MetadataLookupRequest,
        candidates: list[MetadataCandidate],
    ) -> None:
        data = self._load_raw()
        key = self._key(provider_name, request)

        data[key] = {
            "created_at": time.time(),
            "request": asdict(request),
            "candidates": [asdict(item) for item in candidates],
        }
        self._save_raw(data)
