from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FramekitWarning:
    code: str
    message: str
    source: str = "framekit"


class WarningCollector:
    def __init__(self) -> None:
        self._items: list[FramekitWarning] = []

    def add(self, code: str, message: str, *, source: str = "framekit") -> None:
        self._items.append(FramekitWarning(code=code, message=message, source=source))

    def extend(self, warnings: list[FramekitWarning]) -> None:
        self._items.extend(warnings)

    @property
    def items(self) -> tuple[FramekitWarning, ...]:
        return tuple(self._items)

    def __bool__(self) -> bool:
        return bool(self._items)
