"""Unit tests for :mod:`framekit.modules.watch.validator`.

The validator exposes pure functions plus one ``is_stable`` method that
polls ``Path.stat().st_size``. We monkeypatch :func:`time.sleep` to keep
tests instantaneous and override the stat sequence to simulate growing or
stable files.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from framekit.modules.watch import validator as validator_module
from framekit.modules.watch.models import ValidationConfig
from framekit.modules.watch.validator import FileValidator


@pytest.fixture
def fast_sleep(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """Replace ``time.sleep`` with a no-op that records call durations."""

    calls: list[float] = []

    def _record(duration: float) -> None:
        calls.append(duration)

    monkeypatch.setattr(validator_module.time, "sleep", _record)
    return calls


@pytest.fixture
def cfg() -> ValidationConfig:
    return ValidationConfig(
        stability_timeout=4,
        check_interval=2,
        min_file_size=10,
    )


@pytest.fixture
def validator(cfg: ValidationConfig) -> FileValidator:
    return FileValidator(
        config=cfg,
        valid_extensions=[".mkv", ".mp4"],
        ignore_extensions=[".tmp", ".part", ".crdownload"],
    )


# ---------------------------------------------------------------------------
# is_valid_extension / is_temporary
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("release.mkv", True),
        ("release.MKV", True),
        ("release.mp4", True),
        ("release.avi", False),
        ("release.txt", False),
        ("release", False),
    ],
)
def test_is_valid_extension(
    validator: FileValidator, tmp_path: Path, name: str, expected: bool
) -> None:
    target = tmp_path / name
    assert validator.is_valid_extension(target) is expected


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("download.tmp", True),
        ("download.part", True),
        ("download.crdownload", True),
        ("download.CRDOWNLOAD", True),
        ("release.mkv", False),
        ("ready", False),
    ],
)
def test_is_temporary(validator: FileValidator, tmp_path: Path, name: str, expected: bool) -> None:
    target = tmp_path / name
    assert validator.is_temporary(target) is expected


# ---------------------------------------------------------------------------
# is_stable
# ---------------------------------------------------------------------------


def test_is_stable_returns_false_when_missing(validator: FileValidator, tmp_path: Path) -> None:
    assert validator.is_stable(tmp_path / "ghost.mkv") is False


def test_is_stable_returns_false_when_below_min_size(
    validator: FileValidator, tmp_path: Path
) -> None:
    target = tmp_path / "tiny.mkv"
    target.write_bytes(b"\x00")  # 1 byte, below min 10
    assert validator.is_stable(target) is False


def test_is_stable_returns_true_when_size_constant(
    validator: FileValidator, tmp_path: Path, fast_sleep: list[float]
) -> None:
    target = tmp_path / "release.mkv"
    target.write_bytes(b"\x00" * 1024)
    assert validator.is_stable(target) is True
    # 2 checks total (stability_timeout 4 // check_interval 2)
    assert len(fast_sleep) == 2
    assert all(d == 2 for d in fast_sleep)


def test_is_stable_returns_false_when_size_grows(
    validator: FileValidator,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fast_sleep: list[float],
) -> None:
    target = tmp_path / "growing.mkv"
    target.write_bytes(b"\x00" * 1024)

    # Override Path.stat to simulate a growing file across consecutive polls.
    sizes = iter([1024, 1024, 4096])

    class _Stat:
        def __init__(self, size: int) -> None:
            self.st_size = size
            # Add required stat attributes to maintain contract
            self.st_mode = 0o100644
            self.st_ino = 1
            self.st_dev = 1
            self.st_nlink = 1
            self.st_uid = 0
            self.st_gid = 0
            self.st_atime = 0.0
            self.st_mtime = 0.0
            self.st_ctime = 0.0

    def _stat(self: Path, *, follow_symlinks: bool = True) -> _Stat:
        try:
            return _Stat(next(sizes))
        except StopIteration:
            return _Stat(4096)

    monkeypatch.setattr(Path, "stat", _stat)
    assert validator.is_stable(target) is False


def test_is_stable_returns_false_when_file_disappears(
    validator: FileValidator,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fast_sleep: list[float],
) -> None:
    target = tmp_path / "ephemeral.mkv"
    target.write_bytes(b"\x00" * 1024)

    # First ``exists`` returns True (initial check), subsequent returns False.
    states = iter([True, False])

    real_exists = Path.exists

    def _exists(self: Path) -> bool:
        if self == target:
            try:
                return next(states)
            except StopIteration:
                return False
        return real_exists(self)

    monkeypatch.setattr(Path, "exists", _exists)
    assert validator.is_stable(target) is False


def test_is_stable_handles_stat_exception(
    validator: FileValidator, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "broken.mkv"
    target.write_bytes(b"\x00" * 1024)

    call_count = 0

    def _raise(self: Path, *, follow_symlinks: bool = True):  # type: ignore[no-untyped-def]
        nonlocal call_count
        call_count += 1
        # Let the first call (from exists()) succeed, then fail
        if call_count == 1:
            # Return a minimal stat result for exists() check
            class _Stat:
                st_mode = 0o100644
                st_size = 1024

            return _Stat()
        raise OSError("simulated stat failure")

    monkeypatch.setattr(Path, "stat", _raise)
    assert validator.is_stable(target) is False


def test_is_stable_uses_explicit_timeout(
    validator: FileValidator, tmp_path: Path, fast_sleep: list[float]
) -> None:
    target = tmp_path / "release.mkv"
    target.write_bytes(b"\x00" * 1024)
    validator.is_stable(target, timeout=2)
    # timeout 2 // interval 2 = 1 sleep cycle
    assert len(fast_sleep) == 1


# ---------------------------------------------------------------------------
# validate (end-to-end)
# ---------------------------------------------------------------------------


def test_validate_missing_path(validator: FileValidator, tmp_path: Path) -> None:
    ok, reason = validator.validate(tmp_path / "ghost.mkv")
    assert ok is False
    assert reason == "File does not exist"


def test_validate_directory_path(validator: FileValidator, tmp_path: Path) -> None:
    target = tmp_path / "folder"
    target.mkdir()
    ok, reason = validator.validate(target)
    assert ok is False
    assert reason == "Path is not a file"


def test_validate_temporary_extension(validator: FileValidator, tmp_path: Path) -> None:
    target = tmp_path / "release.tmp"
    target.write_bytes(b"\x00" * 1024)
    ok, reason = validator.validate(target)
    assert ok is False
    assert reason == "File is temporary"


def test_validate_invalid_extension(validator: FileValidator, tmp_path: Path) -> None:
    target = tmp_path / "release.avi"
    target.write_bytes(b"\x00" * 1024)
    ok, reason = validator.validate(target)
    assert ok is False
    assert reason.startswith("Invalid extension")


def test_validate_unstable_file(
    validator: FileValidator,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fast_sleep: list[float],
) -> None:
    target = tmp_path / "release.mkv"
    target.write_bytes(b"\x00" * 1024)

    # ``is_stable`` is exercised directly in its own tests above with a real
    # stat-call sequence. Here we only verify ``validate()`` propagates an
    # unstable result without duplicating that machinery — patching the
    # method on the validator instance is enough.
    monkeypatch.setattr(validator, "is_stable", lambda *args, **kwargs: False)
    ok, reason = validator.validate(target)
    assert ok is False
    assert reason == "File is not stable"


def test_validate_success(
    validator: FileValidator, tmp_path: Path, fast_sleep: list[float]
) -> None:
    target = tmp_path / "release.mkv"
    target.write_bytes(b"\x00" * 1024)
    ok, reason = validator.validate(target)
    assert ok is True
    assert reason == "File is valid"
