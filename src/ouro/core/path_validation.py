"""Security utilities for path validation and sanitization."""

from pathlib import Path

from loguru import logger


class PathValidationError(Exception):
    """Raised when path validation fails."""


class SecurityConfig:
    """Global security configuration for path validation.

    Attributes:
        strict_mode: Enable strict path validation (production mode)
        allowed_base_dirs: Whitelist of allowed base directories
        allow_symlinks: Whether to allow symbolic links
        allow_absolute_paths: Whether to allow absolute paths outside base dirs
    """

    def __init__(
        self,
        strict_mode: bool = False,
        allowed_base_dirs: list[Path] | None = None,
        allow_symlinks: bool = True,
        allow_absolute_paths: bool = True,
    ):
        self.strict_mode = strict_mode
        self.allowed_base_dirs = allowed_base_dirs or []
        self.allow_symlinks = allow_symlinks
        self.allow_absolute_paths = allow_absolute_paths


# Global security configuration instance
_security_config = SecurityConfig()


def configure_security(
    strict_mode: bool = False,
    allowed_base_dirs: list[Path | str] | None = None,
    allow_symlinks: bool = True,
    allow_absolute_paths: bool = True,
) -> None:
    """Configure global security settings for path validation.

    Args:
        strict_mode: Enable strict validation (recommended for production)
        allowed_base_dirs: Whitelist of allowed base directories
        allow_symlinks: Whether to allow symbolic links
        allow_absolute_paths: Whether to allow absolute paths outside base dirs
    """
    global _security_config

    base_dirs = []
    if allowed_base_dirs:
        for dir_path in allowed_base_dirs:
            try:
                base_dirs.append(Path(dir_path).resolve())
            except Exception as e:
                logger.warning(f"Invalid base directory {dir_path}: {e}")

    _security_config = SecurityConfig(
        strict_mode=strict_mode,
        allowed_base_dirs=base_dirs,
        allow_symlinks=allow_symlinks,
        allow_absolute_paths=allow_absolute_paths,
    )

    logger.info(
        f"Security configured: strict_mode={strict_mode}, "
        f"base_dirs={len(base_dirs)}, allow_symlinks={allow_symlinks}"
    )


def get_security_config() -> SecurityConfig:
    """Get current security configuration."""
    return _security_config


def _check_symlink(path: Path, strict: bool = False) -> None:
    """Check if path is or contains symbolic links.

    Args:
        path: Path to check
        strict: If True, raise exception. If False, log warning.

    Raises:
        PathValidationError: If strict=True and symlink detected
    """
    try:
        # Check if the path itself is a symlink
        if path.is_symlink():
            msg = f"Path is a symbolic link: {path}"
            if strict:
                raise PathValidationError(msg)
            logger.warning(msg)
            return

        # Check if any parent is a symlink (junction point on Windows)
        for parent in path.parents:
            if parent.is_symlink():
                msg = f"Path contains symbolic link in parent: {parent}"
                if strict:
                    raise PathValidationError(msg)
                logger.warning(msg)
                return

    except PathValidationError:
        raise
    except Exception as e:
        if strict:
            raise PathValidationError(f"Failed to check for symlinks: {e}") from e
        logger.warning(f"Failed to check for symlinks: {e}")


def _check_path_traversal(
    path: Path,
    allowed_base_dirs: list[Path] | None = None,
    strict: bool = False,
) -> None:
    """Check for path traversal attacks.

    Args:
        path: Resolved absolute path to check
        allowed_base_dirs: Whitelist of allowed base directories
        strict: If True, raise exception. If False, log warning.

    Raises:
        PathValidationError: If strict=True and path traversal detected
    """
    # If no base dirs specified, use current working directory
    if not allowed_base_dirs:
        allowed_base_dirs = [Path.cwd()]

    # Check if path is within any allowed base directory
    is_allowed = False
    for base_dir in allowed_base_dirs:
        try:
            path.relative_to(base_dir)
            is_allowed = True
            break
        except ValueError:
            continue

    if not is_allowed:
        msg = f"Path outside allowed directories: {path}"
        if strict:
            raise PathValidationError(msg)
        logger.warning(msg)


def _resolve_security_args(
    *,
    strict: bool | None,
    allowed_base_dirs: list[Path] | None,
) -> tuple[SecurityConfig, bool, list[Path] | None]:
    config = _security_config
    strict_effective = config.strict_mode if strict is None else strict
    base_dirs_effective = (
        config.allowed_base_dirs if allowed_base_dirs is None else allowed_base_dirs
    )
    return config, strict_effective, base_dirs_effective


def _resolve_path(path_value: Path | str, *, must_exist: bool) -> Path:
    try:
        return Path(path_value).resolve(strict=must_exist)
    except (OSError, RuntimeError) as exc:
        raise PathValidationError(f"Invalid path: {exc}") from exc


def _resolve_directory_path(path_value: Path | str) -> Path:
    try:
        return Path(path_value).resolve()
    except (OSError, RuntimeError) as exc:
        raise PathValidationError(f"Invalid directory path: {exc}") from exc


