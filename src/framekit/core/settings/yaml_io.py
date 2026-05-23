from __future__ import annotations

from io import StringIO
from pathlib import Path
from typing import Any

import yaml
from ruamel.yaml import (
    YAML,  # pyright: ignore[reportMissingImports]  # ruamel.yaml ships without typed stubs in some envs
)
from ruamel.yaml.scalarstring import (
    SingleQuotedScalarString,  # pyright: ignore[reportMissingImports]  # ruamel.yaml ships without typed stubs in some envs
)

from .schema import ENCRYPTED_PLACEHOLDER


def _yaml_quote(value: Any) -> str:
    """Quote a value for safe insertion into the hand-rolled YAML emitter.

    Uses ``yaml.safe_dump`` so quotes and other special characters are escaped
    according to the YAML spec. Always emits a single-quoted scalar so the
    resulting line is predictable.
    """
    if value is None:
        value = ""
    text = str(value)
    # default_style="'" forces single-quoted style; rstrip the trailing newline.
    return yaml.safe_dump(text, default_style="'", default_flow_style=False).rstrip("\n")


def _ruamel_round_trip() -> YAML:
    """Return a configured ruamel YAML round-trip loader/dumper.

    Round-trip mode (``typ='rt'``) preserves comments, blank lines, key order
    and quoting style. Block style + 2-space indent matches the project's
    hand-rolled emitter so existing files don't get reformatted noisily on
    the first round-trip save.
    """
    yaml_rt = YAML(typ="rt")
    yaml_rt.preserve_quotes = True
    yaml_rt.indent(mapping=2, sequence=4, offset=2)
    yaml_rt.width = 4096  # avoid line-wrapping of long announce URLs etc.
    yaml_rt.default_flow_style = False
    return yaml_rt


def round_trip_load(path: Path) -> Any:
    """Load YAML preserving comments and ordering for later round-trip save.

    The returned object behaves like a dict (it *is* a ``CommentedMap``) so
    code that does ``data["key"]["subkey"] = value`` keeps working. Pass it
    back to :func:`round_trip_save` to write the file with comments intact.
    """
    yaml_rt = _ruamel_round_trip()
    with path.open("r", encoding="utf-8") as fh:
        return yaml_rt.load(fh) or {}


def round_trip_save(data: Any, path: Path) -> None:
    """Write ``data`` to ``path`` preserving user comments and ordering.

    ``data`` should normally be a ``CommentedMap`` returned by
    :func:`round_trip_load`, mutated in place. A plain ``dict`` also works —
    in that case no comments are added (use the initial template generator
    for first-time writes).
    """
    yaml_rt = _ruamel_round_trip()
    buf = StringIO()
    yaml_rt.dump(data, buf)
    path.write_text(buf.getvalue(), encoding="utf-8")


def update_preserving_comments(
    source_path: Path,
    new_data: dict[str, Any],
    destination: Path | None = None,
) -> None:
    """Persist ``new_data`` to disk while preserving comments from ``source_path``.

    The function loads the existing file with ruamel (keeping comments + key
    order intact), recursively overlays ``new_data`` on top of it, then dumps
    the result back. Useful for ``SettingsStore.save`` when the YAML file
    already exists and the user may have annotated it manually.

    When the source file is missing (or is not a mapping), the function
    falls back to writing ``new_data`` from scratch using ruamel — comments
    only appear on subsequent edits at that point.
    """
    target = destination or source_path
    if source_path.exists():
        try:
            existing = round_trip_load(source_path)
        except Exception:
            existing = None
        if isinstance(existing, dict):
            _merge_into_commented(existing, new_data)
            round_trip_save(existing, target)
            return
    round_trip_save(new_data, target)


def _merge_into_commented(target: Any, updates: Any) -> None:
    """Recursively overlay ``updates`` onto a ruamel ``CommentedMap``.

    Mutates ``target`` in place. Adds new keys; replaces scalar/list values;
    descends into nested mappings. Lists and scalars are replaced wholesale
    (preserving comments only makes sense for mappings — replacing a list
    would otherwise duplicate items on every save).
    """
    if not isinstance(target, dict) or not isinstance(updates, dict):
        return
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            _merge_into_commented(target[key], value)
        else:
            target[key] = (
                SingleQuotedScalarString(value)
                if isinstance(value, str) and "\n" not in value and value != value.strip()
                else value
            )


def _append_tmdb_warning(lines: list[str], tmdb_token: str) -> None:
    if tmdb_token and tmdb_token != ENCRYPTED_PLACEHOLDER:
        lines.append(
            "  # WARNING: Token stored in plaintext. Enable security.enabled "
            "to keep it in the encrypted vault instead."
        )


