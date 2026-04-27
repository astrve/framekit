from __future__ import annotations

import hashlib
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from framekit.core.i18n import tr
from framekit.core.naming import torrent_name_from_payload
from framekit.core.reporting import OperationReport


@dataclass(frozen=True, slots=True)
class TorrentBuildOptions:
    announce: str
    private: bool = True
    piece_length: int | None = None
    output_path: Path | None = None
    progress_callback: Callable[..., None] | None = None
    payload_files: tuple[Path, ...] | None = None
    payload_name: str | None = None


@dataclass(frozen=True, slots=True)
class TorrentBuildResult:
    output_path: Path
    files_count: int
    total_size: int
    piece_length: int
    pieces_count: int


def is_valid_announce_url(value: str | None) -> bool:
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
        for key in sorted(
            value, key=lambda item: item if isinstance(item, bytes) else str(item).encode("utf-8")
        ):
            encoded_key = key if isinstance(key, bytes) else str(key).encode("utf-8")
            items.append(_bencode(encoded_key) + _bencode(value[key]))
        return b"d" + b"".join(items) + b"e"
    raise TypeError(f"Unsupported bencode value: {type(value).__name__}")


def _iter_payload_files(input_path: Path) -> list[Path]:
    if input_path.is_file():
        return [input_path]
    return sorted(
        path
        for path in input_path.rglob("*")
        if path.is_file() and not path.name.lower().endswith(".torrent")
    )


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
                    pieces.append(hashlib.sha1(piece).digest())
        if progress_callback is not None:
            progress_callback(0, files=1)

    if buffer:
        pieces.append(hashlib.sha1(bytes(buffer)).digest())

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
                b"path": [part for part in relative.parts],
            }
        )
    info[b"files"] = file_entries
    return info


class TorrentService:
    def build(
        self,
        input_path: Path,
        *,
        options: TorrentBuildOptions,
        write: bool = True,
    ) -> tuple[OperationReport, TorrentBuildResult]:
        if not input_path.exists():
            raise ValueError(
                tr(
                    "torrent.error.path_not_found",
                    default="Path not found: {path}",
                    path=input_path,
                )
            )

        files = (
            list(options.payload_files)
            if options.payload_files is not None
            else _iter_payload_files(input_path)
        )
        if not files:
            raise ValueError(
                tr("torrent.error.no_files", default="No files found for torrent creation.")
            )

        total_size = sum(path.stat().st_size for path in files)
        piece_length = options.piece_length or _auto_piece_length(total_size)
        pieces = _hash_pieces(files, piece_length, options.progress_callback)
        pieces_count = len(pieces) // 20

        announce = options.announce.strip()
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

        output_name = options.payload_name or _safe_torrent_name(input_path)
        output_path = options.output_path or input_path.parent / f"{output_name}.torrent"
        meta: dict[bytes, Any] = {
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

        if write:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(_bencode(meta))

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

        return report, TorrentBuildResult(
            output_path=output_path,
            files_count=len(files),
            total_size=total_size,
            piece_length=piece_length,
            pieces_count=pieces_count,
        )
