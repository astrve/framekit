"""Command aliases system for Ouro.

Provides functionality for creating, managing, and resolving command aliases
with parameter substitution, circular reference detection, and conflict prevention.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from loguru import logger

from ouro.core.exceptions import OuroError
from ouro.core.settings import SettingsStore


class AliasError(OuroError):
    """Base exception for alias-related errors."""


class InvalidAliasNameError(AliasError):
    """Raised when an alias name is invalid."""


class CircularReferenceError(AliasError):
    """Raised when a circular reference is detected in alias chain."""


# Valid alias name pattern: alphanumeric, dash, underscore
ALIAS_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")

# Built-in commands that cannot be shadowed by aliases
BUILTIN_COMMANDS = {
    "about",
    "doctor",
    "language",
    "settings",
    "inspect",
    "renamer",
    "cleanmkv",
    "nfo",
    "metadata",
    "torrent",
    "prez",
    "screenshot",
    "extract",
    "pipeline",
    "batch",
    "setup",
    "init",
    "examples",
    "encode",
    "upload",
    "watch",
    "seedbox",
    "config",
    "validate",
    "profile",
    "browse",
    "sort",
}


@dataclass
class AliasDefinition:
    """Definition of a command alias.

    Attributes:
        name: The alias name
        command: The command string (may contain parameter placeholders)
        description: Human-readable description
        enabled: Whether the alias is enabled
    """

    name: str
    command: str
    description: str
    enabled: bool

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, AliasDefinition):
            return False
        return (
            self.name == other.name
            and self.command == other.command
            and self.description == other.description
            and self.enabled == other.enabled
        )


@dataclass
class AliasResolutionResult:
    """Result of alias resolution.

    Attributes:
        command: The resolved command name
        args: The resolved arguments list
        chain: List of alias names in the resolution chain
    """

    command: str
    args: list[str]
    chain: list[str] = field(default_factory=list)


class AliasManager:
    """Manager for command aliases.

    Handles CRUD operations for aliases, resolution with parameter substitution,
    circular reference detection, and conflict prevention.
    """

    def __init__(self, settings_store: SettingsStore, max_chain_depth: int | None = None):
        """Initialize the alias manager.

        Args:
            settings_store: The settings store instance
            max_chain_depth: Maximum alias chain depth (default from settings)
        """
        self.settings_store = settings_store
        self._settings = settings_store.load()
        self._max_chain_depth = max_chain_depth or self._settings.get("aliases", {}).get(
            "max_chain_depth", 5
        )

    def _get_aliases_config(self) -> dict[str, Any]:
        """Get the aliases configuration from settings."""
        return self._settings.get("aliases", {})

    def _save_aliases_config(self, config: dict[str, Any]) -> None:
        """Save the aliases configuration to settings."""
        self._settings["aliases"] = config
        self.settings_store.save(self._settings)
        self._settings = self.settings_store.load()

    def _removed_aliases(self, config: dict[str, Any] | None = None) -> set[str]:
        aliases = config if config is not None else self._get_aliases_config()
        raw_removed = aliases.get("removed", [])
        if not isinstance(raw_removed, list):
            return set()
        return {str(item).strip() for item in raw_removed if str(item).strip()}

    def _mark_removed(self, name: str, config: dict[str, Any]) -> None:
        removed = self._removed_aliases(config)
        removed.add(name)
        config["removed"] = sorted(removed)

    def _unmark_removed(self, name: str, config: dict[str, Any]) -> None:
        removed = self._removed_aliases(config)
        removed.discard(name)
        config["removed"] = sorted(removed)

    def _is_valid_alias_name(self, name: str) -> bool:
        """Check if an alias name is valid.

        Args:
            name: The alias name to validate

        Returns:
            True if valid, False otherwise
        """
        return bool(name and ALIAS_NAME_PATTERN.match(name))

    def _check_conflict_with_builtin(self, name: str) -> None:
        """Check if alias name conflicts with a built-in command.

        Args:
            name: The alias name to check

        Raises:
            AliasError: If the name conflicts with a built-in command
        """
        if name in BUILTIN_COMMANDS:
            raise AliasError(f"Alias '{name}' conflicts with built-in command")

    def list_aliases(
        self,
        user_only: bool = False,
        builtin_only: bool = False,
        enabled_only: bool = False,
    ) -> dict[str, AliasDefinition]:
        """List all aliases.

        Args:
            user_only: Only return user-defined aliases
            builtin_only: Only return built-in aliases
            enabled_only: Only return enabled aliases

        Returns:
            Dictionary mapping alias names to definitions
        """
        config = self._get_aliases_config()
        result: dict[str, AliasDefinition] = {}
        removed = self._removed_aliases(config)

        if not builtin_only:
            result.update(
                self._collect_alias_group(config.get("user", {}), enabled_only=enabled_only)
            )

        if not user_only:
            result.update(
                self._collect_alias_group(config.get("builtin", {}), enabled_only=enabled_only)
            )

        for alias_name in removed:
            result.pop(alias_name, None)
        return result

    def _collect_alias_group(
        self,
        aliases: dict[str, Any],
        *,
        enabled_only: bool,
    ) -> dict[str, AliasDefinition]:
        collected: dict[str, AliasDefinition] = {}
        for name, definition in aliases.items():
            if not isinstance(definition, dict):
                continue
            alias = AliasDefinition(
                name=name,
                command=definition.get("command", ""),
                description=definition.get("description", ""),
                enabled=definition.get("enabled", True),
            )
            if enabled_only and not alias.enabled:
                continue
            collected[name] = alias
        return collected

    def get_alias(self, name: str) -> AliasDefinition | None:
        """Get a specific alias by name.

        Args:
            name: The alias name

        Returns:
            The alias definition, or None if not found
        """
        config = self._get_aliases_config()
        if name in self._removed_aliases(config):
            return None

        # Check user aliases first
        user_aliases = config.get("user", {})
        if name in user_aliases:
            definition = user_aliases[name]
            if isinstance(definition, dict):
                return AliasDefinition(
                    name=name,
                    command=definition.get("command", ""),
                    description=definition.get("description", ""),
                    enabled=definition.get("enabled", True),
                )

        # Check builtin aliases
        builtin_aliases = config.get("builtin", {})
        if name in builtin_aliases:
            definition = builtin_aliases[name]
            if isinstance(definition, dict):
                return AliasDefinition(
                    name=name,
                    command=definition.get("command", ""),
                    description=definition.get("description", ""),
                    enabled=definition.get("enabled", True),
                )

        return None

    def add_alias(
        self,
        name: str,
        command: str,
        description: str = "",
        enabled: bool = True,
    ) -> None:
        """Add a new user alias.

        Args:
            name: The alias name
            command: The command string
            description: Optional description
            enabled: Whether the alias is enabled

        Raises:
            InvalidAliasNameError: If the alias name is invalid
            AliasError: If the alias conflicts with a built-in command
        """
        if not self._is_valid_alias_name(name):
            raise InvalidAliasNameError(f"Invalid alias name: '{name}'")

        self._check_conflict_with_builtin(name)

        config = self._get_aliases_config()
        self._unmark_removed(name, config)
        user_aliases = config.setdefault("user", {})

        user_aliases[name] = {
            "command": command,
            "description": description,
            "enabled": enabled,
        }

        self._save_aliases_config(config)
        logger.debug(f"Added alias: {name} -> {command}")

    def remove_alias(self, name: str) -> None:
        """Remove a user alias.

        Args:
            name: The alias name

        Raises:
            AliasError: If alias not found
        """
        config = self._get_aliases_config()
        removed = self._removed_aliases(config)
        if name in removed:
            raise AliasError(f"Alias not found: '{name}'")

        builtin_aliases = config.get("builtin", {})
        user_aliases = config.get("user", {})
        found_user = isinstance(user_aliases, dict) and name in user_aliases
        found_builtin = isinstance(builtin_aliases, dict) and name in builtin_aliases

        if not found_user and not found_builtin:
            raise AliasError(f"Alias not found: '{name}'")

        if found_user:
            del user_aliases[name]
        if found_builtin:
            del builtin_aliases[name]
        self._mark_removed(name, config)
        self._save_aliases_config(config)
        logger.debug(f"Removed alias: {name}")

    def enable_alias(self, name: str) -> None:
        """Enable an alias.

        Args:
            name: The alias name

        Raises:
            AliasError: If alias not found
        """
        config = self._get_aliases_config()
        if name in self._removed_aliases(config):
            self._unmark_removed(name, config)
            self._save_aliases_config(config)
            logger.debug(f"Enabled alias: {name}")
            return

        # Check user aliases
        user_aliases = config.get("user", {})
        if name in user_aliases:
            user_aliases[name]["enabled"] = True
            self._save_aliases_config(config)
            logger.debug(f"Enabled alias: {name}")
            return

        # Check builtin aliases
        builtin_aliases = config.get("builtin", {})
        if name in builtin_aliases:
            builtin_aliases[name]["enabled"] = True
            self._save_aliases_config(config)
            logger.debug(f"Enabled alias: {name}")
            return

        raise AliasError(f"Alias not found: '{name}'")

    def disable_alias(self, name: str) -> None:
        """Disable an alias.

        Args:
            name: The alias name

        Raises:
            AliasError: If alias not found
        """
        config = self._get_aliases_config()

        # Check user aliases
        user_aliases = config.get("user", {})
        if name in user_aliases:
            user_aliases[name]["enabled"] = False
            self._save_aliases_config(config)
            logger.debug(f"Disabled alias: {name}")
            return

        # Check builtin aliases
        builtin_aliases = config.get("builtin", {})
        if name in builtin_aliases:
            builtin_aliases[name]["enabled"] = False
            self._save_aliases_config(config)
            logger.debug(f"Disabled alias: {name}")
            return

        raise AliasError(f"Alias not found: '{name}'")

    def _substitute_parameters(self, command: str, args: list[str]) -> list[str]:
        """Substitute parameters in command string.

        Args:
            command: The command string with placeholders
            args: The arguments to substitute

        Returns:
            List of command parts with substituted parameters

        Raises:
            AliasError: If required parameters are missing
        """
        # Find all parameter placeholders
        param_pattern = re.compile(r"\{(\d+)\}")
        matches = param_pattern.findall(command)

        if matches:
            # Check if we have enough arguments
            max_index = max(int(m) for m in matches)
            if max_index >= len(args):
                raise AliasError(
                    f"Not enough parameters: command requires at least {max_index + 1} "
                    f"parameter(s), but only {len(args)} provided"
                )

            # Substitute parameters
            result = command
            for match in matches:
                index = int(match)
                result = result.replace(f"{{{match}}}", args[index])

            # Split into parts and add remaining args
            parts = result.split()
            used_indices = {int(m) for m in matches}
            remaining_args = [arg for i, arg in enumerate(args) if i not in used_indices]
            parts.extend(remaining_args)

            return parts
        else:
            # No parameters, just split and add args
            parts = command.split()
            parts.extend(args)
            return parts

    def resolve(self, alias_name: str, args: list[str]) -> AliasResolutionResult:
        """Resolve an alias to its final command.

        Args:
            alias_name: The alias name to resolve
            args: Arguments to pass to the command

        Returns:
            Resolution result with command, args, and chain

        Raises:
            AliasError: If alias not found, disabled, or circular reference detected
        """
        chain: list[str] = []
        current_name = alias_name
        current_args = args

        for depth in range(self._max_chain_depth + 1):
            if depth >= self._max_chain_depth:
                raise CircularReferenceError(
                    f"Maximum alias chain depth ({self._max_chain_depth}) exceeded. "
                    f"Possible circular reference in chain: {' -> '.join(chain)}"
                )

            # Get the alias
            alias = self.get_alias(current_name)
            if alias is None:
                # Not an alias, treat as final command
                if not chain:
                    raise AliasError(f"Alias not found: '{alias_name}'")
                return AliasResolutionResult(
                    command=current_name,
                    args=current_args,
                    chain=chain,
                )

            # Check if enabled
            if not alias.enabled:
                raise AliasError(f"Alias '{current_name}' is disabled")

            # Add to chain
            chain.append(current_name)

            # Check for circular reference
            if chain.count(current_name) > 1:
                raise CircularReferenceError(
                    f"Circular reference detected in alias chain: {' -> '.join(chain)}"
                )

            # Substitute parameters and get command parts
            parts = self._substitute_parameters(alias.command, current_args)

            if not parts:
                raise AliasError(f"Alias '{current_name}' has empty command")

            # First part is the next command/alias
            current_name = parts[0]
            current_args = parts[1:]

            # Check if this is a built-in command (final resolution)
            if current_name in BUILTIN_COMMANDS or current_name not in self.list_aliases():
                return AliasResolutionResult(
                    command=current_name,
                    args=current_args,
                    chain=chain,
                )

        # Should not reach here
        raise CircularReferenceError(
            f"Maximum alias chain depth ({self._max_chain_depth}) exceeded"
        )
