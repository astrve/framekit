"""Property-based + fuzz tests for Ouro parsers.

Uses Hypothesis to generate diverse inputs (~thousands per session) and
validates that the parsers never crash, never leak secrets, and always
return well-typed results — even on malformed payloads.

Four parsers are targeted in S2 of the pro-grade roadmap:

* ``ouro.core.naming.release_name_from_mkv_paths`` — accepts arbitrary
  filename lists; must always return ``str``.
* ``ouro.modules.torrent.service._bencode`` (and its decoder) — must
  round-trip valid bencoded payloads and reject malformed ones cleanly.
* ``ouro.modules.nfo.scanner`` ingestion — given arbitrary folder
  structures, must never raise an unhandled exception.
* ``ouro.modules.extract.audio_extractor.AudioExtractor.validate_bitrate`` —
  bitrate parser must reject malformed values and keep strict range bounds.

Run locally:

    pytest tests/fuzz/ -v --hypothesis-show-statistics

The S1 scaffold ships shallow examples (``max_examples=200`` defaults) so
CI stays fast; the 100k-iteration sweep is wired in S2 via the
``HYPOTHESIS_PROFILE=ci_long`` env profile.
"""

from __future__ import annotations
