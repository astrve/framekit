"""File validation for Watch Mode."""

import time
from pathlib import Path

from loguru import logger

from .models import ValidationConfig


class FileValidator:
    """Validates files before processing."""

    def __init__(
        self, config: ValidationConfig, valid_extensions: list[str], ignore_extensions: list[str]
    ):
        """Initialize the file validator.

        Args:
            config: Validation configuration
            valid_extensions: List of valid video file extensions
            ignore_extensions: List of temporary file extensions to ignore
        """
        self.config = config
        self.valid_extensions = [ext.lower() for ext in valid_extensions]
        self.ignore_extensions = [ext.lower() for ext in ignore_extensions]

    def is_valid_extension(self, file_path: Path) -> bool:
        """Check if file has a valid video extension.

        Args:
            file_path: Path to the file

        Returns:
            True if extension is valid, False otherwise
        """
        extension = file_path.suffix.lower()
        is_valid = extension in self.valid_extensions

        if not is_valid:
            logger.debug(f"File {file_path.name} has invalid extension: {extension}")

        return is_valid

    def is_temporary(self, file_path: Path) -> bool:
        """Check if file is a temporary file.

        Args:
            file_path: Path to the file

        Returns:
            True if file is temporary, False otherwise
        """
        extension = file_path.suffix.lower()
        is_temp = extension in self.ignore_extensions

        if is_temp:
            logger.debug(f"File {file_path.name} is temporary: {extension}")

        return is_temp

    def is_stable(self, file_path: Path, timeout: int | None = None) -> bool:
        """Check if file is stable (size not changing).

        Monitors file size at regular intervals to ensure the file
        is not being written to (e.g., during download or copy).

        Args:
            file_path: Path to the file
            timeout: Timeout in seconds (uses config default if None)

        Returns:
            True if file is stable, False otherwise
        """
        if timeout is None:
            timeout = self.config.stability_timeout

        if not file_path.exists():
            logger.warning(f"File {file_path} does not exist")
            return False

        try:
            # Get initial size
            initial_size = file_path.stat().st_size

            # Check minimum file size
            if initial_size < self.config.min_file_size:
                logger.debug(
                    f"File {file_path.name} is too small: {initial_size} bytes "
                    f"(minimum: {self.config.min_file_size} bytes)"
                )
                return False

            logger.info(
                f"Checking stability for {file_path.name} "
                f"(timeout: {timeout}s, interval: {self.config.check_interval}s)"
            )

            # Monitor file size over time
            checks = timeout // self.config.check_interval
            for i in range(checks):
                time.sleep(self.config.check_interval)

                if not file_path.exists():
                    logger.warning(f"File {file_path} disappeared during stability check")
                    return False

                current_size = file_path.stat().st_size

                if current_size != initial_size:
                    logger.debug(
                        f"File {file_path.name} size changed: "
                        f"{initial_size} -> {current_size} bytes (check {i + 1}/{checks})"
                    )
                    return False

                logger.debug(
                    f"File {file_path.name} stable check {i + 1}/{checks}: {current_size} bytes"
                )

            logger.info(f"File {file_path.name} is stable ({initial_size} bytes)")
            return True

        except Exception as e:
            logger.error(f"Error checking file stability for {file_path}: {e}")
            return False

    def validate(self, file_path: Path) -> tuple[bool, str]:
        """Perform complete validation on a file.

        Args:
            file_path: Path to the file

        Returns:
            Tuple of (is_valid, reason)
        """
        # Check if file exists
        if not file_path.exists():
            return False, "File does not exist"

        # Check if it's a file (not a directory)
        if not file_path.is_file():
            return False, "Path is not a file"

        # Check if temporary
        if self.is_temporary(file_path):
            return False, "File is temporary"

        # Check extension
        if not self.is_valid_extension(file_path):
            return False, f"Invalid extension: {file_path.suffix}"

        # Check stability
        if not self.is_stable(file_path):
            return False, "File is not stable"

        return True, "File is valid"
