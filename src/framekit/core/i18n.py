from __future__ import annotations

import json
import os
from collections.abc import Iterator
from contextlib import contextmanager
from functools import cache, lru_cache
from importlib import resources
from typing import Any

from babel.core import Locale, UnknownLocaleError

DEFAULT_LOCALE = "en"
SUPPORTED_LOCALES = frozenset({"en", "fr", "es"})
LOCALE_PACKAGE = "framekit.locales"


def _normalize_locale(value: str | None) -> str:
    raw = (value or "").strip()
    if not raw:
        return DEFAULT_LOCALE

    try:
        locale = Locale.parse(raw.replace("_", "-"), sep="-")
    except (UnknownLocaleError, ValueError):
        short = raw.split("_", 1)[0].split("-", 1)[0].lower()
        return short if short in SUPPORTED_LOCALES else DEFAULT_LOCALE

    language = (locale.language or "").lower()
    return language if language in SUPPORTED_LOCALES else DEFAULT_LOCALE


@cache
def _load_catalog(locale_code: str) -> dict[str, str]:
    normalized = _normalize_locale(locale_code)
    try:
        resource = resources.files(LOCALE_PACKAGE).joinpath(f"{normalized}.json")
        raw = resource.read_text(encoding="utf-8")
        payload = json.loads(raw)
    except Exception:
        if normalized != DEFAULT_LOCALE:
            return _load_catalog(DEFAULT_LOCALE)
        return {}

    if not isinstance(payload, dict):
        return {}

    return {str(key): str(value) for key, value in payload.items()}


@lru_cache(maxsize=1)
def get_locale() -> str:
    env_candidates = [
        os.environ.get("FRAMEKIT_LOCALE", ""),
        os.environ.get("LC_ALL", ""),
        os.environ.get("LC_MESSAGES", ""),
        os.environ.get("LANG", ""),
    ]

    for candidate in env_candidates:
        normalized = _normalize_locale(candidate)
        if normalized in SUPPORTED_LOCALES:
            return normalized

    return DEFAULT_LOCALE


def get_supported_locales() -> tuple[str, ...]:
    return tuple(sorted(SUPPORTED_LOCALES))


def set_locale(locale_code: str) -> None:
    normalized = _normalize_locale(locale_code)
    os.environ["FRAMEKIT_LOCALE"] = normalized
    get_locale.cache_clear()


@contextmanager
def temporary_locale(locale_code: str | None) -> Iterator[None]:
    previous = get_locale()
    if locale_code:
        set_locale(locale_code)
    try:
        yield
    finally:
        set_locale(previous)


def tr(key: str, default: str | None = None, **kwargs: Any) -> str:
    locale_code = get_locale()
    template = (
        _load_catalog(locale_code).get(key)
        or _load_catalog(DEFAULT_LOCALE).get(key)
        or default
        or key
    )

    if kwargs:
        try:
            return template.format(**kwargs)
        except Exception:
            return template

    return template
