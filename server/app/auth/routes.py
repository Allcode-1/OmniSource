import hashlib
import secrets
import time
from datetime import datetime, timedelta, timezone
from threading import Lock
from urllib.parse import parse_qs, unquote, urlparse

from beanie.exceptions import CollectionWasNotInitialized
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from jose import JWTError

from app.auth import utils as auth_utils
from app.auth.dependencies import require_admin
from app.auth.schemas import (
    ForgotPassword,
    RefreshTokenRequest,
    ResetPassword,
    TokenPair,
    UserCreate,
    UserRead,
)
from app.auth.tokens import create_access_token, create_refresh_token
from app.core.config import settings
from app.core.email import send_reset_password_email
from app.core.logging import get_logger
from app.models.auth import PasswordReset, RefreshSession
from app.models.user import User

router = APIRouter(prefix="/auth", tags=["JWT based auth"])
logger = get_logger(__name__)
_RATE_LIMIT_LOCK = Lock()
_RATE_LIMIT_BUCKETS: dict[str, tuple[int, float]] = {}

# Compatibility aliases for existing tests and older imports.
verify_password = auth_utils.validate_password
get_password_hash = auth_utils.hash_password


def _normalize_reset_token(raw_token: str) -> str:
    token = unquote((raw_token or "").strip()).strip('"').strip("'")
    if not token:
        return ""

    parsed = urlparse(token)
    if parsed.scheme and parsed.query:
        query_token = parse_qs(parsed.query).get("token", [""])[0].strip()
        if query_token:
            token = query_token

    return token.replace(" ", "").replace("\n", "").replace("\r", "")


def _hash_reset_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def _extract_client_ip(request: Request) -> str:
    forwarded = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
    if forwarded:
        return forwarded
    return request.client.host if request.client else "unknown"


async def _consume_rate_limit(
    scope: str,
    identifier: str,
    max_attempts: int,
    window_seconds: int,
) -> bool:
    if max_attempts <= 0 or window_seconds <= 0:
        return True

    key = f"ratelimit:{scope}:{identifier}"
    now = time.monotonic()
    with _RATE_LIMIT_LOCK:
        current_count, reset_at = _RATE_LIMIT_BUCKETS.get(key, (0, now + window_seconds))
        if now >= reset_at:
            current_count = 0
            reset_at = now + window_seconds
        if current_count >= max_attempts:
            _RATE_LIMIT_BUCKETS[key] = (current_count, reset_at)
            return False
        _RATE_LIMIT_BUCKETS[key] = (current_count + 1, reset_at)
        return True


def _issue_access_token(user: User) -> str:
    token_version = int(getattr(user, "token_version", 0))
    try:
        return create_access_token(user.id, token_version=token_version)
    except TypeError:
        return create_access_token(user.id)


async def _persist_refresh_session(
    *,
    user: User,
    jti: str,
    expires_at: datetime,
) -> None:
    try:
        refresh_session = RefreshSession(
            jti=jti,
            user_id=str(user.id),
            expires_at=expires_at,
        )
        await refresh_session.insert()
    except CollectionWasNotInitialized:
        logger.warning("RefreshSession collection is not initialized; skipping session insert")


async def _issue_token_pair(user: User) -> TokenPair:
    access_token = _issue_access_token(user)
    refresh_token, refresh_jti, refresh_expires_at = create_refresh_token(user)
    await _persist_refresh_session(
        user=user,
        jti=refresh_jti,
        expires_at=refresh_expires_at,
    )
    return TokenPair(
        access_token=access_token,
        refresh_token=refresh_token,
        user=UserRead.model_validate(user),
    )


def _invalid_token() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid token",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


async def _decode_refresh_payload(refresh_token: str) -> dict:
    try:
        payload = auth_utils.decode_jwt(refresh_token)
    except JWTError as exc:
        raise _invalid_token() from exc

    if payload.get("type") != "refresh" or not payload.get("jti"):
        raise _invalid_token()
    return payload


async def _get_valid_refresh_session(payload: dict) -> RefreshSession:
    jti = payload.get("jti")
    if not jti:
        raise _invalid_token()

    refresh_session = await RefreshSession.find_one(RefreshSession.jti == jti)
    if refresh_session is None:
        raise _invalid_token()
    if refresh_session.revoked_at is not None:
        raise _invalid_token()
    if _utc(refresh_session.expires_at) < datetime.now(timezone.utc):
        raise _invalid_token()
    return refresh_session


@router.post("/register", response_model=TokenPair)
async def register(user_in: UserCreate):
    email = str(user_in.email).strip().lower()
    username = user_in.username.strip()
    if await User.find_one(User.email == email):
        raise HTTPException(status_code=400, detail="Email already registered")
    if hasattr(User, "username") and await User.find_one(User.username == username):
        raise HTTPException(status_code=409, detail="Username already exists")

    user_kwargs = {
        "username": username,
        "email": email,
        "hashed_password": get_password_hash(user_in.password),
        "interests": user_in.interests,
        "is_onboarding_completed": False,
        "ranking_variant": user_in.ranking_variant,
        "is_active": True,
        "role": "user",
    }
    try:
        new_user = User(**user_kwargs)
    except TypeError:
        legacy_keys = {
            "username",
            "email",
            "hashed_password",
            "interests",
            "is_onboarding_completed",
        }
        new_user = User(**{key: value for key, value in user_kwargs.items() if key in legacy_keys})
    await new_user.insert()
    logger.info("Registered new user id=%s email=%s", new_user.id, new_user.email)
    return await _issue_token_pair(new_user)


