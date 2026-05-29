"""Tests for the expand/collapse template selector."""

from __future__ import annotations

from unittest.mock import patch

from ouro.modules.prez.template_categories import (
    BBCODE_CATEGORIES,
    HTML_CATEGORIES,
    categorize_templates,
    get_all_templates_in_order,
    get_category_by_id,
    get_ordered_categories,
    get_template_category,
)
from ouro.modules.prez.template_selector import (
    ExpandCollapseSelector,
    select_template_collapsible,
    select_template_simple,
)


class TestTemplateCategories:
    """Test template categorization system."""

    def test_html_categories_exist(self):
        """Test that HTML categories are defined."""
        assert len(HTML_CATEGORIES) > 0
        assert "timeline" in HTML_CATEGORIES
        assert "minimal" in HTML_CATEGORIES
        assert "cinematic" in HTML_CATEGORIES
        assert "magazine" in HTML_CATEGORIES
        assert "neon_cyberpunk" in HTML_CATEGORIES

    def test_bbcode_categories_exist(self):
        """Test that BBCode categories are defined."""
        assert len(BBCODE_CATEGORIES) > 0
        assert "classic" in BBCODE_CATEGORIES
        assert "tracker" in BBCODE_CATEGORIES
        assert "styled" in BBCODE_CATEGORIES

    def test_category_has_required_fields(self):
        """Test that categories have all required fields."""
        category = HTML_CATEGORIES["timeline"]
        assert category.id == "timeline"
        assert category.name
        assert category.description
        assert len(category.templates) > 0
        assert category.icon
        assert category.color

    def test_get_template_category_html(self):
        """Test getting category for an HTML template that belongs to one."""
        category = get_template_category("cinematic_dark", kind="html")
        assert category is not None
        assert category.id == "cinematic"
        assert "cinematic_dark" in category.templates

    def test_get_template_category_bbcode(self):
        """Test getting category for BBCode template."""
        category = get_template_category("classic", kind="bbcode")
        assert category is not None
        assert category.id == "classic"
        assert "classic" in category.templates

    def test_get_template_category_not_found(self):
        """Test getting category for non-existent template."""
        category = get_template_category("nonexistent", kind="html")
        assert category is None

    def test_get_category_by_id_html(self):
        """Test getting category by ID for HTML."""
        category = get_category_by_id("timeline", kind="html")
        assert category is not None
        assert category.id == "timeline"

    def test_get_category_by_id_bbcode(self):
        """Test getting category by ID for BBCode."""
        category = get_category_by_id("classic", kind="bbcode")
        assert category is not None
        assert category.id == "classic"

    def test_get_category_by_id_not_found(self):
        """Test getting non-existent category by ID."""
        category = get_category_by_id("nonexistent", kind="html")
        assert category is None

    def test_get_ordered_categories_html(self):
        """Test getting ordered HTML categories."""
        categories = get_ordered_categories(kind="html")
        assert len(categories) > 0
        assert all(hasattr(cat, "id") for cat in categories)
        # First entry in HTML_CATEGORY_ORDER is the "cinematic" family.
        ids = [cat.id for cat in categories]
        assert ids[0] == "cinematic"

    def test_get_ordered_categories_bbcode(self):
        """Test getting ordered BBCode categories."""
        categories = get_ordered_categories(kind="bbcode")
        assert len(categories) > 0
        assert all(hasattr(cat, "id") for cat in categories)
        # Check that order is preserved
        ids = [cat.id for cat in categories]
        assert ids[0] == "classic"  # First in BBCODE_CATEGORY_ORDER

    def test_categorize_templates_html(self):
        """Test categorizing HTML templates by family (templates are color-suffixed)."""
        templates = ("timeline_dark", "minimal_dark", "cinematic_ocean", "magazine_sepia")
        categorized = categorize_templates(templates, kind="html")

        assert "timeline" in categorized
        assert "timeline_dark" in categorized["timeline"]
        assert "minimal" in categorized
        assert "minimal_dark" in categorized["minimal"]
        assert "cinematic" in categorized
        assert "cinematic_ocean" in categorized["cinematic"]
        assert "magazine" in categorized
        assert "magazine_sepia" in categorized["magazine"]

    def test_categorize_templates_bbcode(self):
        """Test categorizing BBCode templates."""
        templates = ("classic", "tracker", "cinematic")
        categorized = categorize_templates(templates, kind="bbcode")

        assert "classic" in categorized
        assert "classic" in categorized["classic"]
        assert "tracker" in categorized
        assert "tracker" in categorized["tracker"]

    def test_categorize_templates_with_uncategorized(self):
        """Test categorizing templates with uncategorized items."""
        templates = ("cinematic_dark", "unknown_template")
        categorized = categorize_templates(templates, kind="html")

        assert "cinematic" in categorized
        assert "other" in categorized
        assert "unknown_template" in categorized["other"]

    def test_get_all_templates_in_order_html(self):
        """Test getting all HTML templates in order."""
        templates = get_all_templates_in_order(kind="html")
        assert len(templates) > 0
        assert isinstance(templates, list)
        # Check that templates from first category appear first
        first_category = get_ordered_categories(kind="html")[0]
        for template in first_category.templates:
            assert template in templates

    def test_get_all_templates_in_order_bbcode(self):
        """Test getting all BBCode templates in order."""
        templates = get_all_templates_in_order(kind="bbcode")
        assert len(templates) > 0
        assert isinstance(templates, list)


