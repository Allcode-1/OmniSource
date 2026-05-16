import pytest
from fastapi import HTTPException
from jose import JWTError

from app.auth import dependencies as deps


class _FakeUser:
    def __init__(self, user_id: str) -> None:
        self.id = user_id


@pytest.mark.asyncio
async def test_get_optional_user_returns_none_when_token_missing() -> None:
    result = await deps.get_optional_user(token=None)
    assert result is None


@pytest.mark.asyncio
async def test_get_optional_user_returns_none_on_jwt_error(monkeypatch) -> None:
    def fake_decode(*args, **kwargs):
        raise JWTError("bad token")

    monkeypatch.setattr(deps.jwt, "decode", fake_decode)
    result = await deps.get_optional_user(token="bad")
    assert result is None


@pytest.mark.asyncio
async def test_get_optional_user_returns_user_on_valid_token(monkeypatch) -> None:
    async def fake_user_get(user_id: str):
        return _FakeUser(user_id)

    monkeypatch.setattr(deps.jwt, "decode", lambda *args, **kwargs: {"sub": "u1"})
    monkeypatch.setattr(deps.User, "get", fake_user_get)

    result = await deps.get_optional_user(token="ok")
    assert result is not None
    assert result.id == "u1"


@pytest.mark.asyncio
async def test_get_current_user_raises_401_when_sub_missing(monkeypatch) -> None:
    monkeypatch.setattr(deps.jwt, "decode", lambda *args, **kwargs: {})

    with pytest.raises(HTTPException) as error:
        await deps.get_current_user(token="no-sub")

    assert error.value.status_code == 401
    assert "Could not validate credentials" in error.value.detail


@pytest.mark.asyncio
async def test_get_current_user_returns_user_on_valid_payload(monkeypatch) -> None:
    async def fake_user_get(user_id: str):
        return _FakeUser(user_id)

    monkeypatch.setattr(deps.jwt, "decode", lambda *args, **kwargs: {"sub": "user-42"})
    monkeypatch.setattr(deps.User, "get", fake_user_get)

    user = await deps.get_current_user(token="valid")
    assert user.id == "user-42"


@pytest.mark.asyncio
async def test_get_current_user_raises_401_when_user_not_found(monkeypatch) -> None:
    async def fake_user_get(user_id: str):
        return None

    monkeypatch.setattr(deps.jwt, "decode", lambda *args, **kwargs: {"sub": "missing"})
    monkeypatch.setattr(deps.User, "get", fake_user_get)

    with pytest.raises(HTTPException) as error:
        await deps.get_current_user(token="valid")

    assert error.value.status_code == 401


@pytest.mark.asyncio
async def test_get_optional_user_returns_none_when_sub_missing(monkeypatch) -> None:
    monkeypatch.setattr(deps.jwt, "decode", lambda *args, **kwargs: {"sub": ""})
    result = await deps.get_optional_user(token="x")
    assert result is None
