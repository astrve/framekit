"""Tests for TMDb models and data transformation."""

from __future__ import annotations

from framekit.core.models.metadata import (
    EpisodeMetadata,
    MetadataCandidate,
    MovieMetadata,
    SeasonMetadata,
)
from framekit.modules.metadata.providers.tmdb_models import (
    TMDbCastMember,
    TMDbCrewMember,
    TMDbEpisode,
    TMDbGenre,
    TMDbImage,
    TMDbMovie,
    TMDbProductionCompany,
    TMDbSearchResult,
    TMDbTVSeries,
)


class TestTMDbSearchResult:
    """Tests for TMDbSearchResult model."""

    def test_basic_search_result(self):
        """Test basic search result parsing."""
        result = TMDbSearchResult(
            tmdb_id=12345,
            title="Test Movie",
            year=2020,
            overview="Test overview",
            poster_path="/test_poster.jpg",
            media_type="movie",
        )

        assert result.tmdb_id == 12345
        assert result.title == "Test Movie"
        assert result.year == 2020
        assert result.overview == "Test overview"
        assert result.poster_path == "/test_poster.jpg"
        assert result.media_type == "movie"

    def test_search_result_optional_fields(self):
        """Test search result with optional fields missing."""
        result = TMDbSearchResult(
            tmdb_id=12345,
            title="Test Movie",
        )

        assert result.tmdb_id == 12345
        assert result.title == "Test Movie"
        assert result.year is None
        assert result.overview is None
        assert result.poster_path is None
        assert result.media_type == "movie"

    def test_to_metadata_candidate_movie(self):
        """Test conversion to MetadataCandidate for movie."""
        result = TMDbSearchResult(
            tmdb_id=12345,
            title="Test Movie",
            year=2020,
            overview="Test overview",
            poster_path="/test_poster.jpg",
            media_type="movie",
        )

        candidate = result.to_metadata_candidate(
            kind="movie",
            confidence=0.85,
            reasons=["exact title", "year match"],
        )

        assert isinstance(candidate, MetadataCandidate)
        assert candidate.provider_name == "tmdb"
        assert candidate.provider_id == "12345"
        assert candidate.kind == "movie"
        assert candidate.title == "Test Movie"
        assert candidate.year == "2020"
        assert candidate.overview == "Test overview"
        assert candidate.external_url == "https://www.themoviedb.org/movie/12345"
        assert candidate.confidence == 0.85
        assert candidate.reasons == ["exact title", "year match"]

    def test_to_metadata_candidate_tv(self):
        """Test conversion to MetadataCandidate for TV series."""
        result = TMDbSearchResult(
            tmdb_id=67890,
            title="Test Series",
            year=2021,
            overview="Series overview",
            media_type="tv",
        )

        candidate = result.to_metadata_candidate(
            kind="single_episode",
            confidence=0.75,
            reasons=["partial title"],
        )

        assert isinstance(candidate, MetadataCandidate)
        assert candidate.provider_name == "tmdb"
        assert candidate.provider_id == "67890"
        assert candidate.kind == "single_episode"
        assert candidate.title == "Test Series"
        assert candidate.external_url == "https://www.themoviedb.org/tv/67890"


class TestTMDbGenre:
    """Tests for TMDbGenre model."""

    def test_basic_genre(self):
        """Test basic genre parsing."""
        genre = TMDbGenre(id=28, name="Action")

        assert genre.id == 28
        assert genre.name == "Action"


class TestTMDbProductionCompany:
    """Tests for TMDbProductionCompany model."""

    def test_basic_company(self):
        """Test basic production company parsing."""
        company = TMDbProductionCompany(
            id=1,
            name="Test Studios",
            logo_path="/logo.png",
            origin_country="US",
        )

        assert company.id == 1
        assert company.name == "Test Studios"
        assert company.logo_path == "/logo.png"
        assert company.origin_country == "US"

    def test_company_optional_fields(self):
        """Test production company with optional fields missing."""
        company = TMDbProductionCompany(id=1, name="Test Studios")

        assert company.id == 1
        assert company.name == "Test Studios"
        assert company.logo_path is None
        assert company.origin_country is None


