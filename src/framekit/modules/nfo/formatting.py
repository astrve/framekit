from __future__ import annotations


def format_bytes_human(value: int | None) -> str:
    if value is None:
        return "-"

    size = float(value)

    if size >= 1024**3:
        return f"{size / (1024**3):.2f} Go"
    if size >= 1024**2:
        return f"{size / (1024**2):.2f} Mo"
    if size >= 1024:
        return f"{size / 1024:.2f} Ko"

    return f"{int(size)} o"


def format_duration_ms_human(value: int | None) -> str:
    if value is None:
        return "-"

    total_seconds = int(value // 1000)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60

    if hours:
        return f"{hours}h {minutes:02d}m {seconds:02d}s"

    return f"{minutes}m {seconds:02d}s"


def format_percent_human(value: float | None) -> str:
    if value is None:
        return "-"

    ratio = float(value)
    if ratio <= 1.0:
        ratio *= 100.0

    return f"{ratio:.1f}%"


def format_bitrate_human(value: int | None) -> str:
    if value is None:
        return "-"

    bps = int(value)

    if bps >= 1_000_000:
        return f"{bps / 1_000_000:.2f} Mb/s"
    if bps >= 1_000:
        return f"{bps / 1_000:.0f} kb/s"
    return f"{bps} b/s"


def format_kbps_human(value: int | None) -> str:
    if value is None:
        return "-"

    kbps = int(value)

    if kbps >= 1000:
        return f"{kbps / 1000:.2f} Mb/s"
    return f"{kbps} kb/s"


def format_fps_human(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value:.3f} fps"


def format_bit_depth_human(value: int | None) -> str:
    if value is None:
        return "-"
    return f"{value}-bit"
