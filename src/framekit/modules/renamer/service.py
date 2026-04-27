from __future__ import annotations

import uuid
from pathlib import Path

from framekit.core.i18n import tr
from framekit.core.models.renamer import RenamePlanItem
from framekit.core.reporting import OperationReport
from framekit.modules.renamer.planner import build_rename_plan


class RenamerService:
    def build_plan(
        self,
        folder: Path,
        *,
        default_lang: str,
        force_lang: bool,
        remove_terms: tuple[str, ...] = (),
    ) -> list[RenamePlanItem]:
        return build_rename_plan(
            folder,
            default_lang=default_lang,
            force_lang=force_lang,
            remove_terms=remove_terms,
        )

    def _apply_case_only_rename(self, source: Path, target: Path) -> None:
        temp_name = f".__framekit_tmp__{uuid.uuid4().hex}{source.suffix}"
        temp_path = source.with_name(temp_name)
        source.rename(temp_path)
        temp_path.rename(target)

    def run(
        self,
        folder: Path,
        *,
        default_lang: str,
        apply_changes: bool,
        force_lang: bool,
        remove_terms: tuple[str, ...] = (),
    ) -> OperationReport:
        plan = self.build_plan(
            folder,
            default_lang=default_lang,
            force_lang=force_lang,
            remove_terms=remove_terms,
        )
        report = OperationReport(tool="renamer")
        report.scanned = len(plan)

        for item in plan:
            report.processed += 1

            if item.collision:
                report.skipped += 1
                report.add_error(
                    "rename_collision",
                    tr(
                        "renamer.error.target_conflict",
                        default="Target already exists or conflicts: {target}",
                        target=item.target.name,
                    ),
                    source=str(item.source),
                    target=str(item.target),
                )
                report.add_detail(
                    file=item.source.name,
                    action="rename",
                    status="collision",
                    message=tr(
                        "renamer.message.target_conflict",
                        default="Target conflict: {target}",
                        target=item.target.name,
                    ),
                    before={"name": item.source.name},
                    after={"name": item.target.name},
                )
                continue

            if not item.changed:
                report.skipped += 1
                report.add_detail(
                    file=item.source.name,
                    action="rename",
                    status="unchanged",
                    message=tr(
                        "renamer.message.already_normalized", default="Name already normalized."
                    ),
                    before={"name": item.source.name},
                    after={"name": item.target.name},
                )
                continue

            if apply_changes:
                if item.case_only:
                    self._apply_case_only_rename(item.source, item.target)
                else:
                    item.source.rename(item.target)

            report.modified += 1

            if item.case_only:
                status = "case-only" if apply_changes else "planned-case-only"
                message = (
                    tr("renamer.message.case_only_applied", default="Case-only rename applied.")
                    if apply_changes
                    else tr(
                        "renamer.message.case_only_prepared", default="Case-only rename prepared."
                    )
                )
            else:
                status = "renamed" if apply_changes else "planned"
                message = (
                    tr("renamer.message.rename_applied", default="Rename applied.")
                    if apply_changes
                    else tr("renamer.message.rename_prepared", default="Rename prepared.")
                )

            report.add_detail(
                file=item.source.name,
                action="rename",
                status=status,
                message=message,
                before={"name": item.source.name},
                after={"name": item.target.name},
            )

        return report
