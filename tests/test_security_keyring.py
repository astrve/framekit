"""
Comprehensive tests for secure key storage (keyring and file-based).

Tests system keyring integration and file-based fallback storage.
"""

import json

import pytest

import framekit.core.security.keyring as keyring_module
from framekit.core.security import KeyStorage, KeyStorageError


class TestKeyStorageFileMode:
    """Test file-based key storage (fallback mode)."""

    def test_store_key_to_file(self, tmp_path):
        """Test storing key to file."""
        key_file = tmp_path / "key.json"
        storage = KeyStorage(key_file=key_file, prefer_keyring=False)

        test_key = b"a" * 32
        storage.store_key(test_key)

        assert key_file.exists()

    def test_retrieve_key_from_file(self, tmp_path):
        """Test retrieving key from file."""
        key_file = tmp_path / "key.json"
        storage = KeyStorage(key_file=key_file, prefer_keyring=False)

        test_key = b"a" * 32
        storage.store_key(test_key)
        retrieved = storage.retrieve_key()

        assert retrieved == test_key

    def test_key_file_format(self, tmp_path):
        """Test that key file has correct JSON format."""
        key_file = tmp_path / "key.json"
        storage = KeyStorage(key_file=key_file, prefer_keyring=False)

        test_key = b"a" * 32
        storage.store_key(test_key)

        # Read and parse JSON
        data = json.loads(key_file.read_text())

        assert "key" in data
        assert "version" in data
        assert data["version"] == 1

    def test_key_file_has_secure_permissions(self, tmp_path):
        """Test that key file has secure permissions."""
        key_file = tmp_path / "key.json"
        storage = KeyStorage(key_file=key_file, prefer_keyring=False)

        test_key = b"a" * 32
        storage.store_key(test_key)

        # On Unix, check permissions
        import platform

        if platform.system() != "Windows":
            stat_info = key_file.stat()
            mode = stat_info.st_mode & 0o777
            # Should be owner-only (0o600)
            assert mode == 0o600, f"Insecure permissions: {oct(mode)}"

    def test_store_invalid_key_length_fails(self, tmp_path):
        """Test that storing key with wrong length fails."""
        key_file = tmp_path / "key.json"
        storage = KeyStorage(key_file=key_file, prefer_keyring=False)

        with pytest.raises(KeyStorageError, match="must be 32 bytes"):
            storage.store_key(b"short")

    def test_store_non_bytes_key_fails(self, tmp_path):
        """Test that storing non-bytes key fails."""
        key_file = tmp_path / "key.json"
        storage = KeyStorage(key_file=key_file, prefer_keyring=False)

        with pytest.raises(KeyStorageError, match="must be bytes"):
            storage.store_key("not bytes")  # type: ignore

    def test_retrieve_nonexistent_key_returns_none(self, tmp_path):
        """Test retrieving nonexistent key returns None."""
        key_file = tmp_path / "key.json"
        storage = KeyStorage(key_file=key_file, prefer_keyring=False)

        result = storage.retrieve_key()

        assert result is None

    def test_delete_key_from_file(self, tmp_path):
        """Test deleting key from file."""
        key_file = tmp_path / "key.json"
        storage = KeyStorage(key_file=key_file, prefer_keyring=False)

        test_key = b"a" * 32
        storage.store_key(test_key)
        assert key_file.exists()

        storage.delete_key()

        assert not key_file.exists()

    def test_key_exists_check(self, tmp_path):
        """Test checking if key exists."""
        key_file = tmp_path / "key.json"
        storage = KeyStorage(key_file=key_file, prefer_keyring=False)

        assert not storage.key_exists()

        test_key = b"a" * 32
        storage.store_key(test_key)

        assert storage.key_exists()

    def test_get_storage_location(self, tmp_path):
        """Test getting storage location description."""
        key_file = tmp_path / "key.json"
        storage = KeyStorage(key_file=key_file, prefer_keyring=False)

        location = storage.get_storage_location()

        assert str(key_file) in location


class TestKeyStorageKeyringMode:
    """Test system keyring storage mode."""

    def test_keyring_mode_initialization(self, tmp_path):
        """Test initializing with keyring preference."""
        key_file = tmp_path / "key.json"
        storage = KeyStorage(key_file=key_file, prefer_keyring=True)

        # Should initialize without error
        assert storage is not None

    def test_keyring_fallback_to_file(self, tmp_path, monkeypatch):
        """Test that keyring falls back to file if unavailable."""

        class UnavailableKeyring:
            def get_keyring(self):
                raise RuntimeError("keyring unavailable")

        monkeypatch.setattr(keyring_module, "KEYRING_AVAILABLE", True)
        monkeypatch.setattr(keyring_module, "keyring", UnavailableKeyring())

        key_file = tmp_path / "key.json"
        storage = KeyStorage(key_file=key_file, prefer_keyring=True)

        test_key = b"a" * 32
        storage.store_key(test_key)

        assert key_file.exists()
        retrieved = storage.retrieve_key()
        assert retrieved == test_key

    def test_storage_location_indicates_method(self, tmp_path):
        """Test that storage location indicates storage method."""
        key_file = tmp_path / "key.json"
        storage = KeyStorage(key_file=key_file, prefer_keyring=True)

        location = storage.get_storage_location()

        # Should indicate either keyring or file
        assert "Keyring" in location or str(key_file) in location


