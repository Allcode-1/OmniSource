from datetime import datetime, timedelta, timezone

import pytest

from app.schemas.content import UnifiedContent
from app.services import library_service as library_module
from app.services.library_service import LibraryService


class _FakeField:
    def __init__(self, name: str) -> None:
        self.name = name

    def __eq__(self, other):
        return ("eq", self.name, other)


class _FakeRedis:
    def __init__(self) -> None:
        self.storage = {}
        self.deleted_prefixes = []
        self.deleted_keys = []
        self.set_calls = []

    async def get_cache(self, key: str):
        return self.storage.get(key)

    async def set_cache(self, key: str, value, expire: int = 0):
        self.storage[key] = value
        self.set_calls.append((key, expire))

    async def delete_cache(self, key: str):
        self.deleted_keys.append(key)
        self.storage.pop(key, None)

    async def delete_by_prefix(self, prefix: str, limit: int = 500):
        self.deleted_prefixes.append(prefix)
        keys = [key for key in self.storage if key.startswith(prefix)]
        for key in keys:
            self.storage.pop(key, None)
        return len(keys)


class _FakeMetaDoc:
    def __init__(
        self,
        *,
        ext_id: str,
        type: str,
        title: str,
        subtitle: str | None = None,
        description: str | None = None,
        image_url: str | None = None,
        rating: float = 0.0,
        release_date: str | None = None,
        genres=None,
        features_vector=None,
        vector_dim: int | None = None,
        vector_model: str | None = None,
    ) -> None:
        self.ext_id = ext_id
        self.type = type
        self.title = title
        self.subtitle = subtitle
        self.description = description
        self.image_url = image_url
        self.rating = rating
        self.release_date = release_date
        self.genres = genres or []
        self.features_vector = features_vector or []
        self.vector_dim = vector_dim
        self.vector_model = vector_model

    async def insert(self) -> None:
        _FakeContentMetadata._docs[self.ext_id] = self

    async def save(self) -> None:
        _FakeContentMetadata._docs[self.ext_id] = self


class _FakeMetaQuery:
    def __init__(self, docs):
        self._docs = list(docs)

    def find(self, condition):
        if isinstance(condition, tuple) and condition[0] == "eq" and condition[1] == "type":
            self._docs = [doc for doc in self._docs if doc.type == condition[2]]
        return self

    async def to_list(self):
        return list(self._docs)


class _FakeContentMetadata:
    ext_id = _FakeField("ext_id")
    type = _FakeField("type")
    _docs = {}

    @classmethod
    async def find_one(cls, *conditions):
        for condition in conditions:
            if isinstance(condition, tuple) and condition[1] == "ext_id":
                return cls._docs.get(condition[2])
        return None

    @classmethod
    def find(cls, query):
        if isinstance(query, dict):
            ids = query.get("ext_id", {}).get("$in", [])
            docs = [cls._docs[item_id] for item_id in ids if item_id in cls._docs]
            return _FakeMetaQuery(docs)
        return _FakeMetaQuery(cls._docs.values())

    def __new__(cls, **kwargs):
        return _FakeMetaDoc(**kwargs)


class _FakeInteractionDoc:
    def __init__(self, *, user_id: str, ext_id: str, type: str, weight: float = 1.0):
        self.user_id = user_id
        self.ext_id = ext_id
        self.type = type
        self.weight = weight
        self.created_at = datetime.now(timezone.utc)
        self.deleted = False

    async def insert(self) -> None:
        _FakeInteraction._rows.append(self)

    async def delete(self) -> None:
        self.deleted = True
        _FakeInteraction._rows = [row for row in _FakeInteraction._rows if row is not self]


class _FakeInteractionQuery:
    def __init__(self, rows):
        self._rows = list(rows)

    def sort(self, expression: str):
        reverse = expression.startswith("-")
        field = expression[1:] if reverse else expression
        self._rows.sort(key=lambda item: getattr(item, field), reverse=reverse)
        return self

    async def to_list(self):
        return list(self._rows)