def _validate_common_security_checks(
    *,
    path: Path,
    config: SecurityConfig,
    strict: bool,
    allowed_base_dirs: list[Path] | None,
) -> None:
    if not config.allow_symlinks:
        _check_symlink(path, strict=strict)
    if allowed_base_dirs or strict:
        _check_path_traversal(path, allowed_base_dirs, strict=strict)


def _validate_absolute_path_policy(
    *,
    path: Path,
    config: SecurityConfig,
    allowed_base_dirs: list[Path] | None,
) -> None:
    if config.allow_absolute_paths or not path.is_absolute():
        return
    if allowed_base_dirs:
        _check_path_traversal(path, allowed_base_dirs, strict=True)


def _validate_extension(path: Path, allowed_extensions: set[str] | None) -> None:
    if not allowed_extensions:
        return
    if path.suffix.lower() in allowed_extensions:
        return
    raise PathValidationError(f"Invalid extension {path.suffix}. Allowed: {allowed_extensions}")


def _validate_file_size(path: Path, max_size_mb: float) -> None:
    try:
        size_mb = path.stat().st_size / (1024 * 1024)
    except OSError as exc:
        raise PathValidationError(f"Failed to check file size: {exc}") from exc
    if size_mb > max_size_mb:
        raise PathValidationError(f"File too large: {size_mb:.2f}MB > {max_size_mb}MB")


def _ensure_directory_exists(
    path: Path,
    *,
    must_exist: bool,
    create_if_missing: bool,
) -> None:
    if not must_exist or path.exists():
        return
    if not create_if_missing:
        raise PathValidationError(f"Directory does not exist: {path}")
    try:
        path.mkdir(parents=True, exist_ok=True)
        logger.info(f"Created directory: {path}")
    except OSError as exc:
        raise PathValidationError(f"Failed to create directory: {exc}") from exc


def validate_file_path(
    file_path: Path | str,
    allowed_extensions: set[str] | None = None,
    max_size_mb: float | None = None,
    must_exist: bool = True,
    strict: bool | None = None,
    allowed_base_dirs: list[Path] | None = None,
) -> Path:
    """Validate file path for security and constraints.

    Args:
        file_path: Path to validate
        allowed_extensions: Set of allowed extensions (e.g., {'.mkv', '.mp4'})
        max_size_mb: Maximum file size in MB
        must_exist: Whether file must exist
        strict: Override global strict mode setting
        allowed_base_dirs: Override global allowed base directories

    Returns:
        Resolved absolute path

    Raises:
        PathValidationError: If validation fails
    """
    config, strict_effective, base_dirs_effective = _resolve_security_args(
        strict=strict,
        allowed_base_dirs=allowed_base_dirs,
    )
    if not config.allow_symlinks:
        _check_symlink(Path(file_path), strict=strict_effective)
    path = _resolve_path(file_path, must_exist=must_exist)
    _validate_common_security_checks(
        path=path,
        config=config,
        strict=strict_effective,
        allowed_base_dirs=base_dirs_effective,
    )
    _validate_absolute_path_policy(
        path=path,
        config=config,
        allowed_base_dirs=base_dirs_effective,
    )
    _validate_extension(path, allowed_extensions)
    if must_exist and max_size_mb:
        _validate_file_size(path, max_size_mb)
    return path


def validate_directory_path(
    dir_path: Path | str,
    must_exist: bool = True,
    create_if_missing: bool = False,
    strict: bool | None = None,
    allowed_base_dirs: list[Path] | None = None,
) -> Path:
    """Validate directory path with security checks.

    Args:
        dir_path: Directory path to validate
        must_exist: Whether directory must exist
        create_if_missing: Create directory if it doesn't exist
        strict: Override global strict mode setting
        allowed_base_dirs: Override global allowed base directories

    Returns:
        Resolved absolute path

    Raises:
        PathValidationError: If validation fails
    """
    config, strict_effective, base_dirs_effective = _resolve_security_args(
        strict=strict,
        allowed_base_dirs=allowed_base_dirs,
    )
    if not config.allow_symlinks:
        _check_symlink(Path(dir_path), strict=strict_effective)
    path = _resolve_directory_path(dir_path)
    _validate_common_security_checks(
        path=path,
        config=config,
        strict=strict_effective,
        allowed_base_dirs=base_dirs_effective,
    )
    _ensure_directory_exists(path, must_exist=must_exist, create_if_missing=create_if_missing)
    if path.exists() and not path.is_dir():
        raise PathValidationError(f"Path is not a directory: {path}")
    return path


def sanitize_filename(filename: str, replacement: str = "_") -> str:
    """Sanitize a filename by neutralising dangerous characters.

    Replaces path separators, null bytes and ``..`` sequences with
    ``replacement``. Strips leading/trailing dots and spaces. When the
    resulting string contains only replacement characters (i.e. nothing of
    substance survived) returns the literal ``"unnamed"`` so the caller can
    always rely on a non-empty, non-tautological filename.

    Args:
        filename: Candidate filename.
        replacement: Character used in place of dangerous tokens.

    Returns:
        A safe, non-empty filename.
    """
    dangerous_chars = ["/", "\\", "\0", ".."]
    sanitized = filename

    for char in dangerous_chars:
        sanitized = sanitized.replace(char, replacement)

    sanitized = sanitized.strip(". ")

    if not sanitized or sanitized.strip(replacement) == "":
        return "unnamed"

    return sanitized
