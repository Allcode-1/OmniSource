from beanie import Document, Indexed
from pydantic import EmailStr, Field
from typing import List, Annotated

class User(Document):
    username: Annotated[str, Indexed(unique=True)]
    email: Annotated[EmailStr, Indexed(unique=True)]
    hashed_password: str
    interests: List[str] = Field(default_factory=list)
    is_onboarding_completed: bool = False
    ranking_variant: str = "hybrid_ml"
    token_version: int = 0
    is_active: bool = True
    role: str = "user"

    class Settings:
        name = "users"
