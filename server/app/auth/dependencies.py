from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError

from app.auth import utils as auth_utils
from app.models.user import User

jwt = auth_utils.jwt

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
oauth2_scheme_optional = OAuth2PasswordBearer(
    tokenUrl="/auth/login",
    auto_error=False,
)


def _credentials_exception() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_token_payload(token: str = Depends(oauth2_scheme)) -> dict:
    try:
        payload = auth_utils.decode_jwt(token)
    except JWTError as exc:
        raise _credentials_exception() from exc

    if payload.get("type", "access") != "access":
        raise _credentials_exception()
    if not payload.get("sub"):
        raise _credentials_exception()
    return payload


async def get_current_user(
    token: str | None = None,
    payload: dict | None = Depends(get_current_token_payload),
) -> User:
    if token is not None:
        payload = await get_current_token_payload(token=token)
    if not isinstance(payload, dict):
        raise _credentials_exception()
    user_id = payload.get("sub")
    if not user_id:
        raise _credentials_exception()

    try:
        user = await User.get(str(user_id))
        token_version = int(payload.get("ver", 0))
    except (TypeError, ValueError) as exc:
        raise _credentials_exception() from exc

    if user is None:
        raise _credentials_exception()
    if token_version != int(getattr(user, "token_version", 0)):
        raise _credentials_exception()
    return user


async def get_current_active_user(
    user: User = Depends(get_current_user),
) -> User:
    if not getattr(user, "is_active", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User inactive",
        )
    return user


async def require_admin(
    user: User = Depends(get_current_active_user),
) -> User:
    if getattr(user, "role", "user") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    return user


async def get_optional_user(
    token: str | None = Depends(oauth2_scheme_optional),
) -> User | None:
    if not token:
        return None
    try:
        payload = auth_utils.decode_jwt(token)
        if payload.get("type", "access") != "access":
            return None
        user_id = payload.get("sub")
        if not user_id:
            return None
        token_version = int(payload.get("ver", 0))
        user = await User.get(str(user_id))
        if user is None:
            return None
        if token_version != int(getattr(user, "token_version", 0)):
            return None
        if not getattr(user, "is_active", True):
            return None
        return user
    except (JWTError, TypeError, ValueError):
        return None
