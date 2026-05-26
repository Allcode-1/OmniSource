from datetime import datetime, timedelta, timezone

import pytest

from app.schemas.analytics import TrackEventRequest, UserStats
from app.services import analytics_service as analytics_module
from app.services.analytics_service import AnalyticsService


class _FakeField:
    def __init__(self, name: str) -> None:
        self.name = name

    def __eq__(self, other):
        return ("eq", self.name, other)

    def __ge__(self, other):
        return ("ge", self.name, other)


class _FakeContentDoc:
    def __init__(
        self,
        *,
        ext_id: str,
        type: str,
        title: str = "",
        subtitle: str | None = None,
        image_url: str | None = None,
        rating: float = 0.0,
        genres=None,
        release_date: str | None = None,
        features_vector=None,
        vector_dim: int | None = None,
        vector_model: str | None = None,
    ) -> None:
        self.ext_id = ext_id
        self.type = type
        self.title = title
        self.subtitle = subtitle
        self.image_url = image_url
        self.rating = rating
        self.genres = genres or []
        self.release_date = release_date
        self.features_vector = features_vector or []
        self.vector_dim = vector_dim
        self.vector_model = vector_model
        self.saved = False

    async def save(self) -> None:
        self.saved = True

    async def insert(self) -> None:
        _FakeContentMetadata._docs[self.ext_id] = self


class _FakeContentMetadata:
    ext_id = _FakeField("ext_id")
    _docs = {}

    @classmethod
    async def find_one(cls, *conditions):
        for condition in conditions:
            if isinstance(condition, tuple) and condition[1] == "ext_id":
                return cls._docs.get(condition[2])
        return None

    @classmethod
    def find(cls, query):
        ids = query.get("ext_id", {}).get("$in", [])
        docs = [cls._docs[item_id] for item_id in ids if item_id in cls._docs]
        return _FakeQuery(docs)

    def __new__(cls, **kwargs):
        return _FakeContentDoc(**kwargs)


class _FakeInteractionDoc:
    def __init__(
        self,
        *,
        user_id: str,
        ext_id: str,
        content_type: str | None,
        type: str,
        weight: float,
        meta: dict | None = None,
    ) -> None:
        self.id = f"interaction-{len(_FakeInteraction._rows) + 1}"
        self.user_id = user_id
        self.ext_id = ext_id
        self.content_type = content_type
        self.type = type
        self.weight = weight
        self.meta = meta or {}
        self.created_at = datetime.now(timezone.utc)

    async def insert(self) -> None:
        _FakeInteraction._rows.append(self)


class _FakeQuery:
    def __init__(self, items):
        self._items = list(items)
        self._limit = None

    def sort(self, expression: str):
        reverse = expression.startswith("-")
        field = expression[1:] if reverse else expression
        self._items.sort(key=lambda item: getattr(item, field), reverse=reverse)
        return self

    def limit(self, value: int):
        self._limit = value
        return self

    async def to_list(self):
        if self._limit is None:
            return list(self._items)
        return list(self._items[: self._limit])


class _FakeInteraction:
    user_id = _FakeField("user_id")
    created_at = _FakeField("created_at")
    _rows = []

    @classmethod
    def find(cls, *conditions):
        rows = list(cls._rows)
        for condition in conditions:
            if not isinstance(condition, tuple):
                continue
            op, field, value = condition
            if op == "eq":
                rows = [row for row in rows if getattr(row, field) == value]
            elif op == "ge":
                rows = [row for row in rows if getattr(row, field) >= value]
        return _FakeQuery(rows)

    def __new__(cls, **kwargs):
        return _FakeInteractionDoc(**kwargs)


class _FakeVectorizer:
    def get_embedding(self, text: str):
        return [0.1, 0.2, 0.3]


@pytest.mark.asyncio
async def test_track_event_inserts_metadata_and_interaction(monkeypatch) -> None:
    _FakeContentMetadata._docs = {}
    _FakeInteraction._rows = []

    monkeypatch.setattr(analytics_module, "ContentMetadata", _FakeContentMetadata)
    monkeypatch.setattr(analytics_module, "Interaction", _FakeInteraction)
    monkeypatch.setattr(analytics_module, "get_vectorizer", lambda: _FakeVectorizer())

    service = AnalyticsService()
    payload = TrackEventRequest(
        type="open_detail",
        ext_id="m1",
        content_type="movie",
        meta={"title": "Matrix", "description": "Sci-fi classic"},
    )

    result = await service.track_event("u1", payload, ranking_variant="hybrid_ml")
    assert result["status"] == "ok"
    assert "m1" in _FakeContentMetadata._docs
    assert len(_FakeInteraction._rows) == 1
    assert _FakeInteraction._rows[0].meta["ranking_variant"] == "hybrid_ml"


