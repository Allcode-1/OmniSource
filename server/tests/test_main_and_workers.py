from types import SimpleNamespace

import pytest
from starlette.requests import Request
from starlette.responses import Response

from app import main as main_module
import app.workers as workers_package
from app.workers import precompute_worker as worker_module


def _request(path: str = "/test", method: str = "GET", headers=None) -> Request:
    raw_headers = headers or []
    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "headers": raw_headers,
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 80),
    }
    return Request(scope)


@pytest.mark.asyncio
async def test_startup_event_runs_init_db_and_checks_redis(monkeypatch) -> None:
    captured = {"init_db": 0, "ping": 0, "task": 0}

    async def fake_init_db():
        captured["init_db"] += 1

    async def fake_ping():
        captured["ping"] += 1
        return True

    def fake_create_task(coro):
        captured["task"] += 1
        coro.close()
        return SimpleNamespace(done=lambda: True)

    monkeypatch.setattr(main_module, "init_db", fake_init_db)
    monkeypatch.setattr(main_module.redis_client, "enabled", True)
    monkeypatch.setattr(main_module.redis_client, "ping", fake_ping)
    monkeypatch.setattr(main_module.asyncio, "create_task", fake_create_task)

    await main_module.startup_event()
    assert captured == {"init_db": 1, "ping": 1, "task": 1}


@pytest.mark.asyncio
async def test_shutdown_event_closes_services(monkeypatch) -> None:
    captured = {"content": 0, "ml": 0, "research": 0, "redis": 0}

    async def close_content():
        captured["content"] += 1

    async def close_ml():
        captured["ml"] += 1

    async def close_research():
        captured["research"] += 1

    async def close_redis():
        captured["redis"] += 1

    monkeypatch.setattr(main_module.content.service, "close", close_content)
    monkeypatch.setattr(main_module.content.ml_engine, "close", close_ml)
    monkeypatch.setattr(main_module.research.engine, "close", close_research)
    monkeypatch.setattr(main_module.redis_client, "close", close_redis)

    await main_module.shutdown_event()
    assert captured == {"content": 1, "ml": 1, "research": 1, "redis": 1}


@pytest.mark.asyncio
async def test_request_context_middleware_success(monkeypatch) -> None:
    request = _request(path="/ok")
    observed = []

    def fake_observe(method: str, path: str, status: int, duration_ms: float):
        observed.append((method, path, status))

    async def call_next(req: Request):
        return Response(content=b"ok", status_code=201)

    monkeypatch.setattr(main_module.metrics_registry, "observe", fake_observe)
    response = await main_module.request_context_middleware(request, call_next)

    assert response.status_code == 201
    assert "x-request-id" in response.headers
    assert observed and observed[0][2] == 201


@pytest.mark.asyncio
async def test_request_context_middleware_error_path(monkeypatch) -> None:
    request = _request(path="/boom")
    observed = []
    logged = {"called": 0}

    def fake_observe(method: str, path: str, status: int, duration_ms: float):
        observed.append((method, path, status))

    def fake_exception(*args, **kwargs):
        logged["called"] += 1

    async def call_next(req: Request):
        raise RuntimeError("boom")

    monkeypatch.setattr(main_module.metrics_registry, "observe", fake_observe)
    monkeypatch.setattr(main_module.logger, "exception", fake_exception)

    with pytest.raises(RuntimeError):
        await main_module.request_context_middleware(request, call_next)

    assert observed and observed[0][2] == 500
    assert logged["called"] == 1


@pytest.mark.asyncio
async def test_unhandled_exception_handler_returns_json_with_request_id(monkeypatch) -> None:
    request = _request(path="/err")
    request.state.request_id = "req-1"
    captured = {"called": 0}

    def fake_exception(*args, **kwargs):
        captured["called"] += 1

    monkeypatch.setattr(main_module.logger, "exception", fake_exception)
    response = await main_module.unhandled_exception_handler(
        request,
        RuntimeError("broken"),
    )
    body = response.body.decode()

    assert response.status_code == 500
    assert "Internal server error" in body
    assert "req-1" in body
    assert captured["called"] == 1


@pytest.mark.asyncio
async def test_health_and_metrics_endpoints(monkeypatch) -> None:
    async def fake_ping():
        return False

    monkeypatch.setattr(main_module.redis_client, "enabled", True)
    monkeypatch.setattr(main_module.redis_client, "ping", fake_ping)
    monkeypatch.setattr(main_module.metrics_registry, "render_prometheus", lambda: "metric 1\n")

    health = await main_module.health_check()
    metrics = await main_module.metrics()

    assert health["status"] == "ok"
    assert health["redis"] == "down"
    assert metrics.status_code == 200
    assert "metric 1" in metrics.body.decode()


