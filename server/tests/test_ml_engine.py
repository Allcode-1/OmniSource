import pytest

from app.ml import engine as engine_module
from app.ml.engine import RecommenderEngine
from app.schemas.content import UnifiedContent


class _FakeField:
    def __init__(self, name: str) -> None:
        self.name = name

    def __eq__(self, other):
        return ("eq", self.name, other)


class _FakeInteractionDoc:
    def __init__(self, *, user_id: str, ext_id: str, type: str, weight: float = 1.0):
        self.user_id = user_id
        self.ext_id = ext_id
        self.type = type
        self.weight = weight


class _FakeQuery:
    def __init__(self, rows):
        self._rows = list(rows)
        self._limit = None

    def find(self, condition):
        if isinstance(condition, tuple) and condition[0] == "eq" and condition[1] == "type":
            self._rows = [row for row in self._rows if getattr(row, "type", None) == condition[2]]
        return self

    def limit(self, value: int):
        self._limit = value
        return self

    async def to_list(self):
        if self._limit is None:
            return list(self._rows)
        return list(self._rows[: self._limit])


class _FakeInteractionModel:
    user_id = _FakeField("user_id")
    type = _FakeField("type")
    _rows = []

    @classmethod
    def find(cls, *conditions):
        rows = list(cls._rows)
        for condition in conditions:
            if not isinstance(condition, tuple):
                continue
            op = condition[0]
            if op == "eq" and condition[1] == "user_id":
                rows = [row for row in rows if row.user_id == condition[2]]
            if op == "in" and condition[1] == "type":
                rows = [row for row in rows if row.type in set(condition[2])]
        return _FakeQuery(rows)


class _FakeContentDoc:
    def __init__(
        self,
        *,
        ext_id: str,
        type: str,
        title: str,
        features_vector=None,
        rating: float = 0.0,
    ) -> None:
        self.ext_id = ext_id
        self.type = type
        self.title = title
        self.subtitle = type.title()
        self.image_url = f"https://img.test/{ext_id}.jpg"
        self.features_vector = list(features_vector or [])
        self.rating = rating
        self.genres = []
        self.release_date = None


class _FakeContentMetadata:
    ext_id = _FakeField("ext_id")
    type = _FakeField("type")
    _docs = {}

    @classmethod
    def find(cls, query=None):
        rows = list(cls._docs.values())

        if isinstance(query, tuple) and query[0] == "in" and query[1] == "ext_id":
            allowed = set(query[2])
            rows = [row for row in rows if row.ext_id in allowed]
        elif isinstance(query, dict):
            excluded = set(query.get("ext_id", {}).get("$nin", []))
            if excluded:
                rows = [row for row in rows if row.ext_id not in excluded]
            if query.get("features_vector.0", {}).get("$exists"):
                rows = [row for row in rows if row.features_vector]
            if "type" in query:
                rows = [row for row in rows if row.type == query["type"]]

        return _FakeQuery(rows)


class _FakeRedis:
    def __init__(self) -> None:
        self.storage = {}
        self.set_calls = []

    async def get_cache(self, key: str):
        return self.storage.get(key)

    async def set_cache(self, key: str, value, expire: int = 0):
        self.storage[key] = value
        self.set_calls.append((key, expire))


class _FakeVectorizer:
    def __init__(self, vector):
        self.vector = vector

    def get_embedding(self, text: str):
        return self.vector


def _content(ext_id: str, type_value: str = "movie", rating: float = 8.0) -> UnifiedContent:
    return UnifiedContent(
        id=f"{type_value}_{ext_id}",
        external_id=ext_id,
        type=type_value,
        title=f"{type_value}-{ext_id}",
        subtitle=type_value.title(),
        image_url=f"https://img.test/{ext_id}.jpg",
        rating=rating,
    )


def _patch_common(monkeypatch):
    fake_redis = _FakeRedis()
    monkeypatch.setattr(engine_module, "Interaction", _FakeInteractionModel)
    monkeypatch.setattr(engine_module, "ContentMetadata", _FakeContentMetadata)
    monkeypatch.setattr(engine_module, "redis_client", fake_redis)
    monkeypatch.setattr(engine_module, "In", lambda field, values: ("in", field.name, values))
    return fake_redis


