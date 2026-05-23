"""Setup wizard implementation."""

from __future__ import annotations

from typing import Any

from framekit.core.i18n import tr
from framekit.core.settings import SettingsStore
from framekit.modules.setup.profiles import (
    get_profile,
    should_ask_question,
)
from framekit.modules.setup.selector import ChoiceOption, choose_option
from framekit.modules.setup.ui import (
    confirm_action,
    prompt_input,
    show_completion_banner,
    show_configuration_summary,
    show_example,
    show_help_text,
    show_info_message,
    show_navigation_help,
    show_profile_comparison,
    show_success_message,
    show_validation_error,
    show_welcome_banner,
    show_wizard_header,
)
from framekit.modules.setup.validators import (
    test_tmdb_connection,
    validate_announce_url,
    validate_memory_size,
    validate_tmdb_token,
    validate_worker_count,
)
from framekit.ui.console import console


class WizardCancelled(Exception):
    """Exception raised when wizard is cancelled."""


class SetupWizard:
    """Interactive setup wizard for Framekit configuration."""

    TOTAL_STEPS = 8

    def __init__(self, profile: str = "beginner") -> None:
        """Initialize the wizard.

        Args:
            profile: Profile name (beginner, advanced, custom)
        """
        self.profile_config = get_profile(profile)
        self.config: dict[str, Any] = {}
        self.current_step = 0
        self.history: list[int] = []

        # Initialize config with profile defaults
        self._apply_defaults()

    def _apply_defaults(self) -> None:
        """Apply profile defaults to configuration."""
        for key, value in self.profile_config.defaults.items():
            self._set_nested_value(key, value)

    def _set_nested_value(self, path: str, value: Any) -> None:
        """Set a nested configuration value.

        Args:
            path: Dot-separated path (e.g., "general.locale")
            value: Value to set
        """
        parts = path.split(".")
        current = self.config

        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]

        current[parts[-1]] = value

    def _get_nested_value(self, path: str, default: Any = None) -> Any:
        """Get a nested configuration value.

        Args:
            path: Dot-separated path
            default: Default value if not found

        Returns:
            Configuration value
        """
        parts = path.split(".")
        current = self.config

        for part in parts:
            if not isinstance(current, dict) or part not in current:
                return default
            current = current[part]

        return current

    def run(self) -> dict[str, Any]:
        """Run the complete wizard flow.

        Returns:
            Complete configuration dictionary

        Raises:
            WizardCancelled: If user cancels the wizard
        """
        try:
            # Step 1: Welcome & Profile Selection
            self.step_welcome()

            # Step 2: Language Selection
            if should_ask_question(self.profile_config, "language"):
                self.step_language()

            # Step 3: TMDb Configuration
            if should_ask_question(self.profile_config, "tmdb_token"):
                self.step_tmdb()

            # Step 4: Torrent Configuration
            if should_ask_question(self.profile_config, "torrent_announce"):
                self.step_torrent()

            # Step 5: Default Presets
            if should_ask_question(self.profile_config, "presets"):
                self.step_presets()

            # Step 6: Performance Settings
            if should_ask_question(self.profile_config, "performance"):
                self.step_performance()

            # Step 7: Security Settings
            if should_ask_question(self.profile_config, "security"):
                self.step_security()

            # Step 8: Summary & Confirmation
            self.step_summary()

            return self.config

        except KeyboardInterrupt as exc:
            raise WizardCancelled("Wizard cancelled by user") from exc

    def step_welcome(self) -> None:
        """Step 1: Welcome and profile selection."""
        self.current_step = 1
        show_welcome_banner()

        console.print(
            tr(
                "wizard.welcome.message",
                default="This wizard will guide you through the initial setup of Framekit.\n"
                "You can choose a setup profile based on your experience level.",
            ),
            style="white",
        )
        console.print()

        show_profile_comparison()

        # Profile selection
        options = [
            ChoiceOption(
                value="beginner",
                label=tr("wizard.profile.beginner", default="Beginner"),
                description=tr(
                    "wizard.profile.beginner.desc",
                    default="Quick setup with sensible defaults",
                ),
            ),
            ChoiceOption(
                value="advanced",
                label=tr("wizard.profile.advanced", default="Advanced"),
                description=tr(
                    "wizard.profile.advanced.desc",
                    default="Full control over all settings",
                ),
            ),
            ChoiceOption(
                value="custom",
                label=tr("wizard.profile.custom", default="Custom"),
                description=tr(
                    "wizard.profile.custom.desc",
                    default="Guided setup with explanations",
                ),
            ),
        ]

        selected = choose_option(
            title=tr("wizard.profile.select", default="Select Setup Profile"),
            options=options,
            preferred_value=self.profile_config.name,
        )

        if selected and selected != self.profile_config.name:
            # Update profile
            self.profile_config = get_profile(selected)
            self._apply_defaults()

        show_navigation_help()

    def step_language(self) -> None:
        """Step 2: Language selection."""
        self.current_step = 2
        show_wizard_header(
            self.current_step,
            self.TOTAL_STEPS,
            tr("wizard.language.title", default="Language Selection"),
        )

        if self.profile_config.show_help:
            show_help_text(
                tr(
                    "wizard.language.help",
                    default="Choose the interface language for Framekit. "
                    "This affects menus, messages, and documentation.",
                )
            )

        # Language options
        options = [
            ChoiceOption(
                value="en",
                label=tr("wizard.language.english", default="English"),
                description="English",
            ),
            ChoiceOption(
                value="fr",
                label=tr("wizard.language.french", default="French"),
                description="Français",
            ),
            ChoiceOption(
                value="es",
                label=tr("wizard.language.spanish", default="Spanish"),
                description="Español",
            ),
        ]

        current = self._get_nested_value("general.locale", "en")
        selected = choose_option(
            title=tr("wizard.language.select", default="Select Interface Language"),
            options=options,
            preferred_value=current,
        )

        if selected:
            self._set_nested_value("general.locale", selected)

            # Also set metadata language
            metadata_lang_map = {
                "en": "en-US",
                "fr": "fr-FR",
                "es": "es-ES",
            }
            self._set_nested_value("metadata.language", metadata_lang_map.get(selected, "en-US"))

            show_success_message(
                tr("wizard.language.success", default=f"Language set to: {selected}")
            )

    def step_tmdb(self) -> None:
        """Step 3: TMDb configuration."""
        self.current_step = 3
        show_wizard_header(
            self.current_step,
            self.TOTAL_STEPS,
            tr("wizard.tmdb.title", default="TMDb API Configuration"),
        )

        if self.profile_config.show_help:
            show_help_text(
                tr(
                    "wizard.tmdb.help",
                    default="TMDb (The Movie Database) is used to fetch movie and TV show metadata. "
                    "You need a free API token from https://www.themoviedb.org/settings/api",
                )
            )

        show_example("tmdb_v4_token_example_replace_with_your_real_token")

        current_token = self._get_nested_value("metadata.tmdb_read_access_token", "")

        while True:
            token = prompt_input(
                tr("wizard.tmdb.prompt", default="Enter your TMDb API token"),
                default=current_token if current_token else "",
                password=True,
            )

            if not token:
                show_validation_error(tr("wizard.tmdb.required", default="TMDb token is required"))
                continue

            # Validate format
            is_valid, error = validate_tmdb_token(token)
            if not is_valid:
                show_validation_error(error)
                continue

            # Test connection
            if confirm_action(
                tr("wizard.tmdb.test", default="Test TMDb connection?"),
                default=True,
            ):
                show_info_message(tr("wizard.tmdb.testing", default="Testing TMDb connection..."))

                is_valid, error = test_tmdb_connection(token)
                if not is_valid:
                    show_validation_error(error)
                    if not confirm_action(
                        tr("wizard.tmdb.use_anyway", default="Use this token anyway?"),
                        default=False,
                    ):
                        continue
                else:
                    show_success_message(
                        tr("wizard.tmdb.success", default="TMDb connection successful!")
                    )

            self._set_nested_value("metadata.tmdb_read_access_token", token)
            break

    def step_torrent(self) -> None:
        """Step 4: Torrent configuration."""
        self.current_step = 4
        show_wizard_header(
            self.current_step,
            self.TOTAL_STEPS,
            tr("wizard.torrent.title", default="Torrent Configuration"),
        )

        if self.profile_config.show_help:
            show_help_text(
                tr(
                    "wizard.torrent.help",
                    default="Configure torrent tracker announce URLs. "
                    "You can add multiple trackers for redundancy.",
                )
            )

        show_example("https://tracker.example.com/announce/your-passkey")

        announce_urls: list[str] = []

        while True:
            if announce_urls:
                show_info_message(
                    tr(
                        "wizard.torrent.current",
                        default=f"Current trackers: {len(announce_urls)}",
                        count=len(announce_urls),
                    )
                )

            url = prompt_input(
                tr(
                    "wizard.torrent.prompt",
                    default="Enter announce URL (or press Enter to finish)",
                ),
                default="",
            )

            if not url:
                if announce_urls or confirm_action(
                    tr("wizard.torrent.skip", default="Skip torrent configuration?"),
                    default=True,
                ):
                    break
                continue

            # Validate URL
            is_valid, error = validate_announce_url(url)
            if not is_valid:
                show_validation_error(error)
                continue

            announce_urls.append(url)
            show_success_message(tr("wizard.torrent.added", default="Announce URL added"))

            if not confirm_action(
                tr("wizard.torrent.add_more", default="Add another tracker?"),
                default=False,
            ):
                break

        if announce_urls:
            self._set_nested_value("modules.torrent.announce_urls", announce_urls)
            self._set_nested_value("modules.torrent.announce", announce_urls[0])
            self._set_nested_value("modules.torrent.selected_announce", announce_urls[0])

    def step_presets(self) -> None:
        """Step 5: Default presets."""
        self.current_step = 5
        show_wizard_header(
            self.current_step,
            self.TOTAL_STEPS,
            tr("wizard.presets.title", default="Default Presets"),
        )

        if self.profile_config.show_help:
            show_help_text(
                tr(
                    "wizard.presets.help",
                    default="Configure default presets for CleanMKV, NFO templates, and Prez formats.",
                )
            )

        # CleanMKV preset
        cleanmkv_options = [
            ChoiceOption(
                value="multi",
                label=tr("wizard.presets.cleanmkv.multi", default="Multi"),
                description=tr(
                    "wizard.presets.cleanmkv.multi.desc",
                    default="Keep all audio/subtitle tracks",
                ),
            ),
            ChoiceOption(
                value="single",
                label=tr("wizard.presets.cleanmkv.single", default="Single"),
                description=tr(
                    "wizard.presets.cleanmkv.single.desc",
                    default="Keep only primary tracks",
                ),
            ),
        ]

        cleanmkv_preset = choose_option(
            title=tr("wizard.presets.cleanmkv.select", default="Select CleanMKV Preset"),
            options=cleanmkv_options,
            preferred_value=self._get_nested_value("modules.cleanmkv.default_preset", "multi"),
        )

        if cleanmkv_preset:
            self._set_nested_value("modules.cleanmkv.default_preset", cleanmkv_preset)

        # NFO template
        nfo_options = [
            ChoiceOption(
                value="default",
                label=tr("wizard.presets.nfo.default", default="Default"),
                description=tr(
                    "wizard.presets.nfo.default.desc",
                    default="Standard NFO template",
                ),
            ),
        ]

        nfo_template = choose_option(
            title=tr("wizard.presets.nfo.select", default="Select NFO Template"),
            options=nfo_options,
            preferred_value=self._get_nested_value("modules.nfo.active_template", "default"),
        )

        if nfo_template:
            self._set_nested_value("modules.nfo.active_template", nfo_template)

        # Prez format
        prez_options = [
            ChoiceOption(
                value="both",
                label=tr("wizard.presets.prez.both", default="Both"),
                description=tr(
                    "wizard.presets.prez.both.desc",
                    default="HTML and BBCode",
                ),
            ),
            ChoiceOption(
                value="html",
                label=tr("wizard.presets.prez.html", default="HTML Only"),
                description=tr(
                    "wizard.presets.prez.html.desc",
                    default="HTML format only",
                ),
            ),
            ChoiceOption(
                value="bbcode",
                label=tr("wizard.presets.prez.bbcode", default="BBCode Only"),
                description=tr(
                    "wizard.presets.prez.bbcode.desc",
                    default="BBCode format only",
                ),
            ),
        ]

        prez_format = choose_option(
            title=tr("wizard.presets.prez.select", default="Select Prez Format"),
            options=prez_options,
            preferred_value=self._get_nested_value("modules.prez.format", "both"),
        )

        if prez_format:
            self._set_nested_value("modules.prez.format", prez_format)

        # Renamer — default language tag
        lang_tag_options = [
            ChoiceOption(
                value="MULTI.VFF",
                label="MULTI.VFF",
                description=tr(
                    "wizard.presets.renamer.lang_tag.multi_vff.desc",
                    default="Multiple languages including French (most French releases)",
                ),
            ),
            ChoiceOption(
                value="MULTI",
                label="MULTI",
                description=tr(
                    "wizard.presets.renamer.lang_tag.multi.desc",
                    default="Multiple languages, no French implied",
                ),
            ),
            ChoiceOption(
                value="VFF",
                label="VFF",
                description=tr(
                    "wizard.presets.renamer.lang_tag.vff.desc",
                    default="French audio only",
                ),
            ),
            ChoiceOption(
                value="",
                label=tr(
                    "wizard.presets.renamer.lang_tag.none", default="None (no auto-injection)"
                ),
                description=tr(
                    "wizard.presets.renamer.lang_tag.none.desc",
                    default="Do not inject a language tag automatically — use --lang explicitly",
                ),
            ),
        ]

        lang_tag = choose_option(
            title=tr(
                "wizard.presets.renamer.lang_tag.select",
                default="Default Language Tag for Renamer",
            ),
            options=lang_tag_options,
            preferred_value=self._get_nested_value(
                "modules.renamer.default_language_tag", "MULTI.VFF"
            ),
        )

        if lang_tag is not None:
            self._set_nested_value("modules.renamer.default_language_tag", lang_tag)

    def step_performance(self) -> None:
        """Step 6: Performance settings."""
        self.current_step = 6
        show_wizard_header(
            self.current_step,
            self.TOTAL_STEPS,
            tr("wizard.performance.title", default="Performance Settings"),
        )

        if self.profile_config.show_help:
            show_help_text(
                tr(
                    "wizard.performance.help",
                    default="Configure performance settings like parallel processing, "
                    "memory limits, and cache sizes.",
                )
            )

        # Parallel processing
        if confirm_action(
            tr(
                "wizard.performance.parallel",
                default="Enable parallel processing?",
            ),
            default=self._get_nested_value("performance.parallel_processing.enabled", True),
        ):
            self._set_nested_value("performance.parallel_processing.enabled", True)

            # Worker count
            while True:
                workers = prompt_input(
                    tr(
                        "wizard.performance.workers",
                        default="Number of worker threads (1-16)",
                    ),
                    default=str(
                        self._get_nested_value("performance.parallel_processing.max_workers", 4)
                    ),
                )

                is_valid, error = validate_worker_count(workers)
                if not is_valid:
                    show_validation_error(error)
                    continue

                self._set_nested_value("performance.parallel_processing.max_workers", int(workers))
                break
        else:
            self._set_nested_value("performance.parallel_processing.enabled", False)

        # Memory limit
        while True:
            memory = prompt_input(
                tr(
                    "wizard.performance.memory",
                    default="Maximum cache size in MB (10-10000)",
                ),
                default=str(self._get_nested_value("performance.memory.max_cache_size_mb", 500)),
            )

            is_valid, error = validate_memory_size(memory)
            if not is_valid:
                show_validation_error(error)
                continue

            self._set_nested_value("performance.memory.max_cache_size_mb", int(memory))
            break

    def step_security(self) -> None:
        """Step 7: Security settings."""
        self.current_step = 7
        show_wizard_header(
            self.current_step,
            self.TOTAL_STEPS,
            tr("wizard.security.title", default="Security Settings"),
        )

        if self.profile_config.show_help:
            show_help_text(
                tr(
                    "wizard.security.help",
                    default="Configure security features like encryption.",
                )
            )

    def step_summary(self) -> dict[str, Any] | None:
        """Step 8: Summary and confirmation.

        Returns:
            Configuration dict if saved, None if restarting
        """
        self.current_step = 8
        show_wizard_header(
            self.current_step,
            self.TOTAL_STEPS,
            tr("wizard.summary.title", default="Configuration Summary"),
        )

        # Show configuration summary
        show_configuration_summary(self.config)

        # Confirm and save
        if not confirm_action(
            tr("wizard.summary.confirm", default="Save this configuration?"),
            default=True,
        ):
            if confirm_action(
                tr("wizard.summary.restart", default="Restart wizard?"),
                default=True,
            ):
                # Reset and restart
                self.config = {}
                self._apply_defaults()
                self.current_step = 0
                return self.run()
            else:
                raise WizardCancelled("Configuration not saved")

        # Mark setup as completed
        self._set_nested_value("setup.completed", True)
        self._set_nested_value("setup.profile", self.profile_config.name)
        self._set_nested_value("setup.wizard_version", "1.0")

        # Save configuration
        self._save_configuration()

        show_completion_banner()
        show_success_message(
            tr(
                "wizard.complete.message",
                default="Setup complete! Configuration saved to framekit.yaml",
            )
        )

    def _save_configuration(self) -> None:
        """Save configuration to framekit.yaml."""
        store = SettingsStore()
        store.save(self.config)
        config_path = store.path

        show_info_message(
            tr(
                "wizard.save.success",
                default=f"Configuration saved to: {config_path}",
                path=str(config_path),
            )
        )
