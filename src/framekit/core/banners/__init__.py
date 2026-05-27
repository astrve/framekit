"""Banner Registry for the Framekit presentation system.

Manages 168 banners across 8 designs, 7 sections, and 3 languages.
"""

from dataclasses import dataclass
from enum import Enum


class BannerSection(Enum):
    """Available banner sections."""

    INFORMATION = "information"
    METADATA = "metadata"
    SYNOPSIS = "synopsis"
    RELEASE = "release"
    TECHNICAL = "technical"
    AUDIO = "audio"
    SUBTITLES = "subtitles"


class BannerDesign(Enum):
    """Available banner designs. Format: {suite}_{color}."""

    ASTRO_GRADIENT_BLUE = "astro-gradient_blue"
    ASTRO_GRADIENT_PURPLE = "astro-gradient_purple"
    ASTRO_GRADIENT_ORANGE = "astro-gradient_orange"
    BLACK_AND_WHITE_CLASSIC = "black-and-white_classic"
    BLACK_AND_WHITE_INVERTED = "black-and-white_inverted"
    CYBERPUNK_YELLOW = "cyberpunk_yellow"
    CYBERPUNK_PINK = "cyberpunk_pink"
    CYBERPUNK_BLUE = "cyberpunk_blue"
    CYBERPUNK_GREEN = "cyberpunk_green"
    DARK_FANTASY_RED = "dark-fantasy_red"
    DARK_FANTASY_GOLD = "dark-fantasy_gold"
    DARK_FANTASY_PURPLE = "dark-fantasy_purple"
    DIGITAL_BLUE_CYAN = "digital-blue_cyan"
    DIGITAL_BLUE_ELECTRIC = "digital-blue_electric"
    DIGITAL_BLUE_NAVY = "digital-blue_navy"
    MILITARY_GREEN_OLIVE = "military-green_olive"
    MILITARY_GREEN_FOREST = "military-green_forest"
    MINIMAL_BLUE_ICE = "minimal-blue_ice"
    MINIMAL_BLUE_STEEL = "minimal-blue_steel"
    MINIMAL_BLUE_MIDNIGHT = "minimal-blue_midnight"
    MINIMAL_BLUE_SLATE = "minimal-blue_slate"
    ROBOTIC_CHROME = "robotic_chrome"
    ROBOTIC_RUST = "robotic_rust"
    ROBOTIC_GRAPHITE = "robotic_graphite"
    NEON_GREEN = "neon_green"
    NEON_PINK = "neon_pink"
    SUNSET_WARM = "sunset_warm"
    SUNSET_COLD = "sunset_cold"
    VINTAGE_SEPIA = "vintage_sepia"
    VINTAGE_NOIR = "vintage_noir"


@dataclass
class BannerConfig:
    """Configuration for a single banner."""

    design: BannerDesign
    section: BannerSection
    language: str

    @property
    def filename(self) -> str:
        """Banner filename."""
        return f"{self.section.value}.png"

    @property
    def path(self) -> str:
        """Relative path within the archive."""
        return f"banners/{self.design.value}/{self.language}/{self.filename}"

    @property
    def url(self) -> str:
        """Direct download URL for this banner."""
        base_url = "https://github.com/astrve/framekit/releases/download/banners-v1.0.0"
        # GitHub serves files from ZIP archives directly
        return f"{base_url}/framekit-banners-v1.0.0.zip#{self.path}"


class BannerRegistry:
    """Centralized banner registry."""

    # Base URL for banner archive
    ARCHIVE_URL = "https://github.com/astrve/framekit/releases/download/banners-v1.0.0/framekit-banners-v1.0.0.zip"

    # Translated labels for each section
    SECTION_LABELS: dict[BannerSection, dict[str, str]] = {
        BannerSection.INFORMATION: {"en": "Information", "fr": "Informations", "es": "Información"},
        BannerSection.METADATA: {"en": "Metadata", "fr": "Métadonnées", "es": "Metadatos"},
        BannerSection.SYNOPSIS: {"en": "Synopsis", "fr": "Synopsis", "es": "Sinopsis"},
        BannerSection.RELEASE: {"en": "Release", "fr": "Release", "es": "Release"},
        BannerSection.TECHNICAL: {
            "en": "Technical Information",
            "fr": "Informations techniques",
            "es": "Información técnica",
        },
        BannerSection.AUDIO: {"en": "Audio", "fr": "Audio", "es": "Audio"},
        BannerSection.SUBTITLES: {"en": "Subtitles", "fr": "Sous-titres", "es": "Subtítulos"},
    }

    @classmethod
    def get_banner(cls, design: str, section: str, language: str) -> BannerConfig | None:
        """Get banner configuration.

        Args:
            design: Design name (e.g., "classic")
            section: Section name (e.g., "information")
            language: Language code (e.g., "fr")

        Returns:
            BannerConfig or None if invalid
        """
        try:
            design_enum = BannerDesign(design)
            section_enum = BannerSection(section)

            if language not in ["en", "fr", "es"]:
                return None

            return BannerConfig(design=design_enum, section=section_enum, language=language)
        except (ValueError, KeyError):
            return None

    @classmethod
    def get_all_banners(cls, design: str, language: str) -> dict[str, str]:
        """Get all banner URLs for a design/language combination.

        Args:
            design: Design name
            language: Language code

        Returns:
            Dictionary mapping section names to URLs
        """
        banners = {}

        for section in BannerSection:
            banner = cls.get_banner(design, section.value, language)
            if banner:
                # For now, return a placeholder URL structure
                # In production, these would point to extracted banner files
                # or use a CDN with the actual banner images
                banners[section.value] = (
                    f"https://raw.githubusercontent.com/astrve/framekit/refs/heads/feature/banners/{design}/{language}/{section.value}.png"
                )

        return banners

    @classmethod
    def get_section_label(cls, section: str, language: str) -> str:
        """Get translated label for a section.

        Args:
            section: Section name
            language: Language code

        Returns:
            Translated label or section name if not found
        """
        try:
            section_enum = BannerSection(section)
            return cls.SECTION_LABELS[section_enum].get(language, section)
        except (ValueError, KeyError):
            return section

    @classmethod
    def list_designs(cls) -> list[str]:
        """List all available designs."""
        return [design.value for design in BannerDesign]

    @classmethod
    def list_sections(cls) -> list[str]:
        """List all available sections."""
        return [section.value for section in BannerSection]

    @classmethod
    def list_languages(cls) -> list[str]:
        """List all supported languages."""
        return ["en", "fr", "es"]

    @classmethod
    def get_archive_url(cls) -> str:
        """Get the URL for the complete banner archive."""
        return cls.ARCHIVE_URL


# Export main classes
__all__ = ["BannerConfig", "BannerDesign", "BannerRegistry", "BannerSection"]
