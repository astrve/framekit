"""Security module for encrypting and protecting sensitive data.

Provides encryption utilities, secure key storage, and a vault for
managing encrypted configuration data.
"""

from .encryption import DecryptionError, EncryptionError, EncryptionManager
from .keyring import KeyStorage, KeyStorageError
from .permissions import (
    PermissionError,
    get_permission_info,
    set_secure_permissions,
    verify_secure_permissions,
)
from .vault import SecureVault, VaultError

__all__ = [
    "DecryptionError",
    "EncryptionError",
    # Encryption
    "EncryptionManager",
    # Key Storage
    "KeyStorage",
    "KeyStorageError",
    # Permissions
    "PermissionError",
    "get_permission_info",
    "set_secure_permissions",
    "verify_secure_permissions",
    # Vault
    "SecureVault",
    "VaultError",
]
