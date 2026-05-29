"""Tests for vault key-mismatch recovery (``SecureVault.reset`` + CLI hint)."""

from __future__ import annotations

from pathlib import Path

import pytest

from ouro.core.security.encryption import EncryptionManager
from ouro.core.security.keyring import KeyStorage
from ouro.core.security.vault import SecureVault, VaultKeyMismatchError


def _fresh_vault(tmp_path: Path) -> tuple[SecureVault, Path, KeyStorage]:
    """Create a brand-new file-backed vault and return its parts."""
    vault_path = tmp_path / "vault.enc"
    key_file = tmp_path / "key.json"
    key_storage = KeyStorage(key_file=key_file, prefer_keyring=False)
    vault = SecureVault(vault_path, key_storage)
    return vault, vault_path, key_storage


def test_key_mismatch_raises_dedicated_exception(tmp_path: Path) -> None:
    """When the key store is wiped, the vault must surface ``VaultKeyMismatchError``."""
    vault, vault_path, key_storage = _fresh_vault(tmp_path)
    vault.store("token", "secret-value")

    # Wipe the key file and re-create the storage so a fresh key is generated.
    key_file = tmp_path / "key.json"
    key_file.unlink()
    new_storage = KeyStorage(key_file=key_file, prefer_keyring=False)
    new_storage.store_key(EncryptionManager.generate_key())

    vault2 = SecureVault(vault_path, new_storage)
    with pytest.raises(VaultKeyMismatchError, match="decryption failed"):
        vault2.retrieve("token")


def test_reset_moves_broken_vault_aside_and_creates_fresh(tmp_path: Path) -> None:
    """``reset()`` backs up the unreadable vault and creates an empty one."""
    vault, vault_path, key_storage = _fresh_vault(tmp_path)
    vault.store("token", "secret-value")
    assert vault_path.exists()

    # Trigger a mismatch by replacing the key.
    key_file = tmp_path / "key.json"
    key_file.unlink()
    new_storage = KeyStorage(key_file=key_file, prefer_keyring=False)
    new_storage.store_key(EncryptionManager.generate_key())

    vault2 = SecureVault(vault_path, new_storage)
    backup = vault2.reset()

    assert backup is not None
    assert backup.exists(), "old vault should be moved aside, not deleted"
    assert vault_path.exists(), "a fresh empty vault should now exist at the original path"
    # The new vault is readable with the current key.
    vault2._loaded = False  # force a reload from disk
    assert vault2.list_keys() == []


def test_reset_when_no_vault_returns_none(tmp_path: Path) -> None:
    """``reset()`` on an empty/missing vault still creates a fresh file."""
    _vault, vault_path, key_storage = _fresh_vault(tmp_path)
    # The auto_initialize step writes nothing until ``store()`` is called.
    if vault_path.exists():
        vault_path.unlink()
    fresh = SecureVault(vault_path, key_storage)
    backup = fresh.reset()
    assert backup is None
    assert vault_path.exists()


def test_settings_helper_detects_mismatch_through_chain() -> None:
    """``_is_vault_mismatch`` follows ``__cause__`` / ``__context__``."""
    from ouro.commands.settings import _is_vault_mismatch
    from ouro.core.exceptions import SettingsError

    leaf = VaultKeyMismatchError("decryption failed")
    middle: Exception
    try:
        try:
            raise leaf
        except VaultKeyMismatchError as exc:
            raise RuntimeError("wrap") from exc
    except RuntimeError as exc:
        middle = exc

    try:
        raise SettingsError("Failed to set torrent announces") from middle
    except SettingsError as exc:
        assert _is_vault_mismatch(exc) is True


def test_settings_helper_returns_false_for_unrelated_error() -> None:
    """Unrelated exceptions do not trigger the reset-vault hint."""
    from ouro.commands.settings import _is_vault_mismatch

    assert _is_vault_mismatch(ValueError("nope")) is False
