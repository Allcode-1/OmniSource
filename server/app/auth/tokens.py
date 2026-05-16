from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from app.auth import utils as auth_utils
from app.core.config import settings
from app.models.user import User


def _user_subject(user_or_subject: User | str | Any) -> str:
    if isinstance(user_or_subject, User):
        return str(user_or_subject.id)
    user_id = getattr(user_or_subject, "id", None)
    if user_id is not None:
        return str(user_id)
    return str(user_or_subject)


def _user_claims(user_or_subject: User | str | Any) -> dict[str, Any]:
    claims: dict[str, Any] = {"sub": _user_subject(user_or_subject)}
    username = getattr(user_or_subject, "username", None)
    email = getattr(user_or_subject, "email", None)
    if username is not None:
        claims["username"] = username
    if email is not None:
        claims["email"] = str(email)
    return claims


def create_access_token(
    user_or_subject: User | str | Any,
    token_version: int | None = None,
) -> str:
    resolved_version = token_version
    if resolved_version is None:
        resolved_version = int(getattr(user_or_subject, "token_version", 0))
    payload = {
        **_user_claims(user_or_subject),
        "type": "access",
        "ver": int(resolved_version),
    }
    return auth_utils.encode_jwt(payload)


def create_refresh_token(
    user_or_subject: User | str | Any,
    token_version: int | None = None,
) -> tuple[str, str, datetime]:
    resolved_version = token_version
    if resolved_version is None:
        resolved_version = int(getattr(user_or_subject, "token_version", 0))
    jti = str(uuid4())
    expires_at = datetime.now(timezone.utc) + timedelta(
        days=settings.REFRESH_TOKEN_EXPIRE_DAYS,
    )
    payload = {
        **_user_claims(user_or_subject),
        "type": "refresh",
        "ver": int(resolved_version),
        "jti": jti,
    }
    token = auth_utils.encode_jwt(
        payload,
        expire_timedelta=timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )
    return token, jti, expires_at