def _append_torrent_announces(lines: list[str], announce_urls: list[str]) -> None:
    if announce_urls:
        lines.append("    announce_urls:")
        lines.extend(f"      - {_yaml_quote(url)}" for url in announce_urls)
        return
    lines.append("    announce_urls: []")


def _append_upload_list(lines: list[str], key: str, items: list[dict[str, Any]]) -> None:
    if items:
        dumped = yaml.dump({key: items}, default_flow_style=False, allow_unicode=True)
        lines.extend(f"  {line}" for line in dumped.splitlines())
        return
    lines.append(f"  {key}: []")


def _append_watch_folders(lines: list[str], folders: list[dict[str, Any]]) -> None:
    if not folders:
        lines.append("  folders: []")
        return
    lines.append("  folders:")
    for folder in folders:
        lines.append(f"    - path: {_yaml_quote(str(folder.get('path', '')))}")
        lines.append(f"      preset: {folder.get('preset', '')}")
        lines.append(f"      enabled: {str(folder.get('enabled', True)).lower()}")


def _generate_yaml_with_comments(data: dict[str, Any]) -> str:  # pyright: ignore[reportUnusedFunction]  # Re-exported through package __init__
    """Generate YAML content with English section headers and comments."""
    lines = []

    # Header comments
    lines.append("# Framekit Configuration")
    lines.append("# https://github.com/astrve/framekit")
    lines.append("")

    # Schema version
    lines.append(f"schema_version: {data['schema_version']}")
    lines.append("")

    # General section
    lines.append("# General Settings")
    lines.append("general:")
    lines.append(f"  locale: {data['general']['locale']}")
    lines.append(f"  default_folder: {_yaml_quote(data['general']['default_folder'])}")
    lines.append(f"  report_output_folder: {_yaml_quote(data['general']['report_output_folder'])}")
    lines.append("")

    # Tools section
    lines.append("# External Tools")
    lines.append("tools:")
    lines.append(f"  mkvmerge: '{data['tools']['mkvmerge']}'")
    lines.append("")

    # Setup section
    lines.append("# Setup")
    lines.append("setup:")
    lines.append(f"  completed: {str(data['setup']['completed']).lower()}")
    lines.append(f"  prompt_on_start: {str(data['setup']['prompt_on_start']).lower()}")
    lines.append("")

    # Security section
    lines.append("# Security")
    lines.append("security:")
    lines.append(f"  enabled: {str(data['security']['enabled']).lower()}")
    lines.append(f"  vault_path: '{data['security']['vault_path']}'")
    lines.append(f"  key_storage: {data['security']['key_storage']}")
    lines.append(f"  auto_migrate: {str(data['security']['auto_migrate']).lower()}")
    lines.append(
        f"  backup_before_changes: {str(data['security']['backup_before_changes']).lower()}"
    )
    lines.append("")

    # Metadata section
    lines.append("# Metadata Provider")
    lines.append("metadata:")
    lines.append(f"  provider: {data['metadata']['provider']}")
    lines.append(
        f"  interactive_confirmation: {str(data['metadata']['interactive_confirmation']).lower()}"
    )
    lines.append(f"  cache_ttl_hours: {data['metadata']['cache_ttl_hours']}")
    lines.append(f"  language: {data['metadata']['language']}")

    tmdb_token = data["metadata"]["tmdb_read_access_token"]
    _append_tmdb_warning(lines, tmdb_token)
    lines.append(f"  tmdb_read_access_token: {_yaml_quote(tmdb_token)}")
    lines.append(f"  enabled_by_default: {str(data['metadata']['enabled_by_default']).lower()}")
    lines.append(
        "  prompt_missing_token_in_pipeline: "
        f"{str(data['metadata']['prompt_missing_token_in_pipeline']).lower()}"
    )
    lines.append("")

    # Cache section
    lines.append("# Intelligent Cache System")
    lines.append("cache:")
    lines.append(f"  enabled: {str(data['cache']['enabled']).lower()}")
    lines.append(f"  directory: '{data['cache']['directory']}'")
    lines.append(f"  auto_cleanup: {str(data['cache']['auto_cleanup']).lower()}")
    lines.append(f"  cleanup_on_startup: {str(data['cache']['cleanup_on_startup']).lower()}")
    lines.append("  tmdb:")
    lines.append(f"    enabled: {str(data['cache']['tmdb']['enabled']).lower()}")
    lines.append(f"    ttl_days: {data['cache']['tmdb']['ttl_days']}")
    lines.append(f"    max_size_mb: {data['cache']['tmdb']['max_size_mb']}")
    lines.append("  mediainfo:")
    lines.append(f"    enabled: {str(data['cache']['mediainfo']['enabled']).lower()}")
    lines.append(f"    ttl_days: {data['cache']['mediainfo']['ttl_days']}")
    lines.append(f"    max_size_mb: {data['cache']['mediainfo']['max_size_mb']}")
    lines.append("  release:")
    lines.append(f"    enabled: {str(data['cache']['release']['enabled']).lower()}")
    lines.append(f"    ttl_days: {data['cache']['release']['ttl_days']}")
    lines.append(f"    max_size_mb: {data['cache']['release']['max_size_mb']}")
    lines.append("")

    # Modules section
    lines.append("# Modules")
    lines.append("modules:")
    lines.append("")

    # Renamer module
    lines.append("  # Renamer Module")
    lines.append("  renamer:")
    lines.append(f"    default_folder: '{data['modules']['renamer']['default_folder']}'")
    _lang_tag = data["modules"]["renamer"]["default_language_tag"]
    lines.append(f"    default_language_tag: '{_lang_tag}'")
    lines.append("")

    # CleanMKV module
    lines.append("  # CleanMKV Module")
    lines.append("  cleanmkv:")
    lines.append(f"    default_folder: '{data['modules']['cleanmkv']['default_folder']}'")
    lines.append(f"    output_dir_name: {data['modules']['cleanmkv']['output_dir_name']}")
    lines.append(f"    default_preset: {data['modules']['cleanmkv']['default_preset']}")
    lines.append(
        f"    copy_unchanged_files: {str(data['modules']['cleanmkv']['copy_unchanged_files']).lower()}"
    )
    lines.append("")

    # NFO module
    lines.append("  # NFO Module")
    lines.append("  nfo:")
    lines.append(f"    default_folder: '{data['modules']['nfo']['default_folder']}'")
    lines.append(f"    active_template: {data['modules']['nfo']['active_template']}")
    lines.append(f"    locale: {data['modules']['nfo']['locale']}")
    lines.append(f"    logo_path: '{data['modules']['nfo']['logo_path']}'")
    lines.append(f"    active_logo: '{data['modules']['nfo']['active_logo']}'")
    lines.append(f"    with_metadata: {str(data['modules']['nfo']['with_metadata']).lower()}")
    lines.append(f"    mode: {data['modules']['nfo']['mode']}")
    lines.append("")

    # Torrent module
    lines.append("  # Torrent Module")
    lines.append("  torrent:")
    lines.append(f"    default_folder: {_yaml_quote(data['modules']['torrent']['default_folder'])}")
    lines.append(f"    announce: {_yaml_quote(data['modules']['torrent']['announce'])}")
    announce_urls = data["modules"]["torrent"]["announce_urls"]
    _append_torrent_announces(lines, announce_urls)
    lines.append(
        f"    selected_announce: {_yaml_quote(data['modules']['torrent']['selected_announce'])}"
    )
    lines.append(f"    private: {str(data['modules']['torrent']['private']).lower()}")
    lines.append(f"    piece_length: {data['modules']['torrent']['piece_length']}")
    lines.append(
        "    prompt_save_announce: "
        f"{str(data['modules']['torrent']['prompt_save_announce']).lower()}"
    )
    lines.append("")

    # Prez module
    lines.append("  # Prez Module")
    lines.append("  prez:")
    lines.append(f"    default_folder: '{data['modules']['prez']['default_folder']}'")
    lines.append(f"    locale: {data['modules']['prez']['locale']}")
    lines.append(f"    format: {data['modules']['prez']['format']}")
    lines.append(f"    preset: {data['modules']['prez']['preset']}")
    lines.append(f"    html_template: {data['modules']['prez']['html_template']}")
    lines.append(f"    bbcode_template: {data['modules']['prez']['bbcode_template']}")
    lines.append(f"    mediainfo_mode: {data['modules']['prez']['mediainfo_mode']}")
    lines.append(
        f"    include_mediainfo: {str(data['modules']['prez']['include_mediainfo']).lower()}"
    )
    lines.append(f"    with_metadata: {str(data['modules']['prez']['with_metadata']).lower()}")
    lines.append("")

    # Pipeline module
    lines.append("  # Pipeline Module")
    lines.append("  pipeline:")
    lines.append(f"    default_folder: '{data['modules']['pipeline']['default_folder']}'")
    lines.append(f"    stop_on_error: {str(data['modules']['pipeline']['stop_on_error']).lower()}")
    lines.append("    enabled_modules:")
    lines.extend(f"      - {module}" for module in data["modules"]["pipeline"]["enabled_modules"])
    lines.append(f"    with_metadata: {str(data['modules']['pipeline']['with_metadata']).lower()}")
    lines.append("")

    # Encoder module
    lines.append("  # Encoder Module")
    lines.append("  encoder:")
    lines.append(f"    default_folder: '{data['modules']['encoder']['default_folder']}'")
    lines.append(f"    output_dir_name: {data['modules']['encoder']['output_dir_name']}")
    lines.append(f"    preset: '{data['modules']['encoder'].get('preset', '')}'")
    lines.append(f"    ffmpeg_path: '{data['modules']['encoder'].get('ffmpeg_path', 'ffmpeg')}'")
    lines.append(f"    ffprobe_path: '{data['modules']['encoder'].get('ffprobe_path', 'ffprobe')}'")
    lines.append("")

    # Upload section
    upload_data = data.get("upload", {})
    lines.append("# Upload")
    lines.append("upload:")
    lines.append(f"  enabled: {str(upload_data.get('enabled', False)).lower()}")
    lines.append(f"  auto_upload: {str(upload_data.get('auto_upload', False)).lower()}")
    lines.append(f"  max_parallel_uploads: {upload_data.get('max_parallel_uploads', 3)}")
    lines.append(f"  image_host: {_yaml_quote(upload_data.get('image_host', ''))}")
    lines.append(f"  image_host_api_key: {_yaml_quote(upload_data.get('image_host_api_key', ''))}")
    lines.append(f"  torrent_client: {_yaml_quote(upload_data.get('torrent_client', ''))}")
    lines.append(
        f"  torrent_client_host: {_yaml_quote(upload_data.get('torrent_client_host', 'localhost'))}"
    )
    lines.append(f"  torrent_client_port: {upload_data.get('torrent_client_port', 8080)}")
    lines.append(
        f"  torrent_client_username: {_yaml_quote(upload_data.get('torrent_client_username', ''))}"
    )
    lines.append(
        f"  torrent_client_password: {_yaml_quote(upload_data.get('torrent_client_password', ''))}"
    )
    lines.append(
        f"  torrent_client_category: {_yaml_quote(upload_data.get('torrent_client_category', 'framekit'))}"
    )
    trackers = upload_data.get("trackers", [])
    presets = upload_data.get("presets", [])
    _append_upload_list(lines, "trackers", trackers)
    _append_upload_list(lines, "presets", presets)

    # Seedbox section
    lines.append("")
    lines.append("# Seedbox")
    lines.append("# Transfer files to/from a seedbox via rclone.")
    lines.append("seedbox:")
    seedbox_data = data.get("seedbox", {})
    lines.append(f"  default: {_yaml_quote(seedbox_data.get('default', ''))}")
    lines.append(f"  history_enabled: {str(seedbox_data.get('history_enabled', True)).lower()}")
    seedboxes = seedbox_data.get("seedboxes", [])
    if seedboxes:
        lines.append("  seedboxes:")
    else:
        lines.append("  seedboxes: []")
    for sb in seedboxes:
        lines.append(f"    - name: {_yaml_quote(sb.get('name', ''))}")
        lines.append(f"      rclone_remote: {_yaml_quote(sb.get('rclone_remote', ''))}")
        lines.append(f"      remote_base_path: {_yaml_quote(sb.get('remote_base_path', '/'))}")
        lines.append(f"      bandwidth_limit: {_yaml_quote(sb.get('bandwidth_limit', ''))}")
        lines.append(f"      disk_check_enabled: {str(sb.get('disk_check_enabled', True)).lower()}")
        lines.append(f"      min_free_gb: {sb.get('min_free_gb', 5)}")
        lines.append(f"      post_upload_command: {_yaml_quote(sb.get('post_upload_command', ''))}")
        cat_paths = sb.get("category_paths", {})
        lines.append("      category_paths:")
        if cat_paths:
            for cat, path_val in cat_paths.items():
                lines.append(f"        {cat}: {_yaml_quote(path_val)}")
        else:
            lines.append("        {}")

    # Watch section
    lines.append("")
    lines.append("# Watch Mode")
    lines.append("watch:")
    watch_data = data.get("watch", {})
    lines.append(f"  enabled: {str(watch_data.get('enabled', False)).lower()}")
    folders = watch_data.get("folders", [])
    _append_watch_folders(lines, folders)
    notif = watch_data.get("notifications", {})
    lines.append("  notifications:")
    lines.append(f"    enabled: {str(notif.get('enabled', True)).lower()}")
    lines.append(f"    on_watch_started: {str(notif.get('on_watch_started', True)).lower()}")
    lines.append(f"    on_start: {str(notif.get('on_start', False)).lower()}")
    lines.append(f"    on_success: {str(notif.get('on_success', False)).lower()}")
    lines.append(f"    on_error: {str(notif.get('on_error', True)).lower()}")

    return "\n".join(lines) + "\n"
