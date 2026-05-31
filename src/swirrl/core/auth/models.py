"""User store backed by SQLite with bcrypt password hashing."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from threading import Lock
from typing import Any
from uuid import uuid4

from loguru import logger

from swirrl.core.paths import get_config_dir


class UserRole(str, Enum):
    """User access roles."""

    ADMIN = "admin"
    VIEWER = "viewer"


class User:
    """Represents one user account."""

    def __init__(
        self,
        *,
        id: str,
        username: str,
        password_hash: str,
        role: str,
        created_at: str,
        enabled: bool,
    ) -> None:
        """Initialize user."""
        self.id = id
        self.username = username
        self.password_hash = password_hash
        self.role = UserRole(role) if role in (r.value for r in UserRole) else UserRole.VIEWER
        self.created_at = created_at
        self.enabled = enabled

    def to_public_dict(self) -> dict[str, Any]:
        """Return user info without password hash."""
        return {
            "id": self.id,
            "username": self.username,
            "role": self.role.value,
            "created_at": self.created_at,
            "enabled": self.enabled,
        }

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> User:
        """Build User from a DB row."""
        return cls(
            id=str(row["id"]),
            username=str(row["username"]),
            password_hash=str(row["password_hash"]),
            role=str(row["role"]),
            created_at=str(row["created_at"]),
            enabled=bool(row["enabled"]),
        )


class UserStore:
    """SQLite-backed user store with bcrypt password hashing.

    Requires the ``bcrypt`` package (included in the default install).
    Auth is disabled by default; enable via ``auth.enabled`` setting.
    """

    _lock = Lock()

    def __init__(self, db_path: Path | None = None) -> None:
        """Initialize user store."""
        self._db_path = db_path or (get_config_dir() / "users.db")
        self._init_db()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_db(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'viewer',
                    created_at TEXT NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 1
                )
                """
            )
            conn.commit()

    @staticmethod
    def _hash_password(password: str) -> str:
        """Hash password with bcrypt."""
        try:
            import bcrypt  # type: ignore[import-untyped]
        except ImportError as exc:
            raise RuntimeError("bcrypt package required — install swirrl-auto") from exc
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode(), salt).decode()

    @staticmethod
    def _verify_password(password: str, hashed: str) -> bool:
        """Verify a bcrypt password hash."""
        try:
            import bcrypt  # type: ignore[import-untyped]
        except ImportError:
            return False
        try:
            return bool(bcrypt.checkpw(password.encode(), hashed.encode()))
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def count(self) -> int:
        """Return total number of registered users."""
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) FROM users").fetchone()
            return int(row[0]) if row else 0

    def create(self, *, username: str, password: str, role: UserRole = UserRole.VIEWER) -> User:
        """Create a new user.

        Args:
            username: Unique username (3-32 chars, alphanumeric + underscore)
            password: Plaintext password (will be hashed)
            role: Access role (default: viewer)

        Returns:
            The newly created User.

        Raises:
            ValueError: If username is invalid or already exists.
        """
        username = username.strip().lower()
        if not (3 <= len(username) <= 32):
            raise ValueError("username must be 3-32 characters")
        if not all(c.isalnum() or c == "_" for c in username):
            raise ValueError("username must contain only letters, digits, and underscores")
        if not password or len(password) < 8:
            raise ValueError("password must be at least 8 characters")
        password_hash = self._hash_password(password)
        user_id = str(uuid4())
        created_at = datetime.now(UTC).isoformat()
        with self._lock, self._connect() as conn:
            try:
                conn.execute(
                    "INSERT INTO users (id, username, password_hash, role, created_at, enabled) "
                    "VALUES (?, ?, ?, ?, ?, 1)",
                    (user_id, username, password_hash, role.value, created_at),
                )
                conn.commit()
            except sqlite3.IntegrityError as exc:
                raise ValueError(f"username '{username}' already exists") from exc
        logger.info("Created user '{}' with role '{}'", username, role.value)
        return User(
            id=user_id,
            username=username,
            password_hash=password_hash,
            role=role.value,
            created_at=created_at,
            enabled=True,
        )

    def authenticate(self, *, username: str, password: str) -> User | None:
        """Verify credentials and return the user, or None on failure."""
        username = username.strip().lower()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE username = ? AND enabled = 1", (username,)
            ).fetchone()
        if row is None:
            return None
        user = User.from_row(row)
        if not self._verify_password(password, user.password_hash):
            return None
        return user

    def get_by_id(self, user_id: str) -> User | None:
        """Return user by ID, or None."""
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return User.from_row(row) if row else None

    def get_by_username(self, username: str) -> User | None:
        """Return user by username, or None."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE username = ?", (username.strip().lower(),)
            ).fetchone()
        return User.from_row(row) if row else None

    def list_users(self) -> list[User]:
        """Return all users ordered by creation date."""
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM users ORDER BY created_at").fetchall()
        return [User.from_row(r) for r in rows]

    def set_enabled(self, user_id: str, *, enabled: bool) -> bool:
        """Enable or disable a user. Returns True if found."""
        with self._lock, self._connect() as conn:
            result = conn.execute(
                "UPDATE users SET enabled = ? WHERE id = ?", (1 if enabled else 0, user_id)
            )
            conn.commit()
            return result.rowcount > 0

    def set_role(self, user_id: str, role: UserRole) -> bool:
        """Change user role. Returns True if found."""
        with self._lock, self._connect() as conn:
            result = conn.execute(
                "UPDATE users SET role = ? WHERE id = ?", (role.value, user_id)
            )
            conn.commit()
            return result.rowcount > 0

    def delete(self, user_id: str) -> bool:
        """Delete a user. Returns True if found."""
        with self._lock, self._connect() as conn:
            result = conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
            conn.commit()
            return result.rowcount > 0

    def change_password(self, user_id: str, new_password: str) -> bool:
        """Change user password. Returns True if found."""
        if not new_password or len(new_password) < 8:
            raise ValueError("password must be at least 8 characters")
        password_hash = self._hash_password(new_password)
        with self._lock, self._connect() as conn:
            result = conn.execute(
                "UPDATE users SET password_hash = ? WHERE id = ?", (password_hash, user_id)
            )
            conn.commit()
            return result.rowcount > 0
