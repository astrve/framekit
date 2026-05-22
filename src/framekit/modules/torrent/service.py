from __future__ import annotations

import hashlib
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from loguru import logger

from framekit.core.i18n import tr
from framekit.core.naming import torrent_name_from_payload
from framekit.core.reporting import OperationReport


@dataclass(frozen=True, slots=True)
class TorrentBuildOptions:
    """Torrent build options."""

    announce: str
    private: bool = True
    piece_length: int | None = None
    output_path: Path | None = None
    progress_callback: Callable[..., None] | None = None
    payload_files: tuple[Path, ...] | None = None
    payload_name: str | None = None


@dataclass(frozen=True, slots=True)
class TorrentBuildResult:
    """Result of torrent build."""

    output_path: Path
    files_count: int
    total_size: int
    piece_length: int
    pieces_count: int


def is_valid_announce_url(value: str | None) -> bool:
    """Return ``True`` if is valid announce url."""
    raw = str(value or "").strip()
    if not raw:
        return False
    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https", "udp"}:
        return False
    return bool(parsed.netloc)


def _bencode(value: Any) -> bytes:
    if isinstance(value, bytes):
        return str(len(value)).encode("ascii") + b":" + value
    if isinstance(value, str):
        encoded = value.encode("utf-8")
        return str(len(encoded)).encode("ascii") + b":" + encoded
    if isinstance(value, int):
        return b"i" + str(value).encode("ascii") + b"e"
    if isinstance(value, list | tuple):
        return b"l" + b"".join(_bencode(item) for item in value) + b"e"
    if isinstance(value, dict):
        items = []

        def _sort_key(item: object) -> bytes:
            return item if isinstance(item, bytes) else str(item).encode("utf-8")

        for key in sorted(value, key=_sort_key):
            encoded_key = key if isinstance(key, bytes) else str(key).encode("utf-8")
            items.append(_bencode(encoded_key) + _bencode(value[key]))
        return b"d" + b"".join(items) + b"e"
    raise TypeError(f"Unsupported bencode value: {type(value).__name__}")


def _iter_payload_files(input_path: Path) -> list[Path]:
    if input_path.is_file():
        if input_path.is_symlink():
            logger.warning("Skipping symlink in torrent payload: {}", input_path)
            return []
        return [input_path]
    results: list[Path] = []
    for path in sorted(input_path.rglob("*")):
        if not path.is_file() or path.name.lower().endswith(".torrent"):
            continue
        if path.is_symlink():
            logger.warning("Skipping symlink in torrent payload: {}", path)
            continue
        results.append(path)
    return results


def _auto_piece_length(total_size: int) -> int:
    gib = 1024 * 1024 * 1024
    mib = 1024 * 1024

    if total_size < 1 * gib:
        return 1 * mib
    if total_size < 2 * gib:
        return 2 * mib
    if total_size < 3 * gib:
        return 4 * mib
    if total_size < 8 * gib:
        return 8 * mib
    return 16 * mib


def _safe_torrent_name(input_path: Path) -> str:
    return torrent_name_from_payload(input_path)


def _hash_pieces(
    files: list[Path], piece_length: int, progress_callback: Callable[..., None] | None = None
) -> bytes:
    pieces: list[bytes] = []
    buffer = bytearray()

    for file_path in files:
        with file_path.open("rb") as handle:
            while True:
                chunk = handle.read(1024 * 1024)
                if not chunk:
                    break
                buffer.extend(chunk)
                if progress_callback is not None:
                    progress_callback(len(chunk))
                while len(buffer) >= piece_length:
                    piece = bytes(buffer[:piece_length])
                    del buffer[:piece_length]
                    # SHA1 is mandated by the BitTorrent v1 specification for
                    # piece hashing. ``usedforsecurity=False`` documents that
                    # this is a protocol identifier, not a cryptographic
                    # signature, and silences Bandit B324.
                    # nosemgrep: python.lang.security.insecure-hash-algorithms.insecure-hash-algorithm-sha1
                    pieces.append(hashlib.sha1(piece, usedforsecurity=False).digest())
        if progress_callback is not None:
            progress_callback(0, files=1)

    if buffer:
        # BitTorrent v1 protocol piece hash (see note above).
        # nosemgrep: python.lang.security.insecure-hash-algorithms.insecure-hash-algorithm-sha1
        pieces.append(hashlib.sha1(bytes(buffer), usedforsecurity=False).digest())

    return b"".join(pieces)


def _build_info_dict(
    input_path: Path,
    files: list[Path],
    piece_length: int,
    pieces: bytes,
    *,
    private: bool,
    payload_name: str | None = None,
) -> dict[bytes, Any]:
    info: dict[bytes, Any] = {
        b"name": payload_name or input_path.name,
        b"piece length": piece_length,
        b"pieces": pieces,
    }
    if private:
        info[b"private"] = 1

    if input_path.is_file():
        info[b"length"] = input_path.stat().st_size
        return info

    file_entries = []
    for file_path in files:
        relative = file_path.relative_to(input_path)
        file_entries.append(
            {
                b"length": file_path.stat().st_size,
                b"path": list(relative.parts),
            }
        )
    info[b"files"] = file_entries
    return info


