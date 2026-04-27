from __future__ import annotations

import sys

import pytest

from framekit.core.settings import redact_settings
from framekit.ui.selector import (
    SelectorOption,
    confirm_choice,
    select_many,
    select_one,
    text_input,
)


def test_redact_settings_masks_authorization_and_bearer() -> None:
    """Ensure that settings redaction masks authorization- and bearer-related keys.

    The SECRET_KEY_PARTS in settings are extended to include 'authorization' and
    'bearer'.  This test confirms that those keys are replaced with the
    placeholder by ``redact_settings``.
    """
    settings = {
        "modules": {},
        "authorization": "Bearer secret-token",
        "Bearer": "some-bearer-value",
        "bearer_token": "abc123",
        "client_secret": "shhh",
    }
    masked = redact_settings(settings)
    assert masked["authorization"] == "********"
    assert masked["Bearer"] == "********"
    assert masked["bearer_token"] == "********"
    assert masked["client_secret"] == "********"


def test_selector_functions_raise_in_headless(monkeypatch) -> None:
    """Interactive selector functions should raise RuntimeError when stdin is not a TTY.

    By monkeypatching ``sys.stdin.isatty`` to return ``False``, we simulate a
    headless environment.  All functions that rely on interactive input should
    refuse to operate under these conditions.
    """
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)

    with pytest.raises(RuntimeError):
        select_one(
            title="Test",
            entries=[SelectorOption(value=1, label="One")],
        )

    with pytest.raises(RuntimeError):
        select_many(
            title="Test",
            entries=[SelectorOption(value=1, label="One")],
        )

    with pytest.raises(RuntimeError):
        confirm_choice(title="Are you sure?", default=True)

    with pytest.raises(RuntimeError):
        text_input(title="Enter value")