@pytest.mark.asyncio
async def test_get_recommendations_without_interactions_returns_fallback(monkeypatch) -> None:
    _FakeInteractionModel._rows = []
    _FakeContentMetadata._docs = {
        "m1": _FakeContentDoc(ext_id="m1", type="movie", title="M1", features_vector=[1.0]),
        "b1": _FakeContentDoc(ext_id="b1", type="book", title="B1", features_vector=[1.0]),
    }
    _patch_common(monkeypatch)
    engine = RecommenderEngine()

    result = await engine.get_recommendations("u1", content_type="movie", limit=1)
    assert len(result) == 1
    assert result[0].ext_id == "m1"


@pytest.mark.asyncio
async def test_get_recommendations_returns_empty_when_no_vectorizable_history(monkeypatch) -> None:
    _FakeInteractionModel._rows = [
        _FakeInteractionDoc(user_id="u1", ext_id="app", type="view", weight=0.2),
    ]
    _FakeContentMetadata._docs = {}
    _patch_common(monkeypatch)
    engine = RecommenderEngine()

    result = await engine.get_recommendations("u1", content_type="all", limit=5)
    assert result == []


@pytest.mark.asyncio
async def test_get_recommendations_scores_and_sorts_candidates(monkeypatch) -> None:
    _FakeInteractionModel._rows = [
        _FakeInteractionDoc(user_id="u1", ext_id="seed1", type="like", weight=1.0),
        _FakeInteractionDoc(user_id="u1", ext_id="seed2", type="view", weight=0.2),
    ]
    _FakeContentMetadata._docs = {
        "seed1": _FakeContentDoc(ext_id="seed1", type="movie", title="Seed 1", features_vector=[1.0, 0.0], rating=8.0),
        "seed2": _FakeContentDoc(ext_id="seed2", type="movie", title="Seed 2", features_vector=[1.0, 0.0], rating=7.0),
        "candA": _FakeContentDoc(ext_id="candA", type="movie", title="A", features_vector=[1.0, 0.0], rating=9.0),
        "candB": _FakeContentDoc(ext_id="candB", type="movie", title="B", features_vector=[0.0, 1.0], rating=10.0),
    }
    _patch_common(monkeypatch)
    engine = RecommenderEngine()

    # A is more similar to user profile than B in this synthetic setup.
    monkeypatch.setattr(
        engine.similarity,
        "calculate_cosine_similarity",
        lambda left, right: 1.0 if right == [1.0, 0.0] else 0.1,
    )

    result = await engine.get_recommendations("u1", content_type="movie", limit=2)
    assert [item.ext_id for item in result] == ["candA", "candB"]


@pytest.mark.asyncio
async def test_get_recommendations_skips_dimension_mismatch_vectors(monkeypatch) -> None:
    _FakeInteractionModel._rows = [
        _FakeInteractionDoc(user_id="u1", ext_id="seed1", type="like", weight=1.0),
        _FakeInteractionDoc(user_id="u1", ext_id="seed2", type="view", weight=0.2),
    ]
    _FakeContentMetadata._docs = {
        "seed1": _FakeContentDoc(ext_id="seed1", type="movie", title="Seed 1", features_vector=[1.0, 0.0], rating=8.0),
        "seed2": _FakeContentDoc(ext_id="seed2", type="movie", title="Seed 2", features_vector=[1.0, 0.0, 0.0], rating=7.0),
        "candA": _FakeContentDoc(ext_id="candA", type="movie", title="A", features_vector=[1.0, 0.0], rating=9.0),
        "candB": _FakeContentDoc(ext_id="candB", type="movie", title="B", features_vector=[1.0, 0.0, 0.0], rating=10.0),
    }
    _patch_common(monkeypatch)
    engine = RecommenderEngine()

    monkeypatch.setattr(
        engine.similarity,
        "calculate_cosine_similarity",
        lambda left, right: 1.0 if right == [1.0, 0.0] else -1.0,
    )

    result = await engine.get_recommendations("u1", content_type="movie", limit=5)
    assert [item.ext_id for item in result] == ["candA"]


