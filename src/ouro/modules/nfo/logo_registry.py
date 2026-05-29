from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from filelock import FileLock

from ouro.core.paths import get_bundled_nfo_logos_dir, get_lock_dir, get_nfo_logo_registry_file


@dataclass(slots=True)
class NfoLogoRecord:
    """Nfo logo record."""

    display_name: str
    logo_name: str
    file_path: str


class NfoLogoRegistry:
    """Registry of nfo logo."""

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

    @staticmethod
    def _scan_bundled() -> list[NfoLogoRecord]:
        """Scan bundled logos shipped with the package."""
        bundled_dir = get_bundled_nfo_logos_dir()
        if not bundled_dir.is_dir():
            return []
        records: list[NfoLogoRecord] = []
        for path in sorted(bundled_dir.iterdir()):
            if path.suffix.lower() in {".txt", ".nfo", ".asc"} and path.is_file():
                records.append(
                    NfoLogoRecord(
                        display_name=path.stem.replace("_", " ").title(),
                        logo_name=f"bundled:{path.stem}",
                        file_path=str(path),
                    )
                )
        return records

    def load_all(self) -> list[NfoLogoRecord]:
        """Load all logos (bundled + user-imported)."""
        bundled = self._scan_bundled()
        user = [NfoLogoRecord(**row) for row in self._load_raw()]
        return bundled + user

    def save_all(self, records: list[NfoLogoRecord]) -> None:
        """Save all."""
        self._save_raw([asdict(record) for record in records])

    def register(self, record: NfoLogoRecord) -> None:
        """Handle register."""
        records = self.load_all()
        records = [item for item in records if item.logo_name != record.logo_name]
        records.append(record)
        self.save_all(records)

    def find(self, logo_name: str) -> NfoLogoRecord | None:
        """Find a logo by name (searches bundled and user logos)."""
        for record in self.load_all():
            if record.logo_name == logo_name:
                return record
        return None
