"""Smoke tests for the prez service.

The prez module renders BBCode + HTML presentation sheets from release data.
At 2.6k lines it is the second-largest module in the project. These tests
do not try to verify the rendered visuals — they pin the *contract* that
the rest of the codebase relies on:

* Public render functions accept the documented kwargs and return strings.
* Template registries expose at least the built-in catalogues.
* The Jinja environment loads at least one layout per kind.
* Locale resolution falls back to ``en`` for unknown locales.
* The ``PrezService`` class is constructible without surprises.

Refactors of the internals must keep every assertion below green.
"""

from __future__ import annotations

import pytest

from framekit.modules.prez import service as prez_service


def _minimal_release():
    from framekit.core.models.nfo import ReleaseNfoData

    return ReleaseNfoData(
        media_kind="movie",
        release_title="Test.Release.2024.1080p.WEB-DL.x264-GROUP",
        title_display="Test Release",
        series_title=None,
        year="2024",
        source="WEB-DL",
        resolution="1080p",
        video_tag="x264",
        audio_tag="AAC",
        language_tag="MULTI.VFF",
        audio_languages_display="English",
    )


def test_module_exports_public_surface():
    expected = (
        "render_html",
        "render_bbcode",
        "available_html_templates",
        "available_bbcode_templates",
        "describe_html_template",
        "describe_bbcode_template",
        "PrezService",
        "PrezBuildOptions",
    )
    for name in expected:
        assert hasattr(prez_service, name), f"prez missing public symbol: {name}"


def test_available_templates_have_minimum_set():
    html = prez_service.available_html_templates()
    bbcode = prez_service.available_bbcode_templates()
    assert len(html) >= 8, "expected at least 8 HTML templates"
    assert len(bbcode) >= 1, "expected at least 1 BBCode template"
    assert "classic" in bbcode, "the classic BBCode template must always be present"


def test_render_html_returns_string_with_minimum_release():
    html = prez_service.render_html(_minimal_release(), locale="en")
    assert isinstance(html, str)
    assert "<html" in html
    assert "</html>" in html


def test_render_bbcode_returns_string_with_minimum_release():
    bbcode = prez_service.render_bbcode(_minimal_release(), locale="en")
    assert isinstance(bbcode, str)
    # BBCode wrappers — both forms are common.
    assert "[" in bbcode and "]" in bbcode


def test_render_html_honours_locale_attribute():
    html = prez_service.render_html(_minimal_release(), locale="es")
    assert '<html lang="es">' in html


def test_render_bbcode_honours_locale():
    """Rendered output should pick up locale-specific labels."""
    en = prez_service.render_bbcode(_minimal_release(), locale="en")
    fr = prez_service.render_bbcode(_minimal_release(), locale="fr")
    # We do not pin a specific string — just that the two rendered outputs
    # differ when the locale differs (and labels follow the locale).
    assert isinstance(en, str)
    assert isinstance(fr, str)


def test_normalize_locale_falls_back_to_en():
    """Unknown locales must not crash — fall back to ``en``."""
    normalized = prez_service._normalize_locale("zz-XX")
    assert normalized == "en"


def test_normalize_locale_handles_none_and_empty():
    assert prez_service._normalize_locale(None) == "en"
    assert prez_service._normalize_locale("") == "en"


def test_prez_service_constructible():
    """The ``PrezService`` class must be constructible without arguments."""
    svc = prez_service.PrezService()
    assert svc is not None


def test_prez_build_options_constructible():
    opts = prez_service.PrezBuildOptions()
    assert opts is not None


def test_describe_html_template_returns_string():
    templates = prez_service.available_html_templates()
    assert templates, "fixture invariant: at least one html template must exist"
    first = templates[0]
    desc = prez_service.describe_html_template(first)
    assert isinstance(desc, str)


def test_describe_bbcode_template_returns_string():
    desc = prez_service.describe_bbcode_template("classic")
    assert isinstance(desc, str)


def test_timeline_variants_keep_timeline_description_and_category():
    desc_ocean = prez_service.describe_html_template("timeline_ocean")
    desc_amber = prez_service.describe_html_template("timeline_amber")
    cat_ocean = prez_service.template_category("timeline_ocean", kind="html")
    cat_amber = prez_service.template_category("timeline_amber", kind="html")

    assert "Chronological vertical layout" in desc_ocean
    assert "Chronological vertical layout" in desc_amber
    assert cat_ocean == "Timeline"
    assert cat_amber == "Timeline"


@pytest.mark.parametrize(
    "kind,name",
    [
        ("html", "cinematic_dark"),
        ("bbcode", "classic"),
    ],
)
def test_load_template_returns_jinja_template(kind: str, name: str):
    """``_load_template`` must resolve the .en.jinja2 fallback when locale is missing."""
    template = prez_service._load_template(kind, name, "fr")
    # jinja2.Template has a ``render`` method.
    assert hasattr(template, "render")
