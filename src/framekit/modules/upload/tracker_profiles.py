"""Tracker profiles database.

Pre-configured profiles for common UNIT3D trackers with fallback data
when API discovery fails or is incomplete.
"""

import copy
from typing import Any
from urllib.parse import urlparse

from loguru import logger

# Pre-configured tracker profiles
TRACKER_PROFILES: dict[str, dict[str, Any]] = {
    "beyond-hd.me": {
        "name": "Beyond-HD",
        "type": "unit3d",
        "categories": {
            "Movie": 1,
            "TV": 2,
            "Documentary": 3,
            "Sport": 4,
            "Music": 5,
            "Anime": 6,
        },
        "types": {
            "Blu-ray Remux": 1,
            "Encode": 2,
            "WEB Remux": 3,
            "WEB-DL": 4,
            "WEBRip": 5,
            "HDTV": 6,
            "DVD": 7,
            "Other": 8,
        },
        "resolutions": {
            "2160p": 1,
            "1080p": 2,
            "1080i": 3,
            "720p": 4,
            "576p": 5,
            "480p": 6,
            "Other": 7,
        },
    },
    "blutopia.cc": {
        "name": "Blutopia",
        "type": "unit3d",
        "categories": {
            "Movie": 1,
            "TV": 2,
        },
        "types": {
            "Blu-ray Remux": 1,
            "Encode": 2,
            "WEB Remux": 3,
            "WEB-DL": 4,
            "WEBRip": 5,
            "HDTV": 6,
            "DVD": 7,
        },
        "resolutions": {
            "2160p": 1,
            "1080p": 2,
            "1080i": 3,
            "720p": 4,
            "576p": 5,
            "480p": 6,
        },
    },
    "aither.cc": {
        "name": "Aither",
        "type": "unit3d",
        "categories": {
            "Movie": 1,
            "TV": 2,
            "Documentary": 3,
            "Music": 4,
            "Anime": 5,
        },
        "types": {
            "Blu-ray Remux": 1,
            "Encode": 2,
            "WEB Remux": 3,
            "WEB-DL": 4,
            "WEBRip": 5,
            "HDTV": 6,
            "DVD": 7,
            "Other": 8,
        },
        "resolutions": {
            "2160p": 1,
            "1080p": 2,
            "1080i": 3,
            "720p": 4,
            "576p": 5,
            "480p": 6,
            "Other": 7,
        },
    },
    "reelflix.xyz": {
        "name": "ReelFliX",
        "type": "unit3d",
        "categories": {
            "Movie": 1,
            "TV": 2,
            "Documentary": 3,
        },
        "types": {
            "Blu-ray Remux": 1,
            "Encode": 2,
            "WEB Remux": 3,
            "WEB-DL": 4,
            "WEBRip": 5,
            "HDTV": 6,
            "DVD": 7,
            "Other": 8,
        },
        "resolutions": {
            "2160p": 1,
            "1080p": 2,
            "1080i": 3,
            "720p": 4,
            "576p": 5,
            "480p": 6,
            "Other": 7,
        },
    },
    "fearnopeer.com": {
        "name": "FearNoPeer",
        "type": "unit3d",
        "categories": {
            "Movie": 1,
            "TV": 2,
            "Documentary": 3,
            "Sport": 4,
            "Music": 5,
            "Anime": 6,
        },
        "types": {
            "Blu-ray Remux": 1,
            "Encode": 2,
            "WEB Remux": 3,
            "WEB-DL": 4,
            "WEBRip": 5,
            "HDTV": 6,
            "DVD": 7,
            "Other": 8,
        },
        "resolutions": {
            "2160p": 1,
            "1080p": 2,
            "1080i": 3,
            "720p": 4,
            "576p": 5,
            "480p": 6,
            "Other": 7,
        },
    },
    "torrentleech.org": {
        "name": "TorrentLeech",
        "type": "custom",
        "categories": {
            "Movie": 8,
            "TV": 26,
            "Documentary": 29,
            "Anime": 34,
        },
        "types": {
            "BluRay": 1,
            "WEB-DL": 2,
            "WEBRip": 3,
            "HDTV": 4,
            "DVD": 5,
        },
        "resolutions": {
            "2160p": 1,
            "1080p": 2,
            "720p": 3,
            "480p": 4,
        },
    },
}


def get_profile(url: str) -> dict[str, Any] | None:
    """Get tracker profile by URL.

    Extracts domain from URL and returns matching profile if available.

    Args:
        url: Tracker URL (e.g., "https://beyond-hd.me" or "beyond-hd.me")

    Returns:
        Tracker profile dictionary or None if not found
    """
    try:
        # Parse URL to extract domain
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"

        parsed = urlparse(url)
        domain = parsed.netloc.lower()

        # Remove www. prefix if present
        if domain.startswith("www."):
            domain = domain[4:]

        # Look up profile
        profile = TRACKER_PROFILES.get(domain)

        if profile:
            logger.debug(f"Found tracker profile for: {domain}")
            # Deep-copy: callers MAY mutate nested dicts (categories/types/
            # resolutions) when merging discovered data; a shallow ``.copy()``
            # would let them poison the in-memory registry for the rest of
            # the process.
            return copy.deepcopy(profile)
        logger.debug(f"No tracker profile found for: {domain}")
        return None

    except Exception as e:
        logger.warning(f"Failed to parse tracker URL '{url}': {e}")
        return None


def merge_profile_with_discovered(
    profile: dict[str, Any], discovered: dict[str, Any]
) -> dict[str, Any]:
    """Merge static profile with live API discovery data.

    Live data has priority over static profile data. This allows profiles
    to provide fallback values while still using the most up-to-date
    information from the tracker API.

    Args:
        profile: Static tracker profile
        discovered: Live API discovery data

    Returns:
        Merged profile dictionary
    """
    result = profile.copy()

    # Merge categories (discovered takes priority)
    if discovered.get("categories"):
        result["categories"] = discovered["categories"]
        logger.debug("Using discovered categories (overriding profile)")
    elif "categories" not in result:
        result["categories"] = {}

    # Merge types (discovered takes priority)
    if discovered.get("types"):
        result["types"] = discovered["types"]
        logger.debug("Using discovered types (overriding profile)")
    elif "types" not in result:
        result["types"] = {}

    # Merge resolutions (discovered takes priority)
    if discovered.get("resolutions"):
        result["resolutions"] = discovered["resolutions"]
        logger.debug("Using discovered resolutions (overriding profile)")
    elif "resolutions" not in result:
        result["resolutions"] = {}

    # Update tracker type if discovered
    if discovered.get("tracker_type"):
        result["type"] = discovered["tracker_type"]

    # Update name if discovered
    if discovered.get("name"):
        result["name"] = discovered["name"]

    return result


def list_supported_trackers() -> list[str]:
    """Get list of tracker domains with pre-configured profiles.

    Returns:
        List of tracker domain names
    """
    return sorted(TRACKER_PROFILES.keys())


def get_tracker_info(domain: str) -> dict[str, Any] | None:
    """Get basic information about a tracker.

    Args:
        domain: Tracker domain (e.g., "beyond-hd.me")

    Returns:
        Dictionary with name and type, or None if not found
    """
    profile = TRACKER_PROFILES.get(domain.lower())
    if profile:
        return {
            "name": profile["name"],
            "type": profile["type"],
            "domain": domain,
        }
    return None
