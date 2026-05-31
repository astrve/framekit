"""Unit tests for :mod:`swirrl.modules.upload.tracker_profiles`.

Covers the pre-configured tracker registry, URL → profile lookup, the
merge-with-discovered logic, and the public listing helpers. All tests are
pure-functional (no network, no I/O) so they run fast and deterministically
inside the CI matrix.
"""

from __future__ import annotations

import pytest

from swirrl.modules.upload.tracker_profiles import (
    TRACKER_PROFILES,
    get_profile,
    get_tracker_info,
    list_supported_trackers,
    merge_profile_with_discovered,
)

# ---------------------------------------------------------------------------
# Registry shape
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "domain",
    [
        "beyond-hd.me",
        "blutopia.cc",
        "aither.cc",
        "reelflix.xyz",
        "fearnopeer.com",
        "torrentleech.org",
    ],
)
def test_registry_contains_known_domain(domain: str) -> None:
    """Each ship-default tracker must be present with the required keys."""

    assert domain in TRACKER_PROFILES
    profile = TRACKER_PROFILES[domain]
    assert profile.get("name")
    assert profile["type"] in ("unit3d", "gazelle", "custom")
    assert isinstance(profile.get("categories"), dict)
    assert isinstance(profile.get("types"), dict)
    assert isinstance(profile.get("resolutions"), dict)


def test_registry_values_are_integer_ids() -> None:
    """Category/type/resolution IDs must be ints — trackers reject strings."""

    for domain, profile in TRACKER_PROFILES.items():
        for bucket in ("categories", "types", "resolutions"):
            mapping = profile.get(bucket, {})
            for label, value in mapping.items():
                assert isinstance(value, int), (
                    f"{domain}.{bucket}[{label!r}] must be int, got {type(value).__name__}"
                )
                assert value > 0


# ---------------------------------------------------------------------------
# get_profile
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "https://beyond-hd.me",
        "http://beyond-hd.me",
        "beyond-hd.me",
        "https://www.beyond-hd.me",
        "https://beyond-hd.me/upload",
        "https://BEYOND-HD.ME",
    ],
)
def test_get_profile_accepts_url_variants(url: str) -> None:
    """Schemeless, scheme, ``www.``-prefixed and uppercased URLs all map."""

    profile = get_profile(url)
    assert profile is not None
    assert profile["name"] == "Beyond-HD"


def test_get_profile_returns_copy_not_reference() -> None:
    """Mutating the returned dict must not poison the registry."""

    first = get_profile("beyond-hd.me")
    assert first is not None
    first["categories"]["JunkBucket"] = 999
    second = get_profile("beyond-hd.me")
    assert second is not None
    assert "JunkBucket" not in second["categories"]


def test_get_profile_unknown_returns_none() -> None:
    assert get_profile("not-a-real-tracker.example") is None


def test_get_profile_handles_garbage_input() -> None:
    """Malformed input must return ``None`` without raising."""

    # ``urlparse`` accepts almost anything so we exercise the broad catch.
    assert get_profile("") is None
    assert get_profile("://broken") is None


# ---------------------------------------------------------------------------
# merge_profile_with_discovered
# ---------------------------------------------------------------------------


def test_merge_keeps_profile_when_nothing_discovered() -> None:
    profile = {
        "name": "X",
        "type": "unit3d",
        "categories": {"Movie": 1},
        "types": {"Encode": 2},
        "resolutions": {"1080p": 3},
    }
    merged = merge_profile_with_discovered(profile, {})
    assert merged["categories"] == {"Movie": 1}
    assert merged["types"] == {"Encode": 2}
    assert merged["resolutions"] == {"1080p": 3}
    assert merged["name"] == "X"
    assert merged["type"] == "unit3d"


def test_merge_overrides_with_discovered_categories() -> None:
    profile = {"name": "X", "type": "unit3d", "categories": {"Movie": 1}}
    discovered = {"categories": {"Movie": 99, "TV": 100}}
    merged = merge_profile_with_discovered(profile, discovered)
    assert merged["categories"] == {"Movie": 99, "TV": 100}


def test_merge_overrides_with_discovered_types_and_resolutions() -> None:
    profile = {"name": "X", "type": "unit3d", "types": {"Encode": 1}}
    discovered = {
        "types": {"Encode": 7, "WEB-DL": 8},
        "resolutions": {"1080p": 1, "2160p": 2},
    }
    merged = merge_profile_with_discovered(profile, discovered)
    assert merged["types"] == {"Encode": 7, "WEB-DL": 8}
    assert merged["resolutions"] == {"1080p": 1, "2160p": 2}


def test_merge_supplies_empty_buckets_when_missing() -> None:
    """Profiles lacking ``categories`` get an empty bucket, never KeyError."""

    profile = {"name": "X", "type": "unit3d"}
    merged = merge_profile_with_discovered(profile, {})
    assert merged["categories"] == {}
    assert merged["types"] == {}
    assert merged["resolutions"] == {}


def test_merge_updates_tracker_type_and_name() -> None:
    profile = {"name": "Old Name", "type": "unit3d"}
    discovered = {"name": "New Name", "tracker_type": "gazelle"}
    merged = merge_profile_with_discovered(profile, discovered)
    assert merged["name"] == "New Name"
    assert merged["type"] == "gazelle"


def test_merge_does_not_mutate_input_profile() -> None:
    profile = {"name": "X", "type": "unit3d", "categories": {"Movie": 1}}
    discovered = {"categories": {"Movie": 99}}
    merge_profile_with_discovered(profile, discovered)
    assert profile["categories"] == {"Movie": 1}  # original untouched


# ---------------------------------------------------------------------------
# list_supported_trackers
# ---------------------------------------------------------------------------


def test_list_supported_trackers_returns_sorted_strings() -> None:
    trackers = list_supported_trackers()
    assert trackers == sorted(trackers)
    assert all(isinstance(t, str) for t in trackers)
    assert len(trackers) == len(TRACKER_PROFILES)


# ---------------------------------------------------------------------------
# get_tracker_info
# ---------------------------------------------------------------------------


def test_get_tracker_info_returns_summary() -> None:
    info = get_tracker_info("beyond-hd.me")
    assert info is not None
    assert info == {"name": "Beyond-HD", "type": "unit3d", "domain": "beyond-hd.me"}


def test_get_tracker_info_lowercases_input() -> None:
    info = get_tracker_info("BEYOND-HD.ME")
    assert info is not None
    assert info["name"] == "Beyond-HD"


def test_get_tracker_info_unknown_returns_none() -> None:
    assert get_tracker_info("nope.example") is None
