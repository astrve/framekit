"""
Comprehensive tests for secure vault encryption and storage.

Tests encryption, decryption, key rotation, backup/restore, and security features.
"""

import pytest

from framekit.core.security import (
    DecryptionError,
    EncryptionError,
    EncryptionManager,
    KeyStorage,
    SecureVault,
    VaultError,
)


class TestEncryptionManager:
    """Test encryption manager functionality."""

    def test_generate_key(self):
        """Test generating encryption key."""
        key = EncryptionManager.generate_key()

        assert isinstance(key, bytes)
        assert len(key) == 32

    def test_encrypt_decrypt_cycle(self):
        """Test basic encrypt/decrypt cycle."""
        manager = EncryptionManager()
        plaintext = "sensitive data"

        encrypted = manager.encrypt(plaintext)
        decrypted = manager.decrypt(encrypted)

        assert decrypted == plaintext
        assert encrypted != plaintext.encode()

    def test_encrypt_empty_string(self):
        """Test encrypting empty string."""
        manager = EncryptionManager()

        encrypted = manager.encrypt("")
        decrypted = manager.decrypt(encrypted)

        assert decrypted == ""

    def test_encrypt_unicode(self):
        """Test encrypting Unicode characters."""
        manager = EncryptionManager()
        plaintext = "Hello 世界 🔒"

        encrypted = manager.encrypt(plaintext)
        decrypted = manager.decrypt(encrypted)

        assert decrypted == plaintext

    def test_decrypt_with_wrong_key_fails(self):
        """Test that decryption with wrong key fails."""
        manager1 = EncryptionManager()
        manager2 = EncryptionManager()  # Different key

        encrypted = manager1.encrypt("secret")

        with pytest.raises(DecryptionError, match="Invalid encryption key"):
            manager2.decrypt(encrypted)

    def test_decrypt_corrupted_data_fails(self):
        """Test that decrypting corrupted data fails."""
        manager = EncryptionManager()

        with pytest.raises(DecryptionError):
            manager.decrypt(b"corrupted data")

    def test_verify_key_valid(self):
        """Test key verification with valid key."""
        manager = EncryptionManager()

        assert manager.verify_key() is True

    def test_verify_key_invalid(self):
        """Test key verification with invalid key."""
        # Create manager with invalid key (wrong length)
        with pytest.raises(EncryptionError, match="must be 32 bytes"):
            EncryptionManager(b"short")

    def test_encrypt_to_file(self, tmp_path):
        """Test encrypting data to file."""
        manager = EncryptionManager()
        test_file = tmp_path / "encrypted.dat"
        plaintext = "secret data"

        manager.encrypt_to_file(plaintext, test_file)

        assert test_file.exists()
        # File should not contain plaintext
        assert plaintext not in test_file.read_text(errors="ignore")

    def test_decrypt_from_file(self, tmp_path):
        """Test decrypting data from file."""
        manager = EncryptionManager()
        test_file = tmp_path / "encrypted.dat"
        plaintext = "secret data"

        manager.encrypt_to_file(plaintext, test_file)
        decrypted = manager.decrypt_from_file(test_file)

        assert decrypted == plaintext

    def test_decrypt_nonexistent_file_fails(self, tmp_path):
        """Test decrypting nonexistent file fails."""
        manager = EncryptionManager()
        test_file = tmp_path / "nonexistent.dat"

        with pytest.raises(DecryptionError, match="not found"):
            manager.decrypt_from_file(test_file)