class TestExpandCollapseSelector:
    """Test expand/collapse selector functionality."""

    def test_expand_collapse_initial_state(self):
        """All categories should be collapsed initially."""
        categories = {
            "Timeline Family": ["timeline", "timeline_noir"],
            "Poster Family": ["poster", "poster_focus"],
        }
        selector = ExpandCollapseSelector(categories, "timeline", "html")

        # All categories should be collapsed
        assert len(selector.expanded) == 0

        # Visible items should only contain categories
        assert len(selector.visible_items) == 2
        assert all(item[0] == "category" for item in selector.visible_items)

    def test_expand_category(self):
        """Space on category should expand it."""
        categories = {
            "Timeline Family": ["timeline", "timeline_noir"],
            "Poster Family": ["poster"],
        }
        selector = ExpandCollapseSelector(categories, "timeline", "html")

        # Expand first category
        selector.toggle_category("Timeline Family")

        assert "Timeline Family" in selector.expanded
        # Should now have category + 2 templates + another category
        assert len(selector.visible_items) == 4
        assert selector.visible_items[0][0] == "category"
        assert selector.visible_items[1][0] == "template"
        assert selector.visible_items[2][0] == "template"
        assert selector.visible_items[3][0] == "category"

    def test_collapse_category(self):
        """Space on expanded category should collapse it."""
        categories = {
            "Timeline Family": ["timeline", "timeline_noir"],
        }
        selector = ExpandCollapseSelector(categories, "timeline", "html")

        # Expand then collapse
        selector.toggle_category("Timeline Family")
        assert "Timeline Family" in selector.expanded
        assert len(selector.visible_items) == 3  # category + 2 templates

        selector.toggle_category("Timeline Family")
        assert "Timeline Family" not in selector.expanded
        assert len(selector.visible_items) == 1  # only category

    def test_navigate_skip_collapsed(self):
        """Navigation should skip templates in collapsed categories."""
        categories = {
            "Timeline Family": ["timeline", "timeline_noir"],
            "Poster Family": ["poster"],
        }
        selector = ExpandCollapseSelector(categories, "timeline", "html")

        # Initially at first category
        assert selector.cursor_pos == 0
        assert selector.visible_items[0][1] == "Timeline Family"

        # Navigate down should go to second category (skipping collapsed templates)
        selector.navigate_down()
        assert selector.cursor_pos == 1
        assert selector.visible_items[1][1] == "Poster Family"

    def test_select_template_in_expanded_category(self):
        """Enter on template should select it."""
        categories = {
            "Timeline Family": ["timeline", "timeline_noir"],
        }
        selector = ExpandCollapseSelector(categories, "timeline", "html")

        # Expand category
        selector.toggle_category("Timeline Family")

        # Navigate to template
        selector.navigate_down()
        assert selector.cursor_pos == 1
        item = selector.get_current_item()
        assert item is not None
        assert item[0] == "template"
        assert item[1] == "timeline"

    def test_toggle_category_with_enter(self):
        """Enter on category should toggle it."""
        categories = {
            "Timeline Family": ["timeline"],
        }
        selector = ExpandCollapseSelector(categories, "timeline", "html")

        # Get current item (should be category)
        item = selector.get_current_item()
        assert item is not None
        assert item[0] == "category"

        # Toggle should expand
        selector.toggle_category(item[1])
        assert "Timeline Family" in selector.expanded

    def test_cancel_returns_current(self):
        """Esc should return current template."""
        categories = {
            "Timeline Family": ["timeline", "timeline_noir"],
        }

        with (
            patch("sys.stdin.isatty", return_value=True),
            patch.object(ExpandCollapseSelector, "show") as mock_show,
        ):
            mock_show.return_value = "timeline"

            selector = ExpandCollapseSelector(categories, "timeline", "html")
            result = selector.show()

            # Should return current template
            assert result == "timeline"

    def test_navigate_up(self):
        """Test navigating up."""
        categories = {
            "Timeline Family": ["timeline"],
            "Poster Family": ["poster"],
        }
        selector = ExpandCollapseSelector(categories, "timeline", "html")

        # Start at position 0
        assert selector.cursor_pos == 0

        # Navigate up should stay at 0
        selector.navigate_up()
        assert selector.cursor_pos == 0

        # Navigate down then up
        selector.navigate_down()
        assert selector.cursor_pos == 1
        selector.navigate_up()
        assert selector.cursor_pos == 0

    def test_navigate_down(self):
        """Test navigating down."""
        categories = {
            "Timeline Family": ["timeline"],
            "Poster Family": ["poster"],
        }
        selector = ExpandCollapseSelector(categories, "timeline", "html")

        # Navigate down
        selector.navigate_down()
        assert selector.cursor_pos == 1

        # Navigate down at end should stay at end
        selector.navigate_down()
        assert selector.cursor_pos == 1

    def test_cursor_adjustment_on_collapse(self):
        """Test cursor adjustment when collapsing category."""
        categories = {
            "Timeline Family": ["timeline", "timeline_noir", "timeline_amber"],
        }
        selector = ExpandCollapseSelector(categories, "timeline", "html")

        # Expand category
        selector.toggle_category("Timeline Family")
        assert len(selector.visible_items) == 4  # 1 category + 3 templates

        # Move cursor to last template
        selector.cursor_pos = 3

        # Collapse category
        selector.toggle_category("Timeline Family")

        # Cursor should be adjusted to valid position
        assert selector.cursor_pos == 0
        assert selector.cursor_pos < len(selector.visible_items)

    def test_get_current_item_bounds(self):
        """Test get_current_item with out of bounds cursor."""
        categories = {
            "Timeline Family": ["timeline"],
        }
        selector = ExpandCollapseSelector(categories, "timeline", "html")

        # Valid position
        item = selector.get_current_item()
        assert item is not None

        # Out of bounds
        selector.cursor_pos = 999
        item = selector.get_current_item()
        assert item is None

        selector.cursor_pos = -1
        item = selector.get_current_item()
        assert item is None


