"""File browser TUI component.

This module provides the terminal user interface for the file browser,
using Rich for rendering and the existing selector input adapter for
keyboard handling.
"""

from __future__ import annotations

import sys
from pathlib import Path

from rich.console import Group
from rich.live import Live
from rich.padding import Padding
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

from ouro.core.file_browser import BrowserConfig, FileBrowserEngine
from ouro.ui.console import ACCENT, console
from ouro.ui.unified_selector import SelectorAction, SelectorInputAdapter


class FileBrowserTUI:
    """Terminal UI for file browser.

    Provides an interactive file browser interface with keyboard navigation,
    file filtering, and selection capabilities.
    """

    def __init__(self, config: BrowserConfig) -> None:
        """Initialize the file browser TUI.

        Args:
            config: Browser configuration
        """
        self.engine = FileBrowserEngine(config)
        self.input_adapter = SelectorInputAdapter()
        self.show_help = False

    def _format_size(self, size: int) -> str:
        """Format file size in human-readable format.

        Args:
            size: Size in bytes

        Returns:
            Formatted size string
        """
        if size < 1024:
            return f"{size}B"
        elif size < 1024 * 1024:
            return f"{size / 1024:.1f}KB"
        elif size < 1024 * 1024 * 1024:
            return f"{size / (1024 * 1024):.1f}MB"
        else:
            return f"{size / (1024 * 1024 * 1024):.2f}GB"

    def _render_breadcrumb(self) -> Text:
        """Render breadcrumb navigation.

        Returns:
            Rich Text object with breadcrumb
        """
        path_parts = self.engine.state.current_dir.parts
        breadcrumb = Text()

        for i, part in enumerate(path_parts):
            if i > 0:
                breadcrumb.append(" / ", style="bright_black")
            breadcrumb.append(part, style=ACCENT if i == len(path_parts) - 1 else "white")

        return breadcrumb

    def _render_file_list(self) -> Table:
        """Render file list table.

        Returns:
            Rich Table with file entries
        """
        table = Table(
            show_header=False,
            show_edge=False,
            box=None,
            pad_edge=False,
            padding=(0, 1, 0, 0),
            expand=True,
        )

        table.add_column("Sel", justify="right", no_wrap=True, width=4)
        table.add_column("Name", overflow="ellipsis", no_wrap=True, ratio=5)
        table.add_column("Size", justify="right", no_wrap=True, width=10)

        entries = self.engine.state.entries
        cursor_idx = self.engine.state.cursor_index
        selected_indices = self.engine.state.selected_indices

        if not entries:
            table.add_row(Text(""), Text("(empty directory)", style="bright_black"), Text(""))
            return table

        for idx, entry in enumerate(entries):
            is_cursor = idx == cursor_idx
            is_selected = idx in selected_indices

            # Selection indicator
            if is_selected:
                sel_text = Text("[X]", style=f"bold {ACCENT}")
            else:
                sel_text = Text("[ ]", style="bright_black")

            # Name with icon
            if entry.is_directory:
                icon = "📁 "
                name_style = f"bold {ACCENT}" if is_cursor else "bold white"
            else:
                icon = "📄 "
                name_style = f"bold {ACCENT}" if is_cursor else "white"

            name_text = Text(icon + entry.name, style=name_style)

            # Size
            if entry.is_directory:
                size_text = Text("<DIR>", style="bright_black")
            else:
                size_style = f"bold {ACCENT}" if is_cursor else "bright_black"
                size_text = Text(self._format_size(entry.size), style=size_style)

            table.add_row(sel_text, name_text, size_text)

        return table

    def _render_status_bar(self) -> Text:
        """Render status bar with keyboard shortcuts.

        Returns:
            Rich Text object with status bar
        """
        status = Text(style="bright_black")

        # Navigation
        status.append("↑↓/jk", style="bold white")
        status.append(" move  ", style="bright_black")

        # Selection
        if self.engine.config.multi_select:
            status.append("space", style="bold white")
            status.append(" toggle  ", style="bright_black")

        # Actions
        status.append("enter", style="bold white")
        status.append(" select  ", style="bright_black")

        status.append("backspace", style="bold white")
        status.append(" up  ", style="bright_black")

        status.append("r", style="bold white")
        status.append(" refresh  ", style="bright_black")

        status.append("?", style="bold white")
        status.append(" help  ", style="bright_black")

        status.append("q/esc", style="bold white")
        status.append(" quit", style="bright_black")

        # Selection count
        if self.engine.config.multi_select:
            count = len(self.engine.state.selected_indices)
            status.append(f"  [{count} selected]", style=ACCENT)

        return status

    def _render_help_overlay(self) -> Panel:
        """Render help overlay.

        Returns:
            Rich Panel with help text
        """
        help_text = Text()
        help_text.append("File Browser Keyboard Shortcuts\n\n", style="bold white")

        shortcuts = [
            ("↑/↓ or j/k", "Move cursor up/down"),
            ("Enter", "Select file/Enter directory"),
            ("Backspace", "Go to parent directory"),
            ("Space", "Toggle selection (multi-select mode)"),
            ("r", "Refresh directory"),
            ("?", "Toggle this help"),
            ("q or Esc", "Quit browser"),
        ]

        for key, desc in shortcuts:
            help_text.append(f"  {key:15}", style=f"bold {ACCENT}")
            help_text.append(f" {desc}\n", style="white")

        return Panel(help_text, title="Help", border_style=ACCENT, expand=False)

    def _render(self):
        """Render complete UI.

        Returns:
            Rich renderable with all UI elements
        """
        if self.show_help:
            return Group(Text(""), self._render_help_overlay(), Text(""), self._render_status_bar())

        # Title with breadcrumb
        title_rule = Rule(self._render_breadcrumb(), style="bright_black")

        # File list
        file_list = self._render_file_list()

        # Status bar
        status_bar = self._render_status_bar()

        return Padding(Group(title_rule, file_list, Text(""), status_bar), (0, 2))

    def _current_entry(self):
        entries = self.engine.state.entries
        if not entries:
            return None
        return entries[self.engine.state.cursor_index]

    def _handle_confirm(self) -> list[Path] | None:
        current_entry = self._current_entry()
        if current_entry is None:
            return self.engine.get_selected_paths()

        if current_entry.is_directory:
            self.engine.navigate_into()
            return None

        if not self.engine.config.multi_select:
            self.engine.toggle_selection()
        return self.engine.get_selected_paths()

    def _handle_expand(self) -> None:
        current_entry = self._current_entry()
        if current_entry is not None and current_entry.is_directory:
            self.engine.navigate_into()

    def _handle_action(self, action: SelectorAction) -> list[Path] | None:
        if action == SelectorAction.UP:
            self.engine.move_cursor(-1)
            return None
        if action == SelectorAction.DOWN:
            self.engine.move_cursor(1)
            return None
        if action == SelectorAction.TOGGLE:
            if self.engine.config.multi_select:
                self.engine.toggle_selection()
            return None
        if action == SelectorAction.CONFIRM:
            return self._handle_confirm()
        if action == SelectorAction.LEFT:
            self.engine.navigate_up()
            return None
        if action == SelectorAction.EXPAND:
            self._handle_expand()
            return None
        if action == SelectorAction.CANCEL:
            raise KeyboardInterrupt
        return None

    def run(self) -> list[Path]:
        """Run the file browser TUI.

        Returns:
            List of selected file paths

        Raises:
            RuntimeError: If not running in a TTY
            KeyboardInterrupt: If user cancels
        """
        if not sys.stdin.isatty():
            raise RuntimeError(
                "Interactive file browser is not available in headless mode (no TTY)."
            )

        try:
            with Live(self._render(), console=console, auto_refresh=False, transient=True) as live:
                while True:
                    live.update(self._render(), refresh=True)
                    action = self.input_adapter.read_action()
                    selected_paths = self._handle_action(action)
                    if selected_paths is not None:
                        return selected_paths

        except KeyboardInterrupt:
            # User cancelled
            return []
