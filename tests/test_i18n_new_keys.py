from __future__ import annotations

# Tests to ensure newly added translation keys are present and correctly translated for French
# and Spanish locales. These tests verify that important user-visible strings do not fall back
# to English defaults when a non-English locale is active. They use the ``temporary_locale``
# context manager to avoid polluting global locale state. Converting this module-level
# documentation to comments ensures that imports remain at the top of the file, satisfying
# the Ruff E402 rule without suppressing it.
from framekit.core.i18n import temporary_locale, tr


def test_common_labels_are_translated_in_french_and_spanish() -> None:
    """
    Ensure that common summary labels such as Errors, Unchanged, Files, Forced and Processing
    are translated in French and Spanish. When the locale is set to FR or ES, tr() should not
    return the English default string.
    """
    # Mapping of keys to their English defaults for assertion purposes
    english_defaults = {
        "common.errors": "Errors",
        "common.unchanged": "Unchanged",
        "common.files": "Files",
        "common.forced": "Forced",
        "common.processing": "Processing",
    }

    for locale in ("fr", "es"):
        with temporary_locale(locale):
            for key, default in english_defaults.items():
                result = tr(key, default=default)
                assert result != default, (
                    f"Key {key} unexpectedly returned English default for locale {locale}: {result}"
                )


def test_cleanmkv_and_pipeline_keys_are_translated() -> None:
    """
    Verify that specific keys used in CleanMKV previews, pipeline output and headless/error
    messages are translated in French and Spanish. If the translation catalog is incomplete,
    this test will detect fallbacks to the English default.
    """
    test_cases = [
        ("cleanmkv.audio_kept", "Audio tracks kept"),
        ("cleanmkv.subtitles_kept", "Subtitle tracks kept"),
        ("pipeline.success.completed", "Pipeline completed."),
        (
            "selector.error.headless",
            "Interactive selection is not available in headless mode (no TTY).",
        ),
        ("torrent.announce.none", "No announce URL configured."),
    ]

    for locale in ("fr", "es"):
        with temporary_locale(locale):
            for key, english_default in test_cases:
                translated = tr(key, default=english_default)
                assert translated != english_default, (
                    f"Key {key} unexpectedly returned English default for locale {locale}: {translated}"
                )
