from app.auth import utils as auth_utils
from app.auth.tokens import create_access_token
from app.auth.utils import hash_password as get_password_hash
from app.auth.utils import validate_password as verify_password


def test_password_hash_roundtrip() -> None:
    password = "StrongPass1!"
    hashed = get_password_hash(password)

    assert hashed != password
    assert verify_password(password, hashed) is True
    assert verify_password("WrongPass1!", hashed) is False


def test_create_access_token_contains_subject_and_exp() -> None:
    token = create_access_token("user-123")
    payload = auth_utils.decode_jwt(token)

    assert payload["sub"] == "user-123"
    assert payload["type"] == "access"
    assert "exp" in payload