@pytest.mark.asyncio
async def test_get_deep_research_returns_cached_payload(monkeypatch) -> None:
    fake_redis = _patch_common(monkeypatch)
    cached = [_content("cached", "movie").model_dump()]
    fake_redis.storage["deep_research:movie:3:cyberpunk"] = cached
    engine = RecommenderEngine()

    result = await engine.get_deep_research("cyberpunk", content_type="movie", limit=3)
    assert len(result) == 1
    assert result[0].external_id == "cached"


@pytest.mark.asyncio
async def test_get_deep_research_falls_back_when_tag_vector_empty(monkeypatch) -> None:
    _patch_common(monkeypatch)
    engine = RecommenderEngine()

    monkeypatch.setattr(engine_module, "get_vectorizer", lambda: _FakeVectorizer([]))

    async def fake_discovery(tag: str, type: str = "all"):
        return [_content("d1"), _content("d2")]

    monkeypatch.setattr(engine.content_service, "get_discovery", fake_discovery)

    result = await engine.get_deep_research("cyberpunk", content_type="all", limit=1)
    assert len(result) == 1
    assert result[0].external_id == "d1"


@pytest.mark.asyncio
async def test_get_deep_research_scores_candidates_and_merges_discovery(monkeypatch) -> None:
    fake_redis = _patch_common(monkeypatch)
    _FakeContentMetadata._docs = {
        "v1": _FakeContentDoc(ext_id="v1", type="movie", title="V1", features_vector=[1.0, 0.0], rating=7.0),
        "v2": _FakeContentDoc(ext_id="v2", type="movie", title="V2", features_vector=[0.2, 0.8], rating=6.0),
    }
    engine = RecommenderEngine()
    engine.MIN_DEEP_VECTOR_CANDIDATES = 1

    monkeypatch.setattr(engine_module, "get_vectorizer", lambda: _FakeVectorizer([1.0, 0.0]))
    monkeypatch.setattr(
        engine.similarity,
        "calculate_cosine_similarity",
        lambda left, right: 1.0 if right == [1.0, 0.0] else -0.1,
    )

    async def fake_discovery(tag: str, type: str = "all"):
        return [_content("v1", "movie"), _content("extra", "movie")]

    monkeypatch.setattr(engine.content_service, "get_discovery", fake_discovery)

    result = await engine.get_deep_research("tag", content_type="movie", limit=2)
    assert [item.external_id for item in result] == ["v1", "extra"]
    assert fake_redis.set_calls


@pytest.mark.asyncio
async def test_get_deep_research_skips_dimension_mismatch_vectors(monkeypatch) -> None:
    _patch_common(monkeypatch)
    _FakeContentMetadata._docs = {
        "v1": _FakeContentDoc(ext_id="v1", type="movie", title="V1", features_vector=[1.0, 0.0], rating=7.0),
        "v2": _FakeContentDoc(ext_id="v2", type="movie", title="V2", features_vector=[0.2, 0.8, 0.1], rating=6.0),
    }
    engine = RecommenderEngine()
    engine.MIN_DEEP_VECTOR_CANDIDATES = 1

    monkeypatch.setattr(engine_module, "get_vectorizer", lambda: _FakeVectorizer([1.0, 0.0]))
    monkeypatch.setattr(
        engine.similarity,
        "calculate_cosine_similarity",
        lambda left, right: 1.0 if right == [1.0, 0.0] else -1.0,
    )

    async def fake_discovery(tag: str, type: str = "all"):
        return [_content("extra", "movie")]

    monkeypatch.setattr(engine.content_service, "get_discovery", fake_discovery)

    result = await engine.get_deep_research("tag", content_type="movie", limit=2)
    assert [item.external_id for item in result] == ["v1", "extra"]


@pytest.mark.asyncio
async def test_recommender_close_delegates_content_service(monkeypatch) -> None:
    _patch_common(monkeypatch)
    engine = RecommenderEngine()
    captured = {"closed": 0}

    async def fake_close():
        captured["closed"] += 1

    monkeypatch.setattr(engine.content_service, "close", fake_close)
    await engine.close()
    assert captured["closed"] == 1
