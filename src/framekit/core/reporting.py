from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class WarningItem:
    code: str
    message: str
    context: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ErrorItem:
    code: str
    message: str
    context: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class OperationDetail:
    file: str | None
    action: str
    status: str
    message: str = ""
    before: dict[str, Any] = field(default_factory=dict)
    after: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class OperationReport:
    tool: str
    scanned: int = 0
    processed: int = 0
    modified: int = 0
    skipped: int = 0
    warnings: list[WarningItem] = field(default_factory=list)
    errors: list[ErrorItem] = field(default_factory=list)
    details: list[OperationDetail] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def add_warning(self, code: str, message: str, **context: Any) -> None:
        self.warnings.append(WarningItem(code=code, message=message, context=context))

    def add_error(self, code: str, message: str, **context: Any) -> None:
        self.errors.append(ErrorItem(code=code, message=message, context=context))

    def add_detail(
        self,
        *,
        file: str | None,
        action: str,
        status: str,
        message: str = "",
        before: dict[str, Any] | None = None,
        after: dict[str, Any] | None = None,
    ) -> None:
        self.details.append(
            OperationDetail(
                file=file,
                action=action,
                status=status,
                message=message,
                before=before or {},
                after=after or {},
            )
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