@pytest.mark.asyncio
async def test_warmup_vectorizer_handles_exception(monkeypatch) -> None:
    logged = {"warning": 0}

    class _BrokenVectorizer:
        def get_embedding(self, text: str):
            raise RuntimeError("no model")

    async def fake_to_thread(func, *args, **kwargs):
        return func(*args, **kwargs)

    def fake_warning(*args, **kwargs):
        logged["warning"] += 1

    monkeypatch.setattr(main_module, "get_vectorizer", lambda: _BrokenVectorizer())
    monkeypatch.setattr(main_module.asyncio, "to_thread", fake_to_thread)
    monkeypatch.setattr(main_module.logger, "warning", fake_warning)

    await main_module._warmup_vectorizer()
    assert logged["warning"] == 1


@pytest.mark.asyncio
async def test_worker_warm_global_caches_and_run_once() -> None:
    worker = worker_module.PrecomputeWorker()
    captured = {"home": 0, "recs": 0, "discovery": 0, "deep": 0, "sync": 0, "user": 0}

    async def fake_home_data(content_type: str):
        captured["home"] += 1
        return {}

    async def fake_recommendations(content_type: str):
        captured["recs"] += 1
        return []

    async def fake_discovery(tag: str):
        captured["discovery"] += 1
        return []

    async def fake_deep_research(tag: str, content_type: str = "all"):
        captured["deep"] += 1
        return []

    async def fake_sync_home_snapshot():
        captured["sync"] += 1
        return 0

    async def fake_precompute(limit: int = 200):
        captured["user"] += 1

    worker.content_service.get_home_data = fake_home_data
    worker.content_service.get_recommendations = fake_recommendations
    worker.content_service.get_discovery = fake_discovery
    worker.recommender.get_deep_research = fake_deep_research
    worker.sync_service.sync_home_snapshot = fake_sync_home_snapshot
    worker.precompute_user_recommendations = fake_precompute

    await worker.warm_global_caches()
    assert captured["home"] == 4
    assert captured["recs"] == 4
    assert captured["discovery"] == worker_module.settings.CACHE_WARMUP_TAG_LIMIT
    assert captured["deep"] == worker_module.settings.CACHE_WARMUP_TAG_LIMIT

    await worker.run_once()
    assert captured["sync"] == 1
    assert captured["user"] == 1


@pytest.mark.asyncio
async def test_worker_precompute_user_recommendations_sets_cache(monkeypatch) -> None:
    worker = worker_module.PrecomputeWorker()

    class _FakeUserQuery:
        def limit(self, value: int):
            return self

        async def to_list(self):
            return [SimpleNamespace(id="u1"), SimpleNamespace(id="u2")]

    class _FakeUserModel:
        @staticmethod
        def find_all():
            return _FakeUserQuery()

    class _FakeUnified:
        def __init__(self, ext_id: str):
            self.ext_id = ext_id

        def model_dump(self):
            return {"ext_id": self.ext_id}

    async def fake_recommendations(
        user_id: str,
        content_type: str = "all",
        limit: int = 20,
        interest_tags=None,
    ):
        return [(SimpleNamespace(external_id=f"{user_id}-{content_type}-item"), "reason")]

    def fake_to_unified(item, reason=None):
        return _FakeUnified(item.external_id)

    captured = {"cache_calls": 0}

    async def fake_set_cache(key: str, value, expire: int = 3600):
        captured["cache_calls"] += 1

    monkeypatch.setattr(worker_module, "User", _FakeUserModel)
    monkeypatch.setattr(
        worker.recommender,
        "get_recommendation_results",
        fake_recommendations,
    )
    monkeypatch.setattr(worker.recommender, "_to_unified_content", fake_to_unified)
    monkeypatch.setattr(worker_module.redis_client, "set_cache", fake_set_cache)

    await worker.precompute_user_recommendations(limit=10)
    assert captured["cache_calls"] == 8


@pytest.mark.asyncio
async def test_run_precompute_once_executes_worker(monkeypatch) -> None:
    captured = {"run_once": 0}

    class _FakeWorker:
        async def run_once(self):
            captured["run_once"] += 1

    monkeypatch.setattr(worker_module, "PrecomputeWorker", _FakeWorker)
    await worker_module.run_precompute_once()
    assert captured["run_once"] == 1


def test_workers_package_exports_expected_symbols() -> None:
    assert "PrecomputeWorker" in workers_package.__all__
    assert "run_precompute_once" in workers_package.__all__
