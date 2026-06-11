import asyncio

import pytest

from app.schemas.content import UnifiedContent
from app.services import content_service as content_service_module
from app.services.content_service import ContentService


class _FakeRedis:
    def __init__(self):
        self.storage = {}
        self.set_calls = []

    async def get_cache(self, key: str):
        return self.storage.get(key)

    async def set_cache(self, key: str, value, expire: int = 0):
        self.storage[key] = value
        self.set_calls.append((key, expire))


def _make_item(ext_id: str, type_value: str, rating: float) -> UnifiedContent:
    return UnifiedContent(
        id=f"{type_value}_{ext_id}",
        external_id=ext_id,
        type=type_value,
        title=f"{type_value}-{ext_id}",
        subtitle=type_value.title(),
        image_url=f"https://img.test/{ext_id}.jpg",
        rating=rating,
    )


@pytest.mark.asyncio
async def test_get_unified_search_returns_cached_results(monkeypatch) -> None:
    service = ContentService()
    fake_redis = _FakeRedis()
    cached_item = _make_item("cached-1", "movie", 8.0).model_dump(by_alias=True)
    fake_redis.storage["search:movie:matrix"] = [cached_item]

    monkeypatch.setattr(content_service_module, "redis_client", fake_redis)
    payload = await service.get_unified_search("Matrix", "movie")

    assert len(payload) == 1
    assert payload[0].external_id == "cached-1"


@pytest.mark.asyncio
async def test_get_unified_search_builds_and_sorts_results(monkeypatch) -> None:
    service = ContentService()
    fake_redis = _FakeRedis()
    monkeypatch.setattr(content_service_module, "redis_client", fake_redis)

    async def fake_tmdb(query: str):
        return {"results": [{"id": 1}]}

    async def fake_books(query: str):
        return {"items": [{"id": "b1"}]}

    async def fake_spotify(query: str):
        return {"tracks": {"items": [{"id": "s1"}]}}

    monkeypatch.setattr(service.tmdb, "search_movies", fake_tmdb)
    monkeypatch.setattr(service.books, "search_books", fake_books)
    monkeypatch.setattr(service.spotify, "search_tracks", fake_spotify)
    monkeypatch.setattr(service.mapper, "map_tmdb", lambda raw: _make_item("m1", "movie", 7.2))
    monkeypatch.setattr(service.mapper, "map_google_books", lambda raw: _make_item("b1", "book", 9.1))
    monkeypatch.setattr(service.mapper, "map_spotify", lambda raw: _make_item("s1", "music", 6.8))
    monkeypatch.setattr(service.sanitizer, "is_valid", lambda item: True)

    payload = await service.get_unified_search("matrix", "all")
    assert len(payload) == 3
    assert [item.rating for item in payload] == [9.1, 7.2, 6.8]
    assert fake_redis.set_calls


@pytest.mark.asyncio
async def test_get_unified_search_ignores_task_errors(monkeypatch) -> None:
    service = ContentService()
    fake_redis = _FakeRedis()
    monkeypatch.setattr(content_service_module, "redis_client", fake_redis)

    async def failing_tmdb(query: str):
        raise RuntimeError("tmdb down")

    async def good_books(query: str):
        return {"items": [{"id": "b1"}]}

    async def empty_spotify(query: str):
        return {"tracks": {"items": []}}

    monkeypatch.setattr(service.tmdb, "search_movies", failing_tmdb)
    monkeypatch.setattr(service.books, "search_books", good_books)
    monkeypatch.setattr(service.spotify, "search_tracks", empty_spotify)
    monkeypatch.setattr(service.mapper, "map_google_books", lambda raw: _make_item("b1", "book", 8.0))
    monkeypatch.setattr(service.sanitizer, "is_valid", lambda item: True)

    payload = await service.get_unified_search("query", "all")
    assert len(payload) == 1
    assert payload[0].type == "book"


