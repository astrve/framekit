"""Swirrl auth — Level 2 multi-user authentication.

Provides SQLite user store, bcrypt password hashing, and JWT token management
for the web UI. Auth is opt-in: disabled by default, enabled via settings.
"""

from swirrl.core.auth.models import User, UserRole, UserStore
from swirrl.core.auth.tokens import TokenError, create_access_token, decode_access_token

__all__ = [
    "User",
    "UserRole",
    "UserStore",
    "TokenError",
    "create_access_token",
    "decode_access_token",
]
