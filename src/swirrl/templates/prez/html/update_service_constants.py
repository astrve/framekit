#!/usr/bin/env python3
"""Generate updated constants for service.py with 140 templates."""

# 10 designs
DESIGNS = [
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

# 14 colors
COLORS = [
    ("dark", "Dark"),
    ("forest", "Forest 🌲"),
    ("sunset", "Sunset 🌅"),
    ("ocean", "Ocean 🌊"),
    ("sepia", "Sepia 🟤"),
    ("rainbow", "Rainbow 🌈"),
    ("midnight", "Midnight 🌙"),
    ("cherry", "Cherry 🍒"),
    ("lavender", "Lavender 💜"),
    ("mint", "Mint 🌿"),
    ("amber", "Amber 🟠"),
    ("slate", "Slate 🪨"),
    ("coral", "Coral 🪸"),
    ("teal", "Teal 🦚"),
]

# Design descriptions
DESIGN_DESCRIPTIONS = {
    "cinematic": "Movie-style horizontal layout",
    "magazine": "Editorial multi-column layout",
    "minimal": "Clean and spacious design",
    "card": "Grid-based card layout",
    "timeline": "Chronological vertical layout",
    "glassmorphism": "Frosted glass effects",
    "brutalist": "Raw asymmetric design",
    "neon_cyberpunk": "Glowing futuristic style",
    "vintage_retro": "80s/90s pastel aesthetic",
    "neumorphism": "Soft 3D relief design",
}

# Design categories (capitalized)
DESIGN_CATEGORIES = {
    "cinematic": "Cinematic",
    "magazine": "Magazine",
    "minimal": "Minimal",
    "card": "Card",
    "timeline": "Timeline",
    "glassmorphism": "Glassmorphism",
    "brutalist": "Brutalist",
    "neon_cyberpunk": "Neon Cyberpunk",
    "vintage_retro": "Vintage Retro",
    "neumorphism": "Neumorphism",
}


def generate_template_names():
    """Generate HTML_TEMPLATE_NAMES tuple."""
    print("# New Template System: 10 designs × 14 colors = 140 templates")
    print("HTML_TEMPLATE_NAMES = (")

    for design in DESIGNS:
        design_name = DESIGN_CATEGORIES[design]
        print(f"    # {design_name} (14 variants)")

        # Generate template names for this design
        names = [f'"{design}_{color[0]}"' for color in COLORS]

        # Print in groups of 7 for readability
        for i in range(0, len(names), 7):
            group = names[i : i + 7]
            line = ", ".join(group)
            if i + 7 < len(names):
                print(f"    {line},")
            else:
                # Last line of this design
                if design != DESIGNS[-1]:
                    print(f"    {line},")
                else:
                    print(f"    {line}")

    print(")")


def generate_descriptions():
    """Generate HTML_TEMPLATE_DESCRIPTIONS dict."""
    print("\n# New template descriptions (10 designs × 14 colors)")
    print("HTML_TEMPLATE_DESCRIPTIONS = {")

    for design in DESIGNS:
        desc = DESIGN_DESCRIPTIONS[design]
        for color_id, color_name in COLORS:
            template_name = f"{design}_{color_id}"
            print(f'    "{template_name}": "{desc} - {color_name}",')

    print("}")


def generate_categories():
    """Generate HTML_TEMPLATE_CATEGORIES dict."""
    print("\n# New template categories (10 designs × 14 colors)")
    print("HTML_TEMPLATE_CATEGORIES = {")

    for design in DESIGNS:
        category = DESIGN_CATEGORIES[design]
        # Print all 14 colors for this design on one or two lines
        templates = [f'"{design}_{color[0]}": "{category}"' for color in COLORS]

        # Print in groups of 7
        for i in range(0, len(templates), 7):
            group = templates[i : i + 7]
            line = ", ".join(group)
            print(f"    {line},")

    print("}")


if __name__ == "__main__":
    print("=" * 80)
    print("SERVICE.PY CONSTANTS - 140 TEMPLATES")
    print("=" * 80)
    print()
    generate_template_names()
    generate_descriptions()
    generate_categories()
    print("\n" + "=" * 80)
    print("Copy the above output to service.py")
    print("=" * 80)
