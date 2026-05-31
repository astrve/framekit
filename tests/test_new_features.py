"""Tests for new features: validate, profiles, dry-run, cross-seed, diff, provider chain."""

from __future__ import annotations

from unittest.mock import MagicMock


class TestValidateModule:
    """Tests for the release validation module."""

    def test_validation_service_import(self):
        """Test ValidationService imports cleanly."""
        from swirrl.modules.validate.service import (
            ValidationRules,
            ValidationService,
        )

        assert ValidationService is not None
        assert ValidationRules is not None

    def test_builtin_rulesets_exist(self):
        """Test builtin rulesets are registered."""
        from swirrl.modules.validate.rules import BUILTIN_RULESETS

        assert "default" in BUILTIN_RULESETS
        assert "strict" in BUILTIN_RULESETS
        assert "anime" in BUILTIN_RULESETS

    def test_validate_command_registered(self):
        """Test validate command is registered in CLI."""
        from swirrl.commands.main import cli

        cmd = cli.get_command(None, "validate")
        assert cmd is not None

    def test_validation_empty_folder(self, tmp_path):
        """Test validation on empty folder produces error."""
        from swirrl.modules.validate.rules import BUILTIN_RULESETS
        from swirrl.modules.validate.service import ValidationService

        rules = BUILTIN_RULESETS["default"]
        service = ValidationService(rules=rules)
        result = service.validate(tmp_path)

        assert not result.is_valid


class TestProfileModule:
    """Tests for the config profiles module."""

    def test_profile_group_import(self):
        """Test profile_group imports cleanly."""
        from swirrl.commands.profile import profile_group

        assert profile_group is not None

    def test_profile_group_registered(self):
        """Test profile group is in CLI."""
        from swirrl.commands.main import cli

        cmd = cli.get_command(None, "profile")
        assert cmd is not None

    def test_profiles_service_import(self):
        """Test profiles service imports."""
        from swirrl.core.settings.profiles import (
            list_profiles,
            save_profile,
        )

        assert callable(list_profiles)
        assert callable(save_profile)


class TestPipelineDryRun:
    """Tests for pipeline --dry-run feature."""

    def test_pipeline_context_has_dry_run(self):
        """Test PipelineContext supports dry_run flag."""
        from swirrl.commands.pipeline import PipelineContext

        ctx = PipelineContext(dry_run=True)
        assert ctx.dry_run is True

        ctx2 = PipelineContext()
        assert ctx2.dry_run is False

    def test_dry_run_option_exists(self):
        """Test --dry-run is a registered pipeline option."""
        from swirrl.commands.pipeline import pipeline_command

        param_names = [p.name for p in pipeline_command.params]
        assert "dry_run" in param_names

    def test_encoder_step_dry_run_import(self):
        """Test encoder dry-run step exists."""
        from swirrl.commands.pipeline_steps import _encoder_step_dry_run

        assert callable(_encoder_step_dry_run)


class TestCrossSeedTorrent:
    """Tests for cross-seed torrent feature."""

    def test_bdecode_basic(self):
        """Test bdecoder handles basic types."""
        from swirrl.commands.torrent import _bdecode

        # Integer
        decoded = _bdecode(b"i42e")
        assert decoded == 42

        # String
        decoded = _bdecode(b"4:test")
        assert decoded == b"test"

        # List
        decoded = _bdecode(b"li1ei2ei3ee")
        assert decoded == [1, 2, 3]

        # Dict
        decoded = _bdecode(b"d3:fooi42ee")
        assert decoded == {b"foo": 42}

    def test_read_piece_length_from_torrent(self, tmp_path):
        """Test reading piece_length from a .torrent file."""
        from swirrl.commands.torrent import _read_piece_length_from_torrent
        from swirrl.modules.torrent.service import _bencode

        # Create a minimal .torrent file
        meta = {
            b"info": {
                b"piece length": 2097152,
                b"name": "test",
                b"length": 100,
                b"pieces": b"\x00" * 20,
            },
            b"announce": "http://tracker/announce",
        }
        torrent_file = tmp_path / "test.torrent"
        torrent_file.write_bytes(_bencode(meta))

        result = _read_piece_length_from_torrent(torrent_file)
        assert result == 2097152

    def test_read_piece_length_nonexistent(self, tmp_path):
        """Test reading from nonexistent file returns None."""
        from swirrl.commands.torrent import _read_piece_length_from_torrent

        result = _read_piece_length_from_torrent(tmp_path / "nope.torrent")
        assert result is None

    def test_cross_seed_option_exists(self):
        """Test --cross-seed is a registered torrent option."""
        from swirrl.commands.torrent import torrent_command

        param_names = [p.name for p in torrent_command.params]
        assert "cross_seed_torrent" in param_names


