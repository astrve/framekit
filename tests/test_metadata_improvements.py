"""Tests for metadata improvements: poster naming, manual ID input, and cover selection."""

from unittest.mock import MagicMock, patch

import pytest

from ouro.modules.metadata.cover_selector import choose_cover
from ouro.modules.metadata.tmdb_provider import TMDbProvider
from ouro.modules.metadata.ui import prompt_manual_tmdb_id


class TestIntelligentPosterNaming:
    """Test intelligent poster naming logic."""

    def test_default_poster_name(self):
        """Test that the first poster is named 'Poster (Default)'."""
        provider = TMDbProvider(read_access_token="eyJ.test.token")

        poster = {
            "file_path": "/abc123.jpg",
            "aspect_ratio": 0.667,
        }

        name = provider._intelligent_poster_name(poster, 1, is_first=True)
        assert name == "Poster (Default)"

    def test_season_poster_name(self):
        """Test that season posters are detected and named correctly."""
        provider = TMDbProvider(read_access_token="eyJ.test.token")

        poster = {
            "file_path": "/season/2/poster.jpg",
            "aspect_ratio": 0.667,
        }

        name = provider._intelligent_poster_name(poster, 2, is_first=False)
        assert name == "Poster Season 2"

    def test_horizontal_poster_name(self):
        """Test that horizontal posters are detected."""
        provider = TMDbProvider(read_access_token="eyJ.test.token")

        poster = {
            "file_path": "/wide_poster.jpg",
            "aspect_ratio": 1.78,  # 16:9 aspect ratio
        }

        name = provider._intelligent_poster_name(poster, 2, is_first=False)
        assert name == "Poster Horizontal"

    def test_year_poster_name(self):
        """Test that year in file path is detected."""
        provider = TMDbProvider(read_access_token="eyJ.test.token")

        poster = {
            "file_path": "/posters/2023/poster.jpg",
            "aspect_ratio": 0.667,
        }

        name = provider._intelligent_poster_name(poster, 2, is_first=False)
        assert name == "Poster 2023"

    def test_fallback_numbered_poster(self):
        """Test fallback to numbered poster."""
        provider = TMDbProvider(read_access_token="eyJ.test.token")

        poster = {
            "file_path": "/random_poster.jpg",
            "aspect_ratio": 0.667,
        }

        name = provider._intelligent_poster_name(poster, 5, is_first=False)
        assert name == "Poster #5"


class TestManualTMDBIDInput:
    """Test manual TMDB ID input functionality."""

    @patch("ouro.modules.metadata.ui.console.input")
    def test_numeric_id_input(self, mock_input):
        """Test that numeric ID is accepted."""
        mock_input.return_value = "12345"

        result = prompt_manual_tmdb_id()
        assert result == "12345"

    @patch("ouro.modules.metadata.ui.console.input")
    def test_movie_url_extraction(self, mock_input):
        """Test that movie URL is parsed correctly."""
        mock_input.return_value = "https://www.themoviedb.org/movie/550"

        result = prompt_manual_tmdb_id()
        assert result == "550"

    @patch("ouro.modules.metadata.ui.console.input")
    def test_tv_url_extraction(self, mock_input):
        """Test that TV show URL is parsed correctly."""
        mock_input.return_value = "https://www.themoviedb.org/tv/1399"

        result = prompt_manual_tmdb_id()
        assert result == "1399"

    @patch("ouro.modules.metadata.ui.console.input")
    def test_cancel_input(self, mock_input):
        """Test that 'q' cancels input."""
        mock_input.return_value = "q"

        result = prompt_manual_tmdb_id()
        assert result is None

    @patch("ouro.modules.metadata.ui.console.input")
    @patch("ouro.modules.metadata.ui.print_warning")
    def test_invalid_input_retry(self, mock_warning, mock_input):
        """Test that invalid input shows warning and retries."""
        mock_input.side_effect = ["invalid", "12345"]

        result = prompt_manual_tmdb_id()
        assert result == "12345"
        assert mock_warning.called


