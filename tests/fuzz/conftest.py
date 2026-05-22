"""Fuzz suite Hypothesis profiles.

Three profiles registered:

* ``dev`` (default, ``max_examples=20``) — runs in <1 s locally.
* ``ci`` (``max_examples=200``) — default in CI matrix.
* ``ci_long`` (``max_examples=100_000``) — opt-in via
  ``HYPOTHESIS_PROFILE=ci_long`` for the nightly sweep.

Select with ``--hypothesis-profile=<name>`` or via env.
"""

from __future__ import annotations

from hypothesis import HealthCheck, Verbosity, settings

settings.register_profile(
    "dev",
    max_examples=20,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
    verbosity=Verbosity.normal,
)
settings.register_profile(
    "ci",
    max_examples=200,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)
settings.register_profile(
    "ci_long",
    max_examples=100_000,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.filter_too_much],
)

# Default profile if neither CLI nor env selects one.
settings.load_profile("dev")
