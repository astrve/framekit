"""BBCode template system for generating torrent descriptions.

Provides templates for different tracker types and utilities for rendering
descriptions with metadata and screenshots.
"""

from .metadata_extractor import ParsedRelease
from .models import TorrentMetadata

# Tracker-specific BBCode templates
TRACKER_BBCODE_TEMPLATES: dict[str, str] = {
    "unit3d": """[center]
[b]{title} ({year})[/b]
[/center]

[b]Description:[/b]
{description}

[b]Technical Info:[/b]
[list]
[*]Resolution: {resolution}
[*]Source: {source}
[*]Codec: {codec}
[*]Audio: {audio}
{hdr_line}
[/list]

{screenshots_block}""",
    "gazelle": """{title} ({year})

{description}

[b]Technical:[/b] {resolution} | {source} | {codec} | {audio}

{screenshots_block}""",
    "minimal": "{description}",
}


def _extract_title_year(name: str) -> tuple[str, str]:
    title = name
    year = ""
    import re

    year_match = re.search(r"\b(19\d{2}|20\d{2})\b", name)
    if year_match:
        year = year_match.group(1)
    return title, year


def _unknown(value: str | None) -> str:
    return value or "Unknown"


def _template_variables(
    metadata: TorrentMetadata,
    *,
    parsed: ParsedRelease | None,
    image_urls: list[str] | None,
) -> dict[str, str]:
    title, year = _extract_title_year(metadata.name)
    return {
        "title": title,
        "year": year,
        "description": metadata.description or "No description provided.",
        "resolution": _unknown(metadata.resolution),
        "source": _unknown(metadata.source or (parsed.source if parsed else None)),
        "codec": _unknown(metadata.codec or (parsed.codec if parsed else None)),
        "audio": _unknown(metadata.audio or (parsed.audio if parsed else None)),
        "hdr_line": _hdr_line(metadata, parsed),
        "screenshots_block": _build_screenshots_block(image_urls or []),
    }


def _hdr_line(metadata: TorrentMetadata, parsed: ParsedRelease | None) -> str:
    hdr_value = metadata.hdr or (parsed.hdr if parsed else "")
    return f"[*]HDR: {hdr_value}" if hdr_value else ""


def _render_template_safe(template: str, template_vars: dict[str, str], fallback: str) -> str:
    try:
        return template.format(**template_vars)
    except KeyError:
        return fallback


def render_template(
    template_name: str,
    metadata: TorrentMetadata,
    parsed: ParsedRelease | None = None,
    image_urls: list[str] | None = None,
) -> str:
    """Fill template with metadata and parsed data.

    If metadata.description is already complete BBCode, uses it as-is.
    Otherwise builds from template.

    Args:
        template_name: Name of template to use (unit3d, gazelle, minimal)
        metadata: Torrent metadata
        parsed: Optional parsed release data
        image_urls: Optional list of screenshot URLs

    Returns:
        Rendered BBCode description
    """
    if detect_bbcode_completeness(metadata.description):
        return metadata.description

    template = TRACKER_BBCODE_TEMPLATES.get(template_name, TRACKER_BBCODE_TEMPLATES["minimal"])
    template_vars = _template_variables(metadata, parsed=parsed, image_urls=image_urls)
    return _render_template_safe(
        template,
        template_vars,
        metadata.description or "No description provided.",
    )


def detect_bbcode_completeness(bbcode: str) -> bool:
    """Return True if BBCode seems complete.

    Checks for:
    - Presence of [img] tags (has screenshots)
    - Length > 200 characters (substantial content)

    Args:
        bbcode: BBCode string to check

    Returns:
        True if BBCode appears complete
    """
    if not bbcode:
        return False

    # Check for images
    if "[img]" in bbcode.lower():
        return True

    # Check for substantial content
    if len(bbcode) > 200:
        return True

    return False


def _build_screenshots_block(image_urls: list[str]) -> str:
    """Build BBCode block for screenshots.

    Args:
        image_urls: List of image URLs

    Returns:
        BBCode formatted screenshot block
    """
    if not image_urls:
        return ""

    # Limit to 10 images
    urls = image_urls[:10]

    # Build centered image block
    block = "\n[center]\n[b]Screenshots:[/b]\n"
    for url in urls:
        block += f"[img]{url}[/img]\n"
    block += "[/center]"

    return block


def enrich_description(
    description: str,
    metadata: TorrentMetadata,
    parsed: ParsedRelease | None = None,
    tracker_type: str = "unit3d",
) -> str:
    """Enrich a basic description with technical details.

    If description is already complete, returns as-is.
    Otherwise adds technical information based on tracker type.

    Args:
        description: Base description
        metadata: Torrent metadata
        parsed: Optional parsed release data
        tracker_type: Tracker type (unit3d, gazelle, minimal)

    Returns:
        Enriched description
    """
    # If already complete, return as-is
    if detect_bbcode_completeness(description):
        return description

    # Create temporary metadata with the description
    temp_metadata = TorrentMetadata(
        name=metadata.name,
        description=description,
        category=metadata.category,
        type=metadata.type,
        resolution=metadata.resolution,
        tmdb_id=metadata.tmdb_id,
        imdb_id=metadata.imdb_id,
        source=metadata.source,
        codec=metadata.codec,
        audio=metadata.audio,
        hdr=metadata.hdr,
    )

    # Render with appropriate template
    return render_template(tracker_type, temp_metadata, parsed)


def strip_bbcode(text: str) -> str:
    """Strip BBCode tags from text.

    Useful for extracting plain text from BBCode descriptions.

    Args:
        text: Text with BBCode tags

    Returns:
        Plain text without BBCode tags
    """
    import re

    # Remove BBCode tags
    text = re.sub(r"\[/?[^\]]+\]", "", text)

    # Clean up extra whitespace
    text = re.sub(r"\s+", " ", text)
    text = text.strip()

    return text


def validate_bbcode(text: str) -> tuple[bool, list[str]]:
    """Validate BBCode syntax.

    Checks for:
    - Matching opening/closing tags
    - Valid tag names
    - Proper nesting

    Args:
        text: BBCode text to validate

    Returns:
        Tuple of (is_valid, error_messages)
    """
    import re

    errors = []

    # Find all tags
    tag_pattern = re.compile(r"\[(/?)([^\]]+)\]")
    tags = tag_pattern.findall(text)

    # Track open tags
    open_tags = []

    for is_closing, tag_content in tags:
        # Extract tag name (before any = or space)
        tag_name = tag_content.split("=")[0].split()[0].lower()

        if is_closing == "/":
            # Closing tag
            if not open_tags:
                errors.append(f"Closing tag [{tag_name}] without opening tag")
            elif open_tags[-1] != tag_name:
                errors.append(
                    f"Mismatched closing tag: expected [{open_tags[-1]}], got [{tag_name}]"
                )
            else:
                open_tags.pop()
        else:
            # Opening tag (skip self-closing tags like [*])
            if tag_name not in ["*", "img"]:
                open_tags.append(tag_name)

    # Check for unclosed tags
    if open_tags:
        errors.append(f"Unclosed tags: {', '.join(f'[{tag}]' for tag in open_tags)}")

    return len(errors) == 0, errors