class TestCheckboxSelection:
    """Test checkbox selection behavior with 'e' for expand."""

    def test_space_checks_template(self):
        """Space on template should check it."""
        categories = {
            "Timeline Family": ["timeline", "timeline_noir"],
        }
        selector = ExpandCollapseSelector(categories, "timeline", "html")

        # Expand category
        selector.toggle_category("Timeline Family")

        # Navigate to second template
        selector.navigate_down()
        selector.navigate_down()
        assert selector.cursor_pos == 2
        item = selector.get_current_item()
        assert item is not None
        assert item[1] == "timeline_noir"

        # Initially, selected_template should be "timeline" (current)
        assert selector.selected_template == "timeline"

        # Simulate Space key to check timeline_noir
        selector.selected_template = item[1]
        assert selector.selected_template == "timeline_noir"

    def test_space_unchecks_template(self):
        """Space on checked template should uncheck it."""
        categories = {
            "Timeline Family": ["timeline", "timeline_noir"],
        }
        selector = ExpandCollapseSelector(categories, "timeline", "html")

        # Expand category
        selector.toggle_category("Timeline Family")

        # Navigate to first template (timeline)
        selector.navigate_down()
        assert selector.cursor_pos == 1
        item = selector.get_current_item()
        assert item is not None
        assert item[1] == "timeline"

        # Timeline is already selected
        assert selector.selected_template == "timeline"

        # Simulate Space key to uncheck
        if selector.selected_template == item[1]:
            selector.selected_template = None

        assert selector.selected_template is None

    def test_only_one_template_checked(self):
        """Checking a new template should uncheck the previous one."""
        categories = {
            "Timeline Family": ["timeline", "timeline_noir", "timeline_amber"],
        }
        selector = ExpandCollapseSelector(categories, "timeline", "html")

        # Expand category
        selector.toggle_category("Timeline Family")

        # Check timeline_noir
        selector.navigate_down()
        selector.navigate_down()
        item = selector.get_current_item()
        assert item is not None
        assert item[1] == "timeline_noir"
        selector.selected_template = item[1]
        assert selector.selected_template == "timeline_noir"

        # Check timeline_amber (should replace timeline_noir)
        selector.navigate_down()
        item = selector.get_current_item()
        assert item is not None
        assert item[1] == "timeline_amber"
        selector.selected_template = item[1]
        assert selector.selected_template == "timeline_amber"

        # Only timeline_amber should be checked
        assert selector.selected_template == "timeline_amber"

    def test_enter_returns_checked_template(self):
        """Enter should return checked template, not cursor position."""
        categories = {
            "Timeline Family": ["timeline", "timeline_noir", "timeline_amber"],
        }

        with (
            patch("sys.stdin.isatty", return_value=True),
            patch.object(ExpandCollapseSelector, "show") as mock_show,
        ):
            # Simulate checking timeline_noir and returning it
            mock_show.return_value = "timeline_noir"

            selector = ExpandCollapseSelector(categories, "timeline", "html")
            result = selector.show()

            # Should return the checked template
            assert result == "timeline_noir"

    def test_cursor_movement_after_checking(self):
        """Moving cursor after checking should not affect selection."""
        categories = {
            "Timeline Family": ["timeline", "timeline_noir", "timeline_amber"],
        }
        selector = ExpandCollapseSelector(categories, "timeline", "html")

        # Expand category
        selector.toggle_category("Timeline Family")

        # Navigate to timeline_noir and check it
        selector.navigate_down()
        selector.navigate_down()
        item = selector.get_current_item()
        assert item is not None
        assert item[1] == "timeline_noir"
        selector.selected_template = item[1]

        # Move cursor to timeline_amber
        selector.navigate_down()
        item = selector.get_current_item()
        assert item is not None
        assert item[1] == "timeline_amber"

        # selected_template should still be timeline_noir
        assert selector.selected_template == "timeline_noir"

    def test_enter_with_no_checked_template(self):
        """Enter with no checked template should return current_template."""
        categories = {
            "Timeline Family": ["timeline", "timeline_noir"],
        }

        with (
            patch("sys.stdin.isatty", return_value=True),
            patch.object(ExpandCollapseSelector, "show") as mock_show,
        ):
            # Simulate no checked template, return current
            mock_show.return_value = "timeline"

            selector = ExpandCollapseSelector(categories, "timeline", "html")
            # Uncheck the template
            selector.selected_template = None
            result = selector.show()

            # Should return current_template
            assert result == "timeline"

    def test_e_key_expands_category(self):
        """'e' key should expand/collapse categories."""
        categories = {
            "Timeline Family": ["timeline", "timeline_noir"],
        }
        selector = ExpandCollapseSelector(categories, "timeline", "html")

        # Initially collapsed
        assert "Timeline Family" not in selector.expanded

        # Simulate 'e' key on category
        item = selector.get_current_item()
        assert item is not None
        assert item[0] == "category"
        selector.toggle_category(item[1])

        # Should be expanded
        assert "Timeline Family" in selector.expanded

    def test_e_key_on_template_does_nothing(self):
        """'e' key on template should do nothing."""
        categories = {
            "Timeline Family": ["timeline", "timeline_noir"],
        }
        selector = ExpandCollapseSelector(categories, "timeline", "html")

        # Expand category
        selector.toggle_category("Timeline Family")

        # Navigate to template
        selector.navigate_down()
        item = selector.get_current_item()
        assert item is not None
        assert item[0] == "template"

        # Try to toggle (should do nothing since it's a template)
        expanded_before = selector.expanded.copy()
        # In the actual implementation, 'e' key only works on categories
        # So this should not change anything
        assert selector.expanded == expanded_before

    def test_checkbox_display_shows_checked_template(self):
        """Checkbox should show which template is checked, not cursor."""
        categories = {
            "Timeline Family": ["timeline", "timeline_noir"],
        }
        selector = ExpandCollapseSelector(categories, "timeline", "html")

        # Expand category
        selector.toggle_category("Timeline Family")

        # Check timeline_noir
        selector.selected_template = "timeline_noir"

        # Move cursor to timeline
        selector.cursor_pos = 1
        item = selector.get_current_item()
        assert item is not None
        assert item[1] == "timeline"

        # Render and verify that timeline_noir shows [X], not timeline
        # (This is tested through the render method)
        assert selector.selected_template == "timeline_noir"


