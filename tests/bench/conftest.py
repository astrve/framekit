"""Bench-suite fixtures and pytest configuration.

Keeps the bench tests isolated from the main test collection: the default
``pytest`` invocation does not auto-run them (they live in ``tests/bench/``
which is collected, but every test is marked ``benchmark`` so callers can
deselect via ``-m "not benchmark"``).

Real-media benchmarks carry the ``realmedia`` marker and are excluded
unless ``--realmedia`` is passed on the CLI.
"""

from __future__ import annotations

import pytest


def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers used by this bench suite."""

    config.addinivalue_line("markers", "benchmark: performance benchmark (slow)")
    config.addinivalue_line(
        "markers",
        "realmedia: requires real .mkv/.mp4 fixtures on disk (opt-in)",
    )


def pytest_addoption(parser: pytest.Parser) -> None:
    """Add the ``--realmedia`` opt-in flag."""

    parser.addoption(
        "--realmedia",
        action="store_true",
        default=False,
        help="Run benchmarks that need real media fixtures.",
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Skip ``realmedia`` benchmarks unless ``--realmedia`` was supplied."""

    if config.getoption("--realmedia"):
        return
    skip_real = pytest.mark.skip(reason="realmedia opt-in; pass --realmedia to enable")
    for item in items:
        if "realmedia" in item.keywords:
            item.add_marker(skip_real)
