from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth import routes as auth_router


class _FakeField:
    def __init__(self, name: str) -> None:
        self.name = name

    def __eq__(self, other):
        return (self.name, other)


class _FakeDeleteQuery:
    def __init__(self) -> None:
        self.deleted = False

    async def delete(self) -> None:
        self.deleted = True


class _FakeResetEntry:
    def __init__(self, *, email: str, token_hash: str, expires_at: datetime) -> None:
        self.email = email
        self.token_hash = token_hash
        self.expires_at = expires_at
        self.deleted = False

    async def insert(self) -> None:
        return None

    async def delete(self) -> None:
        self.deleted = True


class _FakeUser:
    def __init__(self, *, email: str, hashed_password: str = "old-hash") -> None:
        self.id = "u-reset"
        self.username = "neo"
        self.email = email
        self.interests = []
        self.is_onboarding_completed = True
        self.ranking_variant = "hybrid_ml"
        self.hashed_password = hashed_password
        self.saved = False

    async def save(self) -> None:
        self.saved = True


def _build_app() -> FastAPI:
    auth_router._RATE_LIMIT_BUCKETS.clear()
    app = FastAPI()
    app.include_router(auth_router.router)
    return app


def _patch_query_fields(monkeypatch) -> None:
    monkeypatch.setattr(auth_router.User, "email", _FakeField("email"), raising=False)
    monkeypatch.setattr(auth_router.PasswordReset, "email", _FakeField("email"), raising=False)
    monkeypatch.setattr(
        auth_router.PasswordReset,
        "token_hash",
        _FakeField("token_hash"),
        raising=False,
    )


