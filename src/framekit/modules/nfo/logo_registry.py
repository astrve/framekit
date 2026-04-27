from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from filelock import FileLock

from framekit.core.paths import get_lock_dir, get_nfo_logo_registry_file


@dataclass(slots=True)
class NfoLogoRecord:
    display_name: str
    logo_name: str
    file_path: str


class NfoLogoRegistry:
    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path else get_nfo_logo_registry_file()
        self.lock = FileLock(str(get_lock_dir() / f"{self.path.name}.lock"))

    def _load_raw(self) -> list[dict]:
        with self.lock:
            if not self.path.exists():
                return []

            try:
                return json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:
                return []

    def _save_raw(self, rows: list[dict]) -> None:
        with self.lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(
                json.dumps(rows, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )

    def load_all(self) -> list[NfoLogoRecord]:
        return [NfoLogoRecord(**row) for row in self._load_raw()]

    def save_all(self, records: list[NfoLogoRecord]) -> None:
        self._save_raw([asdict(record) for record in records])

    def register(self, record: NfoLogoRecord) -> None:
        records = self.load_all()
        records = [item for item in records if item.logo_name != record.logo_name]
        records.append(record)
        self.save_all(records)

    def find(self, logo_name: str) -> NfoLogoRecord | None:
        for record in self.load_all():
            if record.logo_name == logo_name:
                return record
        return None
