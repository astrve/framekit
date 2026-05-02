from __future__ import annotations

import re
from pathlib import Path

try:
    from pathvalidate import sanitize_filename  # type: ignore[import]
except ImportError:
    # Provide a minimal sanitize_filename fallback when pathvalidate is unavailable.
    import re as _re

    def sanitize_filename(filename: str, replacement_text: str = "_") -> str:
        """
        Sanitize a filename by replacing characters illegal on most filesystems.
        This fallback keeps alphanumeric characters, dots, dashes and underscores,
        and replaces any other sequence with the given replacement_text.
        """
        return _re.sub(r"[^A-Za-z0-9._-]+", replacement_text, filename)


from framekit.core.i18n import tr
from framekit.core.models.nfo import ReleaseNfoData
from framekit.core.reporting import OperationReport
from framekit.modules.nfo.builder import build_release_nfo
from framekit.modules.nfo.scanner import scan_nfo_folder
from framekit.modules.nfo.templates import render_template

INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*]+')


def _safe_output_name(name: str) -> str:
    cleaned = sanitize_filename(name, replacement_text="_").strip(" .")
    cleaned = INVALID_FILENAME_CHARS.sub("_", cleaned).strip(" .")
    return cleaned or "release"


def _load_logo_text(logo_path: str | None) -> str | None:
    if not logo_path:
        return None

    path = Path(logo_path)
    if not path.exists() or not path.is_file():
        return None

    content = path.read_text(encoding="utf-8", errors="replace")
    content = content.rstrip("\n\r")
    return content if content else None


def _resolve_template_name(requested_template: str, media_kind: str) -> str:
    if requested_template not in {"default", "detailed"}:
        return requested_template

    if media_kind == "movie":
        return f"movie_{requested_template}"

    if media_kind == "single_episode":
        return f"single_episode_{requested_template}"

    return f"series_{requested_template}"