class _FakeInteraction:
    user_id = _FakeField("user_id")
    ext_id = _FakeField("ext_id")
    type = _FakeField("type")
    _rows = []

    @classmethod
    async def find_one(cls, *conditions):
        query = cls.find(*conditions)
        rows = await query.to_list()
        return rows[0] if rows else None

    @classmethod
    def find(cls, *conditions):
        rows = list(cls._rows)
        for condition in conditions:
            if isinstance(condition, tuple) and condition[0] == "eq":
                rows = [row for row in rows if getattr(row, condition[1]) == condition[2]]
        return _FakeInteractionQuery(rows)

    def __new__(cls, **kwargs):
        return _FakeInteractionDoc(**kwargs)


class _FakePlaylistQuery:
    def __init__(self, playlists):
        self._playlists = list(playlists)

    async def to_list(self):
        return list(self._playlists)


class _FakePlaylist:
    user_id = _FakeField("user_id")
    _db = {}
    _counter = 0

    def __init__(
        self,
        *,
        user_id: str,
        title: str,
        description: str | None = None,
        items=None,
    ) -> None:
        type(self)._counter += 1
        self.id = f"p{type(self)._counter}"
        self.user_id = user_id
        self.title = title
        self.description = description
        self.items = list(items or [])
        self.deleted = False

    async def insert(self) -> None:
        type(self)._db[self.id] = self

    async def save(self) -> None:
        type(self)._db[self.id] = self

    async def delete(self) -> None:
        self.deleted = True
        type(self)._db.pop(self.id, None)

    @classmethod
    async def get(cls, playlist_id: str):
        return cls._db.get(playlist_id)

    @classmethod
    def find(cls, *conditions):
        rows = list(cls._db.values())
        for condition in conditions:
            if isinstance(condition, tuple) and condition[0] == "eq" and condition[1] == "user_id":
                rows = [row for row in rows if row.user_id == condition[2]]
        return _FakePlaylistQuery(rows)


class _FakeVectorizer:
    def get_embedding(self, text: str):
        return [0.1, 0.2]


def _content(external_id: str, type_value: str = "movie", rating: float = 8.0) -> UnifiedContent:
    return UnifiedContent(
        id=f"{type_value}_{external_id}",
        external_id=external_id,
        type=type_value,
        title=f"{type_value}-{external_id}",
        subtitle=type_value.title(),
        image_url=f"https://img.test/{external_id}.jpg",
        rating=rating,
    )


def _patch_dependencies(monkeypatch):
    fake_redis = _FakeRedis()
    monkeypatch.setattr(library_module, "redis_client", fake_redis)
    monkeypatch.setattr(library_module, "ContentMetadata", _FakeContentMetadata)
    monkeypatch.setattr(library_module, "Interaction", _FakeInteraction)
    monkeypatch.setattr(library_module, "Playlist", _FakePlaylist)
    monkeypatch.setattr(library_module, "get_vectorizer", lambda: _FakeVectorizer())
    return fake_redis


@pytest.mark.asyncio
async def test_toggle_like_adds_metadata_and_like(monkeypatch) -> None:
    _FakeContentMetadata._docs = {}
    _FakeInteraction._rows = []
    _FakePlaylist._db = {}
    fake_redis = _patch_dependencies(monkeypatch)

    service = LibraryService()
    result = await service.toggle_like("u1", _content("m1"))

    assert result["status"] == "added"
    assert "m1" in _FakeContentMetadata._docs
    assert len(_FakeInteraction._rows) == 1
    assert fake_redis.deleted_prefixes == [
        "favorites:u1:",
        "user_recs:u1:",
        "playlist_details:u1:",
    ]


@pytest.mark.asyncio
async def test_toggle_like_removes_existing_like(monkeypatch) -> None:
    _FakeContentMetadata._docs = {"m1": _FakeMetaDoc(ext_id="m1", type="movie", title="t")}
    _FakeInteraction._rows = [_FakeInteractionDoc(user_id="u1", ext_id="m1", type="like")]
    _FakePlaylist._db = {}
    _patch_dependencies(monkeypatch)

    service = LibraryService()
    result = await service.toggle_like("u1", _content("m1"))

    assert result["status"] == "removed"
    assert _FakeInteraction._rows == []


@pytest.mark.asyncio
async def test_get_user_favorites_cache_hit(monkeypatch) -> None:
    _FakeContentMetadata._docs = {}
    _FakeInteraction._rows = []
    _FakePlaylist._db = {}
    fake_redis = _patch_dependencies(monkeypatch)
    fake_redis.storage["favorites:u1:all"] = [_content("cached").model_dump(by_alias=True)]

    service = LibraryService()
    payload = await service.get_user_favorites("u1")
    assert len(payload) == 1
    assert payload[0].external_id == "cached"


