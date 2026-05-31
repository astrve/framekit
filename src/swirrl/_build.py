"""Setuptools build helpers for deterministic package-data outputs."""

from __future__ import annotations

import shutil
from pathlib import Path

from setuptools.command.build_py import build_py as _build_py


class SwirrlBuildPy(_build_py):
    """Clean stale static package-data before each Python build."""

    def run(self) -> None:
        static_dir = Path(self.build_lib) / "swirrl" / "web" / "static"
        shutil.rmtree(static_dir, ignore_errors=True)
        super().run()
