from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jose import jwt
from passlib.context import CryptContext

from app.core.config import settings
from app.core.logging import get_logger

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
logger = get_logger(__name__)

_ephemeral_key_pair: tuple[str, str] | None = None
_ephemeral_warning_logged = False


def _server_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _resolve_key_path(path: Path) -> Path:
    if path.is_absolute():
        return path
    return _server_root() / path


def _read_key(path: Path) -> str | None:
    resolved = _resolve_key_path(path)
    if not resolved.exists():
        return None
    value = resolved.read_text(encoding="utf-8").strip()
    if not value or "BEGIN" not in value:
        return None
    return value


def _generate_ephemeral_key_pair() -> tuple[str, str]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")
    return private_pem, public_pem


def _get_key_pair() -> tuple[str, str]:
    global _ephemeral_key_pair, _ephemeral_warning_logged

    private_key = _read_key(settings.AUTH_JWT_PRIVATE_KEY_PATH)
    public_key = _read_key(settings.AUTH_JWT_PUBLIC_KEY_PATH)
    if private_key and public_key:
        return private_key, public_key

    if not settings.AUTH_JWT_ALLOW_EPHEMERAL_KEYS:
        private_path = _resolve_key_path(settings.AUTH_JWT_PRIVATE_KEY_PATH)
        public_path = _resolve_key_path(settings.AUTH_JWT_PUBLIC_KEY_PATH)
        raise RuntimeError(
            "RSA JWT keys are not configured. "
            f"Expected private key at {private_path} and public key at {public_path}."
        )

    if _ephemeral_key_pair is None:
        _ephemeral_key_pair = _generate_ephemeral_key_pair()
    if not _ephemeral_warning_logged:
        logger.warning(
            "RSA JWT key files are missing or empty. Using an in-memory "
            "ephemeral RSA key pair for this process.",
        )
        _ephemeral_warning_logged = True
    return _ephemeral_key_pair


def get_private_key() -> str:
    private_key, _ = _get_key_pair()
    return private_key


def get_public_key() -> str:
    _, public_key = _get_key_pair()
    return public_key


def encode_jwt(
    payload: dict,
    *,
    expire_minutes: int | None = None,
    expire_timedelta: timedelta | None = None,
) -> str:
    to_encode = payload.copy()
    now = datetime.now(timezone.utc)
    if expire_timedelta is not None:
        expire = now + expire_timedelta
    else:
        expire = now + timedelta(
            minutes=expire_minutes or settings.ACCESS_TOKEN_EXPIRE_MINUTES,
        )
    to_encode.update(exp=expire, iat=now)
    return jwt.encode(
        to_encode,
        get_private_key(),
        algorithm=settings.AUTH_JWT_ALGORITHM,
    )


def decode_jwt(token: str | bytes) -> dict:
    return jwt.decode(
        token,
        get_public_key(),
        algorithms=[settings.AUTH_JWT_ALGORITHM],
    )


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def validate_password(password: str, hashed_password: str) -> bool:
    return pwd_context.verify(password, hashed_password)
