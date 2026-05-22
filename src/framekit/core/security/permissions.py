"""Cross-platform file permissions management with Windows ACL support.

Provides secure file permission handling for both Windows (ACL) and Unix (chmod)
systems to ensure sensitive files are only accessible by the current user.

Every external-tool invocation goes through :mod:`framekit.core.subprocess_safe`
(see ADR-0006). That wrapper resolves the binary to an absolute path through
``shutil.which`` so a writable ``PATH`` entry cannot substitute a hostile
``icacls.exe`` on Windows.
"""

import os
import platform
from pathlib import Path
from typing import Literal

from loguru import logger

from framekit.core.subprocess_safe import (
    MissingToolError,
    SafeSubprocessError,
    run_safe,
)


class PermissionError(Exception):
    """Exception raised when permission operations fail."""


PermissionMode = Literal["owner_only", "owner_group", "world_readable"]


def _set_windows_acl(filepath: Path, mode: PermissionMode = "owner_only") -> None:
    """Set Windows ACL permissions using icacls.

    Args:
        filepath: Path to file or directory
        mode: Permission mode (only "owner_only" is secure for sensitive files)

    Raises:
        PermissionError: If ACL setting fails
    """
    if mode != "owner_only":
        logger.warning(f"Non-secure permission mode '{mode}' requested for Windows ACL")

    try:
        # Get current user
        import getpass

        username = getpass.getuser()

        # Convert path to absolute Windows path
        abs_path = str(filepath.resolve())

        # Remove all inherited permissions and existing ACLs.
        # /inheritance:r = remove inheritance. ``run_safe`` resolves
        # ``icacls`` to its absolute path so a writable PATH entry cannot
        # hijack the binary.
        run_safe(
            ["icacls", abs_path, "/inheritance:r"],
            timeout=15,
            check=True,
            log_label="icacls inheritance:r",
        )

        # Grant full control to current user only.
        # /grant:r = replace existing permissions
        # (F) = Full control
        run_safe(
            ["icacls", abs_path, "/grant:r", f"{username}:(F)"],
            timeout=15,
            check=True,
            log_label="icacls grant:r",
        )

        logger.debug(f"Set Windows ACL for {filepath}: owner-only access")

    except MissingToolError as exc:
        raise PermissionError("icacls command not found. Windows ACL not available.") from exc
    except SafeSubprocessError as exc:
        raise PermissionError(f"Failed to set Windows ACL: {exc.stderr or exc}") from exc
    except Exception as e:
        raise PermissionError(f"Failed to set Windows ACL: {e}") from e


def _set_unix_permissions(filepath: Path, mode: PermissionMode = "owner_only") -> None:
    """Set Unix file permissions using chmod.

    Args:
        filepath: Path to file or directory
        mode: Permission mode

    Raises:
        PermissionError: If chmod fails
    """
    try:
        if mode == "owner_only":
            # 0o600 = rw------- (owner read/write only). Default for vault,
            # master.key, and any file containing decrypted secrets.
            os.chmod(filepath, 0o600)
        elif mode == "owner_group":
            # 0o660 = rw-rw---- (owner and group read/write). Only use for
            # files explicitly shared with a service group; never for raw
            # secret material. We log the elevation so audit trails capture
            # the choice.
            logger.warning(
                f"Setting {filepath} to 0o660 (owner_group). Verify the group "
                "really needs read access; secret material should use 'owner_only'."
            )
            # Justification: 0o660 is intentional for owner_group mode. This mode is
            # explicitly documented as less secure and logs a warning. The default
            # mode is owner_only (0o600). Never use owner_group for sensitive files.
            os.chmod(  # nosec B103  # nosemgrep: python.lang.security.audit.insecure-file-permissions.insecure-file-permissions
                filepath, 0o660
            )
        elif mode == "world_readable":
            # 0o644 = rw-r--r-- (owner read/write, others read)
            os.chmod(filepath, 0o644)
        else:
            raise PermissionError(f"Unknown permission mode: {mode}")

        logger.debug(f"Set Unix permissions for {filepath}: {mode}")

    except OSError as e:
        raise PermissionError(f"Failed to set Unix permissions: {e}") from e


