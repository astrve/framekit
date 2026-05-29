"""Setup wizard implementation."""

from __future__ import annotations

from typing import Any

from ouro.core.i18n import tr
from ouro.core.settings import SettingsStore
from ouro.modules.setup.profiles import (
    get_profile,
    should_ask_question,
)
from ouro.modules.setup.selector import ChoiceOption, choose_option
from ouro.ui.unified_selector import SelectorOption, select_many
from ouro.modules.setup.ui import (
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
from ouro.modules.setup.validators import (
    test_tmdb_connection,
    validate_announce_url,
    validate_integer,
    validate_memory_size,
    validate_path,
    validate_tmdb_token,
    validate_worker_count,
)
from ouro.ui.console import console


class WizardCancelled(Exception):
    """Exception raised when wizard is cancelled."""


class SetupWizard:
    """Interactive setup wizard for Ouro configuration."""

    TOTAL_STEPS = 8

    def __init__(self, profile: str = "normal") -> None:
        """Initialize the wizard.

        Args:
            profile: Profile name (normal, advanced)
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
                default="This wizard will guide you through the initial setup of Ouro.\n"
                "You can choose a setup profile based on your experience level.",
            ),
            style="white",
        )
        console.print()

        show_profile_comparison()

        # Profile selection
        options = [
            ChoiceOption(
                value="normal",
                label=tr("wizard.profile.normal", default="Normal"),
                description=tr(
                    "wizard.profile.normal.desc",
                    default="Setup essentiel avec valeurs recommandees",
                ),
            ),
            ChoiceOption(
                value="advanced",
                label=tr("wizard.profile.advanced", default="Advanced"),
                description=tr(
                    "wizard.profile.advanced.desc",
                    default="Configuration complete de tous les modules",
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
                    default="Choose the interface language for Ouro. "
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

        private_flag = confirm_action(
            tr("wizard.torrent.private", default="Create private torrents by default?"),
            default=bool(self._get_nested_value("modules.torrent.private", True)),
        )
        self._set_nested_value("modules.torrent.private", private_flag)

        piece_options = [
            ChoiceOption("auto", tr("wizard.torrent.piece.auto", default="Auto"), "Auto"),
            ChoiceOption("512K", "512K", "512 KiB"),
            ChoiceOption("1M", "1M", "1 MiB"),
            ChoiceOption("2M", "2M", "2 MiB"),
            ChoiceOption("4M", "4M", "4 MiB"),
            ChoiceOption("8M", "8M", "8 MiB"),
            ChoiceOption("16M", "16M", "16 MiB"),
        ]
        piece_length = choose_option(
            title=tr("wizard.torrent.piece.select", default="Default torrent piece length"),
            options=piece_options,
            preferred_value=str(self._get_nested_value("modules.torrent.piece_length", "auto")),
        )
        if piece_length:
            self._set_nested_value("modules.torrent.piece_length", piece_length)

        prompt_save = confirm_action(
            tr(
                "wizard.torrent.prompt_save",
                default="Prompt before saving new announce URLs?",
            ),
            default=bool(self._get_nested_value("modules.torrent.prompt_save_announce", True)),
        )
        self._set_nested_value("modules.torrent.prompt_save_announce", prompt_save)

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

        # Renamer language profile
        renamer_profile_options = [
            ChoiceOption("fr_tracker", "fr_tracker", "French tracker naming"),
            ChoiceOption("en", "en", "English naming"),
            ChoiceOption("en_us", "en_us", "US English naming"),
            ChoiceOption("es", "es", "Spanish naming"),
            ChoiceOption("de", "de", "German naming"),
            ChoiceOption("it", "it", "Italian naming"),
            ChoiceOption("international", "international", "Neutral multi-language"),
            ChoiceOption("no_language", "no_language", "No language tag injection"),
        ]
        active_profile = choose_option(
            title=tr("wizard.presets.renamer.profile", default="Renamer language profile"),
            options=renamer_profile_options,
            preferred_value=self._get_nested_value(
                "modules.renamer.language_profiles.active",
                self._get_nested_value("modules.renamer.profile", "fr_tracker"),
            ),
        )
        if active_profile:
            self._set_nested_value("modules.renamer.profile", active_profile)
            self._set_nested_value("modules.renamer.language_profiles.active", active_profile)

        # Screenshot injection target
        screenshot_target_options = [
            ChoiceOption("prez", "prez", "Inject screenshots in prez"),
            ChoiceOption("nfo", "nfo", "Inject screenshots in NFO"),
            ChoiceOption("both", "both", "Inject screenshots in prez and NFO"),
            ChoiceOption("none", "none", "Disable screenshot injection"),
        ]
        screenshot_target = choose_option(
            title=tr("wizard.presets.screenshot.target", default="Screenshot injection target"),
            options=screenshot_target_options,
            preferred_value=self._get_nested_value("modules.screenshot.target", "prez"),
        )
        if screenshot_target:
            self._set_nested_value("modules.screenshot.target", screenshot_target)

        # Pipeline module selection
        module_catalog = [
            ("renamer", "Renamer", "Release name normalization"),
            ("cleanmkv", "CleanMKV", "Track filtering/remux"),
            ("metadata", "Metadata", "Fetch online metadata"),
            ("nfo", "NFO", "Generate NFO"),
            ("torrent", "Torrent", "Generate torrent"),
            ("prez", "Prez", "Generate prez (HTML/BBCode)"),
            ("encode", "Encode", "Re-encode media"),
            ("screenshot", "Screenshot", "Extract screenshots"),
            ("seedbox", "Seedbox", "Push to seedbox"),
            ("rename-parent", "Rename parent", "Rename source parent folder"),
            ("upload", "Upload", "Upload to trackers"),
        ]
        current_pipeline_modules = list(
            self._get_nested_value(
                "modules.pipeline.enabled_modules",
                ["renamer", "cleanmkv", "metadata", "nfo", "torrent", "prez"],
            )
        )
        selected_pipeline_modules = select_many(
            title=tr("wizard.presets.pipeline.modules", default="Pipeline enabled modules"),
            entries=[
                SelectorOption(
                    value=module_name,
                    label=module_label,
                    hint=module_hint,
                    selected=module_name in current_pipeline_modules,
                )
                for module_name, module_label, module_hint in module_catalog
            ],
            default=current_pipeline_modules,
            minimal_count=1,
        )
        if selected_pipeline_modules:
            deduped = list(dict.fromkeys(str(item) for item in selected_pipeline_modules))
            self._set_nested_value("modules.pipeline.enabled_modules", deduped)

        stop_on_error = confirm_action(
            tr("wizard.presets.pipeline.stop_on_error", default="Stop pipeline on first error?"),
            default=bool(self._get_nested_value("modules.pipeline.stop_on_error", True)),
        )
        self._set_nested_value("modules.pipeline.stop_on_error", stop_on_error)

        pipeline_with_metadata = confirm_action(
            tr(
                "wizard.presets.pipeline.with_metadata",
                default="Enable metadata step by default in pipeline?",
            ),
            default=bool(self._get_nested_value("modules.pipeline.with_metadata", True)),
        )
        self._set_nested_value("modules.pipeline.with_metadata", pipeline_with_metadata)

        # Upload defaults
        upload_enabled = confirm_action(
            tr("wizard.presets.upload.enabled", default="Enable upload module by default?"),
            default=bool(self._get_nested_value("upload.enabled", False)),
        )
        self._set_nested_value("upload.enabled", upload_enabled)

        upload_auto = confirm_action(
            tr(
                "wizard.presets.upload.auto",
                default="Enable automatic upload execution?",
            ),
            default=bool(self._get_nested_value("upload.auto_upload", False)),
        )
        self._set_nested_value("upload.auto_upload", upload_auto)

        while True:
            max_parallel_uploads = prompt_input(
                tr(
                    "wizard.presets.upload.max_parallel",
                    default="Maximum parallel tracker uploads (1-32)",
                ),
                default=str(self._get_nested_value("upload.max_parallel_uploads", 3)),
            )
            valid, error = validate_integer(max_parallel_uploads, min_value=1, max_value=32)
            if not valid:
                show_validation_error(error)
                continue
            self._set_nested_value("upload.max_parallel_uploads", int(max_parallel_uploads))
            break

        # Seedbox defaults
        seedbox_history = confirm_action(
            tr("wizard.presets.seedbox.history", default="Keep seedbox transfer history?"),
            default=bool(self._get_nested_value("seedbox.history_enabled", True)),
        )
        self._set_nested_value("seedbox.history_enabled", seedbox_history)

        while True:
            seedbox_max_uploads = prompt_input(
                tr(
                    "wizard.presets.seedbox.max_uploads",
                    default="Seedbox max concurrent uploads (1-32)",
                ),
                default=str(self._get_nested_value("seedbox.max_concurrent_uploads", 3)),
            )
            valid, error = validate_integer(seedbox_max_uploads, min_value=1, max_value=32)
            if not valid:
                show_validation_error(error)
                continue
            self._set_nested_value("seedbox.max_concurrent_uploads", int(seedbox_max_uploads))
            break

        self._configure_advanced_module_paths()
        self._configure_advanced_metadata_settings()
        self._configure_advanced_module_behavior()
        self._configure_advanced_renamer_profile()
        self._configure_advanced_upload_settings()
        self._configure_advanced_seedbox_settings()
        self._configure_advanced_encoder_settings()

    def _configure_advanced_module_paths(self) -> None:
        if self.profile_config.name != "advanced":
            return
        if not confirm_action(
            tr("wizard.advanced.paths.enable", default="Configure advanced module folders?"),
            default=True,
        ):
            return
        path_targets = (
            ("modules.torrent.default_folder", "Torrent default folder"),
            ("modules.prez.default_folder", "Prez default folder"),
            ("modules.screenshot.default_folder", "Screenshot default folder"),
            ("modules.pipeline.default_folder", "Pipeline default folder"),
            ("modules.encoder.default_folder", "Encoder default folder"),
        )
        for config_path, label in path_targets:
            current = str(self._get_nested_value(config_path, "") or "")
            value = prompt_input(f"{label} (empty = unchanged)", default=current).strip()
            if value:
                self._set_nested_value(config_path, value)

    def _configure_advanced_metadata_settings(self) -> None:
        if self.profile_config.name != "advanced":
            return
        if not confirm_action(
            tr("wizard.advanced.metadata.enable", default="Configure advanced metadata settings?"),
            default=True,
        ):
            return
        provider = choose_option(
            title=tr("wizard.advanced.metadata.provider", default="Metadata provider"),
            options=[
                ChoiceOption("tmdb", "tmdb", "The Movie Database"),
                ChoiceOption("tvdb", "tvdb", "The TV Database"),
                ChoiceOption("trakt", "trakt", "Trakt"),
                ChoiceOption("anilist", "anilist", "AniList"),
            ],
            preferred_value=str(self._get_nested_value("metadata.provider", "tmdb")),
        )
        if provider:
            self._set_nested_value("metadata.provider", provider)

        fallback_selected = select_many(
            title=tr("wizard.advanced.metadata.fallbacks", default="Fallback metadata providers"),
            entries=[
                SelectorOption("tmdb", "tmdb", selected=False),
                SelectorOption("tvdb", "tvdb", selected=False),
                SelectorOption("trakt", "trakt", selected=False),
                SelectorOption("anilist", "anilist", selected=False),
            ],
            default=list(self._get_nested_value("metadata.fallback_providers", [])),
            minimal_count=0,
        )
        self._set_nested_value(
            "metadata.fallback_providers",
            list(dict.fromkeys(str(item) for item in (fallback_selected or []))),
        )

        while True:
            ttl = prompt_input(
                tr("wizard.advanced.metadata.ttl", default="Metadata cache TTL (hours)"),
                default=str(self._get_nested_value("metadata.cache_ttl_hours", 168)),
            )
            valid, error = validate_integer(ttl, min_value=1, max_value=8760)
            if not valid:
                show_validation_error(error)
                continue
            self._set_nested_value("metadata.cache_ttl_hours", int(ttl))
            break

        language = prompt_input(
            tr("wizard.advanced.metadata.language", default="Metadata language code"),
            default=str(self._get_nested_value("metadata.language", "en-US")),
        ).strip()
        if language:
            self._set_nested_value("metadata.language", language)

        self._set_nested_value(
            "metadata.enabled_by_default",
            confirm_action(
                tr(
                    "wizard.advanced.metadata.enabled_by_default",
                    default="Enable metadata by default?",
                ),
                default=bool(self._get_nested_value("metadata.enabled_by_default", True)),
            ),
        )
        self._set_nested_value(
            "metadata.prompt_missing_token_in_pipeline",
            confirm_action(
                tr(
                    "wizard.advanced.metadata.prompt_missing_token",
                    default="Prompt when TMDb token is missing in pipeline?",
                ),
                default=bool(self._get_nested_value("metadata.prompt_missing_token_in_pipeline", True)),
            ),
        )

        tvdb_key = prompt_input(
            tr("wizard.advanced.metadata.tvdb_key", default="TVDB API key (optional)"),
            default=str(self._get_nested_value("metadata.tvdb_api_key", "")),
        ).strip()
        self._set_nested_value("metadata.tvdb_api_key", tvdb_key)
        tvdb_lang = prompt_input(
            tr("wizard.advanced.metadata.tvdb_language", default="TVDB language (e.g. eng)"),
            default=str(self._get_nested_value("metadata.tvdb_language", "eng")),
        ).strip()
        if tvdb_lang:
            self._set_nested_value("metadata.tvdb_language", tvdb_lang)

        self._set_nested_value(
            "metadata.anilist_enabled",
            confirm_action(
                tr("wizard.advanced.metadata.anilist_enabled", default="Enable AniList provider?"),
                default=bool(self._get_nested_value("metadata.anilist_enabled", True)),
            ),
        )
        anilist_lang = prompt_input(
            tr("wizard.advanced.metadata.anilist_language", default="AniList language"),
            default=str(self._get_nested_value("metadata.anilist_language", "en")),
        ).strip()
        if anilist_lang:
            self._set_nested_value("metadata.anilist_language", anilist_lang)

        trakt_client_id = prompt_input(
            tr("wizard.advanced.metadata.trakt_client_id", default="Trakt client id (optional)"),
            default=str(self._get_nested_value("metadata.trakt_client_id", "")),
        ).strip()
        self._set_nested_value("metadata.trakt_client_id", trakt_client_id)
        trakt_client_secret = prompt_input(
            tr(
                "wizard.advanced.metadata.trakt_client_secret",
                default="Trakt client secret (optional)",
            ),
            default=str(self._get_nested_value("metadata.trakt_client_secret", "")),
            password=True,
        ).strip()
        self._set_nested_value("metadata.trakt_client_secret", trakt_client_secret)
        trakt_access_token = prompt_input(
            tr(
                "wizard.advanced.metadata.trakt_access_token",
                default="Trakt access token (optional)",
            ),
            default=str(self._get_nested_value("metadata.trakt_access_token", "")),
            password=True,
        ).strip()
        self._set_nested_value("metadata.trakt_access_token", trakt_access_token)

        for kind in ("anime", "tv", "movie"):
            current_hints = self._get_nested_value(f"metadata.content_type_hints.{kind}", [])
            as_text = ",".join(str(item) for item in current_hints)
            raw = prompt_input(
                tr(
                    "wizard.advanced.metadata.content_type_hints",
                    default=f"Content-type providers for {kind} (csv, optional)",
                ),
                default=as_text,
            ).strip()
            if raw:
                hints = [item.strip() for item in raw.split(",") if item.strip()]
                self._set_nested_value(f"metadata.content_type_hints.{kind}", hints)

    def _configure_advanced_module_behavior(self) -> None:
        if self.profile_config.name != "advanced":
            return
        if not confirm_action(
            tr("wizard.advanced.modules.enable", default="Configure advanced module options?"),
            default=True,
        ):
            return

        self._set_nested_value(
            "modules.cleanmkv.copy_unchanged_files",
            confirm_action(
                tr(
                    "wizard.advanced.cleanmkv.copy_unchanged",
                    default="CleanMKV: copy unchanged files?",
                ),
                default=bool(self._get_nested_value("modules.cleanmkv.copy_unchanged_files", True)),
            ),
        )
        output_dir_name = prompt_input(
            tr(
                "wizard.advanced.cleanmkv.output_dir_name",
                default="CleanMKV output directory pattern",
            ),
            default=str(self._get_nested_value("modules.cleanmkv.output_dir_name", "Release/{release}")),
        ).strip()
        if output_dir_name:
            self._set_nested_value("modules.cleanmkv.output_dir_name", output_dir_name)

        nfo_locale = choose_option(
            title=tr("wizard.advanced.nfo.locale", default="NFO locale"),
            options=[
                ChoiceOption("auto", "auto", "Auto"),
                ChoiceOption("en", "en", "English"),
                ChoiceOption("fr", "fr", "French"),
                ChoiceOption("es", "es", "Spanish"),
            ],
            preferred_value=str(self._get_nested_value("modules.nfo.locale", "auto")),
        )
        if nfo_locale:
            self._set_nested_value("modules.nfo.locale", nfo_locale)
        nfo_mode = choose_option(
            title=tr("wizard.advanced.nfo.mode", default="NFO mode"),
            options=[
                ChoiceOption("global", "global", "One global NFO"),
                ChoiceOption("per_file", "per_file", "One NFO per file"),
                ChoiceOption("both", "both", "Global + per file"),
            ],
            preferred_value=str(self._get_nested_value("modules.nfo.mode", "global")),
        )
        if nfo_mode:
            self._set_nested_value("modules.nfo.mode", nfo_mode)
        self._set_nested_value(
            "modules.nfo.with_metadata",
            confirm_action(
                tr("wizard.advanced.nfo.with_metadata", default="NFO: use metadata context?"),
                default=bool(self._get_nested_value("modules.nfo.with_metadata", True)),
            ),
        )

        prez_locale = choose_option(
            title=tr("wizard.advanced.prez.locale", default="Prez locale"),
            options=[
                ChoiceOption("auto", "auto", "Auto"),
                ChoiceOption("en", "en", "English"),
                ChoiceOption("fr", "fr", "French"),
                ChoiceOption("es", "es", "Spanish"),
            ],
            preferred_value=str(self._get_nested_value("modules.prez.locale", "auto")),
        )
        if prez_locale:
            self._set_nested_value("modules.prez.locale", prez_locale)
        prez_preset = prompt_input(
            tr("wizard.advanced.prez.preset", default="Prez preset name"),
            default=str(self._get_nested_value("modules.prez.preset", "default")),
        ).strip()
        if prez_preset:
            self._set_nested_value("modules.prez.preset", prez_preset)
        prez_mediainfo_mode = choose_option(
            title=tr("wizard.advanced.prez.mediainfo_mode", default="Prez MediaInfo mode"),
            options=[
                ChoiceOption("none", "none", "Disabled"),
                ChoiceOption("summary", "summary", "Summary"),
                ChoiceOption("full", "full", "Full"),
            ],
            preferred_value=str(self._get_nested_value("modules.prez.mediainfo_mode", "none")),
        )
        if prez_mediainfo_mode:
            self._set_nested_value("modules.prez.mediainfo_mode", prez_mediainfo_mode)
        self._set_nested_value(
            "modules.prez.include_mediainfo",
            confirm_action(
                tr("wizard.advanced.prez.include_mediainfo", default="Prez: include MediaInfo block?"),
                default=bool(self._get_nested_value("modules.prez.include_mediainfo", False)),
            ),
        )
        self._set_nested_value(
            "modules.prez.with_metadata",
            confirm_action(
                tr("wizard.advanced.prez.with_metadata", default="Prez: use metadata context?"),
                default=bool(self._get_nested_value("modules.prez.with_metadata", True)),
            ),
        )

        screenshot_target = choose_option(
            title=tr("wizard.advanced.screenshot.target", default="Screenshot injection target"),
            options=[
                ChoiceOption("prez", "prez", "Inject in prez"),
                ChoiceOption("nfo", "nfo", "Inject in NFO"),
                ChoiceOption("both", "both", "Inject in both"),
                ChoiceOption("none", "none", "Disabled"),
            ],
            preferred_value=str(self._get_nested_value("modules.screenshot.target", "prez")),
        )
        if screenshot_target:
            self._set_nested_value("modules.screenshot.target", screenshot_target)

        self._set_nested_value(
            "modules.pipeline.auto_mode",
            confirm_action(
                tr("wizard.advanced.pipeline.auto_mode", default="Pipeline default auto mode?"),
                default=bool(self._get_nested_value("modules.pipeline.auto_mode", False)),
            ),
        )
        self._set_nested_value(
            "modules.pipeline.upload_on_failure",
            confirm_action(
                tr(
                    "wizard.advanced.pipeline.upload_on_failure",
                    default="Pipeline upload on failure?",
                ),
                default=bool(self._get_nested_value("modules.pipeline.upload_on_failure", False)),
            ),
        )
        while True:
            timeout = prompt_input(
                tr(
                    "wizard.advanced.pipeline.upload_timeout",
                    default="Pipeline upload timeout (seconds)",
                ),
                default=str(self._get_nested_value("modules.pipeline.upload_timeout", 300)),
            )
            valid, error = validate_integer(timeout, min_value=10, max_value=86400)
            if not valid:
                show_validation_error(error)
                continue
            self._set_nested_value("modules.pipeline.upload_timeout", int(timeout))
            break

    def _configure_advanced_renamer_profile(self) -> None:
        if self.profile_config.name != "advanced":
            return
        if not confirm_action(
            tr("wizard.advanced.renamer.enable", default="Configure advanced renamer language rules?"),
            default=True,
        ):
            return

        active_profile = choose_option(
            title=tr("wizard.advanced.renamer.active_profile", default="Active renamer profile"),
            options=[
                ChoiceOption("fr_tracker", "fr_tracker", "French tracker rules"),
                ChoiceOption("en", "en", "English rules"),
                ChoiceOption("en_us", "en_us", "US English rules"),
                ChoiceOption("es", "es", "Spanish rules"),
                ChoiceOption("de", "de", "German rules"),
                ChoiceOption("it", "it", "Italian rules"),
                ChoiceOption("international", "international", "Neutral rules"),
                ChoiceOption("no_language", "no_language", "No language injection"),
            ],
            preferred_value=str(self._get_nested_value("modules.renamer.language_profiles.active", "fr_tracker")),
        )
        if active_profile:
            self._set_nested_value("modules.renamer.profile", active_profile)
            self._set_nested_value("modules.renamer.language_profiles.active", active_profile)

        default_tag = prompt_input(
            tr("wizard.advanced.renamer.default_tag", default="Renamer default language tag"),
            default=str(self._get_nested_value("modules.renamer.default_language_tag", "MULTI.VFF")),
        ).strip()
        self._set_nested_value("modules.renamer.default_language_tag", default_tag.upper())

        if not confirm_action(
            tr(
                "wizard.advanced.renamer.custom_profile",
                default="Create or update a custom renamer profile?",
            ),
            default=False,
        ):
            return

        profile_name = prompt_input(
            tr("wizard.advanced.renamer.custom_name", default="Custom profile name"),
            default="custom_profile",
        ).strip()
        if not profile_name:
            return
        default_language = prompt_input(
            tr("wizard.advanced.renamer.default_language", default="Default language code"),
            default="fr",
        ).strip()
        variants_raw = prompt_input(
            tr(
                "wizard.advanced.renamer.variant_languages",
                default="Variant language codes (csv, optional)",
            ),
            default="",
        ).strip()
        variants = [item.strip().lower() for item in variants_raw.split(",") if item.strip()]

        tags = {
            "only_default": prompt_input(
                tr("wizard.advanced.renamer.tag.only_default", default="Tag: only default"),
                default="VFF",
            )
            .strip()
            .upper(),
            "default_plus_others": prompt_input(
                tr(
                    "wizard.advanced.renamer.tag.default_plus_others",
                    default="Tag: default + other languages",
                ),
                default="MULTI.VFF",
            )
            .strip()
            .upper(),
            "default_plus_variants_only": prompt_input(
                tr(
                    "wizard.advanced.renamer.tag.default_plus_variants_only",
                    default="Tag: default + variants only",
                ),
                default="VF2",
            )
            .strip()
            .upper(),
            "default_plus_variants_and_others": prompt_input(
                tr(
                    "wizard.advanced.renamer.tag.default_plus_variants_and_others",
                    default="Tag: default + variants + others",
                ),
                default="MULTI.VF2",
            )
            .strip()
            .upper(),
            "none_default_multi": prompt_input(
                tr(
                    "wizard.advanced.renamer.tag.none_default_multi",
                    default="Tag: no default language but multi",
                ),
                default="MULTI",
            )
            .strip()
            .upper(),
        }
        self._set_nested_value(
            f"modules.renamer.language_profiles.profiles.{profile_name}",
            {
                "default_language": default_language.lower() or "en",
                "variant_languages": variants,
                "tags": tags,
            },
        )
        if confirm_action(
            tr(
                "wizard.advanced.renamer.custom_set_active",
                default="Set this custom profile as active?",
            ),
            default=True,
        ):
            self._set_nested_value("modules.renamer.profile", profile_name)
            self._set_nested_value("modules.renamer.language_profiles.active", profile_name)

    def _configure_advanced_upload_settings(self) -> None:
        if self.profile_config.name != "advanced":
            return
        if not confirm_action(
            tr("wizard.advanced.upload.enable", default="Configure advanced upload settings?"),
            default=True,
        ):
            return

        self._set_nested_value(
            "upload.enabled",
            confirm_action(
                tr("wizard.advanced.upload.enabled", default="Enable upload module?"),
                default=bool(self._get_nested_value("upload.enabled", False)),
            ),
        )
        self._set_nested_value(
            "upload.auto_upload",
            confirm_action(
                tr("wizard.advanced.upload.auto", default="Enable auto upload?"),
                default=bool(self._get_nested_value("upload.auto_upload", False)),
            ),
        )
        while True:
            max_parallel = prompt_input(
                tr(
                    "wizard.advanced.upload.max_parallel",
                    default="Max parallel uploads (1-32)",
                ),
                default=str(self._get_nested_value("upload.max_parallel_uploads", 3)),
            )
            valid, error = validate_integer(max_parallel, min_value=1, max_value=32)
            if not valid:
                show_validation_error(error)
                continue
            self._set_nested_value("upload.max_parallel_uploads", int(max_parallel))
            break

        image_host = choose_option(
            title=tr("wizard.advanced.upload.image_host", default="Image host"),
            options=[
                ChoiceOption("", "None", "Disabled"),
                ChoiceOption("imgbb", "imgbb", "imgbb.com"),
                ChoiceOption("imgbox", "imgbox", "imgbox.com"),
                ChoiceOption("ptpimg", "ptpimg", "ptpimg.me"),
                ChoiceOption("freeimage", "freeimage", "freeimage.host"),
            ],
            preferred_value=str(self._get_nested_value("upload.image_host", "")),
        )
        if image_host is not None:
            self._set_nested_value("upload.image_host", image_host)
        if image_host:
            key = prompt_input(
                tr("wizard.advanced.upload.image_host_key", default="Image host API key"),
                default=str(self._get_nested_value("upload.image_host_api_key", "")),
                password=True,
            ).strip()
            self._set_nested_value("upload.image_host_api_key", key)

        torrent_client = choose_option(
            title=tr("wizard.advanced.upload.torrent_client", default="Torrent client integration"),
            options=[
                ChoiceOption("", "None", "Disabled"),
                ChoiceOption("qbittorrent", "qbittorrent", "qBittorrent Web API"),
            ],
            preferred_value=str(self._get_nested_value("upload.torrent_client", "")),
        )
        if torrent_client is not None:
            self._set_nested_value("upload.torrent_client", torrent_client)
        if torrent_client == "qbittorrent":
            self._set_nested_value(
                "upload.torrent_client_host",
                prompt_input(
                    "Torrent client host",
                    default=str(self._get_nested_value("upload.torrent_client_host", "localhost")),
                ).strip(),
            )
            while True:
                port = prompt_input(
                    "Torrent client port",
                    default=str(self._get_nested_value("upload.torrent_client_port", 8080)),
                )
                valid, error = validate_integer(port, min_value=1, max_value=65535)
                if not valid:
                    show_validation_error(error)
                    continue
                self._set_nested_value("upload.torrent_client_port", int(port))
                break
            self._set_nested_value(
                "upload.torrent_client_username",
                prompt_input(
                    "Torrent client username",
                    default=str(self._get_nested_value("upload.torrent_client_username", "")),
                ).strip(),
            )
            self._set_nested_value(
                "upload.torrent_client_password",
                prompt_input(
                    "Torrent client password",
                    default=str(self._get_nested_value("upload.torrent_client_password", "")),
                    password=True,
                ).strip(),
            )
            self._set_nested_value(
                "upload.torrent_client_category",
                prompt_input(
                    "Torrent client category",
                    default=str(self._get_nested_value("upload.torrent_client_category", "ouro")),
                ).strip()
                or "ouro",
            )

    def _configure_advanced_seedbox_settings(self) -> None:
        if self.profile_config.name != "advanced":
            return
        if not confirm_action(
            tr("wizard.advanced.seedbox.enable", default="Configure advanced seedbox settings?"),
            default=True,
        ):
            return
        self._set_nested_value(
            "seedbox.default",
            prompt_input(
                tr("wizard.advanced.seedbox.default", default="Default seedbox name (optional)"),
                default=str(self._get_nested_value("seedbox.default", "")),
            ).strip(),
        )
        mapping_raw = prompt_input(
            tr(
                "wizard.advanced.seedbox.by_profile",
                default="Default seedbox by profile (csv profile=seedbox, optional)",
            ),
            default="",
        ).strip()
        if mapping_raw:
            mapping: dict[str, str] = {}
            for entry in mapping_raw.split(","):
                if "=" not in entry:
                    continue
                key, value = entry.split("=", 1)
                key = key.strip()
                value = value.strip()
                if key and value:
                    mapping[key] = value
            if mapping:
                self._set_nested_value("seedbox.default_by_profile", mapping)

    def _configure_advanced_encoder_settings(self) -> None:
        if self.profile_config.name != "advanced":
            return
        if not confirm_action(
            tr("wizard.advanced.encoder.enable", default="Configure encoder module defaults?"),
            default=True,
        ):
            return
        self._set_nested_value(
            "modules.encoder.output_dir_name",
            prompt_input(
                tr("wizard.advanced.encoder.output_dir_name", default="Encoder output directory name"),
                default=str(self._get_nested_value("modules.encoder.output_dir_name", "encoded")),
            ).strip()
            or "encoded",
        )
        self._set_nested_value(
            "modules.encoder.preset",
            prompt_input(
                tr("wizard.advanced.encoder.preset", default="Encoder preset name"),
                default=str(self._get_nested_value("modules.encoder.preset", "")),
            ).strip(),
        )
        self._set_nested_value(
            "modules.encoder.ffmpeg_path",
            prompt_input(
                tr("wizard.advanced.encoder.ffmpeg_path", default="FFmpeg executable path"),
                default=str(self._get_nested_value("modules.encoder.ffmpeg_path", "ffmpeg")),
            ).strip()
            or "ffmpeg",
        )
        self._set_nested_value(
            "modules.encoder.ffprobe_path",
            prompt_input(
                tr("wizard.advanced.encoder.ffprobe_path", default="FFprobe executable path"),
                default=str(self._get_nested_value("modules.encoder.ffprobe_path", "ffprobe")),
            ).strip()
            or "ffprobe",
        )

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

        batch_parallel = confirm_action(
            tr(
                "wizard.performance.batch_parallel",
                default="Enable parallel batch release processing?",
            ),
            default=bool(self._get_nested_value("performance.batch.parallel_releases", True)),
        )
        self._set_nested_value("performance.batch.parallel_releases", batch_parallel)

        while True:
            batch_workers = prompt_input(
                tr(
                    "wizard.performance.batch_workers",
                    default="Maximum concurrent batch releases (1-16)",
                ),
                default=str(self._get_nested_value("performance.batch.max_concurrent", 2)),
            )
            is_valid, error = validate_integer(batch_workers, min_value=1, max_value=16)
            if not is_valid:
                show_validation_error(error)
                continue
            self._set_nested_value("performance.batch.max_concurrent", int(batch_workers))
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
                    default=(
                        "Protect sensitive values (TMDb token, announce URLs) with encrypted storage.\n"
                        "You can choose OS keyring or an encrypted local vault file."
                    ),
                )
            )

        security_enabled = confirm_action(
            tr("wizard.security.enabled", default="Enable encrypted secret storage?"),
            default=bool(self._get_nested_value("security.enabled", True)),
        )
        show_info_message("Security: Enable -> Backend -> Vault path -> Migration/Backup")
        self._set_nested_value("security.enabled", security_enabled)
        if not security_enabled:
            show_info_message(
                tr(
                    "wizard.security.disabled_notice",
                    default="Secrets will be stored in plaintext until security is re-enabled.",
                )
            )
            return

        storage_choice = choose_option(
            title=tr("wizard.security.storage", default="Secret storage backend"),
            options=[
                ChoiceOption(
                    "keyring",
                    tr("wizard.security.storage.keyring", default="System keyring"),
                    tr(
                        "wizard.security.storage.keyring_hint",
                        default="Recommended. Uses the OS secure credential store.",
                    ),
                ),
                ChoiceOption(
                    "file",
                    tr("wizard.security.storage.file", default="Encrypted vault file"),
                    tr(
                        "wizard.security.storage.file_hint",
                        default="Portable but requires managing a vault file path.",
                    ),
                ),
            ],
            preferred_value=str(self._get_nested_value("security.key_storage", "keyring")),
        )
        if storage_choice:
            self._set_nested_value("security.key_storage", storage_choice)

        if storage_choice == "file":
            while True:
                vault_path = prompt_input(
                    tr("wizard.security.vault_path", default="Vault file path"),
                    default=str(self._get_nested_value("security.vault_path", "")),
                ).strip()
                if not vault_path:
                    show_validation_error("Vault path is required in file mode.")
                    continue
                is_valid, error = validate_path(vault_path, must_exist=False, must_be_writable=True)
                if not is_valid:
                    show_validation_error(error)
                    continue
                self._set_nested_value("security.vault_path", vault_path)
                break
        else:
            self._set_nested_value("security.vault_path", "")

        auto_migrate = confirm_action(
            tr(
                "wizard.security.auto_migrate",
                default="Migrate existing plaintext secrets automatically?",
            ),
            default=bool(self._get_nested_value("security.auto_migrate", True)),
        )
        self._set_nested_value("security.auto_migrate", auto_migrate)

        backup_before_changes = confirm_action(
            tr(
                "wizard.security.backup_before_changes",
                default="Backup encrypted secrets before updates?",
            ),
            default=bool(self._get_nested_value("security.backup_before_changes", True)),
        )
        self._set_nested_value("security.backup_before_changes", backup_before_changes)

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
                default="Setup complete! Configuration saved to ouro.yaml",
            )
        )

    def _save_configuration(self) -> None:
        """Save configuration to ouro.yaml."""
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