class TestTMDbCastMember:
    """Tests for TMDbCastMember model."""

    def test_basic_cast_member(self):
        """Test basic cast member parsing."""
        cast = TMDbCastMember(
            id=123,
            name="John Doe",
            character="Hero",
            order=0,
            profile_path="/profile.jpg",
        )

        assert cast.id == 123
        assert cast.name == "John Doe"
        assert cast.character == "Hero"
        assert cast.order == 0
        assert cast.profile_path == "/profile.jpg"


class TestTMDbCrewMember:
    """Tests for TMDbCrewMember model."""

    def test_basic_crew_member(self):
        """Test basic crew member parsing."""
        crew = TMDbCrewMember(
            id=456,
            name="Jane Smith",
            job="Director",
            department="Directing",
            profile_path="/director.jpg",
        )

        assert crew.id == 456
        assert crew.name == "Jane Smith"
        assert crew.job == "Director"
        assert crew.department == "Directing"
        assert crew.profile_path == "/director.jpg"


class TestTMDbMovie:
    """Tests for TMDbMovie model."""

    def test_basic_movie(self):
        """Test basic movie parsing."""
        movie = TMDbMovie(
            id=12345,
            title="Test Movie",
            original_title="Original Test Movie",
            overview="Test overview",
            release_date="2020-01-15",
            runtime=120,
            genres=[TMDbGenre(id=28, name="Action"), TMDbGenre(id=12, name="Adventure")],
            vote_average=7.5,
            vote_count=1000,
            poster_path="/poster.jpg",
            imdb_id="tt1234567",
        )

        assert movie.id == 12345
        assert movie.title == "Test Movie"
        assert movie.original_title == "Original Test Movie"
        assert movie.overview == "Test overview"
        assert movie.release_date == "2020-01-15"
        assert movie.runtime == 120
        assert len(movie.genres) == 2
        assert movie.genres[0].name == "Action"
        assert movie.vote_average == 7.5
        assert movie.imdb_id == "tt1234567"

    def test_movie_optional_fields(self):
        """Test movie with optional fields missing."""
        movie = TMDbMovie(id=12345, title="Test Movie")

        assert movie.id == 12345
        assert movie.title == "Test Movie"
        assert movie.original_title is None
        assert movie.overview is None
        assert movie.release_date is None
        assert movie.runtime is None
        assert movie.genres == []
        assert movie.vote_average is None
        assert movie.imdb_id is None

    def test_to_movie_metadata(self):
        """Test conversion to MovieMetadata."""
        movie = TMDbMovie(
            id=12345,
            title="Test Movie",
            original_title="Original Test Movie",
            overview="Test overview",
            release_date="2020-01-15",
            runtime=120,
            genres=[TMDbGenre(id=28, name="Action"), TMDbGenre(id=12, name="Adventure")],
            vote_average=7.5,
            poster_path="/poster.jpg",
            imdb_id="tt1234567",
            production_countries=[{"iso_3166_1": "US", "name": "United States"}],
            spoken_languages=[{"english_name": "English", "iso_639_1": "en"}],
        )

        cast = ["Actor One", "Actor Two"]
        crew = ["Director: John Doe", "Writer: Jane Smith"]

        metadata = movie.to_movie_metadata(cast=cast, crew=crew)

        assert isinstance(metadata, MovieMetadata)
        assert metadata.provider_name == "tmdb"
        assert metadata.provider_id == "12345"
        assert metadata.title == "Test Movie"
        assert metadata.year == "2020"
        assert metadata.overview == "Test overview"
        assert metadata.runtime_minutes == 120
        assert metadata.genres == ["Action", "Adventure"]
        assert metadata.vote_average == 7.5
        assert metadata.poster_url == "https://image.tmdb.org/t/p/w500/poster.jpg"
        assert metadata.imdb_id == "tt1234567"
        assert metadata.cast == cast
        assert metadata.crew == crew
        assert metadata.countries == ["US"]
        assert metadata.spoken_languages == ["English"]

    def test_extract_year_from_release_date(self):
        """Test year extraction from release_date."""
        movie = TMDbMovie(
            id=12345,
            title="Test Movie",
            release_date="2020-03-15",
        )

        metadata = movie.to_movie_metadata()
        assert metadata.year == "2020"

    def test_extract_year_none_when_no_date(self):
        """Test year is None when release_date is missing."""
        movie = TMDbMovie(id=12345, title="Test Movie")

        metadata = movie.to_movie_metadata()
        assert metadata.year is None


