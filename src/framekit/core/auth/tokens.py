"""JWT access token management for Framekit web auth."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from loguru import logger

from framekit.core.paths import get_config_dir

# Token lifetime: 24 hours for access token
ACCESS_TOKEN_EXPIRE_HOURS = 24

_SECRET_KEY_PATH: Path | None = None


def _get_secret_key() -> str:
    """Load or generate the JWT signing key."""
    global _SECRET_KEY_PATH  # noqa: PLW0603
    key_path = _SECRET_KEY_PATH or (get_config_dir() / "auth_secret.key")
    _SECRET_KEY_PATH = key_path
    key_path.parent.mkdir(parents=True, exist_ok=True)
    if key_path.exists():
        return key_path.read_text(encoding="utf-8").strip()
    key = secrets.token_hex(32)
    key_path.write_text(key, encoding="utf-8")
    try:
        key_path.chmod(0o600)
    except OSError:
        pass
    logger.info("Generated new JWT signing key at {}", key_path)
    return key


class TokenError(Exception):
    """Raised when a JWT token is invalid or expired."""


def create_access_token(
    *,
    user_id: str,
    username: str,
    role: str,
    expire_hours: int = ACCESS_TOKEN_EXPIRE_HOURS,
) -> str:
    """Create a signed JWT access token.

    Args:
        user_id: User UUID
        username: Username embedded in token
        role: User role string
        expire_hours: Token lifetime in hours

    Returns:
        Encoded JWT string.
    """
    try:
        import jwt  # type: ignore[import-untyped]
    except ImportError as exc:
        raise RuntimeError("PyJWT package required — install framekit-cli") from exc

    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": user_id,
        "username": username,
        "role": role,
        "iat": now,
        "exp": now + timedelta(hours=expire_hours),
    }
    return str(jwt.encode(payload, _get_secret_key(), algorithm="HS256"))


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT access token.

    Args:
        token: Encoded JWT string.

    Returns:
        Decoded payload dict with ``sub``, ``username``, ``role``.

    Raises:
        TokenError: If token is invalid, expired, or malformed.
    """
    try:
        import jwt  # type: ignore[import-untyped]
        from jwt.exceptions import ExpiredSignatureError, InvalidTokenError
    except ImportError as exc:
        raise RuntimeError("PyJWT package required — install framekit-cli") from exc

    try:
        payload: dict[str, Any] = jwt.decode(
            token, _get_secret_key(), algorithms=["HS256"]
        )
        return payload
    except ExpiredSignatureError as exc:
        raise TokenError("Token expired") from exc
    except InvalidTokenError as exc:
        raise TokenError(f"Invalid token: {exc}") from exc
