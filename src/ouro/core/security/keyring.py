"""Secure key storage using system keyring with file-based fallback.

Provides secure storage for encryption keys using the system's keyring
service when available, with a fallback to encrypted file storage.
"""

import json
from pathlib import Path
from typing import Any, cast

from loguru import logger

from .permissions import set_secure_permissions

# Try to import keyring, but don't fail if not available
keyring: Any = None
KeyringError: type[BaseException] = Exception  # Fallback type
try:
    import keyring as _keyring_module  # type: ignore[import-untyped]
    from keyring.errors import KeyringError as _KeyringError  # type: ignore[import-untyped]

    keyring = _keyring_module
    KeyringError = cast(type[BaseException], _KeyringError)
    _keyring_ok = True
except ImportError:
    _keyring_ok = False

KEYRING_AVAILABLE: bool = _keyring_ok


class KeyStorageError(Exception):
    """Exception raised for key storage errors."""


class KeyStorage:
    """Manages secure storage and retrieval of encryption keys.

    Uses system keyring when available, falls back to file-based storage
    with restricted permissions.
    """

    SERVICE_NAME = "ouro"
    KEY_NAME = "master_encryption_key"

    def __init__(self, key_file: Path | None = None, prefer_keyring: bool = True):
        """Initialize key storage.

        Args:
            key_file: Path to file-based key storage (fallback)
            prefer_keyring: Whether to prefer system keyring over file storage
        """
        self.key_file = key_file
        self.prefer_keyring = prefer_keyring and KEYRING_AVAILABLE
        self._use_keyring = False
        self._actual_storage: str = "unknown"

        # Determine which storage method to use
        if self.prefer_keyring:
            try:
                # Test if keyring is functional
                keyring.get_keyring()
                self._use_keyring = True
                logger.info("Using system keyring for key storage")
            except Exception as e:
                logger.warning(f"System keyring not available: {e}. Using file-based storage.")
                self._use_keyring = False
        else:
            logger.info("Using file-based key storage")

    def store_key(self, key: bytes, *, overwrite: bool = False) -> None:
        """Store an encryption key securely.

        Args:
            key: 32-byte encryption key.
            overwrite: When ``False`` (default), refuse to replace an existing
                key file. Callers that intentionally rotate keys (vault key
                rotation, recovery flows) must pass ``overwrite=True``. The
                keyring backend has no equivalent constraint — values are
                always set under the same ``SERVICE_NAME``/``KEY_NAME``.

        Raises:
            KeyStorageError: when the key is malformed, the keyring/file
                backend fails, or an existing file would be silently replaced.
        """
        self._validate_key_bytes(key)
        key_hex = key.hex()

        if self._try_store_in_keyring(key_hex):
            return

        if self.key_file is None:
            raise KeyStorageError("No key file specified for fallback storage")

        self._store_in_file(key_hex, overwrite=overwrite)

    def _validate_key_bytes(self, key: bytes) -> None:
        if not isinstance(key, bytes):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise KeyStorageError("Key must be bytes")
        if len(key) != 32:
            raise KeyStorageError("Key must be 32 bytes")

    def _try_store_in_keyring(self, key_hex: str) -> bool:
        if not self._use_keyring:
            return False
        try:
            keyring.set_password(self.SERVICE_NAME, self.KEY_NAME, key_hex)
            self._actual_storage = "System Keyring"
            logger.info("Encryption key stored in system keyring")
            return True
        except KeyringError as error:
            logger.error(f"Failed to store key in keyring: {error}")
            return False

    def _store_in_file(self, key_hex: str, *, overwrite: bool) -> None:
        try:
            import os

            if self.key_file is None:
                raise KeyringError("Key file path is not configured.")
            self.key_file.parent.mkdir(parents=True, exist_ok=True)

            key_data = {"key": key_hex, "version": 1}

            # ``O_EXCL`` protects against silent first-time overwrite. When
            # the caller explicitly opts in to overwrite we skip the flag
            # and rely on the same secure-permissions step below.
            flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
            if not overwrite:
                flags |= os.O_EXCL
            fd = os.open(self.key_file, flags, mode=0o600)
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(key_data, f, indent=2)
            except Exception:
                os.close(fd)
                raise

            try:
                set_secure_permissions(self.key_file, mode="owner_only", strict=True)
            except Exception as e:
                logger.error(f"Failed to set secure permissions on key file: {e}")
                try:
                    self.key_file.unlink()
                except Exception as unlink_exc:
                    logger.warning(
                        f"Could not remove insecure key file {self.key_file} after "
                        f"permission failure: {unlink_exc}. Remove it manually."
                    )
                raise KeyStorageError(
                    "Cannot store key securely: failed to set file permissions. "
                    "Ensure keyring is available or the filesystem supports "
                    "secure permissions."
                ) from e

            self._actual_storage = str(self.key_file)
            logger.info(f"Encryption key stored securely in file: {self.key_file}")
        except FileExistsError:
            raise KeyStorageError(
                f"Key file already exists: {self.key_file}. "
                "Pass overwrite=True to replace it (used by key rotation)."
            ) from None
        except Exception as error:
            raise KeyStorageError(f"Failed to store key in file: {error}") from error

    def retrieve_key(self) -> bytes | None:
        """Retrieve encryption key.

        Returns:
            Encryption key (32 bytes) or None if not found

        Raises:
            KeyStorageError: If key retrieval fails
        """
        # Try keyring first if enabled
        if self._use_keyring:
            try:
                key_hex = keyring.get_password(self.SERVICE_NAME, self.KEY_NAME)
                if key_hex:
                    self._actual_storage = "System Keyring"
                    logger.debug("Retrieved encryption key from system keyring")
                    return bytes.fromhex(key_hex)
            except KeyringError as e:
                logger.error(f"Failed to retrieve key from keyring: {e}")
                # Fall through to file storage

        # Try file-based storage
        if self.key_file and self.key_file.exists():
            try:
                key_data = json.loads(self.key_file.read_text())
                key_hex = key_data.get("key")
                if key_hex:
                    self._actual_storage = str(self.key_file)
                    logger.debug(f"Retrieved encryption key from file: {self.key_file}")
                    return bytes.fromhex(key_hex)
            except Exception as e:
                raise KeyStorageError(f"Failed to retrieve key from file: {e}") from e

        return None

    def delete_key(self) -> None:
        """Delete stored encryption key.

        Raises:
            KeyStorageError: If key deletion fails
        """
        errors = []

        # Try to delete from keyring
        if self._use_keyring:
            try:
                keyring.delete_password(self.SERVICE_NAME, self.KEY_NAME)
                logger.info("Deleted encryption key from system keyring")
            except KeyringError as e:
                errors.append(f"Keyring: {e}")

        # Try to delete from file
        if self.key_file and self.key_file.exists():
            try:
                self.key_file.unlink()
                logger.info(f"Deleted encryption key file: {self.key_file}")
            except Exception as e:
                errors.append(f"File: {e}")

        if errors:
            raise KeyStorageError(f"Failed to delete key: {'; '.join(errors)}")

    def key_exists(self) -> bool:
        """Check if encryption key exists.

        Returns:
            True if key exists, False otherwise
        """
        # Check keyring
        if self._use_keyring:
            try:
                key = keyring.get_password(self.SERVICE_NAME, self.KEY_NAME)
                if key:
                    return True
            except KeyringError:
                pass

        # Check file
        if self.key_file and self.key_file.exists():
            try:
                key_data = json.loads(self.key_file.read_text())
                return "key" in key_data
            except Exception as e:
                logger.warning(
                    f"Key file {self.key_file} exists but could not be parsed: {e}. "
                    "Treat as missing."
                )

        return False

    def get_storage_location(self) -> str:
        """Get description of where key is actually stored.

        Returns the actual backend that last succeeded for a store or retrieve
        operation. Falls back to the configured preference when no operation
        has been performed yet.

        Returns:
            Human-readable storage location
        """
        if self._actual_storage != "unknown":
            return self._actual_storage
        # Fallback to configured preference when no operation has resolved yet
        if self._use_keyring:
            return "System Keyring"
        elif self.key_file:
            return str(self.key_file)
        else:
            return "Not configured"

    def migrate_to_keyring(self) -> bool:
        """Migrate key from file storage to system keyring.

        Returns:
            True if migration successful, False otherwise
        """
        if not KEYRING_AVAILABLE:
            logger.warning("System keyring not available for migration")
            return False

        if not self.key_file or not self.key_file.exists():
            logger.warning("No file-based key to migrate")
            return False

        try:
            # Read key from file
            key_data = json.loads(self.key_file.read_text())
            key_hex = key_data.get("key")
            if not key_hex:
                logger.error("Invalid key file format")
                return False

            # Store in keyring
            keyring.set_password(self.SERVICE_NAME, self.KEY_NAME, key_hex)

            # Delete file
            self.key_file.unlink()

            # Update storage method
            self._use_keyring = True

            logger.info("Successfully migrated key from file to system keyring")
            return True
        except Exception as e:
            logger.error(f"Failed to migrate key to keyring: {e}")
            return False