class TestSearchByID:
    """Test TMDb search by ID functionality."""

    @patch.object(TMDbProvider, "_request_json")
    def test_search_by_id_movie(self, mock_request):
        """Test searching for a movie by ID."""
        mock_request.return_value = {
            "id": 550,
            "title": "Fight Club",
            "release_date": "1999-10-15",
            "overview": "A ticking-time-bomb insomniac...",
        }

        provider = TMDbProvider(read_access_token="eyJ.test.token")
        candidate = provider.search_by_id("550", "movie")

        assert candidate is not None
        assert candidate.provider_id == "550"
        assert candidate.title == "Fight Club"
        assert candidate.year == "1999"
        assert candidate.kind == "movie"
        assert "manual ID" in candidate.reasons

    @patch.object(TMDbProvider, "_request_json")
    def test_search_by_id_tv(self, mock_request):
        """Test searching for a TV show by ID."""
        mock_request.return_value = {
            "id": 1399,
            "name": "Game of Thrones",
            "first_air_date": "2011-04-17",
            "overview": "Seven noble families...",
        }

        provider = TMDbProvider(read_access_token="eyJ.test.token")
        candidate = provider.search_by_id("1399", "single_episode")

        assert candidate is not None
        assert candidate.provider_id == "1399"
        assert candidate.title == "Game of Thrones"
        assert candidate.year == "2011"
        assert candidate.kind == "single_episode"

    @patch.object(TMDbProvider, "_request_json")
    def test_search_by_id_not_found(self, mock_request):
        """Test handling of non-existent ID."""
        mock_request.side_effect = Exception("Not found")

        provider = TMDbProvider(read_access_token="eyJ.test.token")
        candidate = provider.search_by_id("999999", "movie")

        assert candidate is None


class TestCoverSelection:
    """Test cover selection functionality."""

    def test_choose_cover_with_intelligent_names(self):
        """Test that cover selector uses intelligent names."""
        posters = [
            {
                "url": "http://example.com/poster1.jpg",
                "url_original": "http://example.com/poster1_orig.jpg",
                "size": "500x750",
                "language": "en",
                "name": "Poster (Default)",
            },
            {
                "url": "http://example.com/poster2.jpg",
                "url_original": "http://example.com/poster2_orig.jpg",
                "size": "500x750",
                "language": "fr",
                "name": "Poster Season 2",
            },
        ]

        # Mock the selector to return the second poster
        with patch("ouro.modules.metadata.cover_selector.select_one") as mock_select:
            mock_select.return_value = posters[1]

            result = choose_cover(posters)

            assert result == posters[1]
            # Verify that select_one was called with on_open_current callback
            call_kwargs = mock_select.call_args[1]
            assert "on_open_current" in call_kwargs
            assert call_kwargs["on_open_current"] is not None

    def test_choose_cover_empty_list(self):
        """Test that empty poster list returns None."""
        result = choose_cover([])
        assert result is None

    @patch("webbrowser.open")
    @patch("ouro.modules.metadata.cover_selector.print_success")
    def test_open_poster_url(self, mock_print, mock_browser):
        """Test that opening poster URL works."""
        from ouro.modules.metadata.cover_selector import _open_poster_url

        poster = {
            "url": "http://example.com/poster.jpg",
            "url_original": "http://example.com/poster_orig.jpg",
        }

        _open_poster_url(poster)

        mock_browser.assert_called_once_with("http://example.com/poster_orig.jpg")
        assert mock_print.called


class TestCoverURLPropagation:
    """Test that cover URL is properly propagated to prez."""

    def test_metadata_context_includes_cover_url(self):
        """Test that build_metadata_context includes cover URLs."""
        from ouro.core.models.metadata import MovieMetadata
        from ouro.modules.metadata.render import build_metadata_context

        metadata = MovieMetadata(
            provider_name="tmdb",
            provider_id="550",
            imdb_id="tt0137523",
            external_url="https://www.themoviedb.org/movie/550",
            title="Fight Club",
            year="1999",
            overview="A ticking-time-bomb insomniac and a slippery soap salesman channel primal male aggression.",
        )

        selected_cover = {
            "url": "http://example.com/custom_poster.jpg",
            "url_original": "http://example.com/custom_poster_orig.jpg",
        }

        context = build_metadata_context(metadata, selected_cover=selected_cover)

        assert context["metadata_cover_url"] == "http://example.com/custom_poster.jpg"
        assert context["metadata_cover_url_original"] == "http://example.com/custom_poster_orig.jpg"

    def test_prez_uses_selected_cover_url(self):
        """Test that prez service prioritizes selected cover URL."""
        from ouro.core.models.nfo import ReleaseNfoData
        from ouro.modules.prez.service import _build_prez_data

        # Create minimal release data
        release = MagicMock(spec=ReleaseNfoData)
        release.media_kind = "movie"
        release.episodes = []
        release.total_duration_ms = 0
        release.total_size_bytes = 0

        metadata_context = {
            "metadata_movie": MagicMock(poster_url="http://default.com/poster.jpg"),
            "metadata_cover_url": "http://selected.com/poster.jpg",
        }

        prez_data = _build_prez_data(
            release,
            metadata_context=metadata_context,
            poster_url="http://fallback.com/poster.jpg",
        )

        # The selected cover URL should be used
        assert prez_data.poster_url == "http://selected.com/poster.jpg"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
