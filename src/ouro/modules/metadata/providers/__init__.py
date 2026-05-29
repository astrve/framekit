"""Metadata provider implementations.

Concrete providers live alongside this file (``tmdb_models``, ``anilist``,
``trakt``, ``tvdb``…). Sub-modules are imported lazily by
:mod:`ouro.modules.metadata.factory` and :mod:`ouro.modules.metadata.chain`,
so this ``__init__`` deliberately stays empty: no eager imports, no
``__all__`` referencing symbols that may not be wired up yet.
"""

from __future__ import annotations
