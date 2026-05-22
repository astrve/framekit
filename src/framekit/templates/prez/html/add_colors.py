#!/usr/bin/env python3
"""Script to add 8 new color variants to all remaining designs in themes.yaml."""

from pathlib import Path

import yaml

# Define the 8 new color variants
NEW_COLORS = {
    "midnight": {
        "primary": "#0a0f1a",
        "secondary": "#141a2e",
        "accent": "#c0c8d8",
        "text": "#e8ecf4",
        "muted": "#8090b0",
        "line": "#2a3550",
        "card": "#0f1420",
    },
    "cherry": {
        "primary": "#1a0a0f",
        "secondary": "#2e1419",
        "accent": "#ff4466",
        "text": "#ffe8ec",
        "muted": "#ff8899",
        "line": "#4a1e28",
        "card": "#200f14",
    },
    "lavender": {
        "primary": "#15101a",
        "secondary": "#251a2e",
        "accent": "#b794f6",
        "text": "#f0e8ff",
        "muted": "#d4b8ff",
        "line": "#3a2850",
        "card": "#1a1420",
    },
    "mint": {
        "primary": "#0a1a14",
        "secondary": "#142e23",
        "accent": "#5de4a8",
        "text": "#e8fff4",
        "muted": "#8fffc8",
        "line": "#1e5038",
        "card": "#0f2018",
    },
    "amber": {
        "primary": "#1a140a",
        "secondary": "#2e2314",
        "accent": "#ffb347",
        "text": "#fff4e8",
        "muted": "#ffd699",
        "line": "#503a1e",
        "card": "#201810",
    },
    "slate": {
        "primary": "#14161a",
        "secondary": "#1e2228",
        "accent": "#94a3b8",
        "text": "#e8ecf0",
        "muted": "#b0bcc8",
        "line": "#2e3540",
        "card": "#181a1e",
    },
    "coral": {
        "primary": "#1a1214",
        "secondary": "#2e1e23",
        "accent": "#ff8a80",
        "text": "#fff0ec",
        "muted": "#ffb8b0",
        "line": "#4a3038",
        "card": "#201618",
    },
    "teal": {
        "primary": "#0a1a1a",
        "secondary": "#142e2e",
        "accent": "#5fd4d4",
        "text": "#e8ffff",
        "muted": "#8fe8e8",
        "line": "#1e5050",
        "card": "#0f2020",
    },
}


def main():
    """Handle main."""
    themes_file = Path(__file__).parent / "themes.yaml"

    # Load the YAML file
    with open(themes_file, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    # Update the header comment
    header_comment = "# Prez Template System - Theme Definitions\n# 10 Designs × 14 Color Variants = 140 Templates\n"

    # Add new colors to each design
    designs_to_update = [
        "minimal",
        "card",
        "timeline",
        "glassmorphism",
        "brutalist",
        "neon_cyberpunk",
        "vintage_retro",
        "neumorphism",
    ]

    for design_name in designs_to_update:
        if design_name in data["designs"]:
            colors = data["designs"][design_name]["colors"]
            # Add new colors if they don't exist
            for color_name, color_values in NEW_COLORS.items():
                if color_name not in colors:
                    colors[color_name] = color_values
                    print(f"[OK] Added {color_name} to {design_name}")

    # Save the updated YAML
    with open(themes_file, "w", encoding="utf-8") as f:
        f.write(header_comment + "\n")
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    print(
        f"\n[SUCCESS] Updated themes.yaml with 8 new colors for {len(designs_to_update)} designs!"
    )
    print("[INFO] Total templates: 10 designs x 14 colors = 140 templates")


if __name__ == "__main__":
    main()
