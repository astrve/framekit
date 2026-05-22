"""Open/close template selector with clean, minimalist interface."""

from __future__ import annotations

import sys
from typing import Any, Literal

from rich.console import Group
from rich.live import Live
from rich.padding import Padding
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

from framekit.core.i18n import tr
from framekit.modules.prez.service import (
    available_bbcode_templates,
    available_html_templates,
    describe_bbcode_template,
    describe_html_template,
)
from framekit.modules.prez.template_categories import get_ordered_categories, get_template_category
from framekit.ui.console import console
from framekit.ui.unified_selector import SelectorInputAdapter


class ExpandCollapseSelector:
    """Expand/collapse selector for template categories."""

    def __init__(
        self,
        categories: dict[str, list[str]],
        current_template: str | None = None,
        kind: Literal["html", "bbcode"] = "html",
    ):
        """Initialize the selector.

        Args:
            categories: Dictionary mapping category names to template lists
            current_template: Currently selected template
            kind: Template kind (html or bbcode)
        """
        self.categories = categories
        self.current_template = current_template
        self.selected_template = current_template  # Track checked template
        self.kind = kind
        self.expanded: set[str] = set()
        self.cursor_pos = 0
        self.visible_items: list[tuple[str, str, Any]] = []
        self.input_adapter = SelectorInputAdapter()
        self._build_visible_items()

    def _build_visible_items(self) -> None:
        """Build list of visible items based on expanded state."""
        self.visible_items = []
        for cat_name, templates in self.categories.items():
            # Add category header
            is_expanded = cat_name in self.expanded
            self.visible_items.append(("category", cat_name, is_expanded))

            # Add templates if expanded
            if is_expanded:
                for tmpl in templates:
                    self.visible_items.append(("template", tmpl, None))

    def toggle_category(self, cat_name: str) -> None:
        """Toggle category expanded state."""
        if cat_name in self.expanded:
            self.expanded.remove(cat_name)
        else:
            self.expanded.add(cat_name)

        # Rebuild visible items
        self._build_visible_items()

        # Adjust cursor if needed
        if self.cursor_pos >= len(self.visible_items):
            self.cursor_pos = max(0, len(self.visible_items) - 1)

    def navigate_up(self) -> None:
        """Move cursor up."""
        if self.cursor_pos > 0:
            self.cursor_pos -= 1

    def navigate_down(self) -> None:
        """Move cursor down."""
        if self.cursor_pos < len(self.visible_items) - 1:
            self.cursor_pos += 1

    def get_current_item(self) -> tuple[str, str, Any] | None:
        """Get item at cursor position."""
        if 0 <= self.cursor_pos < len(self.visible_items):
            return self.visible_items[self.cursor_pos]
        return None

    def _get_template_description(self, template: str) -> str:
        """Get description for a template."""
        if self.kind == "html":
            return describe_html_template(template)
        else:
            return describe_bbcode_template(template)

    def render(self) -> Padding:
        """Render the selector."""
        # Build table
        table = Table(
            show_header=False,
            show_edge=False,
            box=None,
            pad_edge=False,
            padding=(0, 1, 0, 0),
            expand=True,
        )
        table.add_column("Indicator", justify="left", no_wrap=True, width=4)
        table.add_column("Content", overflow="ellipsis", no_wrap=False, ratio=1)

        for i, (item_type, name, data) in enumerate(self.visible_items):
            is_cursor = i == self.cursor_pos

            if item_type == "category":
                # Category line
                is_expanded = data
                arrow = "▼" if is_expanded else "▶"
                count = len(self.categories[name])

                if is_cursor:
                    indicator = Text("→", style="bold cyan")
                    content = Text(f"{arrow} {name} ({count} templates)", style="bold cyan")
                else:
                    indicator = Text(" ", style="white")
                    content = Text(f"{arrow} {name} ({count} templates)", style="white")

                table.add_row(indicator, content)

            elif item_type == "template":
                # Template line
                # Check if THIS template is selected (not cursor position)
                is_selected = name == self.selected_template
                checkbox = "[X]" if is_selected else "[ ]"
                desc = self._get_template_description(name)

                if is_cursor:
                    indicator = Text("→", style="bold cyan")
                    content = Text(f"  {checkbox} {name} - {desc}", style="bold cyan")
                else:
                    if is_selected:
                        indicator = Text(" ", style="white")
                        content = Text(f"  {checkbox} {name} - {desc}", style="bold cyan")
                    else:
                        indicator = Text(" ", style="white")
                        content = Text(f"  {checkbox} {name} - {desc}", style="white")

                table.add_row(indicator, content)

        # Build title
        kind_label = "HTML" if self.kind == "html" else "BBCode"
        title_text = tr(
            "prez.selector.title",
            default="Select {kind} Template",
            kind=kind_label,
        )
        title_rule = Rule(
            Text(title_text, style="bold white"),
            style="bright_black",
        )

        # Build footer
        footer = Text(style="bright_black")
        footer.append("[↑↓] Navigate  ", style="bright_black")
        footer.append("[e] ", style="bold white")
        footer.append("Expand  ", style="bright_black")
        footer.append("[Space] ", style="bold white")
        footer.append("Check  ", style="bright_black")
        footer.append("[Enter] ", style="bold white")
        footer.append("Confirm  ", style="bright_black")
        footer.append("[Esc] ", style="bold white")
        footer.append("Cancel", style="bright_black")

        return Padding(
            Group(
                title_rule,
                table,
                Text(""),
                footer,
            ),
            (0, 2),
        )

    def _current_or_empty(self) -> str:
        return self.current_template or ""

    def _handle_expand(self) -> None:
        item = self.get_current_item()
        if item and item[0] == "category":
            self.toggle_category(item[1])

    def _handle_toggle(self) -> None:
        item = self.get_current_item()
        if not item or item[0] != "template":
            return
        self.selected_template = None if self.selected_template == item[1] else item[1]

    def _handle_confirm(self) -> str:
        return self.selected_template or self._current_or_empty()

    def _handle_action(self, action: Any) -> str | None:
        # Import here to avoid circular dependency
        from framekit.ui.unified_selector import SelectorAction

        if action == SelectorAction.UP:
            self.navigate_up()
            return None
        if action == SelectorAction.DOWN:
            self.navigate_down()
            return None
        if action == SelectorAction.EXPAND:
            self._handle_expand()
            return None
        if action == SelectorAction.TOGGLE:
            self._handle_toggle()
            return None
        if action == SelectorAction.CONFIRM:
            return self._handle_confirm()
        if action == SelectorAction.CANCEL:
            return self._current_or_empty()
        return None

    def show(self) -> str:
        """Show selector and return selected template."""
        if not sys.stdin.isatty():
            return self._current_or_empty()

        try:
            with Live(
                self.render(),
                console=console,
                auto_refresh=False,
                transient=True,
            ) as live:
                while True:
                    live.update(self.render(), refresh=True)
                    action = self.input_adapter.read_action()
                    result = self._handle_action(action)
                    if result is not None:
                        return result

        except KeyboardInterrupt:
            return self._current_or_empty()