@pytest.mark.asyncio
async def test_get_home_data_returns_cached(monkeypatch) -> None:
    service = ContentService()
    fake_redis = _FakeRedis()
    fake_redis.storage["home_data_v4_all"] = {
        "Trending Now": [_make_item("m1", "movie", 7.0).model_dump(by_alias=True)],
    }
    monkeypatch.setattr(content_service_module, "redis_client", fake_redis)

    payload = await service.get_home_data("all")
    assert "Trending Now" in payload
    assert payload["Trending Now"][0].external_id == "m1"


@pytest.mark.asyncio
async def test_get_home_data_builds_filtered_sections(monkeypatch) -> None:
    service = ContentService()
    fake_redis = _FakeRedis()
    monkeypatch.setattr(content_service_module, "redis_client", fake_redis)

    async def movie_payload(*args, **kwargs):
        return {"results": [{"id": "m1"}]}

    async def music_payload(*args, **kwargs):
        return {"tracks": {"items": [{"id": "s1"}]}}

    async def book_payload(*args, **kwargs):
        return {"items": [{"id": "b1"}]}

    monkeypatch.setattr(service.tmdb, "get_popular_movies", movie_payload)
    monkeypatch.setattr(service.tmdb, "get_top_rated_movies", movie_payload)
    monkeypatch.setattr(service.tmdb, "search_movies", movie_payload)
    monkeypatch.setattr(service.spotify, "search_tracks", music_payload)
    monkeypatch.setattr(service.books, "search_books", book_payload)
    monkeypatch.setattr(service.mapper, "map_tmdb", lambda raw: _make_item("m1", "movie", 8.0))
    monkeypatch.setattr(service.mapper, "map_spotify", lambda raw: _make_item("s1", "music", 6.0))
    monkeypatch.setattr(service.mapper, "map_google_books", lambda raw: _make_item("b1", "book", 7.0))
    monkeypatch.setattr(service.sanitizer, "is_valid", lambda item: True)

    payload = await service.get_home_data("movie")
    assert payload
    assert all(item.type == "movie" for section in payload.values() for item in section)
    assert fake_redis.set_calls


@pytest.mark.asyncio
async def test_get_home_data_uses_music_fallback_when_spotify_empty(monkeypatch) -> None:
    service = ContentService()
    fake_redis = _FakeRedis()
    monkeypatch.setattr(content_service_module, "redis_client", fake_redis)

    async def empty_movies(*args, **kwargs):
        return {"results": []}

    async def empty_books(*args, **kwargs):
        return {"items": []}

    async def empty_music(*args, **kwargs):
        return {"tracks": {"items": []}}

    monkeypatch.setattr(service.tmdb, "get_popular_movies", empty_movies)
    monkeypatch.setattr(service.tmdb, "get_top_rated_movies", empty_movies)
    monkeypatch.setattr(service.tmdb, "search_movies", empty_movies)
    monkeypatch.setattr(service.books, "search_books", empty_books)
    monkeypatch.setattr(service.spotify, "search_tracks", empty_music)

    payload = await service.get_home_data("music")

    assert payload
    assert all(item.type == "music" for section in payload.values() for item in section)
    assert any(
        item.external_id.startswith("fallback-")
        for section in payload.values()
        for item in section
    )


@pytest.mark.asyncio
async def test_get_discovery_uses_dedup_and_cache(monkeypatch) -> None:
    service = ContentService()
    fake_redis = _FakeRedis()
    monkeypatch.setattr(content_service_module, "redis_client", fake_redis)

    async def tmdb_payload(*args, **kwargs):
        return {"results": [{"id": "m1"}]}

    async def books_payload(*args, **kwargs):
        return {"items": [{"id": "b1"}]}

    async def spotify_payload(*args, **kwargs):
        return {"tracks": {"items": [{"id": "s1"}]}}

    monkeypatch.setattr(service.tmdb, "search_movies", tmdb_payload)
    monkeypatch.setattr(service.books, "search_books", books_payload)
    monkeypatch.setattr(service.spotify, "search_tracks", spotify_payload)
    monkeypatch.setattr(service.mapper, "map_tmdb", lambda raw: _make_item("dup", "movie", 9.0))
    monkeypatch.setattr(service.mapper, "map_google_books", lambda raw: _make_item("dup", "movie", 8.0))
    monkeypatch.setattr(service.mapper, "map_spotify", lambda raw: _make_item("s1", "music", 7.0))
    monkeypatch.setattr(service.sanitizer, "is_valid", lambda item: True)

    payload = await service.get_discovery("cyberpunk")
    assert len(payload) <= 30
    assert fake_redis.set_calls


