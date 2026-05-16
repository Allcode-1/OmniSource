from types import SimpleNamespace
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth import dependencies as deps
from app.api.routers import actions as actions_router
from app.schemas.content import UnifiedContent


def _content(ext_id: str, title: str) -> UnifiedContent:
    return UnifiedContent(
        id=f"id-{ext_id}",
        external_id=ext_id,
        type="movie",
        title=title,
        subtitle="Movie",
        image_url="https://img.test/x.jpg",
        rating=7.0,
    )


def _build_app(current_user) -> FastAPI:
    app = FastAPI()
    app.include_router(actions_router.router)
    app.dependency_overrides[deps.get_current_user] = lambda: current_user
    return app


def _content_payload(ext_id: str = "e1", title: str = "Item 1") -> dict:
    return {
        "_id": f"id-{ext_id}",
        "ext_id": ext_id,
        "type": "movie",
        "title": title,
        "subtitle": "Movie",
        "image_url": "https://img.test/x.jpg",
        "rating": 7.0,
        "genres": ["action"],
    }


def test_create_playlist_requires_non_blank_title() -> None:
    current_user = SimpleNamespace(id="u1", ranking_variant="hybrid_ml")
    client = TestClient(_build_app(current_user))

    response = client.post("/actions/playlists?title=   ")
    assert response.status_code == 400
    assert response.json()["detail"] == "Playlist title is required"


def test_create_playlist_success(monkeypatch) -> None:
    current_user = SimpleNamespace(id="u1", ranking_variant="hybrid_ml")

    async def fake_create_playlist(user_id: str, title: str, description: str | None = None):
        assert user_id == "u1"
        assert title == "My List"
        assert description == "desc"
        return {"id": "p1", "title": title, "description": description}

    monkeypatch.setattr(actions_router.library_service, "create_playlist", fake_create_playlist)
    client = TestClient(_build_app(current_user))

    response = client.post("/actions/playlists?title=My%20List&description=desc")
    assert response.status_code == 200
    assert response.json()["id"] == "p1"


def test_get_favorites_delegates_to_service(monkeypatch) -> None:
    current_user = SimpleNamespace(id="u1", ranking_variant="hybrid_ml")

    async def fake_get_favorites(user_id: str, type: str | None = None):
        assert user_id == "u1"
        assert type == "movie"
        return [_content("e1", "Item 1")]

    monkeypatch.setattr(actions_router.library_service, "get_user_favorites", fake_get_favorites)
    client = TestClient(_build_app(current_user))

    response = client.get("/actions/favorites?type=movie")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["ext_id"] == "e1"


def test_get_my_playlists_delegates_to_service(monkeypatch) -> None:
    current_user = SimpleNamespace(id="u1", ranking_variant="hybrid_ml")

    async def fake_playlists(user_id: str):
        assert user_id == "u1"
        return [{"id": "p1", "title": "My list"}]

    monkeypatch.setattr(actions_router.library_service, "get_user_playlists", fake_playlists)
    client = TestClient(_build_app(current_user))

    response = client.get("/actions/playlists")
    assert response.status_code == 200
    assert response.json()[0]["id"] == "p1"


def test_delete_playlist_returns_404_when_service_reports_error(monkeypatch) -> None:
    current_user = SimpleNamespace(id="u1", ranking_variant="hybrid_ml")

    async def fake_delete_playlist(user_id: str, playlist_id: str):
        return {"status": "error", "message": "Playlist not found"}

    monkeypatch.setattr(actions_router.library_service, "delete_playlist", fake_delete_playlist)
    client = TestClient(_build_app(current_user))

    response = client.delete("/actions/playlists/missing")
    assert response.status_code == 404
    assert response.json()["detail"] == "Playlist not found"


def test_update_playlist_requires_payload() -> None:
    current_user = SimpleNamespace(id="u1", ranking_variant="hybrid_ml")
    client = TestClient(_build_app(current_user))

    response = client.patch("/actions/playlists/p1", json={})
    assert response.status_code == 400
    assert response.json()["detail"] == "Nothing to update"


