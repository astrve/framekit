"""Tests for TVDB models and data transformation."""

from __future__ import annotations

from framekit.core.models.metadata import EpisodeMetadata, MetadataCandidate, SeasonMetadata
from framekit.modules.metadata.providers.tvdb_models import (
    TVDBArtwork,
    TVDBEpisode,
    TVDBSearchResult,
    TVDBSeries,
)


class TestTVDBSearchResult:
    """Tests for TVDBSearchResult model."""

    def test_basic_search_result(self):
        """Test basic search result parsing."""
        result = TVDBSearchResult(
            tvdb_id="12345",
            name="Test Series",
            year=2020,
            overview="Test overview",
            image_url="https://example.com/image.jpg",
        )

        assert result.tvdb_id == "12345"
        assert result.name == "Test Series"
        assert result.year == 2020
        assert result.overview == "Test overview"
        assert result.image_url == "https://example.com/image.jpg"

    def test_search_result_optional_fields(self):
        """Test search result with optional fields missing."""
        result = TVDBSearchResult(
            tvdb_id="12345",
            name="Test Series",
        )

        assert result.tvdb_id == "12345"
        assert result.name == "Test Series"
        assert result.year is None
        assert result.overview is None
        assert result.image_url is None

    def test_to_metadata_candidate(self):
        """Test conversion to MetadataCandidate."""
        result = TVDBSearchResult(
            tvdb_id="12345",
            name="Test Series",
            year=2020,
            overview="Test overview",
            image_url="https://example.com/image.jpg",
        )

        candidate = result.to_metadata_candidate()

        assert isinstance(candidate, MetadataCandidate)
        assert candidate.provider_name == "tvdb"
        assert candidate.provider_id == "12345"
        assert candidate.title == "Test Series"
        assert candidate.year == "2020"
        assert candidate.overview == "Test overview"
        assert candidate.external_url == "https://thetvdb.com/dereferrer/series/12345"


class TestTVDBSeries:
    """Tests for TVDBSeries model."""

    def test_basic_series(self):
        """Test basic series parsing."""
        series = TVDBSeries(
            id=12345,
            name="Test Series",
            overview="Test overview",
            first_aired="2020-01-01",
            status="Continuing",
            genres=["Drama", "Action"],
            rating=8.5,
        )

        assert series.id == 12345
        assert series.name == "Test Series"
        assert series.overview == "Test overview"
        assert series.first_aired == "2020-01-01"
        assert series.status == "Continuing"
        assert series.genres == ["Drama", "Action"]
        assert series.rating == 8.5

    def test_series_optional_fields(self):
        """Test series with optional fields missing."""
        series = TVDBSeries(
            id=12345,
            name="Test Series",
        )

        assert series.id == 12345
        assert series.name == "Test Series"
        assert series.overview is None
        assert series.first_aired is None
        assert series.status is None
        assert series.genres == []
        assert series.rating is None

    def test_to_season_metadata(self):
        """Test conversion to SeasonMetadata."""
        series = TVDBSeries(
            id=12345,
            name="Test Series",
            overview="Test overview",
            first_aired="2020-01-01",
            status="Continuing",
            genres=["Drama", "Action"],
            rating=8.5,
        )

        metadata = series.to_season_metadata(season_number=1)

        assert isinstance(metadata, SeasonMetadata)
        assert metadata.provider_name == "tvdb"
        assert metadata.provider_id == "12345"
        assert metadata.series_title == "Test Series"
        assert metadata.season_number == 1
        assert metadata.overview == "Test overview"
        assert metadata.first_air_date == "2020-01-01"
        assert metadata.genres == ["Drama", "Action"]
        assert metadata.vote_average == 8.5

    def test_extract_year_from_first_aired(self):
        """Test year extraction from first_aired date."""
        series = TVDBSeries(
            id=12345,
            name="Test Series",
            first_aired="2020-03-15",
        )

        metadata = series.to_season_metadata(season_number=1)
        assert metadata.series_year == "2020"

    def test_extract_year_none_when_no_date(self):
        """Test year is None when first_aired is missing."""
        series = TVDBSeries(
            id=12345,
            name="Test Series",
        )

        metadata = series.to_season_metadata(season_number=1)
        assert metadata.series_year is None


class TestTVDBEpisode:
    """Tests for TVDBEpisode model."""

    def test_basic_episode(self):
        """Test basic episode parsing."""
        episode = TVDBEpisode(
            id=67890,
            name="Test Episode",
            season_number=1,
            episode_number=5,
            overview="Episode overview",
            aired="2020-02-01",
        )

        assert episode.id == 67890
        assert episode.name == "Test Episode"
        assert episode.season_number == 1
        assert episode.episode_number == 5
        assert episode.overview == "Episode overview"
        assert episode.aired == "2020-02-01"

    def test_episode_optional_fields(self):
        """Test episode with optional fields missing."""
        episode = TVDBEpisode(
            id=67890,
            name="Test Episode",
            season_number=1,
            episode_number=5,
        )

        assert episode.id == 67890
        assert episode.name == "Test Episode"
        assert episode.overview is None
        assert episode.aired is None

    def test_to_episode_metadata(self):
        """Test conversion to EpisodeMetadata."""
        episode = TVDBEpisode(
            id=67890,
            name="Test Episode",
            season_number=1,
            episode_number=5,
            overview="Episode overview",
            aired="2020-02-01",
        )

        series = TVDBSeries(
            id=12345,
            name="Test Series",
            first_aired="2020-01-01",
            genres=["Drama"],
        )

        metadata = episode.to_episode_metadata(series)

        assert isinstance(metadata, EpisodeMetadata)
        assert metadata.provider_name == "tvdb"
        assert metadata.provider_id == "67890"
        assert metadata.series_title == "Test Series"
        assert metadata.series_year == "2020"
        assert metadata.season_number == 1
        assert metadata.episode_number == 5
        assert metadata.episode_title == "Test Episode"
        assert metadata.overview == "Episode overview"
        assert metadata.air_date == "2020-02-01"
        assert metadata.genres == ["Drama"]


class TestTVDBArtwork:
    """Tests for TVDBArtwork model."""

    def test_basic_artwork(self):
        """Test basic artwork parsing."""
        artwork = TVDBArtwork(
            id=99999,
            image="https://example.com/artwork.jpg",
            thumbnail="https://example.com/thumb.jpg",
            type="poster",
        )

        assert artwork.id == 99999
        assert artwork.image == "https://example.com/artwork.jpg"
        assert artwork.thumbnail == "https://example.com/thumb.jpg"
        assert artwork.type == "poster"

    def test_artwork_optional_thumbnail(self):
        """Test artwork with optional thumbnail missing."""
        artwork = TVDBArtwork(
            id=99999,
            image="https://example.com/artwork.jpg",
            type="banner",
        )

        assert artwork.id == 99999
        assert artwork.image == "https://example.com/artwork.jpg"
        assert artwork.thumbnail is None
        assert artwork.type == "banner"