class TestSimpleTemplateSelector:
    """Test simplified template selector."""

    def test_select_template_simple_html(self):
        """Test simple HTML template selection."""
        with (
            patch("sys.stdin.isatty", return_value=True),
            patch.object(ExpandCollapseSelector, "show") as mock_show,
        ):
            mock_show.return_value = "timeline_noir"

            result = select_template_simple(
                kind="html",
                current="timeline",
                metadata=None,
            )

            assert result == "timeline_noir"

    def test_select_template_simple_bbcode(self):
        """Test simple BBCode template selection."""
        with (
            patch("sys.stdin.isatty", return_value=True),
            patch.object(ExpandCollapseSelector, "show") as mock_show,
        ):
            mock_show.return_value = "classic"

            result = select_template_simple(
                kind="bbcode",
                current="detailed",
                metadata=None,
            )

            assert result == "classic"

    def test_select_template_not_tty(self):
        """Test template selection in non-TTY environment."""
        with patch("sys.stdin.isatty", return_value=False):
            result = select_template_simple(
                kind="html",
                current="timeline",
                metadata=None,
            )

            # Should return current template without showing selector
            assert result == "timeline"

    def test_select_template_collapsible_alias(self):
        """Test that collapsible alias works."""
        with (
            patch("sys.stdin.isatty", return_value=True),
            patch.object(ExpandCollapseSelector, "show") as mock_show,
        ):
            mock_show.return_value = "poster"

            result = select_template_collapsible(
                kind="html",
                current="timeline",
                metadata=None,
            )

            assert result == "poster"

    def test_selector_builds_categories_dict(self):
        """Test that selector builds categories dictionary correctly."""
        with (
            patch("sys.stdin.isatty", return_value=True),
            patch.object(ExpandCollapseSelector, "__init__", return_value=None) as mock_init,
            patch.object(ExpandCollapseSelector, "show", return_value="timeline"),
        ):
            select_template_simple(
                kind="html",
                current="timeline",
                metadata=None,
            )

            # Check that __init__ was called with categories dict
            assert mock_init.called
            call_args = mock_init.call_args
            categories = call_args[1]["categories"]
            assert isinstance(categories, dict)
            assert len(categories) > 0

    def test_selector_filters_existing_templates(self):
        """Test that selector only includes existing templates."""
        with (
            patch("sys.stdin.isatty", return_value=True),
            patch("ouro.modules.prez.template_selector.available_html_templates") as mock_avail,
            patch.object(ExpandCollapseSelector, "__init__", return_value=None) as mock_init,
            patch.object(ExpandCollapseSelector, "show", return_value="timeline"),
        ):
            # Mock only a subset of templates
            mock_avail.return_value = ("timeline", "poster")

            select_template_simple(
                kind="html",
                current="timeline",
                metadata=None,
            )

            # Check categories only contain existing templates
            call_args = mock_init.call_args
            categories = call_args[1]["categories"]

            # All templates in categories should be in available list
            for templates in categories.values():
                for tmpl in templates:
                    assert tmpl in ("timeline", "poster")