class NfoService:
    def build_from_release(
        self,
        folder: Path,
        *,
        release: ReleaseNfoData,
        template_name: str,
        logo_path: str | None = None,
        template_locale: str = "en",
        extra_context: dict | None = None,
    ) -> tuple[OperationReport, ReleaseNfoData, str]:
        resolved_template_name = _resolve_template_name(template_name, release.media_kind)

        context = {
            "release": release,
            "episodes": release.episodes,
            "logo_text": _load_logo_text(logo_path),
            "metadata_movie": None,
            "metadata_episode": None,
            "metadata_season": None,
            "metadata_episode_map": {},
            "nfo_locale": template_locale,
            "episode_completeness": release.episode_completeness,
            "missing_episode_codes": release.missing_episode_codes,
        }
        if extra_context:
            context.update(extra_context)

        rendered = render_template(
            resolved_template_name,
            context,
            locale=template_locale,
        )

        report = OperationReport(tool="nfo")
        report.scanned = len(release.episodes)
        report.processed = len(release.episodes)
        report.modified = 1
        report.add_detail(
            file=None,
            action="nfo",
            status="built",
            message=tr(
                "nfo.message.built",
                default="NFO built with template '{template}'.",
                template=resolved_template_name,
            ),
            before={"folder": str(folder)},
            after={"template": resolved_template_name, "locale": template_locale},
        )

        return report, release, rendered

    def build_per_file(
        self,
        folder: Path,
        *,
        template_name: str,
        logo_path: str | None = None,
        template_locale: str = "en",
        extra_context: dict | None = None,
    ) -> list[tuple[OperationReport, ReleaseNfoData, str, Path]]:
        """
        Build one NFO per `.mkv` file in `folder`. Each MKV is wrapped in its
        own single-episode release, rendered through the
        single-episode/movie template family (depending on whether the file
        carries an episode code), and returned as a 4-tuple
        `(report, release, rendered_text, source_mkv_path)`.

        The metadata `extra_context` provided by the caller is reused as-is
        for every file. For series, the per-episode metadata (`metadata_episode_map`)
        is resolved from the global context if available so each rendered NFO
        gets its own `metadata_episode` value matching the episode code.
        """
        episodes = scan_nfo_folder(folder)
        if not episodes:
            raise ValueError(
                tr(
                    "nfo.error.no_mkv",
                    default="No MKV files found in folder: {folder}",
                    folder=folder,
                )
            )

        results: list[tuple[OperationReport, ReleaseNfoData, str, Path]] = []
        episode_map = (extra_context or {}).get("metadata_episode_map") or {}

        for episode in episodes:
            single_release = build_release_nfo(folder, [episode])
            # When the global context carries a per-episode map, scope it
            # down to *this* episode's code so the template's
            # `metadata_episode` slot reflects the right entry.
            per_file_extra = dict(extra_context or {})
            if episode.episode_code and episode.episode_code in episode_map:
                per_file_extra["metadata_episode"] = episode_map[episode.episode_code]
            # `metadata_episode_map` itself stays useful for templates that
            # display the whole season — leave it intact.
            report, release, rendered = self.build_from_release(
                folder,
                release=single_release,
                template_name=template_name,
                logo_path=logo_path,
                template_locale=template_locale,
                extra_context=per_file_extra,
            )
            results.append((report, release, rendered, episode.file_path))

        return results

    def write_per_file(
        self,
        folder: Path,
        *,
        results: list[tuple[OperationReport, ReleaseNfoData, str, Path]],
        template_name: str,
        template_locale: str = "en",
    ) -> tuple[OperationReport, list[Path]]:
        """
        Persist a list of per-file NFOs returned by `build_per_file`.

        Each NFO is written next to its source MKV using the MKV stem as the
        base name (`<stem>.nfo`). A consolidated `OperationReport` is
        returned with one detail line per file, suitable for surfacing in the
        CLI summary table.
        """
        report = OperationReport(tool="nfo")
        report.scanned = len(results)
        report.processed = len(results)

        outputs: list[Path] = []
        for _per_file_report, release, rendered, source_path in results:
            target = source_path.with_suffix(".nfo")
            target.write_text(rendered, encoding="utf-8")
            outputs.append(target)
            report.outputs.append(str(target))
            report.modified += 1
            report.add_detail(
                file=source_path.name,
                action="nfo",
                status="written",
                message=tr(
                    "nfo.message.written",
                    default="NFO written with template '{template}'.",
                    template=template_name,
                ),
                before={"folder": str(folder)},
                after={
                    "template": template_name,
                    "locale": template_locale,
                    "output": str(target),
                    "release_title": release.release_title,
                },
            )

        return report, outputs

    def build(
        self,
        folder: Path,
        *,
        template_name: str,
        logo_path: str | None = None,
        template_locale: str = "en",
        extra_context: dict | None = None,
    ) -> tuple[OperationReport, ReleaseNfoData, str]:
        episodes = scan_nfo_folder(folder)
        if not episodes:
            raise ValueError(
                tr(
                    "nfo.error.no_mkv",
                    default="No MKV files found in folder: {folder}",
                    folder=folder,
                )
            )

        release = build_release_nfo(folder, episodes)
        return self.build_from_release(
            folder,
            release=release,
            template_name=template_name,
            logo_path=logo_path,
            template_locale=template_locale,
            extra_context=extra_context,
        )

    def write(
        self,
        folder: Path,
        *,
        template_name: str,
        logo_path: str | None = None,
        output_name: str | None = None,
        template_locale: str = "en",
        extra_context: dict | None = None,
    ) -> tuple[OperationReport, ReleaseNfoData, Path]:
        report, release, rendered = self.build(
            folder,
            template_name=template_name,
            logo_path=logo_path,
            template_locale=template_locale,
            extra_context=extra_context,
        )

        final_name = (
            output_name if output_name else f"{_safe_output_name(release.release_title)}.nfo"
        )
        target = folder / final_name

        target.write_text(rendered, encoding="utf-8")
        report.outputs.append(str(target))
        report.details[0].status = "written"
        report.details[0].message = tr(
            "nfo.message.written",
            default="NFO written with template '{template}'.",
            template=report.details[0].after["template"],
        )

        return report, release, target

    def write_rendered(
        self,
        folder: Path,
        *,
        release: ReleaseNfoData,
        rendered: str,
        template_name: str,
        output_name: str | None = None,
        template_locale: str = "en",
    ) -> tuple[OperationReport, Path]:
        final_name = (
            output_name if output_name else f"{_safe_output_name(release.release_title)}.nfo"
        )
        target = folder / final_name
        target.write_text(rendered, encoding="utf-8")

        report = OperationReport(tool="nfo")
        report.scanned = len(release.episodes)
        report.processed = len(release.episodes)
        report.modified = 1
        report.outputs.append(str(target))
        report.add_detail(
            file=None,
            action="nfo",
            status="written",
            message=tr(
                "nfo.message.written",
                default="NFO written with template '{template}'.",
                template=template_name,
            ),
            before={"folder": str(folder)},
            after={"template": template_name, "locale": template_locale, "output": str(target)},
        )

        return report, target