class TorrentService:
    """Service for torrent."""

    def build(
        self,
        input_path: Path,
        *,
        options: TorrentBuildOptions,
        write: bool = True,
    ) -> tuple[OperationReport, TorrentBuildResult]:
        """Handle build."""
        self._ensure_input_exists(input_path)
        files = self._resolve_payload_files(input_path, options)
        total_size, piece_length, pieces, pieces_count = self._build_piece_data(files, options)
        announce = self._validate_announce(options.announce)
        output_path = self._resolve_output_path(input_path, options)
        meta = self._build_meta(
            input_path=input_path,
            options=options,
            announce=announce,
            files=files,
            piece_length=piece_length,
            pieces=pieces,
        )
        self._write_torrent_file(output_path, meta, write=write)

        report = self._build_operation_report(
            input_path=input_path,
            output_path=output_path,
            files=files,
            total_size=total_size,
            piece_length=piece_length,
            pieces_count=pieces_count,
            write=write,
        )
        result = TorrentBuildResult(
            output_path=output_path,
            files_count=len(files),
            total_size=total_size,
            piece_length=piece_length,
            pieces_count=pieces_count,
        )
        return report, result

    def _ensure_input_exists(self, input_path: Path) -> None:
        if input_path.exists():
            return
        raise ValueError(
            tr(
                "torrent.error.path_not_found",
                default="Path not found: {path}",
                path=input_path,
            )
        )

    def _resolve_payload_files(self, input_path: Path, options: TorrentBuildOptions) -> list[Path]:
        files = (
            list(options.payload_files)
            if options.payload_files is not None
            else _iter_payload_files(input_path)
        )
        if files:
            return files
        raise ValueError(
            tr("torrent.error.no_files", default="No files found for torrent creation.")
        )

    def _build_piece_data(
        self,
        files: list[Path],
        options: TorrentBuildOptions,
    ) -> tuple[int, int, bytes, int]:
        total_size = sum(path.stat().st_size for path in files)
        piece_length = options.piece_length or _auto_piece_length(total_size)
        pieces = _hash_pieces(files, piece_length, options.progress_callback)
        pieces_count = len(pieces) // 20
        return total_size, piece_length, pieces, pieces_count

    def _validate_announce(self, announce_value: str) -> str:
        announce = announce_value.strip()
        if not announce:
            raise ValueError(
                tr(
                    "torrent.error.missing_announce",
                    default="Tracker announce URL is required. Configure modules.torrent.announce or pass --announce.",
                )
            )
        if not is_valid_announce_url(announce):
            raise ValueError(
                tr(
                    "torrent.error.invalid_announce",
                    default="Tracker announce must be a valid http(s) or udp URL.",
                )
            )
        return announce

    def _resolve_output_path(self, input_path: Path, options: TorrentBuildOptions) -> Path:
        output_name = options.payload_name or _safe_torrent_name(input_path)
        return options.output_path or input_path.parent / f"{output_name}.torrent"

    def _build_meta(
        self,
        *,
        input_path: Path,
        options: TorrentBuildOptions,
        announce: str,
        files: list[Path],
        piece_length: int,
        pieces: bytes,
    ) -> dict[bytes, Any]:
        return {
            b"announce": announce,
            b"creation date": int(time.time()),
            b"created by": "Framekit",
            b"info": _build_info_dict(
                input_path,
                files,
                piece_length,
                pieces,
                private=options.private,
                payload_name=options.payload_name,
            ),
        }

    def _write_torrent_file(
        self, output_path: Path, meta: dict[bytes, Any], *, write: bool
    ) -> None:
        if not write:
            return
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(_bencode(meta))

    def _build_operation_report(
        self,
        *,
        input_path: Path,
        output_path: Path,
        files: list[Path],
        total_size: int,
        piece_length: int,
        pieces_count: int,
        write: bool,
    ) -> OperationReport:
        report = OperationReport(tool="torrent")
        report.scanned = len(files)
        report.processed = len(files)
        report.modified = 1 if write else 0
        if write:
            report.outputs.append(str(output_path))
        report.add_detail(
            file=input_path.name,
            action="torrent",
            status="written" if write else "planned",
            message=tr(
                "torrent.message.created",
                default="Torrent created." if write else "Torrent creation planned.",
            ),
            before={"path": str(input_path), "files": len(files), "total_size": total_size},
            after={
                "output": str(output_path),
                "piece_length": piece_length,
                "pieces": pieces_count,
            },
        )
        return report