@pytest.mark.asyncio
async def test_get_recommendations_handles_critical_error(monkeypatch) -> None:
    service = ContentService()
    fake_redis = _FakeRedis()
    monkeypatch.setattr(content_service_module, "redis_client", fake_redis)

    async def failing_top_rated(*args, **kwargs):
        raise RuntimeError("fail")

    monkeypatch.setattr(service.tmdb, "get_top_rated_movies", failing_top_rated)
    payload = await service.get_recommendations("movie")
    assert payload == []


@pytest.mark.asyncio
async def test_get_preview_selects_official_movie_trailer(monkeypatch) -> None:
    service = ContentService()

    async def fake_videos(movie_id: int):
        assert movie_id == 550
        return {
            "results": [
                {
                    "site": "YouTube",
                    "type": "Teaser",
                    "key": "teaser-key",
                    "official": True,
                    "published_at": "2024-01-01",
                },
                {
                    "site": "YouTube",
                    "type": "Trailer",
                    "key": "trailer-key",
                    "name": "Official trailer",
                    "official": True,
                    "published_at": "2024-01-02",
                },
            ]
        }

    monkeypatch.setattr(service.tmdb, "get_movie_videos", fake_videos)

    preview = await service.get_preview("movie", "550", title="Fight Club")

    assert preview is not None
    assert preview.provider == "YouTube"
    assert preview.preview_type == "video"
    assert preview.url.endswith("trailer-key")
    assert preview.embed_url == "https://www.youtube.com/embed/trailer-key"


@pytest.mark.asyncio
async def test_get_preview_uses_spotify_audio_url(monkeypatch) -> None:
    service = ContentService()

    async def fake_track(track_id: str):
        assert track_id == "track-1"
        return {
            "name": "Song",
            "preview_url": "https://audio.test/preview.mp3",
            "artists": [{"name": "Artist"}],
            "external_urls": {"spotify": "https://open.spotify.com/track/track-1"},
        }

    monkeypatch.setattr(service.spotify, "get_track", fake_track)

    preview = await service.get_preview("music", "track-1", title="Song")

    assert preview is not None
    assert preview.provider == "Spotify"
    assert preview.preview_type == "audio"
    assert preview.url == "https://audio.test/preview.mp3"
    assert preview.external_url == "https://open.spotify.com/track/track-1"


@pytest.mark.asyncio
async def test_get_preview_uses_youtube_video_when_spotify_audio_missing(monkeypatch) -> None:
    service = ContentService()

    async def fake_track(track_id: str):
        assert track_id == "track-1"
        return {
            "name": "Song",
            "preview_url": None,
            "artists": [{"name": "Artist"}],
            "external_urls": {"spotify": "https://open.spotify.com/track/track-1"},
        }

    async def fake_youtube_lookup(query: str):
        assert query == "Artist Song"
        return "abc123DEF45"

    monkeypatch.setattr(service.spotify, "get_track", fake_track)
    monkeypatch.setattr(service, "_find_youtube_video_id", fake_youtube_lookup)

    preview = await service.get_preview("music", "track-1", title="Song")

    assert preview is not None
    assert preview.provider == "YouTube"
    assert preview.preview_type == "video"
    assert preview.url == "https://www.youtube.com/watch?v=abc123DEF45"
    assert preview.embed_url == "https://www.youtube.com/embed/abc123DEF45"
    assert preview.external_url == "https://open.spotify.com/track/track-1"
    assert preview.is_playable is True


