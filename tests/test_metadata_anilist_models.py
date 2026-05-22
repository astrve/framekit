"""Tests for AniList models and data transformation."""

from __future__ import annotations

from framekit.core.models.metadata import EpisodeMetadata, MetadataCandidate, SeasonMetadata
from framekit.modules.metadata.providers.anilist_models import (
    AniListCoverImage,
    AniListDate,
    AniListMedia,
    AniListTitle,
)


class TestAniListTitle:
    """Tests for AniListTitle model."""

    def test_basic_title(self):
        """Test basic title parsing."""
        title = AniListTitle(
            romaji="Test Anime",
            english="Test Anime English",
            native="テストアニメ",
        )

        assert title.romaji == "Test Anime"
        assert title.english == "Test Anime English"
        assert title.native == "テストアニメ"

    def test_title_optional_fields(self):
        """Test title with optional fields missing."""
        title = AniListTitle(
            romaji="Test Anime",
        )

        assert title.romaji == "Test Anime"
        assert title.english is None
        assert title.native is None

    def test_get_preferred_title_english(self):
        """Test getting preferred title (English)."""
        title = AniListTitle(
            romaji="Test Anime",
            english="Test Anime English",
            native="テストアニメ",
        )

        assert title.get_preferred("en") == "Test Anime English"

    def test_get_preferred_title_fallback_to_romaji(self):
        """Test fallback to romaji when English is missing."""
        title = AniListTitle(
            romaji="Test Anime",
            native="テストアニメ",
        )

        assert title.get_preferred("en") == "Test Anime"

    def test_get_preferred_title_fallback_to_native(self):
        """Test fallback to native when romaji is missing."""
        title = AniListTitle(
            native="テストアニメ",
        )

        assert title.get_preferred("en") == "テストアニメ"


class TestAniListCoverImage:
    """Tests for AniListCoverImage model."""

    def test_basic_cover_image(self):
        """Test basic cover image parsing."""
        cover = AniListCoverImage(
            large="https://example.com/large.jpg",
            medium="https://example.com/medium.jpg",
        )

        assert cover.large == "https://example.com/large.jpg"
        assert cover.medium == "https://example.com/medium.jpg"

    def test_cover_image_optional_fields(self):
        """Test cover image with optional fields missing."""
        cover = AniListCoverImage()

        assert cover.large is None
        assert cover.medium is None


class TestAniListDate:
    """Tests for AniListDate model."""

    def test_basic_date(self):
        """Test basic date parsing."""
        date = AniListDate(
            year=2020,
            month=3,
            day=15,
        )

        assert date.year == 2020
        assert date.month == 3
        assert date.day == 15

    def test_date_optional_fields(self):
        """Test date with optional fields missing."""
        date = AniListDate(
            year=2020,
        )

        assert date.year == 2020
        assert date.month is None
        assert date.day is None

    def test_to_iso_format_full_date(self):
        """Test conversion to ISO format with full date."""
        date = AniListDate(
            year=2020,
            month=3,
            day=15,
        )

        assert date.to_iso_format() == "2020-03-15"

    def test_to_iso_format_year_month(self):
        """Test conversion to ISO format with year and month."""
        date = AniListDate(
            year=2020,
            month=3,
        )

        assert date.to_iso_format() == "2020-03"

    def test_to_iso_format_year_only(self):
        """Test conversion to ISO format with year only."""
        date = AniListDate(
            year=2020,
        )

        assert date.to_iso_format() == "2020"

    def test_to_iso_format_none(self):
        """Test conversion to ISO format with no date."""
        date = AniListDate()

        assert date.to_iso_format() is None