def test_login_returns_400_on_invalid_credentials(monkeypatch) -> None:
    _patch_query_fields(monkeypatch)

    async def fake_find_one(*args, **kwargs):
        return None

    monkeypatch.setattr(auth_router.User, "find_one", fake_find_one)
    client = TestClient(_build_app())

    response = client.post(
        "/auth/login",
        data={"username": "user@test.dev", "password": "BadPass1!"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Incorrect email or password"


def test_login_success_returns_token_and_user(monkeypatch) -> None:
    _patch_query_fields(monkeypatch)
    fake_user = SimpleNamespace(
        id="u1",
        username="neo",
        email="neo@test.dev",
        interests=[],
        is_onboarding_completed=True,
        ranking_variant="hybrid_ml",
        hashed_password="hash",
    )

    async def fake_find_one(*args, **kwargs):
        return fake_user

    monkeypatch.setattr(auth_router.User, "find_one", fake_find_one)
    monkeypatch.setattr(auth_router, "verify_password", lambda plain, hashed: True)
    monkeypatch.setattr(auth_router, "create_access_token", lambda user_id: f"token-{user_id}")
    client = TestClient(_build_app())

    response = client.post(
        "/auth/login",
        data={"username": "neo@test.dev", "password": "StrongPass1!"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"] == "token-u1"
    assert body["user"]["email"] == "neo@test.dev"


def test_register_returns_400_if_email_exists(monkeypatch) -> None:
    _patch_query_fields(monkeypatch)

    async def fake_find_one(*args, **kwargs):
        return SimpleNamespace(id="existing")

    monkeypatch.setattr(auth_router.User, "find_one", fake_find_one)
    client = TestClient(_build_app())

    response = client.post(
        "/auth/register",
        json={
            "username": "neo",
            "email": "neo@test.dev",
            "password": "StrongPass1!",
            "interests": ["action"],
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Email already registered"


def test_register_creates_user_and_returns_auth_payload(monkeypatch) -> None:
    inserted = {"called": False}

    class _FakeUserDoc:
        email = _FakeField("email")

        def __init__(
            self,
            *,
            username: str,
            email: str,
            hashed_password: str,
            interests: list[str],
            is_onboarding_completed: bool,
        ) -> None:
            self.id = None
            self.username = username
            self.email = email
            self.hashed_password = hashed_password
            self.interests = interests
            self.is_onboarding_completed = is_onboarding_completed
            self.ranking_variant = "hybrid_ml"

        @classmethod
        async def find_one(cls, *args, **kwargs):
            return None

        async def insert(self) -> None:
            self.id = "u-new"
            inserted["called"] = True

    monkeypatch.setattr(auth_router, "User", _FakeUserDoc)
    monkeypatch.setattr(auth_router, "get_password_hash", lambda pwd: f"hashed::{pwd}")
    monkeypatch.setattr(auth_router, "create_access_token", lambda user_id: f"token-{user_id}")
    client = TestClient(_build_app())

    response = client.post(
        "/auth/register",
        json={
            "username": "neo",
            "email": "neo@test.dev",
            "password": "StrongPass1!",
            "interests": ["action", "noir"],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert inserted["called"] is True
    assert body["token_type"] == "bearer"
    assert body["access_token"] == "token-u-new"
    assert body["user"]["email"] == "neo@test.dev"
    assert body["user"]["interests"] == ["action", "noir"]


def test_forgot_password_non_existing_user_is_generic(monkeypatch) -> None:
    _patch_query_fields(monkeypatch)

    async def fake_find_one(*args, **kwargs):
        return None

    monkeypatch.setattr(auth_router.User, "find_one", fake_find_one)
    client = TestClient(_build_app())

    response = client.post("/auth/forgot-password", json={"email": "ghost@test.dev"})
    assert response.status_code == 200
    assert "If the account exists" in response.json()["message"]


def test_forgot_password_existing_user_creates_reset_entry(monkeypatch) -> None:
    fake_user = SimpleNamespace(id="u2", email="neo@test.dev")
    delete_query = _FakeDeleteQuery()
    sent = {}
    inserted_entries = []

    async def fake_user_find_one(*args, **kwargs):
        return fake_user

    async def fake_insert(self) -> None:
        inserted_entries.append(self)

    def fake_send_reset(email: str, token: str) -> None:
        sent["email"] = email
        sent["token"] = token

    class _FakePasswordResetDoc:
        email = _FakeField("email")
        token_hash = _FakeField("token_hash")

        def __init__(self, *, email: str, token_hash: str, expires_at: datetime) -> None:
            self.email = email
            self.token_hash = token_hash
            self.expires_at = expires_at

        @classmethod
        def find(cls, *args, **kwargs):
            return delete_query

        async def insert(self) -> None:
            await fake_insert(self)

    monkeypatch.setattr(auth_router.User, "email", _FakeField("email"), raising=False)
    monkeypatch.setattr(auth_router.User, "find_one", fake_user_find_one)
    monkeypatch.setattr(auth_router, "PasswordReset", _FakePasswordResetDoc)
    monkeypatch.setattr(auth_router, "send_reset_password_email", fake_send_reset)

    client = TestClient(_build_app())
    response = client.post("/auth/forgot-password", json={"email": "neo@test.dev"})

    assert response.status_code == 200
    assert "If the account exists" in response.json()["message"]
    assert delete_query.deleted is True
    assert len(inserted_entries) == 1
    assert inserted_entries[0].email == "neo@test.dev"
    assert sent["email"] == "neo@test.dev"
    assert sent["token"] != inserted_entries[0].token_hash
    assert inserted_entries[0].token_hash == auth_router._hash_reset_token(sent["token"])


def test_reset_password_returns_400_for_invalid_token(monkeypatch) -> None:
    _patch_query_fields(monkeypatch)

    async def fake_find_one(*args, **kwargs):
        return None

    monkeypatch.setattr(auth_router.PasswordReset, "find_one", fake_find_one)
    client = TestClient(_build_app())

    response = client.post(
        "/auth/reset-password",
        json={"token": "missing", "new_password": "StrongPass1!"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid or expired token"


def test_reset_password_returns_400_for_expired_token(monkeypatch) -> None:
    _patch_query_fields(monkeypatch)
    expired_entry = _FakeResetEntry(
        email="neo@test.dev",
        token_hash=auth_router._hash_reset_token("expired"),
        expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
    )

    async def fake_find_one(*args, **kwargs):
        return expired_entry

    monkeypatch.setattr(auth_router.PasswordReset, "find_one", fake_find_one)
    client = TestClient(_build_app())

    response = client.post(
        "/auth/reset-password",
        json={"token": "expired", "new_password": "StrongPass1!"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid or expired token"


def test_reset_password_returns_404_when_user_missing(monkeypatch) -> None:
    _patch_query_fields(monkeypatch)
    active_entry = _FakeResetEntry(
        email="neo@test.dev",
        token_hash=auth_router._hash_reset_token("active"),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
    )

    async def fake_reset_find_one(*args, **kwargs):
        return active_entry

    async def fake_user_find_one(*args, **kwargs):
        return None

    monkeypatch.setattr(auth_router.PasswordReset, "find_one", fake_reset_find_one)
    monkeypatch.setattr(auth_router.User, "find_one", fake_user_find_one)
    client = TestClient(_build_app())

    response = client.post(
        "/auth/reset-password",
        json={"token": "active", "new_password": "StrongPass1!"},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "User not found"


def test_reset_password_updates_user_and_deletes_reset_token(monkeypatch) -> None:
    _patch_query_fields(monkeypatch)
    active_entry = _FakeResetEntry(
        email="neo@test.dev",
        token_hash=auth_router._hash_reset_token("active"),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
    )
    user = _FakeUser(email="neo@test.dev", hashed_password="old-hash")

    async def fake_reset_find_one(*args, **kwargs):
        return active_entry

    async def fake_user_find_one(*args, **kwargs):
        return user

    monkeypatch.setattr(auth_router.PasswordReset, "find_one", fake_reset_find_one)
    monkeypatch.setattr(auth_router.User, "find_one", fake_user_find_one)
    monkeypatch.setattr(auth_router, "get_password_hash", lambda pwd: f"hashed::{pwd}")
    client = TestClient(_build_app())

    response = client.post(
        "/auth/reset-password",
        json={"token": "active", "new_password": "StrongPass1!"},
    )
    assert response.status_code == 200
    assert response.json()["message"] == "Password updated successfully"
    assert user.hashed_password == "hashed::StrongPass1!"
    assert user.saved is True
    assert active_entry.deleted is True


def test_reset_password_accepts_deep_link_token(monkeypatch) -> None:
    _patch_query_fields(monkeypatch)
    active_entry = _FakeResetEntry(
        email="neo@test.dev",
        token_hash=auth_router._hash_reset_token("active-token"),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
    )
    user = _FakeUser(email="neo@test.dev", hashed_password="old-hash")

    async def fake_reset_find_one(condition, *args, **kwargs):
        assert condition == ("token_hash", auth_router._hash_reset_token("active-token"))
        return active_entry

    async def fake_user_find_one(*args, **kwargs):
        return user

    monkeypatch.setattr(auth_router.PasswordReset, "find_one", fake_reset_find_one)
    monkeypatch.setattr(auth_router.User, "find_one", fake_user_find_one)
    monkeypatch.setattr(auth_router, "get_password_hash", lambda pwd: f"hashed::{pwd}")
    client = TestClient(_build_app())

    response = client.post(
        "/auth/reset-password",
        json={
            "token": "  omnisource://reset-password?token=active-token \n",
            "new_password": "StrongPass1!",
        },
    )
    assert response.status_code == 200
    assert response.json()["message"] == "Password updated successfully"
    assert user.saved is True


def test_reset_password_accepts_naive_expiration_datetime(monkeypatch) -> None:
    _patch_query_fields(monkeypatch)
    # naive datetime branch should be interpreted as UTC and still work
    active_entry = _FakeResetEntry(
        email="neo@test.dev",
        token_hash=auth_router._hash_reset_token("naive"),
        expires_at=datetime.now() + timedelta(minutes=5),
    )
    user = _FakeUser(email="neo@test.dev", hashed_password="old-hash")

    async def fake_reset_find_one(*args, **kwargs):
        return active_entry

    async def fake_user_find_one(*args, **kwargs):
        return user

    monkeypatch.setattr(auth_router.PasswordReset, "find_one", fake_reset_find_one)
    monkeypatch.setattr(auth_router.User, "find_one", fake_user_find_one)
    monkeypatch.setattr(auth_router, "get_password_hash", lambda pwd: f"hashed::{pwd}")
    client = TestClient(_build_app())

    response = client.post(
        "/auth/reset-password",
        json={"token": "naive", "new_password": "StrongPass1!"},
    )
    assert response.status_code == 200
    assert user.saved is True


def test_login_returns_429_when_rate_limited(monkeypatch) -> None:
    _patch_query_fields(monkeypatch)

    async def fake_find_one(*args, **kwargs):
        return None

    async def always_limited(*args, **kwargs):
        return False

    monkeypatch.setattr(auth_router.User, "find_one", fake_find_one)
    monkeypatch.setattr(auth_router, "_consume_rate_limit", always_limited)
    client = TestClient(_build_app())

    response = client.post(
        "/auth/login",
        data={"username": "neo@test.dev", "password": "StrongPass1!"},
    )
    assert response.status_code == 429
    assert "Too many login attempts" in response.json()["detail"]


def test_forgot_password_returns_429_when_rate_limited(monkeypatch) -> None:
    _patch_query_fields(monkeypatch)

    async def always_limited(*args, **kwargs):
        return False

    monkeypatch.setattr(auth_router, "_consume_rate_limit", always_limited)
    client = TestClient(_build_app())

    response = client.post("/auth/forgot-password", json={"email": "neo@test.dev"})
    assert response.status_code == 429
    assert "Too many password reset attempts" in response.json()["detail"]
