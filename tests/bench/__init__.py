"""Performance benchmark suite for Swirrl hot paths.

The benchmarks here are intentionally scaffolded with synthetic inputs so
they run inside the CI matrix without external media. Real-media
benchmarks (against ``.mkv`` / ``.mp4`` fixtures) live alongside an
opt-in marker and are excluded from the default collection.

Hot paths covered (S1 baseline, refined in S11):

* ``swirrl.core.mediainfo.probe_media_file`` — MediaInfo parsing.
* ``swirrl.core.settings.normalize.normalize_settings`` — config
  normalisation.
* Pipeline cold start (Click ``--help`` rendering as a proxy for the
  import graph cost; real cold-start measured in S11 with an isolated
  subprocess fixture).
* Batch 20-release sweep — synthetic queue construction + scan.

Run locally:

    pytest tests/bench/ --benchmark-only --benchmark-autosave

Compare against the saved baseline:

    pytest tests/bench/ --benchmark-only --benchmark-compare=0001
"""

from __future__ import annotations
