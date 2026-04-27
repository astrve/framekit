from pathlib import Path

from framekit.core.models.cleanmkv import MkvFileScan, TrackInfo
from framekit.core.naming import sanitized_release_dir
from framekit.modules.cleanmkv.planner import build_remux_plan, get_builtin_preset


def test_sanitized_release_dir_helper() -> None:
    """
    The sanitized_release_dir helper should replace invalid characters in the release name and
    produce a path suitable for filesystem use.
    """
    template = "Release/{release}"
    raw_release = "My Movie: 2024/Quest?"
    result = sanitized_release_dir(template, raw_release)
    # The result should start with the template prefix
    assert result.startswith("Release/")
    # The release portion should not contain colon, slash or question mark
    release_part = result.split("/", 1)[1]
    assert ":" not in release_part and "/" not in release_part and "?" not in release_part


def test_build_remux_plan_sanitizes_output_dir(tmp_path: Path) -> None:
    """
    build_remux_plan should resolve the output directory using sanitized_release_dir so that
    characters invalid on filesystems are stripped out of the folder name.
    """
    # Use a valid MKV file path; the release_name will contain invalid characters to test
    # the sanitization logic on output directory names. Creating directories with characters
    # such as ':' or '?' is not possible on Windows, so avoid using them in the actual path.
    scan_path = tmp_path / "movie.mkv"
    scan_path.touch()
    # Create a minimal audio track so that the preset keeps something
    audio_track = TrackInfo(
        track_id=1,
        kind="audio",
        codec="AAC",
        language="french",
        language_variant=None,
        subtitle_variant=None,
        title=None,
        is_default=True,
        is_forced=False,
    )
    scan = MkvFileScan(path=scan_path, audio_tracks=[audio_track], subtitle_tracks=[])
    preset = get_builtin_preset("multi")
    plan = build_remux_plan(
        scan,
        preset=preset,
        output_dir_name="Release/{release}",
        # Provide a release_name containing invalid characters. The remux plan should
        # sanitize these characters when resolving the output directory.
        release_name="My Film:2024/Quest?",
    )
    # The target should reside in a directory under the parent of the scan path
    target = plan.target
    # The output directory name should not contain colon, slash or question mark
    output_dir = target.parent.name
    assert ":" not in output_dir and "/" not in output_dir and "?" not in output_dir