def test_update_playlist_returns_404_when_service_fails(monkeypatch) -> None:
    current_user = SimpleNamespace(id="u1", ranking_variant="hybrid_ml")

    async def fake_update(*args, **kwargs):
        return {"status": "error", "message": "Playlist not found"}

    monkeypatch.setattr(actions_router.library_service, "update_playlist", fake_update)
    client = TestClient(_build_app(current_user))

    response = client.patch("/actions/playlists/p1", json={"title": "X"})
    assert response.status_code == 404
    assert response.json()["detail"] == "Playlist not found"


def test_track_event_delegates_to_analytics_service(monkeypatch) -> None:
    current_user = SimpleNamespace(id="u1", ranking_variant="content_only")
    captured = {}

    async def fake_track_event(user_id: str, payload, ranking_variant: str):
        captured["user_id"] = user_id
        captured["type"] = payload.type
        captured["ranking_variant"] = ranking_variant
        return {"status": "ok"}

    monkeypatch.setattr(actions_router.analytics_service, "track_event", fake_track_event)
    client = TestClient(_build_app(current_user))

    response = client.post(
        "/actions/event",
        json={"type": "view", "ext_id": "x1", "content_type": "movie"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert captured == {
        "user_id": "u1",
        "type": "view",
        "ranking_variant": "content_only",
    }


def test_toggle_like_tracks_analytics_when_item_added(monkeypatch) -> None:
    current_user = SimpleNamespace(id="u1", ranking_variant="hybrid_ml")
    captured = {}

    async def fake_toggle_like(user_id: str, content):
        assert user_id == "u1"
        return {"status": "added"}

    async def fake_track_event(user_id: str, payload, ranking_variant: str):
        captured["user_id"] = user_id
        captured["event_type"] = payload.type
        captured["ext_id"] = payload.ext_id
        captured["ranking_variant"] = ranking_variant
        return {"status": "ok"}

    monkeypatch.setattr(actions_router.library_service, "toggle_like", fake_toggle_like)
    monkeypatch.setattr(actions_router.analytics_service, "track_event", fake_track_event)
    client = TestClient(_build_app(current_user))

    response = client.post("/actions/like", json=_content_payload(ext_id="m1", title="Matrix"))
    assert response.status_code == 200
    assert response.json()["status"] == "added"
    assert captured == {
        "user_id": "u1",
        "event_type": "like",
        "ext_id": "m1",
        "ranking_variant": "hybrid_ml",
    }


def test_toggle_like_skips_analytics_when_not_added(monkeypatch) -> None:
    current_user = SimpleNamespace(id="u1", ranking_variant="hybrid_ml")

    async def fake_toggle_like(user_id: str, content):
        return {"status": "removed"}

    async def fail_track_event(*args, **kwargs):
        raise AssertionError("track_event should not run when like is not added")

    monkeypatch.setattr(actions_router.library_service, "toggle_like", fake_toggle_like)
    monkeypatch.setattr(actions_router.analytics_service, "track_event", fail_track_event)
    client = TestClient(_build_app(current_user))

    response = client.post("/actions/like", json=_content_payload(ext_id="m2"))
    assert response.status_code == 200
    assert response.json()["status"] == "removed"


def test_get_playlist_details_returns_404_when_missing(monkeypatch) -> None:
    current_user = SimpleNamespace(id="u1", ranking_variant="hybrid_ml")

    async def fake_details(user_id: str, playlist_id: str):
        return None

    monkeypatch.setattr(actions_router.library_service, "get_playlist_details", fake_details)
    client = TestClient(_build_app(current_user))

    response = client.get("/actions/playlists/missing")
    assert response.status_code == 404
    assert response.json()["detail"] == "Playlist not found"


def test_add_item_to_playlist_denies_access_for_foreign_playlist(monkeypatch) -> None:
    current_user = SimpleNamespace(id="u1", ranking_variant="hybrid_ml")

    class _FakePlaylistRepo:
        @staticmethod
        async def get(playlist_id: str):
            return SimpleNamespace(user_id="another-user")

    monkeypatch.setattr(actions_router, "Playlist", _FakePlaylistRepo)
    client = TestClient(_build_app(current_user))

    response = client.post(
        "/actions/playlists/p1/add",
        json=_content_payload(ext_id="m3"),
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Access denied"


def test_add_item_to_playlist_tracks_event_on_success(monkeypatch) -> None:
    current_user = SimpleNamespace(id="u1", ranking_variant="content_only")
    captured = {}

    class _FakePlaylistRepo:
        @staticmethod
        async def get(playlist_id: str):
            return SimpleNamespace(user_id="u1")

    async def fake_add_to_playlist(playlist_id: str, content):
        assert playlist_id == "p1"
        return {"status": "success"}

    async def fake_track_event(user_id: str, payload, ranking_variant: str):
        captured["user_id"] = user_id
        captured["event_type"] = payload.type
        captured["playlist_id"] = payload.meta["playlist_id"]
        captured["ranking_variant"] = ranking_variant
        return {"status": "ok"}

    monkeypatch.setattr(actions_router, "Playlist", _FakePlaylistRepo)
    monkeypatch.setattr(actions_router.library_service, "add_to_playlist", fake_add_to_playlist)
    monkeypatch.setattr(actions_router.analytics_service, "track_event", fake_track_event)
    client = TestClient(_build_app(current_user))

    response = client.post(
        "/actions/playlists/p1/add",
        json=_content_payload(ext_id="m4", title="Inception"),
    )
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    assert captured == {
        "user_id": "u1",
        "event_type": "playlist_add",
        "playlist_id": "p1",
        "ranking_variant": "content_only",
    }


def test_remove_item_from_playlist_returns_403_on_error(monkeypatch) -> None:
    current_user = SimpleNamespace(id="u1", ranking_variant="hybrid_ml")

    async def fake_remove(user_id: str, playlist_id: str, ext_id: str):
        return {"status": "error"}

    monkeypatch.setattr(actions_router.library_service, "remove_from_playlist", fake_remove)
    client = TestClient(_build_app(current_user))

    response = client.delete("/actions/playlists/p1/remove/m1")
    assert response.status_code == 403
    assert response.json()["detail"] == "Access denied"


def test_timeline_stats_notifications_delegate_to_analytics(monkeypatch) -> None:
    current_user = SimpleNamespace(id="u1", ranking_variant="hybrid_ml")

    async def fake_timeline(user_id: str, limit: int = 50):
        assert user_id == "u1"
        assert limit == 2
        return [
            {
                "id": "evt1",
                "type": "view",
                "ext_id": "m1",
                "content_type": "movie",
                "weight": 1.0,
                "title": "Matrix",
                "image_url": "https://img.test/matrix.jpg",
                "created_at": datetime.now(timezone.utc),
                "meta": {},
            }
        ]

    async def fake_stats(user_id: str, days: int = 30):
        assert user_id == "u1"
        assert days == 7
        return {
            "total_events": 10,
            "counts_by_type": {"view": 5},
            "ctr": 0.5,
            "save_rate": 0.2,
            "avg_dwell_seconds": 12.0,
            "top_content_types": {"movie": 7},
            "ab_metrics": {},
        }

    async def fake_notifications(current_user_obj):
        assert current_user_obj.id == "u1"
        return [
            {
                "id": "n1",
                "title": "Test",
                "body": "Body",
                "level": "info",
                "created_at": datetime.now(timezone.utc),
            }
        ]

    monkeypatch.setattr(actions_router.analytics_service, "get_timeline", fake_timeline)
    monkeypatch.setattr(actions_router.analytics_service, "get_stats", fake_stats)
    monkeypatch.setattr(actions_router.analytics_service, "get_notifications", fake_notifications)
    client = TestClient(_build_app(current_user))

    timeline_response = client.get("/actions/timeline?limit=2")
    stats_response = client.get("/actions/stats?days=7")
    notifications_response = client.get("/actions/notifications")

    assert timeline_response.status_code == 200
    assert timeline_response.json()[0]["id"] == "evt1"

    assert stats_response.status_code == 200
    assert stats_response.json()["total_events"] == 10

    assert notifications_response.status_code == 200
    assert notifications_response.json()["items"][0]["id"] == "n1"