@pytest.mark.asyncio
async def test_get_preview_uses_google_books_reader_url(monkeypatch) -> None:
    service = ContentService()

    async def fake_volume(volume_id: str):
        assert volume_id == "book-1"
        return {
            "volumeInfo": {
                "title": "Book",
                "previewLink": "https://books.google.com/book-preview",
                "infoLink": "https://books.google.com/book-info",
            },
            "accessInfo": {
                "webReaderLink": "https://books.google.com/book-reader",
            },
        }

    monkeypatch.setattr(service.books, "get_volume", fake_volume)

    preview = await service.get_preview("book", "book-1", title="Book")

    assert preview is not None
    assert preview.provider == "Google Books"
    assert preview.preview_type == "external"
    assert preview.url == "https://books.google.com/book-preview"
    assert preview.external_url == "https://books.google.com/book-info"


@pytest.mark.asyncio
async def test_get_recommendations_all_combines_sources(monkeypatch) -> None:
    service = ContentService()
    fake_redis = _FakeRedis()
    monkeypatch.setattr(content_service_module, "redis_client", fake_redis)

    async def movies(*args, **kwargs):
        return {"results": [{"id": "m1"}, {"id": "m2"}]}

    async def tracks(*args, **kwargs):
        return {"tracks": {"items": [{"id": "s1"}, {"id": "s2"}]}}

    async def books(*args, **kwargs):
        return {"items": [{"id": "b1"}, {"id": "b2"}]}

    monkeypatch.setattr(service.tmdb, "get_top_rated_movies", movies)
    monkeypatch.setattr(service.spotify, "search_tracks", tracks)
    monkeypatch.setattr(service.books, "search_books", books)
    monkeypatch.setattr(service.mapper, "map_tmdb", lambda raw: _make_item(str(raw["id"]), "movie", 8.0))
    monkeypatch.setattr(service.mapper, "map_spotify", lambda raw: _make_item(str(raw["id"]), "music", 7.0))
    monkeypatch.setattr(service.mapper, "map_google_books", lambda raw: _make_item(str(raw["id"]), "book", 6.0))
    monkeypatch.setattr(service.sanitizer, "is_valid", lambda item: True)

    payload = await service.get_recommendations("all")
    assert len(payload) >= 6
    assert fake_redis.set_calls


@pytest.mark.asyncio
async def test_get_recommendations_music_uses_fallback_when_spotify_empty(
    monkeypatch,
) -> None:
    service = ContentService()
    fake_redis = _FakeRedis()
    monkeypatch.setattr(content_service_module, "redis_client", fake_redis)

    async def empty_tracks(*args, **kwargs):
        return {"tracks": {"items": []}}

    monkeypatch.setattr(service.spotify, "search_tracks", empty_tracks)

    payload = await service.get_recommendations("music")

    assert payload
    assert all(item.type == "music" for item in payload)
    assert payload[0].external_id.startswith("fallback-")


@pytest.mark.asyncio
async def test_content_service_close_closes_all_clients(monkeypatch) -> None:
    service = ContentService()
    calls = {"tmdb": 0, "books": 0, "spotify": 0}

    async def close_tmdb():
        calls["tmdb"] += 1

    async def close_books():
        calls["books"] += 1

    async def close_spotify():
        calls["spotify"] += 1

    monkeypatch.setattr(service.tmdb, "close", close_tmdb)
    monkeypatch.setattr(service.books, "close", close_books)
    monkeypatch.setattr(service.spotify, "close", close_spotify)

    await service.close()
    assert calls == {"tmdb": 1, "books": 1, "spotify": 1}


@pytest.mark.asyncio
async def test_run_dedup_shares_inflight_task() -> None:
    service = ContentService()
    calls = {"factory": 0}
    gate = asyncio.Event()

    async def factory():
        calls["factory"] += 1
        await gate.wait()
        return [1, 2, 3]

    task1 = asyncio.create_task(
        service._run_dedup("k", service._inflight_search, factory),
    )
    task2 = asyncio.create_task(
        service._run_dedup("k", service._inflight_search, factory),
    )
    await asyncio.sleep(0)
    gate.set()

    result1, result2 = await asyncio.gather(task1, task2)
    assert result1 == [1, 2, 3]
    assert result2 == [1, 2, 3]
    assert calls["factory"] == 1
