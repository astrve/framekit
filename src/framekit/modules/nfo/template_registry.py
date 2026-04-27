from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from filelock import FileLock

from framekit.core.paths import get_lock_dir, get_nfo_template_registry_file

VALID_TEMPLATE_SCOPES = (
    "movie",
    "single_episode",
    "season_pack",
    "universal",
)


@dataclass(slots=True)
class NfoTemplateRecord:
    display_name: str
    template_name: str
    source: str
    scope: str
    file_path: str | None = None


def builtin_template_records() -> list[NfoTemplateRecord]:
    return [
        NfoTemplateRecord(
            display_name="Default",
            template_name="default",
            source="builtin",
            scope="universal",
            file_path=None,
        ),
        NfoTemplateRecord(
            display_name="Detailed",
            template_name="detailed",
            source="builtin",
            scope="universal",
            file_path=None,
        ),
    ]


class NfoTemplateRegistry:
    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path else get_nfo_template_registry_file()
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

    def load_custom(self) -> list[NfoTemplateRecord]:
        rows = self._load_raw()
        return [NfoTemplateRecord(**row) for row in rows]

    def save_custom(self, records: list[NfoTemplateRecord]) -> None:
        self._save_raw([asdict(record) for record in records])

    def register(self, record: NfoTemplateRecord) -> None:
        records = self.load_custom()
        records = [item for item in records if item.template_name != record.template_name]
        records.append(record)
        self.save_custom(records)

    def list_all(self) -> list[NfoTemplateRecord]:
        return builtin_template_records() + self.load_custom()

    def find(self, template_name: str) -> NfoTemplateRecord | None:
        for item in self.list_all():
            if item.template_name == template_name:
                return item
        return None


def scope_matches(scope: str, media_kind: str) -> bool:
    return scope == "universal" or scope == media_kind
