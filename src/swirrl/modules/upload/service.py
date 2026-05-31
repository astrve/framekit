"""Upload service for managing torrent uploads to trackers.

Provides high-level interface for uploading torrents with retry logic,
validation, and multi-tracker support.
"""

import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import yaml
from loguru import logger
from pydantic import ValidationError
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)

from .adapters import CustomAdapter, CustomJsonApiAdapter, GazelleAdapter, UNIT3DAdapter
from .models import TorrentFile, TorrentMetadata, TrackerConfig, UploadResult
from .rate_limiter import TrackerRateLimiterRegistry


class UploadService:
    """Service for uploading torrents to trackers."""

    def __init__(self, config: TrackerConfig | None = None):
        """Initialize upload service.

        Args:
            config: Optional tracker configuration. If None, will load from settings.
        """
        self.config = config
        self.adapter = None
        if config:
            self.adapter = self._create_adapter(config)
        self.logger = logger

    def _create_adapter(self, config: TrackerConfig):
        """Create adapter instance based on tracker type."""
        if config.type == "unit3d":
            return UNIT3DAdapter(config)
        elif config.type == "gazelle":
            return GazelleAdapter(config)
        elif config.type == "custom_json_api_v1":
            return CustomJsonApiAdapter(config)
        elif config.type == "custom":
            return CustomAdapter(config)
        else:
            raise ValueError(f"Unknown tracker type: {config.type}")

    def upload(
        self,
        torrent_path: Path,
        metadata: TorrentMetadata,
        tracker_name: str | None = None,
        show_progress: bool = True,
    ) -> UploadResult:
        """Upload torrent to tracker.

        Args:
            torrent_path: Path to torrent file
            metadata: Torrent metadata
            tracker_name: Optional tracker name. If None, uses configured tracker.
            show_progress: Whether to show progress bar (default: True)

        Returns:
            UploadResult with success status and details
        """
        try:
            # Load tracker config if needed
            if tracker_name:
                logger.info(f"Loading tracker configuration: {tracker_name}")
                config = self._load_tracker_config(tracker_name)
                with self._create_adapter(config) as adapter:
                    return self._perform_upload(adapter, torrent_path, metadata, show_progress)
            elif self.adapter:
                # Use existing adapter without context manager (managed externally)
                return self._perform_upload(self.adapter, torrent_path, metadata, show_progress)
            else:
                logger.error("No tracker configured for upload")
                raise ValueError("No tracker configured")

        except Exception as e:
            logger.exception(f"Upload error occurred: {torrent_path} tracker={tracker_name}")
            result = UploadResult(success=False, tracker=tracker_name or "unknown")
            result.add_error(f"Upload error: {e!s}")
            return result

    def _perform_upload(
        self, adapter, torrent_path: Path, metadata: TorrentMetadata, show_progress: bool
    ) -> UploadResult:
        """Perform the actual upload operation.

        Args:
            adapter: Tracker adapter instance
            torrent_path: Path to torrent file
            metadata: Torrent metadata
            show_progress: Whether to show progress bar

        Returns:
            UploadResult with success status and details
        """
        # Create torrent file object
        torrent_file = TorrentFile(
            path=torrent_path,
            name=torrent_path.name,
            size=0,  # Will be set in __post_init__
        )

        # Acquire rate limit token before upload
        rate_registry = TrackerRateLimiterRegistry.get_instance()
        if not rate_registry.acquire(adapter.config, timeout=adapter.config.timeout):
            result = UploadResult(success=False, tracker=adapter.config.name)
            result.add_error("Rate limit timeout — too many requests to this tracker")
            return result

        # Upload with progress bar
        logger.info(
            f"Starting torrent upload: {torrent_path.name} -> {adapter.config.name} ({metadata.name})"
        )

        if show_progress:
            # Get file size for progress tracking
            file_size = torrent_path.stat().st_size

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                DownloadColumn(),
                TransferSpeedColumn(),
                TimeRemainingColumn(),
                transient=True,
            ) as progress:
                task_id = progress.add_task(
                    f"Uploading to {adapter.config.name}...", total=file_size
                )

                def progress_callback(bytes_uploaded: int, total_bytes: int):
                    progress.update(task_id, completed=bytes_uploaded)

                result = adapter.upload_torrent(torrent_file, metadata, progress_callback)
        else:
            result = adapter.upload_torrent(torrent_file, metadata)

        if result.success:
            logger.info(
                f"Upload successful: {adapter.config.name} torrent_id={result.torrent_id} ({result.upload_time:.1f}s)"
            )

            # Verify upload if torrent_id is available
            if result.torrent_id:
                verified = self._verify_upload(adapter, result)
                result.verified = verified
                if verified:
                    result.verification_message = "Upload verified successfully"
                    logger.info(
                        f"Upload verified: {adapter.config.name} torrent_id={result.torrent_id}"
                    )
                else:
                    result.verification_message = (
                        "Upload verification failed (may be pending moderation)"
                    )
                    logger.warning(
                        f"Upload verification failed: {adapter.config.name} torrent_id={result.torrent_id}"
                    )

            # Try to add to torrent client if configured
            self._add_to_torrent_client(torrent_path, adapter.config.name)
        else:
            logger.error(
                f"Upload failed: {adapter.config.name} errors={result.errors} ({result.upload_time:.1f}s)"
            )

        self._persist_result(result, torrent_file.name)
        return result

    def _verify_upload(self, adapter, result: UploadResult) -> bool:
        """Verify that upload was successful by checking if torrent exists on tracker.

        Args:
            adapter: Tracker adapter instance
            result: Upload result with torrent_id

        Returns:
            True if torrent exists with correct status, False otherwise
        """
        if not result.torrent_id:
            return False

        try:
            tracker_type = adapter.config.type

            if tracker_type == "unit3d":
                return self._verify_unit3d(adapter, result.torrent_id)
            elif tracker_type == "gazelle":
                return self._verify_gazelle(adapter, result.torrent_id)
            else:
                # Verification not supported for this tracker type
                return False

        except Exception as e:
            logger.warning(f"Upload verification failed: {e}")
            # Never raise exception - verification is best-effort
            return False

    def _verify_unit3d(self, adapter, torrent_id: int) -> bool:
        """Verify upload on UNIT3D tracker."""
        try:
            api_base = f"{adapter.config.url.rstrip('/')}/api"
            response = adapter.client.get(
                f"{api_base}/torrents/{torrent_id}",
                headers=adapter.get_headers(),
            )

            if response.status_code == 200:
                data = response.json()
                # Check if torrent exists and has valid data
                return data.get("data", {}).get("id") == torrent_id

            return False

        except Exception as e:
            logger.debug(f"UNIT3D verification error: {e}")
            return False

    def _verify_gazelle(self, adapter, torrent_id: int) -> bool:
        """Verify upload on Gazelle tracker."""
        try:
            api_base = f"{adapter.config.url.rstrip('/')}/ajax.php"
            response = adapter.client.get(
                api_base,
                headers=adapter.get_headers(),
                params={"action": "torrent", "id": torrent_id},
            )

            if response.status_code == 200:
                data = response.json()
                # Check if torrent exists
                return data.get("status") == "success"

            return False

        except Exception as e:
            logger.debug(f"Gazelle verification error: {e}")
            return False

    def _add_to_torrent_client(self, torrent_path: Path, tracker_name: str) -> None:
        """Add torrent to configured torrent client for seeding.

        Args:
            torrent_path: Path to torrent file
            tracker_name: Name of the tracker
        """
        from swirrl.core.settings_singleton import get_settings_data

        try:
            settings = get_settings_data()
            upload_config = settings.get("upload", {})
            client_type = upload_config.get("torrent_client", "")

            if not client_type:
                # Torrent client integration disabled
                return

            if client_type == "qbittorrent":
                from .torrent_client import QBittorrentClient

                client = QBittorrentClient(
                    host=upload_config.get("torrent_client_host", "localhost"),
                    port=upload_config.get("torrent_client_port", 8080),
                    username=upload_config.get("torrent_client_username", ""),
                    password=upload_config.get("torrent_client_password", ""),
                )

                # Determine save path (where the original files are)
                save_path = torrent_path.parent
                category = upload_config.get("torrent_client_category", "swirrl")

                client.add_torrent(
                    torrent_path,
                    save_path=save_path,
                    category=category,
                    tags=[tracker_name],
                    skip_checking=True,
                )

                logger.info(f"Added torrent to qBittorrent: {torrent_path.name}")
            else:
                logger.warning(f"Unknown torrent client type: {client_type}")

        except Exception as e:
            # Never fail upload due to client integration issues
            logger.warning(f"Failed to add torrent to client: {e}")

    def _persist_result(self, result: UploadResult, torrent_name: str) -> None:
        import json

        from swirrl.core.paths import get_config_dir

        history_path = get_config_dir() / "upload_history.jsonl"
        try:
            entry = result.to_dict()
            entry["torrent"] = torrent_name
            history_path.parent.mkdir(parents=True, exist_ok=True)
            with open(history_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.warning(f"Failed to persist upload history: {e}")

    def _get_adapter(self, tracker_name: str):
        """Get adapter for a tracker by name.

        Args:
            tracker_name: Tracker name

        Returns:
            Tracker adapter instance
        """
        config = self._load_tracker_config(tracker_name)
        return self._create_adapter(config)

    def upload_to_multiple(
        self,
        torrent_path: Path,
        metadata: TorrentMetadata,
        tracker_names: list[str],
        max_parallel: int = 3,
    ) -> dict[str, UploadResult]:
        """Upload to multiple trackers in parallel using ThreadPoolExecutor.

        Args:
            torrent_path: Path to torrent file
            metadata: Torrent metadata
            tracker_names: List of tracker names to upload to
            max_parallel: Maximum number of parallel uploads (default 3)

        Returns:
            Dict mapping tracker name to UploadResult

        Features:
        - Parallel execution with configurable max workers
        - Rich Progress display with one bar per tracker
        - Graceful error handling per tracker
        - Aggregate results at the end
        """
        results = {}

        with Progress() as progress:
            # Create a task for each tracker
            tasks = {
                tracker: progress.add_task(f"[cyan]Uploading to {tracker}...", total=100)
                for tracker in tracker_names
            }

            with ThreadPoolExecutor(max_workers=max_parallel) as executor:
                # Submit all upload jobs
                futures = {
                    executor.submit(
                        self.upload,
                        torrent_path,
                        metadata,
                        tracker,
                        show_progress=False,  # Disable individual progress bars
                    ): tracker
                    for tracker in tracker_names
                }

                # Process results as they complete
                for future in as_completed(futures):
                    tracker = futures[future]
                    try:
                        result = future.result()
                        results[tracker] = result
                        progress.update(tasks[tracker], completed=100)

                        if result.success:
                            progress.console.print(f"[green]✓[/green] {tracker}: Upload successful")
                        else:
                            progress.console.print(f"[red]✗[/red] {tracker}: {result.message}")
                    except Exception as e:
                        results[tracker] = UploadResult(
                            success=False, tracker=tracker, message=f"Upload failed: {e!s}"
                        )
                        progress.update(tasks[tracker], completed=100)
                        progress.console.print(f"[red]✗[/red] {tracker}: Exception - {e!s}")

        return results

    def test_connection(self, tracker_name: str | None = None) -> tuple[bool, str]:
        """Test connection to tracker.

        Args:
            tracker_name: Optional tracker name. If None, uses configured tracker.

        Returns:
            Tuple of (success, message)
        """
        try:
            if tracker_name:
                config = self._load_tracker_config(tracker_name)
                with self._create_adapter(config) as adapter:
                    if adapter.validate_credentials():
                        return True, f"Connection to {adapter.config.name} successful"
                    else:
                        return False, f"Invalid credentials for {adapter.config.name}"
            elif self.adapter:
                if self.adapter.validate_credentials():
                    return True, f"Connection to {self.adapter.config.name} successful"
                else:
                    return False, f"Invalid credentials for {self.adapter.config.name}"
            else:
                return False, "No tracker configured"

        except Exception as e:
            return False, f"Connection failed: {e!s}"

    def discover(self, tracker_name: str | None = None):
        """Discover tracker API capabilities.

        Args:
            tracker_name: Optional tracker name. If None, uses configured tracker.

        Returns:
            DiscoveryResult
        """
        try:
            if tracker_name:
                config = self._load_tracker_config(tracker_name)
                with self._create_adapter(config) as adapter:
                    return adapter.discover_api()
            elif self.adapter:
                return self.adapter.discover_api()
            else:
                raise ValueError("No tracker configured")

        except Exception as e:
            self.logger.exception(f"Discovery failed: {e}")
            from .models import DiscoveryResult

            result = DiscoveryResult(tracker_type="unknown", tracker_url="")
            result.add_error(f"Discovery failed: {e!s}")
            return result

    def _load_tracker_config(self, tracker_name: str) -> TrackerConfig:
        """Load tracker configuration from settings.

        Args:
            tracker_name: Tracker name

        Returns:
            TrackerConfig
        """
        from swirrl.core.settings import Settings

        settings = Settings()
        data = settings.load()

        # Get upload config
        upload_config = data.get("upload", {})
        trackers = upload_config.get("trackers", [])

        # Find tracker
        tracker_data = None
        for tracker in trackers:
            if tracker.get("name") == tracker_name:
                tracker_data = tracker
                break

        if not tracker_data:
            tracker_data = self._load_tracker_file(tracker_name)
        if not tracker_data:
            raise ValueError(f"Tracker not found: {tracker_name}")

        # Get API key (decrypt if needed)
        api_key = tracker_data.get("api_key", "")
        token_env = str(tracker_data.get("token_env", "") or "")
        if not api_key and token_env:
            api_key = os.environ.get(token_env, "")
        if api_key == settings.ENCRYPTED_PLACEHOLDER:
            vault = settings.get_vault()
            if vault:
                api_key = vault.retrieve(f"tracker.{tracker_name}.api_key", default="")
            else:
                raise ValueError(
                    f"API key encrypted but vault unavailable for tracker: {tracker_name}"
                )

        # Create config
        try:
            return TrackerConfig(
                name=tracker_data.get("name", tracker_name),
                type=tracker_data.get("engine", tracker_data.get("type", "custom")),
                url=tracker_data.get("base_url", tracker_data.get("url", "")),
                api_key=api_key,
                categories=tracker_data.get("categories", {}),
                types=tracker_data.get("types", {}),
                resolutions=tracker_data.get("resolutions", {}),
                defaults=tracker_data.get("defaults", {}),
                retry_attempts=tracker_data.get("retry_attempts", 3),
                retry_delay=tracker_data.get("retry_delay", 5),
                timeout=tracker_data.get("timeout", 300),
            )
        except ValidationError as e:
            raise ValueError(f"Invalid tracker configuration for '{tracker_name}': {e}") from e

    @staticmethod
    def _load_tracker_file(tracker_name: str) -> dict[str, Any] | None:
        from swirrl.core.settings import SettingsStore

        path = SettingsStore().path.parent / "trackers" / f"{tracker_name}.yaml"
        if not path.exists():
            return None
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(data, dict):
            raise ValueError(f"Tracker file must contain a YAML object: {path}")

        auth = data.get("auth", {})
        token_env = auth.get("token_env", "") if isinstance(auth, dict) else ""
        defaults = data.get("defaults", {})
        return {
            "name": data.get("name", tracker_name),
            "engine": data.get("engine", "custom_json_api_v1"),
            "base_url": data.get("base_url", data.get("url", "")),
            "api_key": "",
            "token_env": token_env,
            "defaults": defaults if isinstance(defaults, dict) else {},
            "categories": data.get("categories", {}),
            "types": data.get("types", {}),
            "resolutions": data.get("resolutions", {}),
        }

    @staticmethod
    def list_trackers() -> list[dict[str, Any]]:
        """List all configured trackers.

        Returns:
            List of tracker information dictionaries
        """
        from swirrl.core.settings_singleton import get_settings_data

        data = get_settings_data()

        upload_config = data.get("upload", {})
        trackers = upload_config.get("trackers", [])

        rows = [
            {
                "name": tracker.get("name", ""),
                "type": tracker.get("engine", tracker.get("type", "")),
                "url": tracker.get("base_url", tracker.get("url", "")),
                "categories": len(tracker.get("categories", {})),
                "types": len(tracker.get("types", {})),
                "resolutions": len(tracker.get("resolutions", {})),
            }
            for tracker in trackers
        ]
        try:
            from swirrl.core.settings import SettingsStore

            tracker_dir = SettingsStore().path.parent / "trackers"
            for path in sorted(tracker_dir.glob("*.yaml")):
                raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
                if not isinstance(raw, dict):
                    continue
                rows.append(
                    {
                        "name": raw.get("name", path.stem),
                        "type": raw.get("engine", raw.get("type", "")),
                        "url": raw.get("base_url", raw.get("url", "")),
                        "categories": len(raw.get("categories", {})),
                        "types": len(raw.get("types", {})),
                        "resolutions": len(raw.get("resolutions", {})),
                    }
                )
        except Exception as exc:
            logger.debug(f"Failed to list tracker YAML profiles: {exc}")
        return rows

    @staticmethod
    def get_tracker_info(tracker_name: str) -> dict[str, Any] | None:
        """Get detailed information about a tracker.

        Args:
            tracker_name: Tracker name

        Returns:
            Tracker information dictionary or None if not found
        """
        from swirrl.core.settings_singleton import get_settings_data

        data = get_settings_data()

        upload_config = data.get("upload", {})
        trackers = upload_config.get("trackers", [])

        for tracker in trackers:
            if tracker.get("name") == tracker_name:
                # Return copy without API key
                info = dict(tracker)
                info["api_key"] = "********" if info.get("api_key") else ""
                return info
        file_data = UploadService._load_tracker_file(tracker_name)
        if file_data:
            return {
                "name": file_data.get("name", tracker_name),
                "type": file_data.get("engine", file_data.get("type", "")),
                "url": file_data.get("base_url", file_data.get("url", "")),
                "token_env": file_data.get("token_env", ""),
                "api_key": "",
                "defaults": file_data.get("defaults", {}),
            }

        return None

    @staticmethod
    def get_upload_history(limit: int = 50) -> list[dict]:
        """Return the upload history."""
        import json

        from swirrl.core.paths import get_config_dir

        history_path = get_config_dir() / "upload_history.jsonl"
        if not history_path.exists():
            return []
        lines = history_path.read_text(encoding="utf-8").splitlines()
        entries: list[dict] = []
        for line in reversed(lines):
            if line.strip():
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
            if len(entries) >= limit:
                break
        return entries

    @staticmethod
    def remove_tracker(tracker_name: str) -> bool:
        """Handle remove tracker."""
        from swirrl.core.settings import SettingsStore

        store = SettingsStore()
        settings = store.load()
        upload = settings.setdefault("upload", {})
        trackers = upload.get("trackers", [])
        new_trackers = [t for t in trackers if t.get("name") != tracker_name]
        if len(new_trackers) == len(trackers):
            return False
        upload["trackers"] = new_trackers
        settings["upload"] = upload
        store.save(settings)
        return True

    @staticmethod
    def set_upload_enabled(enabled: bool, auto_upload: bool | None = None) -> None:
        """Set upload enabled."""
        from swirrl.core.settings import SettingsStore

        store = SettingsStore()
        settings = store.load()
        upload = settings.setdefault("upload", {})
        upload["enabled"] = enabled
        if auto_upload is not None:
            upload["auto_upload"] = auto_upload
        settings["upload"] = upload
        store.save(settings)

    @staticmethod
    def is_upload_enabled() -> bool:
        """Check if upload module is enabled.

        Returns:
            True if enabled
        """
        from swirrl.core.settings_singleton import get_settings_data

        try:
            data = get_settings_data()
            return data.get("upload", {}).get("enabled", False)
        except Exception:
            return False

    @staticmethod
    def is_auto_upload_enabled() -> bool:
        """Check if auto-upload after pipeline is enabled.

        Returns:
            True if enabled
        """
        from swirrl.core.settings_singleton import get_settings_data

        try:
            data = get_settings_data()
            return data.get("upload", {}).get("auto_upload", False)
        except Exception:
            return False
