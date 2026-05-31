from __future__ import annotations

from copy import deepcopy

import pytest

from swirrl.core.settings.normalize import normalize_settings
from swirrl.core.settings.schema import DEFAULT_SETTINGS

pytestmark = pytest.mark.benchmark


def test_bench_normalize_settings_default(benchmark) -> None:
    payload = deepcopy(DEFAULT_SETTINGS)
    result = benchmark(normalize_settings, payload)
    assert isinstance(result, dict)
    assert "metadata" in result


def test_bench_normalize_settings_overridden(benchmark) -> None:
    payload = deepcopy(DEFAULT_SETTINGS)
    payload["general"]["locale"] = "fr-FR"
    payload["metadata"]["language"] = "fr-FR"
    payload["cache"]["tmdb"]["ttl_days"] = 14
    payload.setdefault("plugins", {})["allowed"] = ["swirrl-plugin-anilist"]
    result = benchmark(normalize_settings, payload)
    assert result["general"]["locale"] == "fr"