def set_secure_permissions(
    filepath: Path,
    mode: PermissionMode = "owner_only",
    strict: bool = True,
) -> None:
    """Set secure file permissions appropriate for the current platform.

    On Windows: Uses ACL to restrict access to current user only.
    On Unix: Uses chmod to set appropriate permissions.

    Args:
        filepath: Path to file or directory to secure
        mode: Permission mode (default: owner_only for maximum security)
        strict: If True, raises exception on failure. If False, logs warning.

    Raises:
        PermissionError: If strict=True and permission setting fails
    """
    if not filepath.exists():
        raise PermissionError(f"Path does not exist: {filepath}")

    system = platform.system()

    try:
        if system == "Windows":
            _set_windows_acl(filepath, mode)
        else:
            # Unix-like systems (Linux, macOS, BSD, etc.)
            _set_unix_permissions(filepath, mode)

    except PermissionError as e:
        if strict:
            raise
        else:
            logger.warning(f"Failed to set secure permissions for {filepath}: {e}")


def verify_secure_permissions(filepath: Path) -> bool:
    """Verify that file has secure permissions (owner-only access).

    Args:
        filepath: Path to file to verify

    Returns:
        True if permissions are secure, False otherwise
    """
    if not filepath.exists():
        return False

    try:
        if platform.system() == "Windows":
            return _verify_secure_permissions_windows(filepath)
        return _verify_secure_permissions_unix(filepath)

    except Exception as e:
        logger.error(f"Failed to verify permissions for {filepath}: {e}")
        return False


def _verify_secure_permissions_windows(filepath: Path) -> bool:
    result = _read_windows_acl(filepath)
    if result is None or result.returncode != 0:
        return False
    import getpass

    username = getpass.getuser()
    lines = result.stdout.strip().split("\n")
    for line in lines[1:]:
        if _grants_other_user_access(line, username):
            logger.warning(f"File {filepath} has permissions for other users")
            return False
    return True


def _read_windows_acl(filepath: Path):
    try:
        return run_safe(
            ["icacls", str(filepath.resolve())],
            timeout=15,
            check=False,
            log_label="icacls verify",
        )
    except (MissingToolError, SafeSubprocessError):
        return None


def _grants_other_user_access(line: str, username: str) -> bool:
    if not line.strip() or username in line:
        return False
    return any(permission in line for permission in ["(F)", "(M)", "(RX)", "(R)", "(W)"])


def _verify_secure_permissions_unix(filepath: Path) -> bool:
    mode = filepath.stat().st_mode & 0o777
    if mode in (0o600, 0o400):
        return True
    logger.warning(f"File {filepath} has insecure permissions: {oct(mode)}")
    return False


def get_permission_info(filepath: Path) -> dict[str, str | int]:
    """Get human-readable permission information for a file.

    Args:
        filepath: Path to file

    Returns:
        Dictionary with permission information
    """
    if not filepath.exists():
        return {"error": "File does not exist"}  # type: ignore[return-value]

    system = platform.system()
    info: dict[str, str | int] = {
        "platform": system,
        "path": str(filepath),
    }

    try:
        if system == "Windows":
            try:
                result = run_safe(
                    ["icacls", str(filepath.resolve())],
                    timeout=15,
                    check=False,
                    log_label="icacls info",
                )
            except (MissingToolError, SafeSubprocessError) as exc:
                info["error"] = f"Failed to read ACL: {exc}"
                return info

            if result.returncode == 0:
                info["acl"] = result.stdout.strip()
            else:
                info["error"] = "Failed to read ACL"

        else:
            stat_info = filepath.stat()
            mode = stat_info.st_mode & 0o777
            info["mode_octal"] = oct(mode)
            info["mode_symbolic"] = _mode_to_symbolic(mode)

    except Exception as e:
        info["error"] = str(e)

    return info


def _mode_to_symbolic(mode: int) -> str:
    """Convert numeric mode to symbolic representation (e.g., 'rw-r--r--')."""
    symbols = []
    for shift in [6, 3, 0]:  # owner, group, others
        perms = (mode >> shift) & 0o7
        symbols.append("r" if perms & 0o4 else "-")
        symbols.append("w" if perms & 0o2 else "-")
        symbols.append("x" if perms & 0o1 else "-")
    return "".join(symbols)
