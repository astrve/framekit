"""Template categorization system for hierarchical organization."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class TemplateCategory:
    """Represents a template category with metadata."""

    id: str
    name: str
    description: str
    templates: tuple[str, ...]
    icon: str = "📁"
    color: str = "cyan"


# HTML Template Categories - New System (10 designs × 14 colors = 140 templates)
HTML_CATEGORIES: dict[str, TemplateCategory] = {
    "cinematic": TemplateCategory(
        id="cinematic",
        name="Cinematic",
        description="Movie-style horizontal layout",
        templates=(
            "cinematic_dark",
            "cinematic_forest",
            "cinematic_sunset",
            "cinematic_ocean",
            "cinematic_sepia",
            "cinematic_rainbow",
            "cinematic_midnight",
            "cinematic_cherry",
            "cinematic_lavender",
            "cinematic_mint",
            "cinematic_amber",
            "cinematic_slate",
            "cinematic_coral",
            "cinematic_teal",
        ),
        icon="🎬",
        color="cyan",
    ),
    "magazine": TemplateCategory(
        id="magazine",
        name="Magazine",
        description="Editorial multi-column layout",
        templates=(
            "magazine_dark",
            "magazine_forest",
            "magazine_sunset",
            "magazine_ocean",
            "magazine_sepia",
            "magazine_rainbow",
            "magazine_midnight",
            "magazine_cherry",
            "magazine_lavender",
            "magazine_mint",
            "magazine_amber",
            "magazine_slate",
            "magazine_coral",
            "magazine_teal",
        ),
        icon="📰",
        color="yellow",
    ),
    "minimal": TemplateCategory(
        id="minimal",
        name="Minimal",
        description="Clean and spacious design",
        templates=(
            "minimal_dark",
            "minimal_forest",
            "minimal_sunset",
            "minimal_ocean",
            "minimal_sepia",
            "minimal_rainbow",
            "minimal_midnight",
            "minimal_cherry",
            "minimal_lavender",
            "minimal_mint",
            "minimal_amber",
            "minimal_slate",
            "minimal_coral",
            "minimal_teal",
        ),
        icon="✨",
        color="white",
    ),
    "card": TemplateCategory(
        id="card",
        name="Card",
        description="Grid-based card layout",
        templates=(
            "card_dark",
            "card_forest",
            "card_sunset",
            "card_ocean",
            "card_sepia",
            "card_rainbow",
            "card_midnight",
            "card_cherry",
            "card_lavender",
            "card_mint",
            "card_amber",
            "card_slate",
            "card_coral",
            "card_teal",
        ),
        icon="🃏",
        color="blue",
    ),
    "timeline": TemplateCategory(
        id="timeline",
        name="Timeline",
        description="Chronological vertical layout",
        templates=(
            "timeline_dark",
            "timeline_forest",
            "timeline_sunset",
            "timeline_ocean",
            "timeline_sepia",
            "timeline_rainbow",
            "timeline_midnight",
            "timeline_cherry",
            "timeline_lavender",
            "timeline_mint",
            "timeline_amber",
            "timeline_slate",
            "timeline_coral",
            "timeline_teal",
        ),
        icon="⏱️",
        color="purple",
    ),
    "glassmorphism": TemplateCategory(
        id="glassmorphism",
        name="Glassmorphism",
        description="Frosted glass effects",
        templates=(
            "glassmorphism_dark",
            "glassmorphism_forest",
            "glassmorphism_sunset",
            "glassmorphism_ocean",
            "glassmorphism_sepia",
            "glassmorphism_rainbow",
            "glassmorphism_midnight",
            "glassmorphism_cherry",
            "glassmorphism_lavender",
            "glassmorphism_mint",
            "glassmorphism_amber",
            "glassmorphism_slate",
            "glassmorphism_coral",
            "glassmorphism_teal",
        ),
        icon="💎",
        color="cyan",
    ),
    "brutalist": TemplateCategory(
        id="brutalist",
        name="Brutalist",
        description="Raw asymmetric design",
        templates=(
            "brutalist_dark",
            "brutalist_forest",
            "brutalist_sunset",
            "brutalist_ocean",
            "brutalist_sepia",
            "brutalist_rainbow",
            "brutalist_midnight",
            "brutalist_cherry",
            "brutalist_lavender",
            "brutalist_mint",
            "brutalist_amber",
            "brutalist_slate",
            "brutalist_coral",
            "brutalist_teal",
        ),
        icon="🔲",
        color="white",
    ),
    "neon_cyberpunk": TemplateCategory(
        id="neon_cyberpunk",
        name="Neon Cyberpunk",
        description="Glowing futuristic style",
        templates=(
            "neon_cyberpunk_dark",
            "neon_cyberpunk_forest",
            "neon_cyberpunk_sunset",
            "neon_cyberpunk_ocean",
            "neon_cyberpunk_sepia",
            "neon_cyberpunk_rainbow",
            "neon_cyberpunk_midnight",
            "neon_cyberpunk_cherry",
            "neon_cyberpunk_lavender",
            "neon_cyberpunk_mint",
            "neon_cyberpunk_amber",
            "neon_cyberpunk_slate",
            "neon_cyberpunk_coral",
            "neon_cyberpunk_teal",
        ),
        icon="🌃",
        color="magenta",
    ),
    "vintage_retro": TemplateCategory(
        id="vintage_retro",
        name="Vintage Retro",
        description="80s/90s pastel aesthetic",
        templates=(
            "vintage_retro_dark",
            "vintage_retro_forest",
            "vintage_retro_sunset",
            "vintage_retro_ocean",
            "vintage_retro_sepia",
            "vintage_retro_rainbow",
            "vintage_retro_midnight",
            "vintage_retro_cherry",
            "vintage_retro_lavender",
            "vintage_retro_mint",
            "vintage_retro_amber",
            "vintage_retro_slate",
            "vintage_retro_coral",
            "vintage_retro_teal",
        ),
        icon="📼",
        color="yellow",
    ),
    "neumorphism": TemplateCategory(
        id="neumorphism",
        name="Neumorphism",
        description="Soft 3D relief design",
        templates=(
            "neumorphism_dark",
            "neumorphism_forest",
            "neumorphism_sunset",
            "neumorphism_ocean",
            "neumorphism_sepia",
            "neumorphism_rainbow",
            "neumorphism_midnight",
            "neumorphism_cherry",
            "neumorphism_lavender",
            "neumorphism_mint",
            "neumorphism_amber",
            "neumorphism_slate",
            "neumorphism_coral",
            "neumorphism_teal",
        ),
        icon="🎨",
        color="blue",
    ),
}

# BBCode Template Categories
BBCODE_CATEGORIES: dict[str, TemplateCategory] = {
    "classic": TemplateCategory(
        id="classic",
        name="Classic",
        description="Traditional BBCode layouts",
        templates=("classic", "detailed"),
        icon="📝",
        color="cyan",
    ),
    "tracker": TemplateCategory(
        id="tracker",
        name="Tracker",
        description="Tracker-optimized formats",
        templates=("compact", "technical", "tracker"),
        icon="🎯",
        color="green",
    ),
    "styled": TemplateCategory(
        id="styled",
        name="Styled",
        description="Enhanced visual BBCode",
        templates=("cinematic", "spoiler", "boxed"),
        icon="🎨",
        color="magenta",
    ),
}

# Category order for display (new system)
HTML_CATEGORY_ORDER = [
    "cinematic",
    "magazine",
    "minimal",
    "card",
    "timeline",
    "glassmorphism",
    "brutalist",
    "neon_cyberpunk",
    "vintage_retro",
    "neumorphism",
]

BBCODE_CATEGORY_ORDER = [
    "classic",
    "tracker",
    "styled",
]


def get_template_category(
    template_name: str, kind: Literal["html", "bbcode"] = "html"
) -> TemplateCategory | None:
    """Get the category for a given template.

    Args:
        template_name: Name of the template
        kind: Template kind (html or bbcode)

    Returns:
        TemplateCategory if found, None otherwise
    """
    categories = HTML_CATEGORIES if kind == "html" else BBCODE_CATEGORIES

    ordered_categories = sorted(categories.values(), key=lambda item: len(item.id), reverse=True)
    for category in ordered_categories:
        if template_name in category.templates:
            return category
        if kind == "html" and template_name.startswith(f"{category.id}_"):
            return category

    return None


def get_category_by_id(
    category_id: str, kind: Literal["html", "bbcode"] = "html"
) -> TemplateCategory | None:
    """Get a category by its ID.

    Args:
        category_id: ID of the category
        kind: Template kind (html or bbcode)

    Returns:
        TemplateCategory if found, None otherwise
    """
    categories = HTML_CATEGORIES if kind == "html" else BBCODE_CATEGORIES
    return categories.get(category_id)


def get_ordered_categories(kind: Literal["html", "bbcode"] = "html") -> list[TemplateCategory]:
    """Get categories in display order.

    Args:
        kind: Template kind (html or bbcode)

    Returns:
        List of categories in display order
    """
    if kind == "html":
        categories = HTML_CATEGORIES
        order = HTML_CATEGORY_ORDER
    else:
        categories = BBCODE_CATEGORIES
        order = BBCODE_CATEGORY_ORDER

    return [categories[cat_id] for cat_id in order if cat_id in categories]


def categorize_templates(
    templates: tuple[str, ...], kind: Literal["html", "bbcode"] = "html"
) -> dict[str, list[str]]:
    """Organize templates into categories.

    Args:
        templates: Tuple of template names
        kind: Template kind (html or bbcode)

    Returns:
        Dictionary mapping category IDs to lists of template names
    """
    result: dict[str, list[str]] = {}
    uncategorized: list[str] = []

    for template in templates:
        category = get_template_category(template, kind)
        if category:
            if category.id not in result:
                result[category.id] = []
            result[category.id].append(template)
        else:
            uncategorized.append(template)

    # Add uncategorized templates to "other" category if any exist
    if uncategorized:
        result["other"] = uncategorized

    return result


def get_all_templates_in_order(kind: Literal["html", "bbcode"] = "html") -> list[str]:
    """Get all templates in category order.

    Args:
        kind: Template kind (html or bbcode)

    Returns:
        List of all template names in category order
    """
    templates = []
    for category in get_ordered_categories(kind):
        templates.extend(category.templates)
    return templates