class TestTMDbTVSeries:
    """Tests for TMDbTVSeries model."""

    def test_basic_tv_series(self):
        """Test basic TV series parsing."""
        series = TMDbTVSeries(
            id=67890,
            name="Test Series",
            original_name="Original Test Series",
            overview="Series overview",
            first_air_date="2021-01-01",
            last_air_date="2023-12-31",
            genres=[TMDbGenre(id=18, name="Drama")],
            vote_average=8.2,
            poster_path="/series_poster.jpg",
            number_of_seasons=3,
            number_of_episodes=30,
            origin_country=["US", "GB"],
        )

        assert series.id == 67890
        assert series.name == "Test Series"
        assert series.original_name == "Original Test Series"
        assert series.overview == "Series overview"
        assert series.first_air_date == "2021-01-01"
        assert series.last_air_date == "2023-12-31"
        assert len(series.genres) == 1
        assert series.genres[0].name == "Drama"
        assert series.vote_average == 8.2
        assert series.number_of_seasons == 3
        assert series.origin_country == ["US", "GB"]

    def test_tv_series_optional_fields(self):
        """Test TV series with optional fields missing."""
        series = TMDbTVSeries(id=67890, name="Test Series")

        assert series.id == 67890
        assert series.name == "Test Series"
        assert series.original_name is None
        assert series.overview is None
        assert series.first_air_date is None
        assert series.genres == []
        assert series.origin_country == []

    def test_to_season_metadata(self):
        """Test conversion to SeasonMetadata."""
        series = TMDbTVSeries(
            id=67890,
            name="Test Series",
            original_name="Original Test Series",
            overview="Series overview",
            first_air_date="2021-01-01",
            genres=[TMDbGenre(id=18, name="Drama")],
            vote_average=8.2,
            poster_path="/series_poster.jpg",
            origin_country=["US"],
            spoken_languages=["en"],
        )

        cast = ["Actor One", "Actor Two"]
        crew = ["Creator: John Doe"]

        metadata = series.to_season_metadata(
            season_number=1,
            season_overview="Season 1 overview",
            season_air_date="2021-01-01",
            season_poster_path="/season1_poster.jpg",
            cast=cast,
            crew=crew,
        )

        assert isinstance(metadata, SeasonMetadata)
        assert metadata.provider_name == "tmdb"
        assert metadata.provider_id == "67890"
        assert metadata.series_title == "Test Series"
        assert metadata.season_number == 1
        assert metadata.overview == "Season 1 overview"
        assert metadata.series_year == "2021"
        assert metadata.genres == ["Drama"]
        assert metadata.vote_average == 8.2
        assert metadata.poster_url == "https://image.tmdb.org/t/p/w500/season1_poster.jpg"
        assert metadata.cast == cast
        assert metadata.crew == crew
        assert metadata.countries == ["US"]

    def test_season_metadata_fallback_to_series_poster(self):
        """Test season metadata falls back to series poster when season poster missing."""
        series = TMDbTVSeries(
            id=67890,
            name="Test Series",
            poster_path="/series_poster.jpg",
        )

        metadata = series.to_season_metadata(season_number=1)
        assert metadata.poster_url == "https://image.tmdb.org/t/p/w500/series_poster.jpg"