@router.post("/login", response_model=TokenPair)
async def login(request: Request, form_data: OAuth2PasswordRequestForm = Depends()):
    email = (form_data.username or "").strip().lower()
    client_ip = _extract_client_ip(request)
    can_proceed_email = await _consume_rate_limit(
        "login_email",
        email or "unknown",
        settings.AUTH_LOGIN_RATE_LIMIT_ATTEMPTS,
        settings.AUTH_LOGIN_RATE_LIMIT_WINDOW_SECONDS,
    )
    can_proceed_ip = await _consume_rate_limit(
        "login_ip",
        client_ip,
        settings.AUTH_LOGIN_RATE_LIMIT_ATTEMPTS,
        settings.AUTH_LOGIN_RATE_LIMIT_WINDOW_SECONDS,
    )
    if not (can_proceed_email and can_proceed_ip):
        raise HTTPException(status_code=429, detail="Too many login attempts. Try again later.")

    user = await User.find_one(User.email == email)
    if not user or not verify_password(form_data.password, user.hashed_password):
        logger.warning("Failed login attempt for email=%s", email)
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    if not getattr(user, "is_active", True):
        raise HTTPException(status_code=403, detail="User inactive")

    return await _issue_token_pair(user)


@router.post("/logout")
async def logout(payload: RefreshTokenRequest):
    token_payload = await _decode_refresh_payload(payload.refresh_token)
    refresh_session = await _get_valid_refresh_session(token_payload)
    refresh_session.revoked_at = datetime.now(timezone.utc)
    await refresh_session.save()
    return {"message": "Logged out"}


@router.get("/users", response_model=list[UserRead])
async def get_all_users(_: User = Depends(require_admin)):
    return await User.find_all().to_list()


@router.post("/refresh", response_model=TokenPair)
async def refresh_access_token(payload: RefreshTokenRequest):
    token_payload = await _decode_refresh_payload(payload.refresh_token)
    refresh_session = await _get_valid_refresh_session(token_payload)

    user_id = token_payload.get("sub")
    if not user_id:
        raise _invalid_token()

    user = await User.get(str(user_id))
    if user is None or not getattr(user, "is_active", True):
        raise _invalid_token()

    refresh_session.revoked_at = datetime.now(timezone.utc)
    await refresh_session.save()
    return await _issue_token_pair(user)


@router.post("/forgot-password")
async def forgot_password(
    data: ForgotPassword,
    background_tasks: BackgroundTasks,
    request: Request,
):
    email = str(data.email).strip().lower()
    client_ip = _extract_client_ip(request)
    can_proceed_email = await _consume_rate_limit(
        "reset_email",
        email,
        settings.AUTH_PASSWORD_RESET_RATE_LIMIT_ATTEMPTS,
        settings.AUTH_PASSWORD_RESET_RATE_LIMIT_WINDOW_SECONDS,
    )
    can_proceed_ip = await _consume_rate_limit(
        "reset_ip",
        client_ip,
        settings.AUTH_PASSWORD_RESET_RATE_LIMIT_ATTEMPTS,
        settings.AUTH_PASSWORD_RESET_RATE_LIMIT_WINDOW_SECONDS,
    )
    if not (can_proceed_email and can_proceed_ip):
        raise HTTPException(
            status_code=429,
            detail="Too many password reset attempts. Try again later.",
        )

    user = await User.find_one(User.email == email)
    if not user:
        logger.info("Password reset requested for non-existing email=%s", email)
        return {"message": "If the account exists, reset instructions were sent"}

    token = secrets.token_urlsafe(32)
    token_hash = _hash_reset_token(token)
    await PasswordReset.find(PasswordReset.email == email).delete()
    reset_entry = PasswordReset(
        email=email,
        token_hash=token_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
    )
    await reset_entry.insert()
    background_tasks.add_task(send_reset_password_email, email, token)

    logger.info("Password reset token issued for email=%s", email)
    return {"message": "If the account exists, reset instructions were sent"}


@router.post("/reset-password")
async def reset_password(data: ResetPassword):
    normalized_token = _normalize_reset_token(data.token)
    token_hash = _hash_reset_token(normalized_token)
    reset_entry = None
    if hasattr(PasswordReset, "token_hash"):
        reset_entry = await PasswordReset.find_one(
            PasswordReset.token_hash == token_hash,
        )
    if reset_entry is None and hasattr(PasswordReset, "token"):
        reset_entry = await PasswordReset.find_one(
            PasswordReset.token == normalized_token,
        )

    now_utc = datetime.now(timezone.utc)
    if not reset_entry:
        raise HTTPException(status_code=400, detail="Invalid or expired token")

    expires_at = reset_entry.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if expires_at < now_utc:
        raise HTTPException(status_code=400, detail="Invalid or expired token")

    user = await User.find_one(User.email == reset_entry.email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.hashed_password = get_password_hash(data.new_password)
    user.token_version = int(getattr(user, "token_version", 0)) + 1
    await user.save()
    await reset_entry.delete()
    logger.info("Password reset completed for user id=%s", user.id)
    return {"message": "Password updated successfully"}
