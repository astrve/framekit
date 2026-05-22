"""Encryption utilities for securing sensitive data.

Uses Fernet (symmetric encryption) from the cryptography library.
"""

import base64
import secrets
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from .permissions import set_secure_permissions


class EncryptionError(Exception):
    """Base exception for encryption errors."""


class DecryptionError(Exception):
    """Exception raised when decryption fails."""


class EncryptionManager:
    """Manages encryption and decryption operations using Fernet.

    Provides secure encryption/decryption with proper key derivation
    and error handling.
    """

    def __init__(self, key: bytes | None = None):
        """Initialize encryption manager.

        Args:
            key: Encryption key (32 bytes). If None, generates a new key.
        """
        if key is None:
            key = self.generate_key()

        if not isinstance(key, bytes):  # pyright: ignore[reportUnnecessaryIsInstance]  # Runtime guard for callers that bypass type checking
            raise EncryptionError("Encryption key must be bytes")

        if len(key) != 32:
            raise EncryptionError("Encryption key must be 32 bytes")

        # Create Fernet cipher with base64-encoded key
        self._fernet = Fernet(base64.urlsafe_b64encode(key))

    @staticmethod
    def generate_key() -> bytes:
        """Generate a secure random encryption key.

        Returns:
            32-byte encryption key
        """
        return secrets.token_bytes(32)

    def encrypt(self, data: str) -> bytes:
        """Encrypt string data.

        Args:
            data: String to encrypt

        Returns:
            Encrypted data as bytes

        Raises:
            EncryptionError: If encryption fails
        """
        try:
            return self._fernet.encrypt(data.encode("utf-8"))
        except Exception as e:
            raise EncryptionError(f"Encryption failed: {e}") from e

    def decrypt(self, encrypted_data: bytes) -> str:
        """Decrypt encrypted data.

        Args:
            encrypted_data: Encrypted bytes to decrypt

        Returns:
            Decrypted string

        Raises:
            DecryptionError: If decryption fails
        """
        try:
            decrypted = self._fernet.decrypt(encrypted_data)
            return decrypted.decode("utf-8")
        except InvalidToken as exc:
            raise DecryptionError("Invalid encryption key or corrupted data") from exc
        except Exception as e:
            raise DecryptionError(f"Decryption failed: {e}") from e

    def encrypt_to_file(self, data: str, filepath: Path) -> None:
        """Encrypt data and write to file.

        Args:
            data: String to encrypt
            filepath: Path to output file

        Raises:
            EncryptionError: If encryption or file write fails
        """
        try:
            encrypted = self.encrypt(data)
            filepath.parent.mkdir(parents=True, exist_ok=True)
            filepath.write_bytes(encrypted)

            # Set restrictive permissions (Windows ACL + Unix chmod).
            # Failure is surfaced as a warning: the encrypted payload is written
            # but the OS-level access control is weaker than promised, which
            # matters for ``fk doctor`` and security audits.
            try:
                set_secure_permissions(filepath, mode="owner_only", strict=False)
            except Exception as perm_exc:
                from loguru import logger as _logger

                _logger.warning(
                    "Encrypted file written but permission tightening failed for "
                    f"{filepath}: {perm_exc}. The ciphertext is safe; verify file "
                    "permissions via `fk doctor --check-config`."
                )
        except EncryptionError:
            raise
        except Exception as e:
            raise EncryptionError(f"Failed to write encrypted file: {e}") from e

    def decrypt_from_file(self, filepath: Path) -> str:
        """Read and decrypt data from file.

        Args:
            filepath: Path to encrypted file

        Returns:
            Decrypted string

        Raises:
            DecryptionError: If file read or decryption fails
        """
        try:
            encrypted = filepath.read_bytes()
            return self.decrypt(encrypted)
        except DecryptionError:
            raise
        except FileNotFoundError as exc:
            raise DecryptionError(f"Encrypted file not found: {filepath}") from exc
        except Exception as e:
            raise DecryptionError(f"Failed to read encrypted file: {e}") from e

    def verify_key(self, test_data: str = "test") -> bool:
        """Verify that the encryption key is valid by performing encrypt/decrypt cycle.

        Args:
            test_data: Test string to use for verification

        Returns:
            True if key is valid, False otherwise
        """
        try:
            encrypted = self.encrypt(test_data)
            decrypted = self.decrypt(encrypted)
            return decrypted == test_data
        except (EncryptionError, DecryptionError):
            return False
