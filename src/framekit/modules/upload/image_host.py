"""Image hosting service for uploading screenshots to image hosts.

Supports multiple image hosting services with automatic retry and batch upload.
"""

import base64
from pathlib import Path
from typing import Any

from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from framekit.core.http import HttpClient, HttpClientConfig, HttpError


class ImageHostError(Exception):
    """Raised when image upload fails."""


class ImageHostService:
    """Service for uploading images to various image hosting services."""

    # Configuration for supported image hosts
    HOSTS: dict[str, dict[str, Any]] = {
        "imgbb": {
            "name": "ImgBB",
            "upload_url": "https://api.imgbb.com/1/upload",
            "requires_api_key": True,
            "max_size_mb": 32,
        },
        "imgbox": {
            "name": "Imgbox",
            "upload_url": "https://imgbox.com/upload/process",
            "requires_api_key": False,
            "max_size_mb": 10,
        },
        "ptpimg": {
            "name": "PTPImg",
            "upload_url": "https://ptpimg.me/upload.php",
            "requires_api_key": True,
            "max_size_mb": 10,
        },
        "freeimage": {
            "name": "FreeImage",
            "upload_url": "https://freeimage.host/api/1/upload",
            "requires_api_key": True,
            "max_size_mb": 16,
        },
    }

    def __init__(self, host: str, api_key: str | None = None):
        """Initialize image host service.

        Args:
            host: Image host identifier (imgbb, imgbox, ptpimg, freeimage)
            api_key: API key for the image host (required for some hosts)

        Raises:
            ValueError: If host is invalid or API key is missing when required
        """
        if host not in self.HOSTS:
            raise ValueError(
                f"Unsupported image host: {host}. Supported: {', '.join(self.HOSTS.keys())}"
            )

        self.host = host
        self.host_config = self.HOSTS[host]
        self.api_key = api_key

        # Validate API key requirement
        if self.host_config["requires_api_key"] and not api_key:
            raise ValueError(f"{self.host_config['name']} requires an API key")

        # Initialize HTTP client
        http_config = HttpClientConfig(
            timeout_seconds=30.0,
            user_agent="Framekit/2.0.0",
            http2=True,
        )
        self.client = HttpClient(config=http_config)
        self.logger = logger.bind(image_host=self.host_config["name"])

    @retry(
        stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), reraise=True
    )
    def upload(self, image_path: Path) -> str:
        """Upload single image to configured host.

        Args:
            image_path: Path to image file

        Returns:
            Direct URL to uploaded image

        Raises:
            ImageHostError: If upload fails after retries
        """
        if not image_path.exists():
            raise ImageHostError(f"Image file not found: {image_path}")

        # Check file size
        file_size_mb = image_path.stat().st_size / (1024 * 1024)
        max_size = self.host_config["max_size_mb"]
        if file_size_mb > max_size:
            raise ImageHostError(f"Image too large: {file_size_mb:.1f}MB (max: {max_size}MB)")

        self.logger.info(f"Uploading image: {image_path.name} ({file_size_mb:.1f}MB)")

        try:
            # Route to appropriate upload method
            if self.host == "imgbb":
                return self._upload_imgbb(image_path)
            elif self.host == "imgbox":
                return self._upload_imgbox(image_path)
            elif self.host == "ptpimg":
                return self._upload_ptpimg(image_path)
            elif self.host == "freeimage":
                return self._upload_freeimage(image_path)
            else:
                raise ImageHostError(f"Upload method not implemented for {self.host}")

        except HttpError as e:
            self.logger.error(f"HTTP error during upload: {e}")
            raise ImageHostError(f"Upload failed: {e}") from e
        except Exception as e:
            self.logger.error(f"Unexpected error during upload: {e}")
            raise ImageHostError(f"Upload failed: {e}") from e

    def upload_batch(self, image_paths: list[Path]) -> list[tuple[Path, str | None]]:
        """Upload multiple images to configured host.

        Args:
            image_paths: List of paths to image files

        Returns:
            List of tuples (image_path, url_or_none) for each image
        """
        results = []

        for image_path in image_paths:
            try:
                url = self.upload(image_path)
                results.append((image_path, url))
                self.logger.info(f"Successfully uploaded: {image_path.name}")
            except ImageHostError as e:
                self.logger.warning(f"Failed to upload {image_path.name}: {e}")
                results.append((image_path, None))

        return results

    def _upload_imgbb(self, image_path: Path) -> str:
        """Upload image to ImgBB."""
        with open(image_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode("utf-8")

        data = {
            "key": self.api_key,
            "image": image_data,
        }

        response = self.client.post(self.host_config["upload_url"], data=data)

        result = response.json()

        if not result.get("success"):
            error_msg = result.get("error", {}).get("message", "Unknown error")
            raise ImageHostError(f"ImgBB upload failed: {error_msg}")

        # Return direct URL
        return result["data"]["url"]

    def _upload_imgbox(self, image_path: Path) -> str:
        """Upload image to Imgbox."""
        with open(image_path, "rb") as f:
            files = {"files[]": (image_path.name, f, "image/png")}

            data = {
                "token_id": "",  # nosec B105
                "token_secret": "",  # nosec B105
                "content_type": "1",  # Safe for work
                "thumbnail_size": "350r",
            }

            response = self.client.post(self.host_config["upload_url"], data=data, files=files)

        result = response.json()

        if not result.get("ok"):
            raise ImageHostError("Imgbox upload failed")

        # Extract direct URL from first file
        files = result.get("files", [])
        if not files:
            raise ImageHostError("No files in Imgbox response")

        return files[0].get("original_url", "")

    def _upload_ptpimg(self, image_path: Path) -> str:
        """Upload image to PTPImg."""
        with open(image_path, "rb") as f:
            files = {"file-upload[0]": (image_path.name, f, "image/png")}

            data = {
                "api_key": self.api_key,
            }

            response = self.client.post(self.host_config["upload_url"], data=data, files=files)

        result = response.json()

        if result.get("status") != "OK":
            error_msg = result.get("message", "Unknown error")
            raise ImageHostError(f"PTPImg upload failed: {error_msg}")

        # Extract URL from first upload
        uploads = result.get("uploads", [])
        if not uploads:
            raise ImageHostError("No uploads in PTPImg response")

        code = uploads[0].get("code", "")
        return f"https://ptpimg.me/{code}.png"

    def _upload_freeimage(self, image_path: Path) -> str:
        """Upload image to FreeImage."""
        with open(image_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode("utf-8")

        data = {
            "key": self.api_key,
            "source": image_data,
            "format": "json",
        }

        response = self.client.post(self.host_config["upload_url"], data=data)

        result = response.json()

        if result.get("status_code") != 200:
            error_msg = result.get("error", {}).get("message", "Unknown error")
            raise ImageHostError(f"FreeImage upload failed: {error_msg}")

        # Return direct URL
        return result["image"]["url"]

    def close(self):
        """Close HTTP client and release resources."""
        if self.client:
            self.client.close()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, *_):
        """Context manager exit."""
        self.close()


def inject_images_into_bbcode(bbcode: str, image_urls: list[str]) -> str:
    """Inject image URLs into BBCode description.

    If bbcode already has [img] tags, returns as-is.
    Otherwise adds [center][img]{url}[/img]...[/center] section at end.
    Limits to 10 images max.

    Args:
        bbcode: Existing BBCode description
        image_urls: List of image URLs to inject

    Returns:
        BBCode with images injected
    """
    # Check if BBCode already has images
    if "[img]" in bbcode.lower():
        return bbcode

    # Limit to 10 images
    urls_to_inject = image_urls[:10]

    if not urls_to_inject:
        return bbcode

    # Build image section
    image_section = "\n\n[center]\n"
    for url in urls_to_inject:
        image_section += f"[img]{url}[/img]\n"
    image_section += "[/center]"

    # Append to existing BBCode
    return bbcode + image_section