def select_template_simple(
    kind: Literal["html", "bbcode"],
    current: str,
    metadata: dict[str, Any] | None = None,
) -> str:
    """Expand/collapse template selector with categories.

    Args:
        kind: Template kind (html or bbcode)
        current: Currently selected template
        metadata: Metadata (unused for now, kept for compatibility)

    Returns:
        Selected template name, or current if cancelled
    """
    if not sys.stdin.isatty():
        return current

    # Get all templates
    if kind == "html":
        all_templates = available_html_templates()
    else:
        all_templates = available_bbcode_templates()

    # Build categories dictionary from the discovered templates.
    ordered_categories = get_ordered_categories(kind)
    categories_dict: dict[str, list[str]] = {category.name: [] for category in ordered_categories}

    for template in all_templates:
        category = get_template_category(template, kind=kind)
        category_name = category.name if category else "Other"
        categories_dict.setdefault(category_name, []).append(template)

    categories_dict = {name: templates for name, templates in categories_dict.items() if templates}

    # Create and show selector
    selector = ExpandCollapseSelector(
        categories=categories_dict,
        current_template=current,
        kind=kind,
    )

    return selector.show()


# Keep old function name for compatibility
def select_template_collapsible(
    kind: Literal["html", "bbcode"],
    current: str,
    metadata: dict[str, Any] | None = None,
) -> str:
    """Alias for select_template_simple for backward compatibility."""
    return select_template_simple(kind, current, metadata)