class TestMediainfoDiff:
    """Tests for cleanmkv --diff feature."""

    def test_diff_module_import(self):
        """Test diff module imports cleanly."""
        from swirrl.modules.cleanmkv.diff import build_diff_table, print_diff_for_plans

        assert callable(build_diff_table)
        assert callable(print_diff_for_plans)

    def test_diff_option_exists(self):
        """Test --diff is a registered cleanmkv option."""
        from swirrl.commands.cleanmkv import cleanmkv_command

        param_names = [p.name for p in cleanmkv_command.params]
        assert "show_diff" in param_names


class TestProviderChain:
    """Tests for metadata provider chain with content_type_hints."""

    def test_provider_chain_search_candidates(self):
        """Test ProviderChain.search_candidates returns full list."""
        from swirrl.core.models.metadata import MetadataCandidate, MetadataLookupRequest
        from swirrl.modules.metadata.chain import ProviderChain

        mock_provider = MagicMock()
        mock_provider.name = "test"
        mock_provider.search.return_value = [
            MetadataCandidate(
                provider_name="test",
                provider_id="1",
                kind="movie",
                title="Movie",
                year="2020",
                confidence=0.9,
                reasons=["match"],
            )
        ]

        chain = ProviderChain(providers=[mock_provider])
        request = MetadataLookupRequest(media_kind="movie", title="Movie", year="2020")
        results = chain.search_candidates(request)

        assert len(results) == 1
        assert results[0].title == "Movie"

    def test_provider_chain_fallback(self):
        """Test chain falls back to second provider on empty results."""
        from swirrl.core.models.metadata import MetadataCandidate, MetadataLookupRequest
        from swirrl.modules.metadata.chain import ProviderChain

        failing_provider = MagicMock()
        failing_provider.name = "first"
        failing_provider.search.return_value = []

        success_provider = MagicMock()
        success_provider.name = "second"
        success_provider.search.return_value = [
            MetadataCandidate(
                provider_name="second",
                provider_id="2",
                kind="movie",
                title="Found",
                year="2021",
                confidence=0.8,
                reasons=["fallback"],
            )
        ]

        chain = ProviderChain(providers=[failing_provider, success_provider])
        request = MetadataLookupRequest(media_kind="movie", title="Test", year=None)
        results = chain.search_candidates(request)

        assert len(results) == 1
        assert results[0].provider_name == "second"

    def test_build_provider_chain_for_content(self):
        """Test content-type-aware chain building."""
        from swirrl.modules.metadata.factory import build_provider_chain_for_content

        settings = {
            "metadata": {
                "provider": "tmdb",
                "tmdb_read_access_token": "test",
                "content_type_hints": {
                    "anime": ["anilist", "tmdb"],
                    "movie": ["tmdb"],
                },
                "anilist_enabled": True,
            }
        }

        # Anime hint should try anilist first
        chain = build_provider_chain_for_content(settings, content_type="anime")
        assert len(chain.providers) >= 1
        assert chain.providers[0].name == "anilist"

    def test_detect_content_type(self):
        """Test content type detection from release."""
        from swirrl.modules.metadata.workflow import _detect_content_type

        mock_release = MagicMock()
        mock_release.title = "Some Movie"
        mock_release.media_kind = "movie"
        mock_release.source = ""
        mock_release.release_group = ""
        assert _detect_content_type(mock_release) == "movie"

        mock_release.media_kind = "single_episode"
        mock_release.title = "Some Show"
        assert _detect_content_type(mock_release) == "tv"

        mock_release.title = "[SubsPlease] Anime Title"
        assert _detect_content_type(mock_release) == "anime"
