"""Tracker API discovery service.

Automatically detects tracker type and discovers available API endpoints,
categories, types, and resolutions.
"""

from typing import Any

from loguru import logger

from framekit.core.http import HttpClient

from .adapters import C411Adapter, CustomAdapter, GazelleAdapter, UNIT3DAdapter
from .models import DiscoveryResult, TrackerConfig
from .tracker_profiles import get_profile, merge_profile_with_discovered


class DiscoveryService:
    """Service for discovering tracker API capabilities."""

    def __init__(self):
        """Initialize discovery service."""
        self.logger = logger

    def discover_tracker(
        self, url: str, api_key: str, tracker_type: str | None = None
    ) -> DiscoveryResult:
        """Discover tracker API capabilities.

        Enriches discovery results with pre-configured tracker profiles when available.

        Args:
            url: Tracker URL
            api_key: API key for authentication
            tracker_type: Optional tracker type hint ("unit3d", "gazelle", "custom")

        Returns:
            DiscoveryResult with discovered information
        """
        # Clean URL
        url = url.rstrip("/")

        # Try to get pre-configured profile
        profile = get_profile(url)
        if profile:
            self.logger.info(
                f"Found pre-configured profile for tracker: {profile.get('name', 'Unknown')}"
            )

        # If type is specified, use it directly
        if tracker_type:
            result = self._discover_with_type(url, api_key, tracker_type)
        else:
            # Otherwise, auto-detect tracker type
            detected_type = self._detect_tracker_type(url, api_key)

            if detected_type:
                self.logger.info(f"Detected tracker type: {detected_type}")
                result = self._discover_with_type(url, api_key, detected_type)
            else:
                result = DiscoveryResult(tracker_type="unknown", tracker_url=url)
                result.add_error("Could not detect tracker type")

        # Merge with profile if available
        if profile and result.success:
            discovered_dict = {
                "categories": result.categories,
                "types": result.types,
                "resolutions": result.resolutions,
                "tracker_type": result.tracker_type,
                "name": profile.get("name"),
            }
            merged = merge_profile_with_discovered(profile, discovered_dict)

            # Update result with merged data
            result.categories = merged.get("categories", result.categories)
            result.types = merged.get("types", result.types)
            result.resolutions = merged.get("resolutions", result.resolutions)

            self.logger.info("Enriched discovery result with tracker profile")
        elif profile and not result.success:
            # If discovery failed but we have a profile, use it as fallback
            self.logger.warning("Discovery failed, using tracker profile as fallback")
            result.categories = profile.get("categories", {})
            result.types = profile.get("types", {})
            result.resolutions = profile.get("resolutions", {})
            result.tracker_type = profile.get("type", "unknown")
            result.success = True
            result.errors = []

        return result

    def _detect_tracker_type(self, url: str, api_key: str) -> str | None:
        """Auto-detect tracker type by testing API endpoints.

        Args:
            url: Tracker URL
            api_key: API key

        Returns:
            Detected tracker type or None
        """
        # Test UNIT3D
        if self._test_c411(url, api_key):
            return "c411"

        # Test UNIT3D
        if self._test_unit3d(url, api_key):
            return "unit3d"

        # Test Gazelle
        if self._test_gazelle(url, api_key):
            return "gazelle"

        # Unknown type
        return None

    def _test_c411(self, url: str, api_key: str) -> bool:
        """Test if tracker follows c411 API contract."""
        try:
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Accept": "application/json",
                "User-Agent": "Framekit/1.0",
            }
            client = HttpClient(base_url=url)
            try:
                response = client.get("/api/categories", headers=headers)
                if response.status_code == 200:
                    data = response.json()
                    payload = data.get("data", data) if isinstance(data, dict) else data
                    if isinstance(payload, list) and payload:
                        first = payload[0]
                        if isinstance(first, dict) and "subcategories" in first:
                            return True
            finally:
                client.close()
        except Exception as e:
            self.logger.debug(f"C411 test failed: {e}")
        return False

    def _test_unit3d(self, url: str, api_key: str) -> bool:
        """Test if tracker is UNIT3D-based."""
        try:
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Accept": "application/json",
                "User-Agent": "Framekit/1.0",
            }
            # Security: Use HttpClient for proper SSL verification and redaction
            client = HttpClient(base_url=url)
            try:
                response = client.get("/api/user", headers=headers)
                if response.status_code in [200, 401]:
                    if response.status_code == 200:
                        data = response.json()
                        if isinstance(data, dict) and "data" in data:
                            return True
                    return True
            finally:
                client.close()
        except Exception as e:
            self.logger.debug(f"UNIT3D test failed: {e}")
        return False

    def _test_gazelle(self, url: str, api_key: str) -> bool:
        """Test if tracker is Gazelle-based."""
        try:
            headers = {
                "Authorization": api_key,
                "Accept": "application/json",
                "User-Agent": "Framekit/1.0",
            }
            # Security: Use HttpClient for proper SSL verification and redaction
            client = HttpClient(base_url=url)
            try:
                response = client.get("/ajax.php?action=index", headers=headers)
                if response.status_code == 200:
                    data = response.json()
                    if isinstance(data, dict) and "status" in data and "response" in data:
                        return True
            finally:
                client.close()
        except Exception as e:
            self.logger.debug(f"Gazelle test failed: {e}")
        return False

    def _discover_with_type(self, url: str, api_key: str, tracker_type: str) -> DiscoveryResult:
        """Discover API using specific tracker type.

        Args:
            url: Tracker URL
            api_key: API key
            tracker_type: Tracker type

        Returns:
            DiscoveryResult
        """
        try:
            # Create temporary config for discovery
            config = TrackerConfig(name="discovery", type=tracker_type, url=url, api_key=api_key)

            # Create adapter
            adapter = self._create_adapter(config)

            # Run discovery
            result = adapter.discover_api()

            return result

        except Exception as e:
            result = DiscoveryResult(tracker_type=tracker_type, tracker_url=url)
            result.add_error(f"Discovery failed: {e!s}")
            self.logger.exception(f"Discovery failed: {e}")
            return result

    def _create_adapter(self, config: TrackerConfig):
        """Create adapter instance based on tracker type."""
        if config.type == "unit3d":
            return UNIT3DAdapter(config)
        elif config.type == "gazelle":
            return GazelleAdapter(config)
        elif config.type == "c411":
            return C411Adapter(config)
        elif config.type == "custom":
            return CustomAdapter(config)
        else:
            raise ValueError(f"Unknown tracker type: {config.type}")

    def save_discovery(
        self, result: DiscoveryResult, name: str, api_key: str, config_path: str | None = None
    ) -> bool:
        """Save discovery result to framekit.yaml configuration.

        Args:
            result: Discovery result
            name: Tracker name
            api_key: API key (will be stored in vault)
            config_path: Optional path to config file

        Returns:
            True if saved successfully
        """
        try:
            from framekit.core.settings import Settings

            # Load settings
            settings = Settings()
            data = settings.load()

            # Store API key in vault if security is enabled
            if settings.is_security_enabled():
                vault = settings.get_vault()
                if vault:
                    vault.store(f"tracker.{name}.api_key", api_key)
                    api_key_value = settings.ENCRYPTED_PLACEHOLDER
                    self.logger.info(f"API key stored securely in vault for tracker: {name}")
                else:
                    api_key_value = api_key
                    self.logger.warning("Vault unavailable, storing API key in plain text")
            else:
                api_key_value = api_key
                self.logger.warning("Security disabled, storing API key in plain text")

            # Create tracker config
            tracker_config = result.to_config(name, api_key)

            # Initialize upload section if not exists
            if "upload" not in data:
                data["upload"] = {"enabled": False, "auto_upload": False, "trackers": []}

            # Ensure trackers list exists
            if "trackers" not in data["upload"]:
                data["upload"]["trackers"] = []

            # Check if tracker already exists
            from typing import cast

            trackers = cast(list[dict[str, Any]], data["upload"]["trackers"])
            existing_index = None
            for i, tracker in enumerate(trackers):
                if tracker.get("name") == name:
                    existing_index = i
                    break

            # Build tracker dict
            tracker_dict = {
                "name": name,
                "type": tracker_config.type,
                "url": tracker_config.url,
                "api_key": api_key_value,
                "categories": tracker_config.categories,
                "types": tracker_config.types,
                "resolutions": tracker_config.resolutions,
                "defaults": tracker_config.defaults,
                "retry_attempts": tracker_config.retry_attempts,
                "retry_delay": tracker_config.retry_delay,
                "timeout": tracker_config.timeout,
            }

            # Update or add tracker
            if existing_index is not None:
                trackers[existing_index] = tracker_dict
                self.logger.info(f"Updated tracker configuration: {name}")
            else:
                trackers.append(tracker_dict)
                self.logger.info(f"Added tracker configuration: {name}")

            # Save settings
            settings.save(data)

            return True

        except Exception as e:
            self.logger.exception(f"Failed to save discovery: {e}")
            return False

    def test_connection(self, config: TrackerConfig) -> tuple[bool, str]:
        """Test connection to tracker.

        Args:
            config: Tracker configuration

        Returns:
            Tuple of (success, message)
        """
        try:
            adapter = self._create_adapter(config)

            if adapter.validate_credentials():
                return True, "Connection successful"
            else:
                return False, "Invalid credentials"

        except Exception as e:
            return False, f"Connection failed: {e!s}"
