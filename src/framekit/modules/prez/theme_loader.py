"""Theme loading and management for presentation templates."""

from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore[assignment]


class ThemeLoader:
    """Loads and manages presentation template themes."""

    def __init__(self):
        """Initialize the theme loader."""
        self._html_themes: dict[str, dict[str, str]] | None = None
        self._bbcode_themes: dict[str, dict[str, str]] | None = None

    def _load_yaml(self, file_path: Path) -> dict[str, Any]:
        """Load a YAML file and return its contents."""
        if yaml is None:
            # Fallback: return empty dict if PyYAML is not available
            return {}

        try:
            with open(file_path, encoding="utf-8") as f:
                data = yaml.safe_load(f)
                return data if data else {}
        except Exception:
            return {}

    def _get_themes_dir(self) -> Path:
        """Get the themes directory path."""
        # Get the directory where this module is located
        module_dir = Path(__file__).parent.parent.parent
        return module_dir / "templates" / "prez" / "themes"

    def load_html_themes(self) -> dict[str, dict[str, str]]:
        """Load HTML themes from YAML configuration."""
        if self._html_themes is None:
            themes_file = self._get_themes_dir() / "html_themes.yaml"
            data = self._load_yaml(themes_file)
            self._html_themes = data.get("themes", {})
        return self._html_themes if self._html_themes is not None else {}

    def load_bbcode_themes(self) -> dict[str, dict[str, str]]:
        """Load BBCode themes from YAML configuration."""
        if self._bbcode_themes is None:
            themes_file = self._get_themes_dir() / "bbcode_themes.yaml"
            data = self._load_yaml(themes_file)
            self._bbcode_themes = data.get("themes", {})
        return self._bbcode_themes if self._bbcode_themes is not None else {}

    def get_html_theme(self, theme_name: str) -> dict[str, str]:
        """Get a specific HTML theme by name.

        Args:
            theme_name: Name of the theme to retrieve

        Returns:
            Dictionary of theme properties, or empty dict if not found
        """
        themes = self.load_html_themes()
        return themes.get(theme_name, {})

    def get_bbcode_theme(self, theme_name: str) -> dict[str, str]:
        """Get a specific BBCode theme by name.

        Args:
            theme_name: Name of the theme to retrieve

        Returns:
            Dictionary of theme properties, or empty dict if not found
        """
        themes = self.load_bbcode_themes()
        return themes.get(theme_name, {})

    def theme_to_css_vars(self, theme: dict[str, str]) -> str:
        """Convert a theme dictionary to CSS custom properties string.

        Args:
            theme: Dictionary of theme properties

        Returns:
            CSS custom properties string (e.g., "--bg:#000;--text:#fff;")
        """
        if not theme:
            return ""

        css_parts = []
        for key, value in theme.items():
            css_parts.append(f"--{key}:{value}")

        return ";".join(css_parts) + ";"

    def get_html_theme_css(self, theme_name: str, fallback_theme: str = "aurora") -> str:
        """Get CSS custom properties string for an HTML theme.

        Args:
            theme_name: Name of the theme
            fallback_theme: Fallback theme if the requested theme is not found

        Returns:
            CSS custom properties string
        """
        theme = self.get_html_theme(theme_name)
        if not theme:
            theme = self.get_html_theme(fallback_theme)
        return self.theme_to_css_vars(theme)


# Global theme loader instance
_theme_loader = ThemeLoader()


def get_html_theme_css(theme_name: str) -> str:
    """Get CSS custom properties for an HTML theme.

    This is a convenience function that uses the global theme loader.

    Args:
        theme_name: Name of the theme

    Returns:
        CSS custom properties string
    """
    return _theme_loader.get_html_theme_css(theme_name)


def get_bbcode_theme(theme_name: str) -> dict[str, str]:
    """Get a BBCode theme configuration.

    This is a convenience function that uses the global theme loader.

    Args:
        theme_name: Name of the theme

    Returns:
        Dictionary of theme properties
    """
    return _theme_loader.get_bbcode_theme(theme_name)