class TestTMDbEpisode:
    """Tests for TMDbEpisode model."""

    def test_basic_episode(self):
        """Test basic episode parsing."""
        episode = TMDbEpisode(
            id=11111,
            name="Test Episode",
            episode_number=5,
            season_number=1,
            overview="Episode overview",
            air_date="2021-02-01",
            runtime=45,
            vote_average=8.0,
            still_path="/still.jpg",
        )

        assert episode.id == 11111
        assert episode.name == "Test Episode"
        assert episode.episode_number == 5
        assert episode.season_number == 1
        assert episode.overview == "Episode overview"
        assert episode.air_date == "2021-02-01"
        assert episode.runtime == 45
        assert episode.vote_average == 8.0
        assert episode.still_path == "/still.jpg"

    def test_episode_optional_fields(self):
        """Test episode with optional fields missing."""
        episode = TMDbEpisode(
            id=11111,
            name="Test Episode",
            episode_number=5,
            season_number=1,
        )

        assert episode.id == 11111
        assert episode.name == "Test Episode"
        assert episode.overview is None
        assert episode.air_date is None
        assert episode.runtime is None

    def test_to_episode_metadata(self):
        """Test conversion to EpisodeMetadata."""
        episode = TMDbEpisode(
            id=11111,
            name="Test Episode",
            episode_number=5,
            season_number=1,
            overview="Episode overview",
            air_date="2021-02-01",
            runtime=45,
            vote_average=8.0,
            still_path="/still.jpg",
        )

        series = TMDbTVSeries(
            id=67890,
            name="Test Series",
            original_name="Original Test Series",
            first_air_date="2021-01-01",
            genres=[TMDbGenre(id=18, name="Drama")],
            vote_average=8.2,
            poster_path="/series_poster.jpg",
            origin_country=["US"],
            spoken_languages=["en"],
        )

        cast = ["Actor One"]
        crew = ["Director: Jane Doe"]

        metadata = episode.to_episode_metadata(
            series=series,
            imdb_id="tt9876543",
            cast=cast,
            crew=crew,
        )

        assert isinstance(metadata, EpisodeMetadata)
        assert metadata.provider_name == "tmdb"
        assert metadata.provider_id == "11111"
        assert metadata.series_title == "Test Series"
        assert metadata.series_year == "2021"
        assert metadata.season_number == 1
        assert metadata.episode_number == 5
        assert metadata.episode_title == "Test Episode"
        assert metadata.overview == "Episode overview"
        assert metadata.air_date == "2021-02-01"
        assert metadata.runtime_minutes == 45
        assert metadata.vote_average == 8.0
        assert metadata.still_url == "https://image.tmdb.org/t/p/w500/still.jpg"
        assert metadata.poster_url == "https://image.tmdb.org/t/p/w500/series_poster.jpg"
        assert metadata.imdb_id == "tt9876543"
        assert metadata.cast == cast
        assert metadata.crew == crew
        assert metadata.genres == ["Drama"]

    def test_episode_metadata_uses_series_vote_average_fallback(self):
        """Test episode metadata uses series vote_average when episode has none."""
        episode = TMDbEpisode(
            id=11111,
            name="Test Episode",
            episode_number=5,
            season_number=1,
        )

        series = TMDbTVSeries(
            id=67890,
            name="Test Series",
            first_air_date="2021-01-01",
            vote_average=8.5,
        )

        metadata = episode.to_episode_metadata(series=series)
        assert metadata.vote_average == 8.5


class TestTMDbImage:
    """Tests for TMDbImage model."""

    def test_basic_image(self):
        """Test basic image parsing."""
        image = TMDbImage(
            file_path="/poster.jpg",
            width=2000,
            height=3000,
            aspect_ratio=0.667,
            vote_average=7.5,
            vote_count=100,
            iso_639_1="en",
        )

        assert image.file_path == "/poster.jpg"
        assert image.width == 2000
        assert image.height == 3000
        assert image.aspect_ratio == 0.667
        assert image.vote_average == 7.5
        assert image.iso_639_1 == "en"

    def test_image_optional_fields(self):
        """Test image with optional fields missing."""
        image = TMDbImage(
            file_path="/poster.jpg",
            width=2000,
            height=3000,
            aspect_ratio=0.667,
        )

        assert image.file_path == "/poster.jpg"
        assert image.vote_average is None
        assert image.iso_639_1 is None

    def test_to_poster_dict(self):
        """Test conversion to poster dictionary."""
        image = TMDbImage(
            file_path="/poster.jpg",
            width=2000,
            height=3000,
            aspect_ratio=0.667,
            iso_639_1="en",
        )

        poster_dict = image.to_poster_dict(name="Poster (Default)")

        assert poster_dict["url"] == "https://image.tmdb.org/t/p/w500/poster.jpg"
        assert poster_dict["url_original"] == "https://image.tmdb.org/t/p/original/poster.jpg"
        assert poster_dict["size"] == "2000x3000"
        assert poster_dict["language"] == "en"
        assert poster_dict["name"] == "Poster (Default)"
        assert poster_dict["aspect_ratio"] == 0.667

    def test_to_poster_dict_default_language(self):
        """Test poster dict uses default language when iso_639_1 is None."""
        image = TMDbImage(
            file_path="/poster.jpg",
            width=2000,
            height=3000,
            aspect_ratio=0.667,
        )

        poster_dict = image.to_poster_dict(name="Test Poster")
        assert poster_dict["language"] == "en"
