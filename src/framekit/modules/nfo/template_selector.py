from __future__ import annotations

from dataclasses import dataclass

from framekit.core.i18n import tr
from framekit.ui.selector import SelectorOption, select_one


@dataclass(slots=True)
class TemplateOption:
    display_name: str
    template_name: str
    source: str
    scope: str


def _display_name_for_record(record) -> str:
    if record.source == "builtin" and record.template_name in {"default", "detailed"}:
        return tr(f"nfo.template.{record.template_name}", default=record.display_name)
    return record.display_name


def build_template_options(records) -> list[TemplateOption]:
    return [
        TemplateOption(
            display_name=_display_name_for_record(record),
            template_name=record.template_name,
            source=record.source,
            scope=record.scope,
        )
        for record in records
    ]


def find_template_option(
    options: list[TemplateOption], template_name: str | None
) -> TemplateOption | None:
    if not template_name:
        return None

    for option in options:
        if option.template_name == template_name:
            return option
    return None


class TemplateSelector:
    def __init__(
        self,
        options: list[TemplateOption],
        preferred_name: str | None = None,
        page_size: int = 8,
    ) -> None:
        self.options = options
        self.preferred_name = preferred_name
        self.page_size = page_size

    def run(self) -> TemplateOption | None:
        entries: list[SelectorOption[TemplateOption]] = [
            SelectorOption(
                value=option,
                label=option.display_name,
                hint=f"{option.scope} · {option.source}",
                selected=False,
            )
            for option in self.options
        ]

        try:
            return select_one(
                title=tr("nfo.template_selector.title", default="NFO Template Selector"),
                entries=entries,
                page_size=self.page_size,
            )
        except KeyboardInterrupt:
            return None


def choose_template(
    options: list[TemplateOption],
    preferred_name: str | None = None,
) -> TemplateOption | None:
    selector = TemplateSelector(options, preferred_name=preferred_name)
    return selector.run()


def choose_template_scope(preferred_scope: str = "universal") -> str | None:
    options = [
        TemplateOption(tr("nfo.scope.movie", default="Movie"), "movie", "scope", "movie"),
        TemplateOption(
            tr("nfo.scope.single_episode", default="Single Episode"),
            "single_episode",
            "scope",
            "single_episode",
        ),
        TemplateOption(
            tr("nfo.scope.season_pack", default="Season Pack"),
            "season_pack",
            "scope",
            "season_pack",
        ),
        TemplateOption(
            tr("nfo.scope.universal", default="Universal"), "universal", "scope", "universal"
        ),
    ]
    chosen = TemplateSelector(options, preferred_name=preferred_scope).run()
    return chosen.scope if chosen else None


def choose_import_location(preferred: str = "appdata") -> str | None:
    options = [
        TemplateOption(
            tr("nfo.location.appdata", default="AppData"), "appdata", "location", "appdata"
        ),
        TemplateOption(
            tr("nfo.location.project", default="Project Folder"), "project", "location", "project"
        ),
    ]
    chosen = TemplateSelector(options, preferred_name=preferred).run()
    return chosen.template_name if chosen else None
