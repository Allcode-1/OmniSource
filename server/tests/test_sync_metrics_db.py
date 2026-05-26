import pytest

from app.core import database as db_module
from app.core.metrics import MetricsRegistry
from app.schemas.content import UnifiedContent
from app.services import sync_service as sync_module
from app.services.sync_service import ContentSyncService


class _FakeField:
    def __init__(self, name: str) -> None:
        self.name = name

    def __eq__(self, other):
        return ("eq", self.name, other)


class _FakeContentDoc:
    def __init__(
        self,
        *,
        ext_id: str,
        type: str,
        title: str,
        subtitle=None,
        description=None,
        image_url=None,
        rating: float = 0.0,
        release_date=None,
        genres=None,
        features_vector=None,
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
        self.saved = False
        self.inserted = False

    async def save(self) -> None:
        self.saved = True
        _FakeContentMetadata._docs[self.ext_id] = self

    async def insert(self) -> None:
        self.inserted = True
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

    def __new__(cls, **kwargs):
        return _FakeContentDoc(**kwargs)


def _item(ext_id: str, type_value: str = "movie") -> UnifiedContent:
    return UnifiedContent(
        id=f"{type_value}_{ext_id}",
        external_id=ext_id,
        type=type_value,
        title=f"{type_value}-{ext_id}",
        subtitle=type_value.title(),
        image_url=f"https://img.test/{ext_id}.jpg",
        rating=7.5,
    )


def test_metrics_registry_observe_and_render() -> None:
    registry = MetricsRegistry()
    registry.observe("get", "/health", 200, 12.3)
    registry.observe("GET", "/health", 200, 5.7)

    payload = registry.render_prometheus()
    assert 'omnisource_http_requests_total{method="GET",path="/health",status="200"} 2' in payload
    assert 'omnisource_http_request_latency_ms_sum{method="GET",path="/health",status="200"} 18.000' in payload


@pytest.mark.asyncio
async def test_init_db_initializes_beanie(monkeypatch) -> None:
    captured = {"url": None, "beanie": 0, "info": 0}

    class _FakeClient:
        def __init__(self, url: str) -> None:
            captured["url"] = url

        def get_default_database(self):
            return "db"

    async def fake_init_beanie(database, document_models):
        captured["beanie"] += 1
        assert database == "db"
        assert len(document_models) >= 5

    def fake_info(*args, **kwargs):
        captured["info"] += 1

    monkeypatch.setattr(db_module, "AsyncIOMotorClient", _FakeClient)
    monkeypatch.setattr(db_module, "init_beanie", fake_init_beanie)
    monkeypatch.setattr(db_module.logger, "info", fake_info)

    await db_module.init_db()
    assert captured["beanie"] == 1
    assert captured["info"] == 1
    assert captured["url"] == db_module.settings.MONGODB_URL


@pytest.mark.asyncio
async def test_sync_service_persist_items_updates_existing_and_inserts_new(monkeypatch) -> None:
    existing = _FakeContentDoc(ext_id="m1", type="movie", title="Old")
    _FakeContentMetadata._docs = {"m1": existing}
    monkeypatch.setattr(sync_module, "ContentMetadata", _FakeContentMetadata)

    service = ContentSyncService()
    count = await service.persist_items(
        [
            _item("m1", "movie"),
            _item("b1", "book"),
            UnifiedContent(
                id="x",
                external_id="",
                type="movie",
                title="skip",
            ),
        ],
    )

    assert count == 2
    assert _FakeContentMetadata._docs["m1"].title == "movie-m1"
    assert _FakeContentMetadata._docs["m1"].saved is True
    assert "b1" in _FakeContentMetadata._docs
    assert _FakeContentMetadata._docs["b1"].inserted is True


@pytest.mark.asyncio
async def test_sync_home_snapshot_aggregates_all_sections(monkeypatch) -> None:
    service = ContentSyncService()
    captured = {"persist_calls": 0}

    async def fake_home_data(content_type: str):
        return {
            "A": [_item(f"{content_type}-1")],
            "B": [_item(f"{content_type}-2")],
        }

    async def fake_persist_items(items):
        captured["persist_calls"] += 1
        return len(list(items))

    monkeypatch.setattr(service.content_service, "get_home_data", fake_home_data)
    monkeypatch.setattr(service, "persist_items", fake_persist_items)

    total = await service.sync_home_snapshot()
    assert captured["persist_calls"] == 8
    assert total == 8