class TestAniListMedia:
    """Tests for AniListMedia model."""

    def test_basic_media(self):
        """Test basic media parsing."""
        media = AniListMedia(
            id=12345,
            title=AniListTitle(
                romaji="Test Anime",
                english="Test Anime English",
            ),
            description="Test description",
            episodes=24,
            coverImage=AniListCoverImage(
                large="https://example.com/large.jpg",
            ),
            genres=["Action", "Drama"],
            averageScore=85,
            startDate=AniListDate(year=2020, month=3, day=15),
        )

        assert media.id == 12345
        assert media.title.romaji == "Test Anime"
        assert media.description == "Test description"
        assert media.episodes == 24
        assert media.genres == ["Action", "Drama"]
        assert media.averageScore == 85

    def test_media_optional_fields(self):
        """Test media with optional fields missing."""
        media = AniListMedia(
            id=12345,
            title=AniListTitle(romaji="Test Anime"),
        )

        assert media.id == 12345
        assert media.title.romaji == "Test Anime"
        assert media.description is None
        assert media.episodes is None
        assert media.coverImage is None
        assert media.genres == []
        assert media.averageScore is None
        assert media.startDate is None

    def test_to_metadata_candidate(self):
        """Test conversion to MetadataCandidate."""
        media = AniListMedia(
            id=12345,
            title=AniListTitle(
                romaji="Test Anime",
                english="Test Anime English",
            ),
            description="Test description",
            startDate=AniListDate(year=2020),
        )

        candidate = media.to_metadata_candidate()

        assert isinstance(candidate, MetadataCandidate)
        assert candidate.provider_name == "anilist"
        assert candidate.provider_id == "12345"
        assert candidate.title == "Test Anime English"
        assert candidate.year == "2020"
        assert candidate.overview == "Test description"
        assert candidate.external_url == "https://anilist.co/anime/12345"
        assert candidate.kind == "tv"

    def test_to_season_metadata(self):
        """Test conversion to SeasonMetadata."""
        media = AniListMedia(
            id=12345,
            title=AniListTitle(
                romaji="Test Anime",
                english="Test Anime English",
            ),
            description="Test description",
            episodes=24,
            genres=["Action", "Drama"],
            averageScore=85,
            startDate=AniListDate(year=2020, month=3, day=15),
            coverImage=AniListCoverImage(
                large="https://example.com/large.jpg",
            ),
        )

        metadata = media.to_season_metadata(season_number=1)

        assert isinstance(metadata, SeasonMetadata)
        assert metadata.provider_name == "anilist"
        assert metadata.provider_id == "12345"
        assert metadata.series_title == "Test Anime English"
        assert metadata.series_year == "2020"
        assert metadata.season_number == 1
        assert metadata.overview == "Test description"
        assert metadata.genres == ["Action", "Drama"]
        assert metadata.vote_average == 8.5  # Converted from 85 to 8.5
        assert metadata.first_air_date == "2020-03-15"
        assert metadata.poster_url == "https://example.com/large.jpg"

    def test_to_episode_metadata(self):
        """Test conversion to EpisodeMetadata."""
        media = AniListMedia(
            id=12345,
            title=AniListTitle(
                romaji="Test Anime",
                english="Test Anime English",
            ),
            description="Test description",
            genres=["Action", "Drama"],
            averageScore=85,
            startDate=AniListDate(year=2020, month=3, day=15),
            coverImage=AniListCoverImage(
                large="https://example.com/large.jpg",
            ),
        )

        metadata = media.to_episode_metadata(
            season_number=1,
            episode_number=5,
            episode_title="Test Episode",
        )

        assert isinstance(metadata, EpisodeMetadata)
        assert metadata.provider_name == "anilist"
        assert metadata.provider_id == "12345"
        assert metadata.series_title == "Test Anime English"
        assert metadata.series_year == "2020"
        assert metadata.season_number == 1
        assert metadata.episode_number == 5
        assert metadata.episode_title == "Test Episode"
        assert metadata.overview == "Test description"
        assert metadata.genres == ["Action", "Drama"]
        assert metadata.vote_average == 8.5
        assert metadata.first_air_date == "2020-03-15"
        assert metadata.poster_url == "https://example.com/large.jpg"

    def test_clean_description_html(self):
        """Test HTML cleaning in description."""
        media = AniListMedia(
            id=12345,
            title=AniListTitle(romaji="Test Anime"),
            description="<p>Test <b>description</b> with <i>HTML</i></p>",
        )

        candidate = media.to_metadata_candidate()
        # Should strip HTML tags
        assert candidate.overview is not None
        assert "<p>" not in candidate.overview
        assert "<b>" not in candidate.overview
        assert "Test description with HTML" in candidate.overview

    def test_score_conversion(self):
        """Test score conversion from 0-100 to 0-10."""
        media = AniListMedia(
            id=12345,
            title=AniListTitle(romaji="Test Anime"),
            averageScore=85,
        )

        metadata = media.to_season_metadata(season_number=1)
        assert metadata.vote_average == 8.5

    def test_score_conversion_none(self):
        """Test score conversion when score is None."""
        media = AniListMedia(
            id=12345,
            title=AniListTitle(romaji="Test Anime"),
        )

        metadata = media.to_season_metadata(season_number=1)
        assert metadata.vote_average is None
