from __future__ import annotations

from pathlib import Path
from typing import Any

from loguru import logger

from swirrl.core.exceptions import SettingsError
from swirrl.core.paths import get_master_key_path, get_vault_path

from .schema import ENCRYPTED_PLACEHOLDER as _ENCRYPTED_PLACEHOLDER
from .store import SettingsStore


class Settings:
    """High-level settings interface with secure vault integration.

    Provides convenient methods for accessing settings and managing
    encrypted sensitive data like API tokens and credentials.
    """

    ENCRYPTED_PLACEHOLDER = _ENCRYPTED_PLACEHOLDER

    def __init__(self, store: SettingsStore | None = None):
        """Initialize settings with optional custom store.

        Args:
            store: Settings store instance. If None, uses default.
        """
        self.store = store or SettingsStore()
        self._vault: Any | None = None  # Lazy-loaded SecureVault
        self._vault_initialized = False

    def get_vault(self) -> Any:
        """Get or initialize the secure vault (lazy loading).

        Returns:
            SecureVault instance or None if unavailable/disabled.
        """
        return self._get_vault()

    def _get_vault(self) -> Any:
        """Get or initialize the secure vault (lazy loading)."""
        if not self._vault_initialized:
            try:
                from swirrl.core.security import KeyStorage, SecureVault

                data = self.store.load()
                security_config = data.get("security", {})

                # Only initialize vault if security is enabled
                if security_config.get("enabled", True):
                    # Determine vault path
                    vault_path_str = security_config.get("vault_path", "")
                    vault_path = Path(vault_path_str) if vault_path_str else get_vault_path()

                    # Determine key storage preference
                    key_storage_type = security_config.get("key_storage", "keyring")
                    prefer_keyring = key_storage_type == "keyring"

                    # Initialize key storage
                    key_storage = KeyStorage(
                        key_file=get_master_key_path(), prefer_keyring=prefer_keyring
                    )

                    # Initialize vault
                    self._vault = SecureVault(
                        vault_path=vault_path, key_storage=key_storage, auto_initialize=True
                    )

                    logger.debug("Secure vault initialized")
                else:
                    logger.debug("Security disabled, vault not initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize secure vault: {e}")
                self._vault = None

            self._vault_initialized = True

        return self._vault

    def load(self) -> dict[str, Any]:
        """Load settings data."""
        return self.store.load()

    def save(self, data: dict[str, Any]) -> None:
        """Save settings data."""
        self.store.save(data)

    def get(self, path: str) -> Any:
        """Get setting value by path."""
        return self.store.get(path)

    def set(self, path: str, value: Any) -> dict[str, Any]:
        """Set setting value by path."""
        return self.store.set(path, value)

    def is_security_enabled(self) -> bool:
        """Check if security/encryption is enabled."""
        try:
            data = self.load()
            return data.get("security", {}).get("enabled", True)
        except Exception:
            return False

    def get_tmdb_token(self) -> str:
        """Get TMDB API token (decrypted if stored in vault).

        Returns:
            TMDB token or empty string if not found
        """
        try:
            data = self.load()
            token = data.get("metadata", {}).get("tmdb_read_access_token", "")

            # Check if token is encrypted placeholder
            if token == self.ENCRYPTED_PLACEHOLDER:
                vault = self._get_vault()
                if vault:
                    token = vault.retrieve("tmdb_api_token", default="")
                else:
                    logger.warning("Token is encrypted but vault not available")
                    token = ""  # nosec B105

            return str(token or "").strip()
        except Exception as e:
            logger.error(f"Failed to retrieve TMDB token: {e}")
            return ""

    def set_tmdb_token(self, token: str) -> None:
        """Set TMDB API token (encrypted in vault if security enabled).

        Args:
            token: TMDB API token to store
        """
        try:
            token = str(token or "").strip()

            if self.is_security_enabled():
                # Store in vault
                vault = self._get_vault()
                if vault:
                    vault.store("tmdb_api_token", token)
                    # Update config with placeholder
                    data = self.load()
                    data.setdefault("metadata", {})["tmdb_read_access_token"] = (
                        self.ENCRYPTED_PLACEHOLDER
                    )
                    self.save(data)
                    logger.info("TMDB token stored securely in vault")
                else:
                    # SECURITY: Fail-closed - do not store token if vault unavailable
                    logger.error(
                        "Vault unavailable - cannot store token securely. "
                        "Please configure vault or use keyring backend."
                    )
                    raise SettingsError(
                        "Cannot store sensitive token: vault unavailable. "
                        "Configure security.vault_enabled or security.use_keyring."
                    )
            else:
                # Store in plain text
                self.set("metadata.tmdb_read_access_token", token)
        except Exception as e:
            logger.error(f"Failed to set TMDB token: {e}")
            raise SettingsError(f"Failed to set TMDB token: {e}") from e

    def get_torrent_announces(self) -> list[str]:
        """Get torrent announce URLs (decrypted if stored in vault).

        Returns:
            List of announce URLs
        """
        try:
            data = self.load()
            announces = data.get("modules", {}).get("torrent", {}).get("announce_urls", [])

            # Check if announces are encrypted
            if announces and len(announces) == 1 and announces[0] == self.ENCRYPTED_PLACEHOLDER:
                vault = self._get_vault()
                if vault:
                    announces = vault.retrieve("torrent_announces", default=[])
                else:
                    logger.warning("Announces are encrypted but vault not available")
                    announces = []

            return announces if isinstance(announces, list) else []
        except Exception as e:
            logger.error(f"Failed to retrieve torrent announces: {e}")
            return []

    def get_selected_announce(self) -> str:
        """Get the selected (active) torrent announce URL.

        Resolves the encrypted placeholder via the vault when security is
        enabled. Falls back to the first announce URL when no explicit
        selection is stored.

        Returns:
            The selected announce URL, or empty string when none configured.
        """
        try:
            data = self.load()
            torrent = data.get("modules", {}).get("torrent", {})
            selected = str(torrent.get("selected_announce", "") or "").strip()

            announces = self.get_torrent_announces()
            if selected == self.ENCRYPTED_PLACEHOLDER:
                vault = self._get_vault()
                if vault:
                    index = vault.retrieve("torrent_selected_announce_index", default=-1)
                    if isinstance(index, int) and 0 <= index < len(announces):
                        return announces[index]
                return announces[0] if announces else ""

            if selected:
                return selected
            return announces[0] if announces else ""
        except Exception as e:
            logger.error(f"Failed to retrieve selected announce: {e}")
            return ""

    def set_selected_announce(self, announce: str) -> None:
        """Set the selected announce URL.

        Stores the vault-backed index when security is enabled and writes the
        encrypted placeholder to the YAML config; otherwise persists the URL
        in cleartext.
        """
        announce = str(announce or "").strip()
        try:
            announces = self.get_torrent_announces()
            if announce and announce not in announces:
                announces = [*announces, announce]
                # Persist updated list using the secure setter (handles vault path)
                self.set_torrent_announces(announces)

            if self._store_selected_announce_securely(announce, announces):
                return
            self._store_selected_announce_plaintext(announce)
        except Exception as e:
            logger.error(f"Failed to set selected announce: {e}")
            raise SettingsError(f"Failed to set selected announce: {e}") from e

    def _store_selected_announce_securely(self, announce: str, announces: list[str]) -> bool:
        if not self.is_security_enabled():
            return False
        vault = self._get_vault()
        if not vault:
            return False
        vault.store(
            "torrent_selected_announce_index", self._selected_announce_index(announce, announces)
        )
        self._save_torrent_selection(
            selected=self.ENCRYPTED_PLACEHOLDER if announce else "",
            announce=self.ENCRYPTED_PLACEHOLDER if announce else "",
        )
        return True

    def _store_selected_announce_plaintext(self, announce: str) -> None:
        self._save_torrent_selection(selected=announce, announce=announce)

    def _selected_announce_index(self, announce: str, announces: list[str]) -> int:
        try:
            return announces.index(announce) if announce else -1
        except ValueError:
            return -1

    def _save_torrent_selection(self, *, selected: str, announce: str) -> None:
        data = self.load()
        torrent_config = data.setdefault("modules", {}).setdefault("torrent", {})
        torrent_config["selected_announce"] = selected
        torrent_config["announce"] = announce
        self.save(data)

    def set_torrent_announces(self, announces: list[str]) -> None:
        """Set torrent announce URLs (encrypted in vault if security enabled).

        Args:
            announces: List of announce URLs to store
        """
        try:
            if not isinstance(announces, list):  # pyright: ignore[reportUnnecessaryIsInstance]  # Defensive guard: callers may pass legacy YAML scalars
                announces = []

            # Clean up announces
            announces = self._clean_announce_list(announces)

            if self._store_announces_securely(announces):
                logger.info("Torrent announces stored securely in vault")
            else:
                self._store_announces_plaintext(announces)
        except Exception as e:
            logger.error(f"Failed to set torrent announces: {e}")
            raise SettingsError(f"Failed to set torrent announces: {e}") from e

    def _clean_announce_list(self, announces: list[str]) -> list[str]:
        return [str(url).strip() for url in announces if str(url).strip()]

    def _store_announces_securely(self, announces: list[str]) -> bool:
        if not self.is_security_enabled():
            return False
        vault = self._get_vault()
        if not vault:
            logger.warning("Vault unavailable, storing announces in plain text")
            return False
        vault.store("torrent_announces", announces)
        vault.store("torrent_selected_announce_index", 0 if announces else -1)
        self._save_torrent_announces_config(
            announce_urls=[self.ENCRYPTED_PLACEHOLDER],
            selected_announce=self.ENCRYPTED_PLACEHOLDER if announces else "",
            announce=self.ENCRYPTED_PLACEHOLDER if announces else "",
        )
        return True

    def _store_announces_plaintext(self, announces: list[str]) -> None:
        selected = announces[0] if announces else ""
        self._save_torrent_announces_config(
            announce_urls=announces,
            selected_announce=selected,
            announce=selected,
        )

    def _save_torrent_announces_config(
        self,
        *,
        announce_urls: list[str],
        selected_announce: str,
        announce: str,
    ) -> None:
        data = self.load()
        torrent_config = data.setdefault("modules", {}).setdefault("torrent", {})
        torrent_config["announce_urls"] = announce_urls
        torrent_config["selected_announce"] = selected_announce
        torrent_config["announce"] = announce
        self.save(data)

    def migrate_to_vault(self) -> dict[str, list[str]]:
        """Migrate plain text sensitive data to encrypted vault.

        Returns:
            Dictionary with lists of migrated keys
        """
        migrated = {"success": [], "failed": []}

        try:
            if not self.is_security_enabled():
                logger.info("Security not enabled, skipping migration")
                return migrated

            vault = self._get_vault()
            if not vault:
                logger.error("Vault not available for migration")
                return migrated

            data = self.load()

            self._migrate_tmdb_token(data, migrated)
            self._migrate_torrent_announces(data, migrated)

            if migrated["success"]:
                logger.info(f"Migration complete: {len(migrated['success'])} items migrated")

        except Exception as e:
            logger.error(f"Migration failed: {e}")

        return migrated

    def _migrate_tmdb_token(self, data: dict[str, Any], migrated: dict[str, list[str]]) -> None:
        tmdb_token = data.get("metadata", {}).get("tmdb_read_access_token", "")
        if not tmdb_token or tmdb_token == self.ENCRYPTED_PLACEHOLDER:
            return
        try:
            self.set_tmdb_token(tmdb_token)
            migrated["success"].append("tmdb_api_token")
            logger.info("Migrated TMDB token to vault")
        except Exception as error:
            logger.error(f"Failed to migrate TMDB token: {error}")
            migrated["failed"].append("tmdb_api_token")

    def _migrate_torrent_announces(
        self,
        data: dict[str, Any],
        migrated: dict[str, list[str]],
    ) -> None:
        announces = data.get("modules", {}).get("torrent", {}).get("announce_urls", [])
        if not self._should_migrate_announces(announces):
            return
        try:
            self.set_torrent_announces(announces)
            migrated["success"].append("torrent_announces")
            logger.info("Migrated torrent announces to vault")
        except Exception as error:
            logger.error(f"Failed to migrate torrent announces: {error}")
            migrated["failed"].append("torrent_announces")

    def _should_migrate_announces(self, announces: Any) -> bool:
        if not announces:
            return False
        if not isinstance(announces, list):
            return False
        return not (len(announces) == 1 and announces[0] == self.ENCRYPTED_PLACEHOLDER)

    def get_vault_status(self) -> dict[str, Any]:
        """Get status of the secure vault.

        Returns:
            Dictionary with vault status information
        """
        try:
            vault = self._get_vault()
            if vault:
                return vault.get_status()
            else:
                return {
                    "enabled": False,
                    "vault_exists": False,
                    "key_exists": False,
                    "entry_count": 0,
                    "keys": [],
                }
        except Exception as e:
            logger.error(f"Failed to get vault status: {e}")
            return {"enabled": False, "error": str(e)}