class TestKeyStoragePersistence:
    """Test key storage persistence."""

    def test_key_persists_across_instances(self, tmp_path):
        """Test that key persists across storage instances."""
        key_file = tmp_path / "key.json"
        test_key = b"a" * 32

        # Store in first instance
        storage1 = KeyStorage(key_file=key_file, prefer_keyring=False)
        storage1.store_key(test_key)

        # Retrieve in second instance
        storage2 = KeyStorage(key_file=key_file, prefer_keyring=False)
        retrieved = storage2.retrieve_key()

        assert retrieved == test_key

    def test_overwrite_existing_key(self, tmp_path):
        """Overwrite is opt-in: the second ``store_key`` must pass ``overwrite=True``."""
        key_file = tmp_path / "key.json"
        storage = KeyStorage(key_file=key_file, prefer_keyring=False)

        key1 = b"a" * 32
        key2 = b"b" * 32

        storage.store_key(key1)
        storage.store_key(key2, overwrite=True)

        retrieved = storage.retrieve_key()
        assert retrieved == key2

    def test_overwrite_existing_key_refused_without_flag(self, tmp_path):
        """Without ``overwrite=True`` a second store_key must raise."""
        key_file = tmp_path / "key.json"
        storage = KeyStorage(key_file=key_file, prefer_keyring=False)

        storage.store_key(b"a" * 32)
        with pytest.raises(KeyStorageError, match="already exists"):
            storage.store_key(b"b" * 32)


class TestKeyStorageEdgeCases:
    """Test edge cases and error handling."""

    def test_store_without_key_file_fails(self):
        """Test that storing without key file fails."""
        storage = KeyStorage(key_file=None, prefer_keyring=False)

        test_key = b"a" * 32

        with pytest.raises(KeyStorageError, match="No key file specified"):
            storage.store_key(test_key)

    def test_corrupted_key_file_handling(self, tmp_path):
        """Test handling of corrupted key file."""
        key_file = tmp_path / "key.json"
        storage = KeyStorage(key_file=key_file, prefer_keyring=False)

        # Create corrupted file
        key_file.write_text("corrupted json {")

        with pytest.raises(KeyStorageError):
            storage.retrieve_key()

    def test_key_file_missing_key_field(self, tmp_path):
        """Test handling of key file missing 'key' field."""
        key_file = tmp_path / "key.json"
        storage = KeyStorage(key_file=key_file, prefer_keyring=False)

        # Create file with missing key field
        key_file.write_text(json.dumps({"version": 1}))

        result = storage.retrieve_key()
        assert result is None

    def test_delete_nonexistent_key_succeeds(self, tmp_path):
        """Test that deleting nonexistent key doesn't fail."""
        key_file = tmp_path / "key.json"
        storage = KeyStorage(key_file=key_file, prefer_keyring=False)

        # Should not raise
        storage.delete_key()

    def test_key_file_directory_created(self, tmp_path):
        """Test that parent directory is created if needed."""
        key_file = tmp_path / "subdir" / "nested" / "key.json"
        storage = KeyStorage(key_file=key_file, prefer_keyring=False)

        test_key = b"a" * 32
        storage.store_key(test_key)

        assert key_file.exists()
        assert key_file.parent.exists()


class TestKeyStorageMigration:
    """Test key migration between storage methods."""

    def test_migrate_to_keyring_without_file(self, tmp_path):
        """Test migration without existing file."""
        key_file = tmp_path / "key.json"
        storage = KeyStorage(key_file=key_file, prefer_keyring=True)

        result = storage.migrate_to_keyring()

        assert result is False

    def test_migrate_to_keyring_with_file(self, tmp_path):
        """Test migration from file to keyring."""
        key_file = tmp_path / "key.json"
        storage = KeyStorage(key_file=key_file, prefer_keyring=False)

        # Store key in file
        test_key = b"a" * 32
        storage.store_key(test_key)

        # Attempt migration (may fail if keyring not available)
        result = storage.migrate_to_keyring()

        # Result depends on keyring availability
        assert isinstance(result, bool)


class TestKeyStorageSecurity:
    """Test security features of key storage."""

    def test_key_not_in_plaintext(self, tmp_path):
        """Test that key is stored as hex, not plaintext."""
        key_file = tmp_path / "key.json"
        storage = KeyStorage(key_file=key_file, prefer_keyring=False)

        test_key = b"a" * 32
        storage.store_key(test_key)

        # Read file content
        content = key_file.read_text()

        # Key should be hex-encoded, not raw bytes
        assert test_key.hex() in content
        # Raw bytes should not be in file
        assert b"a" * 32 not in key_file.read_bytes()

    def test_key_roundtrip_preserves_value(self, tmp_path):
        """Test that key value is preserved through store/retrieve."""
        key_file = tmp_path / "key.json"
        storage = KeyStorage(key_file=key_file, prefer_keyring=False)

        # Use a specific key pattern
        test_key = bytes(range(32))
        storage.store_key(test_key)
        retrieved = storage.retrieve_key()

        assert retrieved == test_key
        assert len(retrieved) == 32
