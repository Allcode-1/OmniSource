import pytest
from pydantic import ValidationError

from app.core.tags import get_tag_queries
from app.schemas.analytics import TrackEventRequest
from app.schemas.content import UnifiedContent
from app.schemas.user import RankingVariantUpdate, ResetPassword, UserCreate, UserUpdate


def test_get_tag_queries_returns_known_mapping() -> None:
    mapping = get_tag_queries("cyberpunk")
    assert mapping.tmdb_keyword == "cyberpunk"
    assert mapping.spotify_genre == "synthwave"
    assert mapping.google_books_subject == "fiction+cyberpunk"


def test_get_tag_queries_falls_back_to_raw_tag_for_unknown_value() -> None:
    mapping = get_tag_queries("unknown-tag")
    assert mapping.tmdb_keyword == "unknown-tag"
    assert mapping.spotify_genre == "unknown-tag"
    assert mapping.google_books_subject == "unknown-tag"


def test_user_create_trims_username_and_accepts_strong_password() -> None:
    user = UserCreate(
        username="  Neo  ",
        email="neo@test.dev",
        password="StrongPass1!",
        interests=["action"],
    )
    assert user.username == "Neo"


@pytest.mark.parametrize(
    ("password", "error_part"),
    [
        ("nouppercase1!", "uppercase"),
        ("NOLOWERCASE1!", "lowercase"),
        ("NoNumber!", "number"),
        ("NoSpecial1", "special"),
    ],
)
def test_user_create_rejects_weak_passwords(password: str, error_part: str) -> None:
    with pytest.raises(ValidationError) as error:
        UserCreate(
            username="Neo",
            email="neo@test.dev",
            password=password,
            interests=["action"],
        )
    assert error_part in str(error.value).lower()


def test_user_update_rejects_blank_username() -> None:
    with pytest.raises(ValidationError):
        UserUpdate(username="   ")


def test_reset_password_schema_rejects_invalid_password() -> None:
    with pytest.raises(ValidationError):
        ResetPassword(token="abc", new_password="weak")


def test_ranking_variant_update_rejects_unknown_value() -> None:
    with pytest.raises(ValidationError):
        RankingVariantUpdate(ranking_variant="invalid")


def test_track_event_request_rejects_unsupported_event_type() -> None:
    with pytest.raises(ValidationError):
        TrackEventRequest(type="unsupported", ext_id="x1", content_type="movie")


def test_track_event_request_accepts_preview_events() -> None:
    payload = TrackEventRequest(type="preview_play", ext_id="x1", content_type="music")
    assert payload.type == "preview_play"


def test_unified_content_alias_supports_ext_id_and_id() -> None:
    model = UnifiedContent.model_validate(
        {
            "_id": "u1",
            "ext_id": "x1",
            "type": "movie",
            "title": "Matrix",
            "subtitle": "Movie",
            "rating": 8.0,
        }
    )
    assert model.id == "u1"
    assert model.external_id == "x1"
