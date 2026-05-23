"""Custom JSON API tracker adapter."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from framekit.core.http import HttpAuthError, HttpError, HttpStatusError

from ..models import DiscoveryResult, TorrentFile, TorrentMetadata, TrackerConfig, UploadResult
from .base import AuthenticationError, TrackerAdapter


class CustomJsonApiAdapter(TrackerAdapter):
    """Adapter for a bearer-token JSON tracker API."""

    def __init__(self, config: TrackerConfig):
        super().__init__(config)
        self.api_base = f"{config.url.rstrip('/')}/api"

    def get_headers(self) -> dict[str, str]:
        headers = super().get_headers()
        headers["Authorization"] = f"Bearer {self.config.api_key}"
        return headers

    @staticmethod
    def _extract_api_message(payload: Any) -> str | None:
        if isinstance(payload, dict):
            message = payload.get("message")
            if isinstance(message, str) and message.strip():
                return message.strip()
            errors = payload.get("errors")
            if isinstance(errors, dict):
                for field, values in errors.items():
                    if isinstance(values, list) and values:
                        return f"{field}: {values[0]}"
                    if values:
                        return f"{field}: {values}"
        return None

    @staticmethod
    def _parse_response_payload(response) -> Any:
        try:
            return response.json()
        except Exception:
            return response.text

    def validate_credentials(self) -> bool:
        try:
            response = self.client.get(
                f"{self.api_base}/categories",
                headers=self.get_headers(),
                timeout=30,
            )
            if response.status_code == 401:
                raise AuthenticationError("Invalid API key")
            scope_probe = self.client.request(
                "POST",
                f"{self.api_base}/torrents",
                headers=self.get_headers(),
                data={},
                timeout=30,
                accepted_statuses={200, 201, 202, 400, 401, 403, 422},
            )
            if scope_probe.status_code == 401:
                raise AuthenticationError("Invalid API key")
            if scope_probe.status_code == 403:
                payload = self._parse_response_payload(scope_probe)
                message = self._extract_api_message(payload) or "Missing upload scope"
                raise AuthenticationError(message)
            return True
        except HttpAuthError as exc:
            raise AuthenticationError("Invalid API key") from exc
        except HttpError as e:
            self.logger.error(f"Credential validation failed: {e}")
            return False

    def discover_api(self) -> DiscoveryResult:
        result = DiscoveryResult(tracker_type="custom_json_api_v1", tracker_url=self.config.url)
        try:
            categories = self._fetch_categories()
            if categories:
                result.categories = categories
            else:
                result.add_error("Failed to fetch categories")
            # This API does not use UNIT3D "types/resolutions" taxonomy.
            result.types = {}
            result.resolutions = {}
            result.required_fields = [
                "torrent",
                "nfo",
                "title",
                "description",
                "categoryId",
                "subcategoryId",
            ]
            result.optional_fields = [
                "descriptionFormat",
                "options",
                "uploaderNote",
                "tmdbData",
                "rawgData",
            ]
        except Exception as e:
            result.add_error(f"Discovery failed: {e!s}")
            self.logger.error(f"API discovery failed: {e}")
        return result

    def _fetch_categories(self) -> dict[str, int]:
        try:
            response = self.client.get(
                f"{self.api_base}/categories",
                headers=self.get_headers(),
                timeout=30,
            )
            payload = response.json()
            data = payload.get("data", payload) if isinstance(payload, dict) else payload
            categories: dict[str, int] = {}
            if isinstance(data, list):
                for category in data:
                    if not isinstance(category, dict):
                        continue
                    name = str(category.get("name", "") or "").strip()
                    category_id = category.get("id")
                    if name and isinstance(category_id, int):
                        categories[name] = category_id
            return categories
        except Exception as e:
            self.logger.error(f"Failed to fetch categories: {e}")
            return {}

    def validate_metadata(self, metadata: TorrentMetadata) -> tuple[bool, list[str]]:
        errors: list[str] = []
        if not metadata.name.strip():
            errors.append("Missing torrent title")
        if len(metadata.description.strip()) < 20:
            errors.append("Description must be at least 20 characters")
        return len(errors) == 0, errors

    def _resolve_nfo_path(
        self, torrent_file: TorrentFile, metadata: TorrentMetadata
    ) -> Path | None:
        explicit = (metadata.nfo_path or "").strip()
        candidate = Path(explicit) if explicit else torrent_file.path.with_suffix(".nfo")
        if candidate.exists() and candidate.is_file() and candidate.suffix.lower() == ".nfo":
            return candidate
        return None

    def _resolve_category_id(self, metadata: TorrentMetadata) -> int | None:
        if metadata.custom_api_category_id is not None:
            return metadata.custom_api_category_id
        value = self.config.defaults.get("custom_api_category_id")
        return int(value) if isinstance(value, int | str) and str(value).isdigit() else None

    def _resolve_subcategory_id(self, metadata: TorrentMetadata) -> int | None:
        if metadata.custom_api_subcategory_id is not None:
            return metadata.custom_api_subcategory_id
        value = self.config.defaults.get("custom_api_subcategory_id")
        return int(value) if isinstance(value, int | str) and str(value).isdigit() else None

    def _resolve_options(self, metadata: TorrentMetadata) -> dict[str, Any]:
        if metadata.custom_api_options:
            return metadata.custom_api_options
        defaults = self.config.defaults.get("custom_api_options", {})
        return defaults if isinstance(defaults, dict) else {}

    def _resolve_description_format(self, metadata: TorrentMetadata) -> str:
        candidate = (metadata.custom_api_description_format or "").strip().lower()
        if candidate in {"standard", "html"}:
            return candidate
        default_value = str(
            self.config.defaults.get("custom_api_description_format", "standard")
        ).lower()
        return default_value if default_value in {"standard", "html"} else "standard"

    def _build_upload_data(self, metadata: TorrentMetadata) -> tuple[dict[str, Any], list[str]]:
        data: dict[str, Any] = {
            "title": metadata.name,
            "description": metadata.description,
        }
        description_format = self._resolve_description_format(metadata)
        if description_format == "html":
            data["descriptionFormat"] = "html"
        errors: list[str] = []

        category_id = self._resolve_category_id(metadata)
        if category_id is None:
            errors.append("Missing categoryId (metadata or tracker defaults)")
        else:
            data["categoryId"] = category_id

        subcategory_id = self._resolve_subcategory_id(metadata)
        if subcategory_id is None:
            errors.append("Missing subcategoryId (metadata or tracker defaults)")
        else:
            data["subcategoryId"] = subcategory_id

        options = self._resolve_options(metadata)
        if options:
            data["options"] = json.dumps(options, ensure_ascii=False)

        uploader_note = (metadata.custom_api_uploader_note or "").strip()
        if uploader_note:
            data["uploaderNote"] = uploader_note

        if metadata.tmdb_data:
            data["tmdbData"] = json.dumps(metadata.tmdb_data, ensure_ascii=False)
        if metadata.rawg_data:
            data["rawgData"] = json.dumps(metadata.rawg_data, ensure_ascii=False)

        return data, errors

    @staticmethod
    def _append_api_errors(result: UploadResult, payload: Any) -> None:
        if isinstance(payload, dict):
            errors_payload = payload.get("errors", payload)
            if isinstance(errors_payload, dict):
                for field, messages in errors_payload.items():
                    if isinstance(messages, list):
                        for message in messages:
                            result.add_error(f"{field}: {message}")
                    else:
                        result.add_error(f"{field}: {messages}")
                return
            message = payload.get("message")
            if isinstance(message, str) and message.strip():
                result.add_error(message.strip())
                return
            result.add_error(str(payload))
            return
        result.add_error("Upload rejected by tracker API")

    def upload_torrent(
        self,
        torrent_file: TorrentFile,
        metadata: TorrentMetadata,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> UploadResult:
        import time

        result = UploadResult(success=False, tracker=self.config.name)
        start_time = time.time()

        try:
            if not self.validate_credentials():
                result.add_error("Invalid API credentials")
                return result
            if not torrent_file.validate():
                result.add_error("Invalid torrent file")
                return result
            is_valid, errors = self.validate_metadata(metadata)
            if not is_valid:
                for error in errors:
                    result.add_error(error)
                return result

            nfo_path = self._resolve_nfo_path(torrent_file, metadata)
            if nfo_path is None:
                result.add_error(
                    "Missing NFO file for custom JSON API upload (expected --nfo or <torrent>.nfo)"
                )
                return result

            upload_data, data_errors = self._build_upload_data(metadata)
            if data_errors:
                for error in data_errors:
                    result.add_error(error)
                return result

            is_draft = getattr(metadata, "custom_api_draft", False)
            endpoint = f"{self.api_base}/user/drafts" if is_draft else f"{self.api_base}/torrents"

            file_size = torrent_file.path.stat().st_size
            with (
                open(torrent_file.path, "rb") as torrent_fp,
                open(nfo_path, "rb") as nfo_fp,
            ):
                files = {
                    "torrent": (torrent_file.name, torrent_fp, "application/x-bittorrent"),
                    "nfo": (nfo_path.name, nfo_fp, "text/plain"),
                }

                torrent_fp.seek(0)
                nfo_fp.seek(0)
                if progress_callback:
                    progress_callback(0, file_size)

                response = self.client.request(
                    "POST",
                    endpoint,
                    headers=self.get_headers(),
                    data=upload_data,
                    files=files,
                    timeout=300,
                    accepted_statuses={200, 201, 202, 400, 401, 403, 422},
                )
                if progress_callback:
                    progress_callback(file_size, file_size)

                if response.status_code == 401:
                    raise AuthenticationError("Authentication failed")
                if response.status_code in {400, 403, 422}:
                    try:
                        payload = response.json()
                    except Exception:
                        payload = response.text
                    self._append_api_errors(result, payload)
                    if response.status_code == 403:
                        result.add_error(
                            "Forbidden by tracker. Check upload rights and descriptionFormat permission."
                        )
                    return result

                payload = response.json()
                if not isinstance(payload, dict):
                    result.add_error("Upload failed: invalid server response")
                    return result

                torrent_id = (
                    payload.get("draft_id")
                    or payload.get("id")
                    or (payload.get("data") or {}).get("id")
                )
                parsed_torrent_id: int | None = None
                if isinstance(torrent_id, int):
                    parsed_torrent_id = torrent_id
                elif isinstance(torrent_id, str) and torrent_id.isdigit():
                    parsed_torrent_id = int(torrent_id)
                result.success = True
                result.torrent_id = parsed_torrent_id
                if is_draft:
                    result.url = (
                        f"{self.config.url}/user/drafts/{result.torrent_id}"
                        if result.torrent_id
                        else None
                    )
                    result.message = "Draft saved"
                else:
                    result.url = (
                        f"{self.config.url}/torrents/{result.torrent_id}"
                        if result.torrent_id
                        else None
                    )
                    result.message = "Upload successful"
                return result

        except AuthenticationError as e:
            result.add_error(f"Authentication failed: {e!s}")
            self.logger.warning(f"Upload auth failed: {e}")
        except HttpError as e:
            self.logger.warning(f"Upload failed: {e}")
            if isinstance(e, HttpStatusError) and e.response_body:
                try:
                    payload = json.loads(e.response_body)
                except Exception:
                    payload = e.response_body
                self._append_api_errors(result, payload)
            else:
                result.add_error(f"Upload failed: {e!s}")
        except Exception as e:
            result.add_error(f"Unexpected error: {e!s}")
            self.logger.exception(f"Upload failed: {e}")
        finally:
            result.upload_time = time.time() - start_time

        return result