class TestSecureVault:
    """Test secure vault operations."""

    def test_vault_initialization(self, tmp_path):
        """Test vault initialization."""
        vault_path = tmp_path / "vault.enc"
        key_file = tmp_path / "key.json"
        key_storage = KeyStorage(key_file=key_file, prefer_keyring=False)

        vault = SecureVault(vault_path, key_storage)

        assert vault.vault_path == vault_path
        assert vault.key_storage == key_storage

    def test_store_and_retrieve_data(self, tmp_path):
        """Test storing and retrieving data."""
        vault_path = tmp_path / "vault.enc"
        key_file = tmp_path / "key.json"
        key_storage = KeyStorage(key_file=key_file, prefer_keyring=False)
        vault = SecureVault(vault_path, key_storage)

        vault.store("api_key", "secret123")
        retrieved = vault.retrieve("api_key")

        assert retrieved == "secret123"

    def test_store_complex_data(self, tmp_path):
        """Test storing complex data structures."""
        vault_path = tmp_path / "vault.enc"
        key_file = tmp_path / "key.json"
        key_storage = KeyStorage(key_file=key_file, prefer_keyring=False)
        vault = SecureVault(vault_path, key_storage)

        complex_data = {
            "tokens": ["token1", "token2"],
            "config": {"enabled": True, "count": 42},
        }

        vault.store("complex", complex_data)
        retrieved = vault.retrieve("complex")

        assert retrieved == complex_data

    def test_retrieve_nonexistent_key_returns_default(self, tmp_path):
        """Test retrieving nonexistent key returns default."""
        vault_path = tmp_path / "vault.enc"
        key_file = tmp_path / "key.json"
        key_storage = KeyStorage(key_file=key_file, prefer_keyring=False)
        vault = SecureVault(vault_path, key_storage)

        result = vault.retrieve("nonexistent", default="default_value")

        assert result == "default_value"

    def test_delete_entry(self, tmp_path):
        """Test deleting vault entry."""
        vault_path = tmp_path / "vault.enc"
        key_file = tmp_path / "key.json"
        key_storage = KeyStorage(key_file=key_file, prefer_keyring=False)
        vault = SecureVault(vault_path, key_storage)

        vault.store("temp", "data")
        assert vault.exists("temp")

        deleted = vault.delete("temp")

        assert deleted is True
        assert not vault.exists("temp")

    def test_delete_nonexistent_entry(self, tmp_path):
        """Test deleting nonexistent entry returns False."""
        vault_path = tmp_path / "vault.enc"
        key_file = tmp_path / "key.json"
        key_storage = KeyStorage(key_file=key_file, prefer_keyring=False)
        vault = SecureVault(vault_path, key_storage)

        deleted = vault.delete("nonexistent")

        assert deleted is False

    def test_list_keys(self, tmp_path):
        """Test listing vault keys."""
        vault_path = tmp_path / "vault.enc"
        key_file = tmp_path / "key.json"
        key_storage = KeyStorage(key_file=key_file, prefer_keyring=False)
        vault = SecureVault(vault_path, key_storage)

        vault.store("key1", "value1")
        vault.store("key2", "value2")
        vault.store("key3", "value3")

        keys = vault.list_keys()

        assert len(keys) == 3
        assert "key1" in keys
        assert "key2" in keys
        assert "key3" in keys

    def test_clear_vault(self, tmp_path):
        """Test clearing all vault data."""
        vault_path = tmp_path / "vault.enc"
        key_file = tmp_path / "key.json"
        key_storage = KeyStorage(key_file=key_file, prefer_keyring=False)
        vault = SecureVault(vault_path, key_storage)

        vault.store("key1", "value1")
        vault.store("key2", "value2")

        vault.clear()

        assert len(vault.list_keys()) == 0
        # Backup should be created
        backup_path = vault_path.with_suffix(".enc.backup")
        assert backup_path.exists()

    def test_vault_persistence(self, tmp_path):
        """Test that vault data persists across instances."""
        vault_path = tmp_path / "vault.enc"
        key_file = tmp_path / "key.json"
        key_storage = KeyStorage(key_file=key_file, prefer_keyring=False)

        # Store data in first instance
        vault1 = SecureVault(vault_path, key_storage)
        vault1.store("persistent", "data")

        # Retrieve in second instance
        vault2 = SecureVault(vault_path, key_storage)
        retrieved = vault2.retrieve("persistent")

        assert retrieved == "data"

    def test_vault_file_is_encrypted(self, tmp_path):
        """Test that vault file is actually encrypted."""
        vault_path = tmp_path / "vault.enc"
        key_file = tmp_path / "key.json"
        key_storage = KeyStorage(key_file=key_file, prefer_keyring=False)
        vault = SecureVault(vault_path, key_storage)

        secret = "super_secret_password_123"
        vault.store("password", secret)

        # Read raw file content
        raw_content = vault_path.read_text(errors="ignore")

        # Secret should not appear in plaintext
        assert secret not in raw_content


class TestKeyRotation:
    """Test encryption key rotation."""

    def test_rotate_key_with_data(self, tmp_path):
        """Test rotating key while preserving data."""
        vault_path = tmp_path / "vault.enc"
        key_file = tmp_path / "key.json"
        key_storage = KeyStorage(key_file=key_file, prefer_keyring=False)
        vault = SecureVault(vault_path, key_storage)

        # Store data with original key
        vault.store("data1", "value1")
        vault.store("data2", "value2")

        # Rotate key
        vault.rotate_key()

        # Data should still be accessible
        assert vault.retrieve("data1") == "value1"
        assert vault.retrieve("data2") == "value2"

    def test_rotate_key_creates_backup(self, tmp_path):
        """Test that key rotation creates backup."""
        vault_path = tmp_path / "vault.enc"
        key_file = tmp_path / "key.json"
        key_storage = KeyStorage(key_file=key_file, prefer_keyring=False)
        vault = SecureVault(vault_path, key_storage)

        vault.store("data", "value")
        vault.rotate_key()

        # Backup uses timestamped name: vault.enc.backup-YYYYMMDD-HHMMSS
        backup_files = list(tmp_path.glob("vault.enc.backup*"))
        assert len(backup_files) >= 1

    def test_rotate_key_with_custom_key(self, tmp_path):
        """Test rotating to a specific key."""
        vault_path = tmp_path / "vault.enc"
        key_file = tmp_path / "key.json"
        key_storage = KeyStorage(key_file=key_file, prefer_keyring=False)
        vault = SecureVault(vault_path, key_storage)

        vault.store("data", "value")

        new_key = EncryptionManager.generate_key()
        vault.rotate_key(new_key)

        # Data should still be accessible
        assert vault.retrieve("data") == "value"

    def test_rotate_key_invalid_length_fails(self, tmp_path):
        """Test that rotating to invalid key fails."""
        vault_path = tmp_path / "vault.enc"
        key_file = tmp_path / "key.json"
        key_storage = KeyStorage(key_file=key_file, prefer_keyring=False)
        vault = SecureVault(vault_path, key_storage)

        with pytest.raises(VaultError, match="must be 32 bytes"):
            vault.rotate_key(b"short_key")


