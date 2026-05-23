from __future__ import annotations

import sys
import uuid
from pathlib import Path

from framekit.core.audit_log import append_audit_event
from framekit.core.i18n import tr
from framekit.core.models.renamer import RenamePlanItem
from framekit.core.reporting import OperationReport
from framekit.core.runs.ledger import new_run_id, record_move
from framekit.modules.renamer.planner import build_rename_plan
from framekit.modules.renamer.profiles import RenamerProfile


class RenamerService:
    """Service for renamer."""

    def build_plan(
        self,
        folder: Path,
        *,
        default_lang: str,
        force_lang: bool,
        remove_terms: tuple[str, ...] = (),
        insert_after_pairs: tuple[tuple[str, str], ...] = (),
        profile: RenamerProfile | None = None,
    ) -> list[RenamePlanItem]:
        """Build plan."""
        return build_rename_plan(
            folder,
            default_lang=default_lang,
            force_lang=force_lang,
            remove_terms=remove_terms,
            insert_after_pairs=insert_after_pairs,
            profile=profile,
        )

    def _apply_case_only_rename(self, source: Path, target: Path) -> None:
        temp_name = f".__framekit_tmp__{uuid.uuid4().hex}{source.suffix}"
        temp_path = source.with_name(temp_name)
        source.rename(temp_path)
        temp_path.rename(target)

    @staticmethod
    def _status_message(*, item, apply_changes: bool) -> tuple[str, str]:
        if item.case_only:
            status = "case-only" if apply_changes else "planned-case-only"
            message = (
                tr("renamer.message.case_only_applied", default="Case-only rename applied.")
                if apply_changes
                else tr("renamer.message.case_only_prepared", default="Case-only rename prepared.")
            )
            return status, message

        status = "renamed" if apply_changes else "planned"
        message = (
            tr("renamer.message.rename_applied", default="Rename applied.")
            if apply_changes
            else tr("renamer.message.rename_prepared", default="Rename prepared.")
        )
        return status, message

    def _record_collision(self, report: OperationReport, item: RenamePlanItem) -> None:
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

    def _record_unchanged(self, report: OperationReport, item: RenamePlanItem) -> None:
        report.skipped += 1
        report.add_detail(
            file=item.source.name,
            action="rename",
            status="unchanged",
            message=tr("renamer.message.already_normalized", default="Name already normalized."),
            before={"name": item.source.name},
            after={"name": item.target.name},
        )

    def _apply_move(self, *, run_id: str, item: RenamePlanItem) -> None:
        if item.case_only:
            self._apply_case_only_rename(item.source, item.target)
        else:
            item.source.rename(item.target)
        record_move(run_id=run_id, module="renamer", src=item.source, dst=item.target)
        append_audit_event(
            action="rename",
            module="renamer",
            run_id=run_id,
            payload={"src": str(item.source), "dst": str(item.target)},
        )

    def _record_success(
        self, report: OperationReport, item: RenamePlanItem, *, apply_changes: bool
    ) -> None:
        report.modified += 1
        status, message = self._status_message(item=item, apply_changes=apply_changes)
        report.add_detail(
            file=item.source.name,
            action="rename",
            status=status,
            message=message,
            before={"name": item.source.name},
            after={"name": item.target.name},
        )

    def _process_item(
        self,
        *,
        report: OperationReport,
        item: RenamePlanItem,
        run_id: str,
        apply_changes: bool,
    ) -> None:
        if item.collision:
            self._record_collision(report, item)
            return
        if not item.changed:
            self._record_unchanged(report, item)
            return
        if apply_changes:
            self._apply_move(run_id=run_id, item=item)
        self._record_success(report, item, apply_changes=apply_changes)

    def run_plan(
        self,
        plan: list[RenamePlanItem],
        *,
        apply_changes: bool,
    ) -> OperationReport:
        """Execute a pre-built (and optionally mutated) rename plan."""
        run_id = new_run_id("renamer")
        report = OperationReport(tool="renamer")
        report.scanned = len(plan)

        for item in plan:
            report.processed += 1
            self._process_item(
                report=report,
                item=item,
                run_id=run_id,
                apply_changes=apply_changes,
            )

        if apply_changes:
            report.outputs.append(f"run_id={run_id}")
        return report

    def run(
        self,
        folder: Path,
        *,
        default_lang: str,
        apply_changes: bool,
        force_lang: bool,
        remove_terms: tuple[str, ...] = (),
        insert_after_pairs: tuple[tuple[str, str], ...] = (),
        profile: RenamerProfile | None = None,
    ) -> OperationReport:
        """Handle run."""
        run_id = new_run_id("renamer")
        plan = self.build_plan(
            folder,
            default_lang=default_lang,
            force_lang=force_lang,
            remove_terms=remove_terms,
            insert_after_pairs=insert_after_pairs,
            profile=profile,
        )
        report = OperationReport(tool="renamer")
        report.scanned = len(plan)

        # Headless mode: warn and suppress renames that would upgrade a
        # single-language tag to MULTI.* — the user must resolve interactively.
        if apply_changes and not sys.stdin.isatty():
            from framekit.ui.console import print_warning

            for i, item in enumerate(plan):
                if item.multi_language_detected and item.changed:
                    print_warning(
                        tr(
                            "renamer.warn.multi_lang_ambiguous",
                            default=(
                                "{file}: multiple audio tracks detected but filename tag is"
                                " '{tag}'. Skipping rename — run interactively to resolve."
                            ),
                            file=item.source.name,
                            tag=item.existing_language_tag or "?",
                        )
                    )
                    # Suppress the rename for this item — leave file unchanged.
                    plan[i].changed = False

        for item in plan:
            report.processed += 1
            self._process_item(
                report=report,
                item=item,
                run_id=run_id,
                apply_changes=apply_changes,
            )

        if apply_changes:
            report.outputs.append(f"run_id={run_id}")
        return report
