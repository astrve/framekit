from framekit.core.models.metadata import MetadataCandidate, MetadataLookupRequest
from framekit.modules.metadata.tmdb_provider import TMDbProvider


def test_tmdb_search_movie_candidates():
    provider = TMDbProvider(api_key="dummy", language="en-US")

    def fake_request_json(path, params=None):
        assert path == "/search/movie"
        return {
            "results": [
                {
                    "id": 100,
                    "title": "Moonlight",
                    "release_date": "2016-10-21",
                    "overview": "A film overview.",
                },
                {
                    "id": 101,
                    "title": "Moonlight Sonata",
                    "release_date": "2019-01-01",
                    "overview": "Another overview.",
                },
            ]
        }

    provider._request_json = fake_request_json  # type: ignore[attr-defined]

    request = MetadataLookupRequest(
        media_kind="movie",
        title="Moonlight",
        year="2016",
    )

    candidates = provider.search(request)

    assert len(candidates) == 2
    assert candidates[0].title == "Moonlight"
    assert candidates[0].confidence > candidates[1].confidence


def test_tmdb_fetch_episode():
    provider = TMDbProvider(api_key="dummy", language="en-US")

    def fake_request_json(path, params=None):
        if path == "/tv/200":
            return {
                "id": 200,
                "name": "The Simpsons",
                "first_air_date": "1989-12-17",
            }

        if path == "/tv/200/season/8/episode/4":
            return {
                "id": 204,
                "name": "Burns, Baby Burns",
                "overview": "Episode overview.",
                "air_date": "1996-11-17",
            }

        if path == "/tv/200/season/8/episode/4/external_ids":
            return {
                "imdb_id": "tt0701051",
            }

        raise AssertionError(f"Unexpected path: {path}")

    provider._request_json = fake_request_json  # type: ignore[attr-defined]

    candidate = MetadataCandidate(
        provider_name="tmdb",
        provider_id="200",
        kind="single_episode",
        title="The Simpsons",
        year="1989",
        season_number=8,
        episode_number=4,
    )

    result = provider.fetch_episode(candidate)

    assert result.series_title == "The Simpsons"
    assert result.series_year == "1989"
    assert result.episode_title == "Burns, Baby Burns"
    assert result.imdb_id == "tt0701051"


def test_tmdb_fetch_season():
    provider = TMDbProvider(api_key="dummy", language="en-US")

    def fake_request_json(path, params=None):
        if path == "/tv/300":
            return {
                "id": 300,
                "name": "The Simpsons",
                "first_air_date": "1989-12-17",
            }

        if path == "/tv/300/season/8":
            return {
                "id": 308,
                "overview": "Season overview.",
                "episodes": [
                    {
                        "id": 801,
                        "episode_number": 1,
                        "name": "Treehouse of Horror VII",
                        "overview": "Episode 1 overview.",
                        "air_date": "1996-10-27",
                    },
                    {
                        "id": 802,
                        "episode_number": 2,
                        "name": "You Only Move Twice",
                        "overview": "Episode 2 overview.",
                        "air_date": "1996-11-03",
                    },
                ],
            }

        if path == "/tv/300/season/8/external_ids":
            return {
                "imdb_id": "tt0096697",
            }

        raise AssertionError(f"Unexpected path: {path}")

    provider._request_json = fake_request_json  # type: ignore[attr-defined]

    candidate = MetadataCandidate(
        provider_name="tmdb",
        provider_id="300",
        kind="season_pack",
        title="The Simpsons",
        year="1989",
        season_number=8,
    )

    result = provider.fetch_season(candidate)

    assert result.series_title == "The Simpsons"
    assert result.season_number == 8
    assert result.imdb_id == "tt0096697"
    assert len(result.episode_summaries) == 2
    assert result.episode_summaries[0].episode_title == "Treehouse of Horror VII"
