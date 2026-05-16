from dataclasses import dataclass, field

from beanie.exceptions import RevisionIdWasChanged
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pymongo.errors import DuplicateKeyError

from app.auth import dependencies as deps
from app.api.routers import user as user_router


class _FakeField:
    def __init__(self, name: str) -> None:
        self.name = name

    def __eq__(self, other):
        return (self.name, other)


@dataclass
class _FakeUser:
    id: str = "u-1"
    username: str = "neo"
    email: str = "neo@test.dev"
    interests: list[str] = field(default_factory=lambda: ["action"])
    is_onboarding_completed: bool = False
    ranking_variant: str = "hybrid_ml"
    saved: bool = False
    deleted: bool = False

    async def save(self) -> None:
        self.saved = True

    async def delete(self) -> None:
        self.deleted = True


class _FakeDeleteQuery:
    def __init__(self) -> None:
        self.deleted = False

    async def delete(self) -> None:
        self.deleted = True


def _build_app(current_user: _FakeUser) -> FastAPI:
    app = FastAPI()
    app.include_router(user_router.router)
    app.dependency_overrides[deps.get_current_user] = lambda: current_user
    return app


def _patch_query_fields(monkeypatch) -> None:
    monkeypatch.setattr(user_router.Interaction, "user_id", _FakeField("user_id"), raising=False)
    monkeypatch.setattr(user_router.Playlist, "user_id", _FakeField("user_id"), raising=False)


def test_get_me_returns_current_user_payload() -> None:
    current = _FakeUser()
    client = TestClient(_build_app(current))

    response = client.get("/user/me")
    assert response.status_code == 200
    body = response.json()
    assert body["_id"] == "u-1"
    assert body["email"] == "neo@test.dev"
    assert body["username"] == "neo"


def test_update_user_persists_changes() -> None:
    current = _FakeUser()
    client = TestClient(_build_app(current))

    response = client.patch("/user/update", json={"username": "trinity"})
    assert response.status_code == 200
    assert current.username == "trinity"
    assert current.saved is True


def test_update_user_returns_409_on_duplicate_username() -> None:
    current = _FakeUser()

    async def duplicate_save() -> None:
        raise DuplicateKeyError("duplicate username")

    current.save = duplicate_save  # type: ignore[method-assign]
    client = TestClient(_build_app(current))

    response = client.patch("/user/update", json={"username": "olzhas"})
    assert response.status_code == 409
    assert response.json()["detail"] == "Username is already taken"


def test_update_user_returns_409_on_wrapped_duplicate_username() -> None:
    current = _FakeUser()

    async def wrapped_duplicate_save() -> None:
        error = RevisionIdWasChanged()
        error.__cause__ = DuplicateKeyError("duplicate username")
        raise error

    current.save = wrapped_duplicate_save  # type: ignore[method-assign]
    client = TestClient(_build_app(current))

    response = client.patch("/user/update", json={"username": "olzhas"})
    assert response.status_code == 409
    assert response.json()["detail"] == "Username is already taken"


def test_complete_onboarding_updates_flags_and_interests() -> None:
    current = _FakeUser(is_onboarding_completed=False)
    client = TestClient(_build_app(current))

    response = client.post(
        "/user/complete-onboarding",
        json={"interests": ["noir", "cyberpunk"]},
    )
    assert response.status_code == 200
    assert current.is_onboarding_completed is True
    assert current.interests == ["noir", "cyberpunk"]


def test_get_and_patch_ranking_variant() -> None:
    current = _FakeUser(ranking_variant="content_only")
    client = TestClient(_build_app(current))

    get_response = client.get("/user/ranking-variant")
    assert get_response.status_code == 200
    assert get_response.json()["ranking_variant"] == "content_only"

    patch_response = client.patch(
        "/user/ranking-variant",
        json={"ranking_variant": "hybrid_ml"},
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["ranking_variant"] == "hybrid_ml"
    assert current.ranking_variant == "hybrid_ml"


def test_update_ranking_variant_rejects_invalid_value() -> None:
    current = _FakeUser(ranking_variant="content_only")
    client = TestClient(_build_app(current))

    response = client.patch(
        "/user/ranking-variant",
        json={"ranking_variant": "bad_variant"},
    )
    assert response.status_code == 422


def test_get_available_tags_returns_master_tags() -> None:
    current = _FakeUser()
    client = TestClient(_build_app(current))

    response = client.get("/user/tags")
    assert response.status_code == 200
    tags = response.json()
    assert "cyberpunk" in tags
    assert "mind-bending" in tags


def test_delete_user_cascades_to_related_collections(monkeypatch) -> None:
    current = _FakeUser()
    interaction_query = _FakeDeleteQuery()
    playlist_query = _FakeDeleteQuery()
    _patch_query_fields(monkeypatch)

    monkeypatch.setattr(user_router.Interaction, "find", lambda *args, **kwargs: interaction_query)
    monkeypatch.setattr(user_router.Playlist, "find", lambda *args, **kwargs: playlist_query)

    client = TestClient(_build_app(current))
    response = client.delete("/user/me")

    assert response.status_code == 204
    assert interaction_query.deleted is True
    assert playlist_query.deleted is True
    assert current.deleted is True
