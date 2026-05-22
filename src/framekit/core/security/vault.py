"""Secure vault for storing and retrieving encrypted sensitive data.

Provides a high-level interface for managing encrypted configuration data
like API tokens and credentials.
"""

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from loguru import logger

from .encryption import DecryptionError, EncryptionError, EncryptionManager
from .keyring import KeyStorage
from .permissions import set_secure_permissions


class VaultError(Exception):
    """Base exception for vault errors."""


class VaultKeyMismatchError(VaultError):
    """Raised when the configured key cannot decrypt the existing vault.

    Distinct from generic ``VaultError`` so callers (CLI handlers) can offer a
    targeted recovery flow ("backup + reset"). Trigger conditions:

    * Keyring was wiped while the vault file was kept (re-install, OS user
      change, keychain reset).
    * The key file (``master.key``) was deleted and regenerated while the
      vault file remained encrypted with the previous key.
    * The vault was restored from a backup taken with a different key.
    """


class SecureVault:
    """Secure vault for storing encrypted sensitive data.

    Manages encryption keys and provides methods for storing/retrieving
    encrypted configuration data.
    """

    def __init__(self, vault_path: Path, key_storage: KeyStorage, auto_initialize: bool = True):
        """Initialize secure vault.

        Args:
            vault_path: Path to encrypted vault file
            key_storage: Key storage instance for managing encryption key
            auto_initialize: Whether to automatically initialize vault if not exists
        """
        self.vault_path = vault_path
        self.key_storage = key_storage
        self._encryption_manager: EncryptionManager | None = None
        self._data: dict[str, Any] = {}
        self._loaded = False

        if auto_initialize:
            self._ensure_initialized()

    def _ensure_initialized(self) -> None:
        """Ensure vault is initialized with encryption key."""
        if self._encryption_manager is None:
            # Try to retrieve existing key
            key = self.key_storage.retrieve_key()

            if key is None:
                # Generate new key
                logger.info("Generating new encryption key for vault")
                key = EncryptionManager.generate_key()
                self.key_storage.store_key(key)

            self._encryption_manager = EncryptionManager(key)

            # Verify key is valid
            if not self._encryption_manager.verify_key():
                raise VaultError("Encryption key verification failed")

    def _load_vault(self) -> None:
        """Load and decrypt vault data."""
        if self._loaded:
            return

        self._ensure_initialized()
        if self._encryption_manager is None:
            raise VaultError("Encryption manager was not initialized; cannot use the vault.")

        if not self.vault_path.exists():
            logger.debug("Vault file does not exist, starting with empty vault")
            self._data = {}
            self._loaded = True
            return

        try:
            encrypted_data = self.vault_path.read_bytes()
            if not encrypted_data:
                logger.debug("Vault file is empty, starting with empty vault")
                self._data = {}
                self._loaded = True
                return

            decrypted_json = self._encryption_manager.decrypt(encrypted_data)
            self._data = json.loads(decrypted_json)
            self._loaded = True
            logger.debug(f"Loaded vault with {len(self._data)} entries")
        except DecryptionError as e:
            # Distinct exception so CLI commands can offer a targeted
            # "backup + reset" recovery flow. The plain ``VaultError`` would
            # be too generic to safely automate a destructive recovery.
            raise VaultKeyMismatchError(
                "Vault decryption failed. The configured encryption key does "
                "not match the existing vault file (key store was wiped or "
                "the vault was restored from a different machine). "
                "Run ``framekit settings security reset-vault`` to back up "
                "the unreadable file and start a fresh vault."
            ) from e
        except json.JSONDecodeError as e:
            raise VaultError(f"Vault data is corrupted: {e}") from e
        except Exception as e:
            raise VaultError(f"Failed to load vault: {e}") from e

    def _save_vault(self) -> None:
        """Encrypt and save vault data."""
        self._ensure_initialized()
        if self._encryption_manager is None:
            raise VaultError("Encryption manager was not initialized; cannot use the vault.")

        try:
            # Serialize and encrypt data
            json_data = json.dumps(self._data, indent=2)
            encrypted_data = self._encryption_manager.encrypt(json_data)

            # Ensure directory exists
            self.vault_path.parent.mkdir(parents=True, exist_ok=True)

            # Write encrypted data
            self.vault_path.write_bytes(encrypted_data)

            # Set restrictive permissions (Windows ACL + Unix chmod)
            try:
                set_secure_permissions(self.vault_path, mode="owner_only", strict=False)
            except Exception as e:
                logger.warning(f"Failed to set secure permissions on vault: {e}")

            logger.debug(f"Saved vault with {len(self._data)} entries")
        except EncryptionError as e:
            raise VaultError(f"Failed to encrypt vault: {e}") from e
        except Exception as e:
            raise VaultError(f"Failed to save vault: {e}") from e

    def store(self, key: str, value: Any) -> None:
        """Store encrypted data in vault.

        Args:
            key: Key to store data under
            value: Value to store (will be JSON-serialized)

        Raises:
            VaultError: If storage fails
        """
        self._load_vault()

        try:
            # Store with metadata
            self._data[key] = {"value": value, "updated_at": datetime.now(UTC).isoformat()}
            self._save_vault()
            logger.info(f"Stored encrypted data for key: {key}")
        except Exception as e:
            raise VaultError(f"Failed to store data for key '{key}': {e}") from e

    def retrieve(self, key: str, default: Any = None) -> Any:
        """Retrieve and decrypt data from vault.

        Args:
            key: Key to retrieve data for
            default: Default value if key not found

        Returns:
            Decrypted value or default if not found

        Raises:
            VaultError: If retrieval fails
        """
        self._load_vault()

        if key not in self._data:
            return default

        try:
            entry = self._data[key]
            return entry.get("value")
        except Exception as e:
            raise VaultError(f"Failed to retrieve data for key '{key}': {e}") from e

    def delete(self, key: str) -> bool:
        """Delete entry from vault.

        Args:
            key: Key to delete

        Returns:
            True if key was deleted, False if key didn't exist

        Raises:
            VaultError: If deletion fails
        """
        self._load_vault()

        if key not in self._data:
            return False

        try:
            del self._data[key]
            self._save_vault()
            logger.info(f"Deleted encrypted data for key: {key}")
            return True
        except Exception as e:
            raise VaultError(f"Failed to delete data for key '{key}': {e}") from e

    def exists(self, key: str) -> bool:
        """Check if key exists in vault.

        Args:
            key: Key to check

        Returns:
            True if key exists, False otherwise
        """
        self._load_vault()
        return key in self._data

    def get_entry_metadata(self, key: str) -> dict[str, Any] | None:
        """Return metadata for a vault entry (updated_at timestamp).

        Args:
            key: Key to look up

        Returns:
            Dictionary with metadata (e.g. ``{"updated_at": "..."}``), or
            ``None`` if the key does not exist in the vault.
        """
        self._load_vault()
        entry = self._data.get(key)
        if entry is None:
            return None
        return {"updated_at": entry.get("updated_at")}

    def list_keys(self) -> list[str]:
        """List all keys in vault (not values).

        Returns:
            List of keys stored in vault
        """
        self._load_vault()
        return list(self._data.keys())

    def clear(self) -> None:
        """Clear all data from vault.

        Raises:
            VaultError: If clearing fails
        """
        self._load_vault()

        try:
            # Create backup before clearing
            if self.vault_path.exists():
                backup_path = self.vault_path.with_suffix(".enc.backup")
                shutil.copy2(self.vault_path, backup_path)
                logger.info(f"Created vault backup before clearing: {backup_path}")

            self._data = {}
            self._save_vault()
            logger.info("Cleared all data from vault")
        except Exception as e:
            raise VaultError(f"Failed to clear vault: {e}") from e

    def reset(self) -> Path | None:
        """Back up an unreadable vault and start fresh.

        Designed for the :class:`VaultKeyMismatchError` recovery flow: the
        existing vault file is moved aside (timestamped) and a brand-new
        empty vault is created with the current key. The old key store stays
        in place; we only touch the encrypted document.

        Returns:
            Path to the backup file if one was created, ``None`` when the
            vault file did not exist beforehand.
        """
        from datetime import datetime

        backup_path: Path | None = None
        if self.vault_path.exists():
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            backup_path = self.vault_path.with_suffix(f".enc.broken-{timestamp}")
            try:
                shutil.move(str(self.vault_path), str(backup_path))
                logger.warning(
                    f"Moved unreadable vault aside as {backup_path}. A fresh vault will be created."
                )
            except OSError as exc:
                raise VaultError(f"Could not move broken vault aside: {exc}") from exc

        # Start a clean session: reset cached state and let _save_vault()
        # write an empty document with the current key.
        self._data = {}
        self._loaded = True
        try:
            self._save_vault()
        except Exception as exc:
            raise VaultError(f"Failed to create fresh vault: {exc}") from exc
        logger.info(f"Created fresh empty vault at {self.vault_path}")
        return backup_path

    def rotate_key(self, new_key: bytes | None = None) -> None:
        """Rotate encryption key by re-encrypting all data with new key.

        Args:
            new_key: New encryption key (32 bytes). If None, generates new key.

        Raises:
            VaultError: If key rotation fails
        """
        self._load_vault()

        try:
            # Create backup with timestamp to avoid collision
            if self.vault_path.exists():
                timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
                backup_path = self.vault_path.with_suffix(f".enc.backup-{timestamp}")
                shutil.copy2(self.vault_path, backup_path)
                logger.info(f"Created vault backup before key rotation: {backup_path}")

            # Generate or validate new key
            if new_key is None:
                new_key = EncryptionManager.generate_key()
            elif len(new_key) != 32:
                raise VaultError("New key must be 32 bytes")

            # Replace the stored key (rotation is the only legitimate
            # overwrite path; ``store_key`` refuses by default).
            self.key_storage.store_key(new_key, overwrite=True)

            # Create new encryption manager with new key
            self._encryption_manager = EncryptionManager(new_key)

            # Re-save vault with new key (data is already loaded)
            self._save_vault()

            logger.info("Successfully rotated encryption key")
        except Exception as e:
            raise VaultError(f"Failed to rotate encryption key: {e}") from e

    def get_status(self) -> dict[str, Any]:
        """Get vault status information.

        Returns:
            Dictionary with vault status information
        """
        self._load_vault()

        return {
            "vault_path": str(self.vault_path),
            "vault_exists": self.vault_path.exists(),
            "key_storage": self.key_storage.get_storage_location(),
            "key_exists": self.key_storage.key_exists(),
            "entry_count": len(self._data),
            "keys": self.list_keys(),
        }

    def restore_from_backup(self) -> bool:
        """Restore vault from backup file.

        Returns:
            True if restore successful, False if no backup exists

        Raises:
            VaultError: If restore fails
        """
        backup_path = self.vault_path.with_suffix(".enc.backup")

        if not backup_path.exists():
            logger.warning("No backup file found to restore from")
            return False

        try:
            shutil.copy2(backup_path, self.vault_path)
            self._loaded = False  # Force reload
            self._load_vault()
            logger.info(f"Restored vault from backup: {backup_path}")
            return True
        except Exception as e:
            raise VaultError(f"Failed to restore from backup: {e}") from e
