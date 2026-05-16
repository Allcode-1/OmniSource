from beanie import Document, Indexed
from datetime import datetime, timezone
from pydantic import Field
from typing import Annotated

class PasswordReset(Document):
    email: Annotated[str, Indexed()]
    token_hash: Annotated[str, Indexed(unique=True)]
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Annotated[datetime, Indexed(expireAfterSeconds=0)]

    class Settings:
        name = "password_resets"


class RefreshSession(Document):
    jti: Annotated[str, Indexed(unique=True)]
    user_id: Annotated[str, Indexed()]
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Annotated[datetime, Indexed(expireAfterSeconds=0)]
    revoked_at: datetime | None = None

    class Settings:
        name = "refresh_sessions"