@pytest.mark.asyncio
async def test_track_event_updates_existing_metadata_when_missing_fields(monkeypatch) -> None:
    _FakeInteraction._rows = []
    existing = _FakeContentDoc(
        ext_id="m2",
        type="movie",
        title="",
        image_url=None,
    )
    _FakeContentMetadata._docs = {"m2": existing}

    monkeypatch.setattr(analytics_module, "ContentMetadata", _FakeContentMetadata)
    monkeypatch.setattr(analytics_module, "Interaction", _FakeInteraction)
    monkeypatch.setattr(analytics_module, "get_vectorizer", lambda: _FakeVectorizer())

    service = AnalyticsService()
    payload = TrackEventRequest(
        type="view",
        ext_id="m2",
        content_type="movie",
        meta={"title": "Updated title", "image_url": "https://img.test/m2.jpg"},
    )
    await service.track_event("u2", payload)

    assert existing.title == "Updated title"
    assert existing.image_url == "https://img.test/m2.jpg"
    assert existing.saved is True


@pytest.mark.asyncio
async def test_get_timeline_uses_content_metadata_when_present(monkeypatch) -> None:
    _FakeContentMetadata._docs = {
        "m1": _FakeContentDoc(
            ext_id="m1",
            type="movie",
            title="From metadata",
            image_url="https://img.test/m1.jpg",
        ),
    }
    _FakeInteraction._rows = [
        _FakeInteractionDoc(
            user_id="u1",
            ext_id="m1",
            content_type="movie",
            type="view",
            weight=0.2,
            meta={"title": "From event"},
        ),
        _FakeInteractionDoc(
            user_id="u1",
            ext_id="app",
            content_type=None,
            type="search",
            weight=0.1,
            meta={"title": "Search term"},
        ),
    ]

    monkeypatch.setattr(analytics_module, "ContentMetadata", _FakeContentMetadata)
    monkeypatch.setattr(analytics_module, "Interaction", _FakeInteraction)

    service = AnalyticsService()
    timeline = await service.get_timeline("u1", limit=10)

    assert len(timeline) == 2
    assert timeline[0].title in {"From metadata", "Search term", "From event"}
    assert any(item.ext_id == "m1" and item.title == "From metadata" for item in timeline)


@pytest.mark.asyncio
async def test_get_stats_computes_core_metrics(monkeypatch) -> None:
    now = datetime.now(timezone.utc)
    _FakeInteraction._rows = [
        _FakeInteractionDoc(
            user_id="u1",
            ext_id="m1",
            content_type="movie",
            type="view",
            weight=0.2,
            meta={"ranking_variant": "content_only"},
        ),
        _FakeInteractionDoc(
            user_id="u1",
            ext_id="m1",
            content_type="movie",
            type="open_detail",
            weight=0.5,
            meta={"ranking_variant": "content_only"},
        ),
        _FakeInteractionDoc(
            user_id="u1",
            ext_id="m1",
            content_type="movie",
            type="like",
            weight=1.0,
            meta={"ranking_variant": "hybrid_ml"},
        ),
        _FakeInteractionDoc(
            user_id="u1",
            ext_id="m1",
            content_type="movie",
            type="dwell_time",
            weight=0.3,
            meta={"seconds": 15},
        ),
        _FakeInteractionDoc(
            user_id="u1",
            ext_id="old",
            content_type="movie",
            type="view",
            weight=0.2,
            meta={},
        ),
    ]
    _FakeInteraction._rows[-1].created_at = now - timedelta(days=90)

    monkeypatch.setattr(analytics_module, "Interaction", _FakeInteraction)
    service = AnalyticsService()
    stats = await service.get_stats("u1", days=30)

    assert stats.total_events == 4
    assert stats.counts_by_type["view"] == 1
    assert stats.ctr == 1.0
    assert stats.save_rate == 1.0
    assert stats.avg_dwell_seconds == 15.0
    assert "content_only" in stats.ab_metrics


@pytest.mark.asyncio
async def test_get_notifications_adds_contextual_messages(monkeypatch) -> None:
    service = AnalyticsService()

    async def fake_stats(user_id: str, days: int = 14):
        return UserStats(
            total_events=20,
            counts_by_type={"view": 15, "open_detail": 1, "like": 0},
            ctr=0.05,
            save_rate=0.0,
            avg_dwell_seconds=4.0,
            top_content_types={"movie": 10},
            ab_metrics={},
        )

    monkeypatch.setattr(service, "get_stats", fake_stats)
    user = type("UserObj", (), {"id": "u1", "interests": ["cyberpunk", "noir"]})()
    notifications = await service.get_notifications(user)
    ids = {item.id for item in notifications}

    assert "digest-weekly" in ids
    assert "likes-empty" in ids
    assert "interests" in ids
    assert "ctr-tip" in ids