class TestVaultBackupRestore:
    """Test vault backup and restore functionality."""

    def test_restore_from_backup(self, tmp_path):
        """Test restoring vault from backup."""
        vault_path = tmp_path / "vault.enc"
        key_file = tmp_path / "key.json"
        key_storage = KeyStorage(key_file=key_file, prefer_keyring=False)
        vault = SecureVault(vault_path, key_storage)

        # Store data and create backup
        vault.store("original", "data")
        vault.clear()  # This creates backup

        # Restore from backup
        restored = vault.restore_from_backup()

        assert restored is True
        assert vault.retrieve("original") == "data"

    def test_restore_without_backup_fails(self, tmp_path):
        """Test that restore without backup returns False."""
        vault_path = tmp_path / "vault.enc"
        key_file = tmp_path / "key.json"
        key_storage = KeyStorage(key_file=key_file, prefer_keyring=False)
        vault = SecureVault(vault_path, key_storage)

        restored = vault.restore_from_backup()

        assert restored is False


class TestVaultStatus:
    """Test vault status and information."""

    def test_get_vault_status(self, tmp_path):
        """Test getting vault status."""
        vault_path = tmp_path / "vault.enc"
        key_file = tmp_path / "key.json"
        key_storage = KeyStorage(key_file=key_file, prefer_keyring=False)
        vault = SecureVault(vault_path, key_storage)

        vault.store("key1", "value1")
        vault.store("key2", "value2")

        status = vault.get_status()

        assert "vault_path" in status
        assert "vault_exists" in status
        assert "key_storage" in status
        assert "key_exists" in status
        assert "entry_count" in status
        assert "keys" in status

        assert status["entry_count"] == 2
        assert len(status["keys"]) == 2


class TestVaultSecurity:
    """Test vault security features."""

    def test_vault_file_has_secure_permissions(self, tmp_path):
        """Test that vault file has secure permissions."""
        vault_path = tmp_path / "vault.enc"
        key_file = tmp_path / "key.json"
        key_storage = KeyStorage(key_file=key_file, prefer_keyring=False)
        vault = SecureVault(vault_path, key_storage)

        vault.store("data", "value")

        # Vault file should exist
        assert vault_path.exists()

        # On Unix, check permissions
        import platform

        if platform.system() != "Windows":
            stat_info = vault_path.stat()
            mode = stat_info.st_mode & 0o777
            # Should be owner-only (0o600) or similar
            assert mode in (0o600, 0o400), f"Insecure permissions: {oct(mode)}"

    def test_vault_metadata_includes_timestamp(self, tmp_path):
        """Test that vault entries include timestamps."""
        vault_path = tmp_path / "vault.enc"
        key_file = tmp_path / "key.json"
        key_storage = KeyStorage(key_file=key_file, prefer_keyring=False)
        vault = SecureVault(vault_path, key_storage)

        vault.store("data", "value")

        # Load vault data directly to check metadata
        vault._load_vault()
        entry = vault._data["data"]

        assert "value" in entry
        assert "updated_at" in entry

    def test_vault_handles_corrupted_data(self, tmp_path):
        """Vault must surface a ``VaultKeyMismatchError`` on bad ciphertext.

        Corrupt-but-non-empty data is indistinguishable from a wrong-key
        scenario at the Fernet layer (both fail with ``DecryptionError``).
        The vault layer wraps that as :class:`VaultKeyMismatchError` so the
        CLI can offer the dedicated reset-vault recovery path.
        """
        from framekit.core.security.vault import VaultKeyMismatchError

        vault_path = tmp_path / "vault.enc"
        key_file = tmp_path / "key.json"
        key_storage = KeyStorage(key_file=key_file, prefer_keyring=False)
        vault = SecureVault(vault_path, key_storage)

        vault.store("data", "value")
        vault_path.write_bytes(b"corrupted data")

        vault2 = SecureVault(vault_path, key_storage)
        with pytest.raises(VaultKeyMismatchError, match="decryption failed"):
            vault2.retrieve("data")