@pytest.mark.asyncio
async def test_get_user_favorites_builds_from_interactions_and_orders(monkeypatch) -> None:
    _FakeContentMetadata._docs = {
        "m1": _FakeMetaDoc(ext_id="m1", type="movie", title="M1", rating=7.0),
        "m2": _FakeMetaDoc(ext_id="m2", type="movie", title="M2", rating=8.0),
        "b1": _FakeMetaDoc(ext_id="b1", type="book", title="B1", rating=9.0),
    }
    newer = _FakeInteractionDoc(user_id="u1", ext_id="m2", type="like")
    older = _FakeInteractionDoc(user_id="u1", ext_id="m1", type="like")
    older.created_at = datetime.now(timezone.utc) - timedelta(days=1)
    duplicate = _FakeInteractionDoc(user_id="u1", ext_id="m2", type="like")
    _FakeInteraction._rows = [older, newer, duplicate]
    _FakePlaylist._db = {}
    fake_redis = _patch_dependencies(monkeypatch)

    service = LibraryService()
    payload = await service.get_user_favorites("u1", content_type="movie")

    assert [item.external_id for item in payload] == ["m2", "m1"]
    assert fake_redis.set_calls


@pytest.mark.asyncio
async def test_create_playlist_and_get_user_playlists(monkeypatch) -> None:
    _FakeContentMetadata._docs = {}
    _FakeInteraction._rows = []
    _FakePlaylist._db = {}
    _FakePlaylist._counter = 0
    _patch_dependencies(monkeypatch)
    service = LibraryService()

    invalid = await service.create_playlist("u1", "   ")
    assert invalid["status"] == "error"

    created = await service.create_playlist("u1", "  My List  ", description="desc")
    playlists = await service.get_user_playlists("u1")

    assert created.title == "My List"
    assert len(playlists) == 1
    assert playlists[0].description == "desc"


@pytest.mark.asyncio
async def test_playlist_update_and_details_and_delete(monkeypatch) -> None:
    _FakeContentMetadata._docs = {
        "m1": _FakeMetaDoc(ext_id="m1", type="movie", title="Movie 1", rating=8.0),
    }
    _FakeInteraction._rows = []
    _FakePlaylist._db = {}
    _FakePlaylist._counter = 0
    fake_redis = _patch_dependencies(monkeypatch)
    service = LibraryService()

    playlist = await service.create_playlist("u1", "List 1")
    playlist.items = ["m1"]
    await playlist.save()

    bad_update = await service.update_playlist("u1", playlist.id, title="   ")
    assert bad_update["status"] == "error"

    updated = await service.update_playlist(
        "u1",
        playlist.id,
        title="Updated",
        description="New desc",
    )
    assert updated.title == "Updated"
    assert updated.description == "New desc"

    details = await service.get_playlist_details("u1", playlist.id)
    assert details["title"] == "Updated"
    assert details["items"][0]["ext_id"] == "m1"

    cached = await service.get_playlist_details("u1", playlist.id)
    assert cached["title"] == "Updated"
    assert fake_redis.set_calls

    deleted = await service.delete_playlist("u1", playlist.id)
    assert deleted["status"] == "success"


@pytest.mark.asyncio
async def test_add_and_remove_from_playlist(monkeypatch) -> None:
    _FakeContentMetadata._docs = {}
    _FakeInteraction._rows = []
    _FakePlaylist._db = {}
    _FakePlaylist._counter = 0
    _patch_dependencies(monkeypatch)
    service = LibraryService()

    missing = await service.add_to_playlist("missing", _content("m1"))
    assert missing["status"] == "error"

    playlist = await service.create_playlist("u1", "List 1")
    added = await service.add_to_playlist(playlist.id, _content("m1"))
    exists = await service.add_to_playlist(playlist.id, _content("m1"))
    denied = await service.remove_from_playlist("other", playlist.id, "m1")
    removed = await service.remove_from_playlist("u1", playlist.id, "m1")

    assert added["status"] == "success"
    assert exists["status"] == "exists"
    assert denied["status"] == "error"
    assert removed["status"] == "success"
