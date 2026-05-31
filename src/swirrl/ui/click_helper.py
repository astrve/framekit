"""Smart Click import with terminal detection."""

import contextlib
import os


def should_use_rich_click() -> bool:
    """Determine if rich-click should be used based on environment."""
    if os.getenv("SWIRRL_NO_RICH_CLICK"):
        return False

    if os.getenv("NO_COLOR"):
        return False

    return True


# Smart import — try rich_click first, fall back to plain click
click = None
if should_use_rich_click():
    with contextlib.suppress(ImportError):
        import rich_click as click  # type: ignore[assignment]

if click is None:
    import click  # type: ignore[assignment]
