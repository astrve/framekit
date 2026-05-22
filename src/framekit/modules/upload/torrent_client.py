"""Torrent client integration for automatic seeding.

Supports qBittorrent Web API.
"""

from pathlib import Path
from typing import Any

import httpx

from framekit.core.exceptions import FramekitError


class TorrentClientError(FramekitError):
    """Raised when torrent client operations fail."""


class QBittorrentClient:
    """Client for qBittorrent Web API.

    Automatically adds uploaded torrents to the client for seeding.
    API docs: https://github.com/qbittorrent/qBittorrent/wiki/WebUI-API-(qBittorrent-4.1).
    """

    def __init__(  # nosec B107
        self,
        host: str = "localhost",
        port: int = 8080,
        username: str = "",
        password: str = "",
        use_https: bool = False,
    ):
        """Initialize qBittorrent client.

        Args:
            host: qBittorrent host (default: localhost)
            port: qBittorrent port (default: 8080)
            username: qBittorrent username
            password: qBittorrent password
            use_https: Use HTTPS instead of HTTP (default: False for localhost)
        """
        scheme = "https" if use_https else "http"
        self.base_url = f"{scheme}://{host}:{port}"
        self.username = username
        self.password = password
        self.session_cookie: str | None = None

    def login(self) -> bool:
        """Login to qBittorrent and get session cookie.

        Returns:
            True if login successful

        Raises:
            TorrentClientError: If login fails
        """
        try:
            response = httpx.post(
                f"{self.base_url}/api/v2/auth/login",
                data={"username": self.username, "password": self.password},
                timeout=10.0,
            )

            if response.status_code == 200 and response.text == "Ok.":
                # Extract session cookie
                self.session_cookie = response.cookies.get("SID")
                return True
            else:
                raise TorrentClientError(f"Login failed: {response.text}")
        except httpx.RequestError as e:
            raise TorrentClientError(f"Connection failed: {e}") from e

    def is_connected(self) -> bool:
        """Check if qBittorrent is accessible.

        Returns:
            True if connected
        """
        try:
            response = httpx.get(f"{self.base_url}/api/v2/app/version", timeout=5.0)
            return response.status_code == 200
        except httpx.RequestError:
            return False

    def add_torrent(
        self,
        torrent_path: Path,
        save_path: Path | None = None,
        category: str = "",
        tags: list[str] | None = None,
        skip_checking: bool = True,
    ) -> bool:
        """Add torrent to qBittorrent.

        Args:
            torrent_path: Path to .torrent file
            save_path: Where to save downloaded files (optional)
            category: Torrent category (optional)
            tags: List of tags (optional)
            skip_checking: Skip hash checking (default: True for seeding)

        Returns:
            True if torrent added successfully

        Raises:
            TorrentClientError: If add fails
        """
        if not self.session_cookie:
            self.login()

        if not torrent_path.exists():
            raise TorrentClientError(f"Torrent file not found: {torrent_path}")

        try:
            with open(torrent_path, "rb") as f:
                files = {"torrents": (torrent_path.name, f, "application/x-bittorrent")}

                data = {
                    "skip_checking": "true" if skip_checking else "false",
                    "paused": "false",
                }

                if save_path:
                    data["savepath"] = str(save_path)
                if category:
                    data["category"] = category
                if tags:
                    data["tags"] = ",".join(tags)

                if not self.session_cookie:
                    raise TorrentClientError(
                        "Not authenticated — login() must succeed before adding torrents"
                    )
                response = httpx.post(
                    f"{self.base_url}/api/v2/torrents/add",
                    files=files,
                    data=data,
                    cookies={"SID": self.session_cookie},
                    timeout=30.0,
                )

                if response.status_code == 200:
                    return True
                else:
                    raise TorrentClientError(f"Add torrent failed: {response.text}")
        except httpx.RequestError as e:
            raise TorrentClientError(f"Request failed: {e}") from e

    def get_torrent_list(self, category: str = "") -> list[dict[str, Any]]:
        """Get list of torrents from qBittorrent.

        Args:
            category: Filter by category (optional)

        Returns:
            List of torrent info dicts
        """
        if not self.session_cookie:
            self.login()

        try:
            params = {}
            if category:
                params["category"] = category

            if not self.session_cookie:
                raise TorrentClientError(
                    "Not authenticated — login() must succeed before listing torrents"
                )
            response = httpx.get(
                f"{self.base_url}/api/v2/torrents/info",
                params=params,
                cookies={"SID": self.session_cookie},
                timeout=10.0,
            )

            if response.status_code == 200:
                return response.json()
            else:
                return []
        except httpx.RequestError:
            return []
