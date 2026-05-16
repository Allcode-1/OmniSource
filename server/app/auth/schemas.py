from datetime import datetime
import re
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from pydantic_core import core_schema


class PyObjectId(str):
    @classmethod
    def __get_pydantic_core_schema__(cls, _source_type, _handler):
        return core_schema.json_or_python_schema(
            json_schema=core_schema.str_schema(),
            python_schema=core_schema.union_schema([
                core_schema.is_instance_schema(cls),
                core_schema.chain_schema([
                    core_schema.is_instance_schema(object),
                    core_schema.no_info_plain_validator_function(str),
                ]),
            ]),
        )


class UserBase(BaseModel):
    username: str
    email: EmailStr
    interests: List[str] = Field(default_factory=list)
    is_onboarding_completed: bool = False
    ranking_variant: str = "hybrid_ml"

    @field_validator("username")
    @classmethod
    def username_not_blank(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Username cannot be empty")
        return normalized


class UserCreate(UserBase):
    password: str = Field(..., min_length=8)

    @field_validator("password")
    @classmethod
    def password_complexity(cls, value: str) -> str:
        validate_password_strength(value)
        return value


class UserRead(UserBase):
    id: PyObjectId = Field(alias="_id")
    is_active: bool = True
    role: str = "user"

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class UserUpdate(BaseModel):
    username: Optional[str] = None
    interests: Optional[List[str]] = None
    ranking_variant: Optional[str] = None

    @field_validator("username")
    @classmethod
    def update_username_not_blank(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        normalized = value.strip()
        if not normalized:
            raise ValueError("Username cannot be empty")
        return normalized

    @field_validator("ranking_variant")
    @classmethod
    def validate_optional_ranking_variant(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        validate_ranking_variant_value(value)
        return value


class OnboardingComplete(BaseModel):
    interests: List[str]


class ForgotPassword(BaseModel):
    email: EmailStr


class ResetPassword(BaseModel):
    token: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def new_password_complexity(cls, value: str) -> str:
        validate_password_strength(value)
        return value


class RankingVariantUpdate(BaseModel):
    ranking_variant: str

    @field_validator("ranking_variant")
    @classmethod
    def validate_ranking_variant(cls, value: str) -> str:
        validate_ranking_variant_value(value)
        return value


class AccessToken(BaseModel):
    access_token: str
    token_type: str = "bearer"


class RefreshToken(BaseModel):
    refresh_token: str
    token_type: str = "bearer"


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserRead | None = None


class TokenPayload(BaseModel):
    sub: str
    type: str
    ver: int = 0
    jti: str | None = None
    exp: int | datetime | None = None
    iat: int | datetime | None = None


class AccessTokenData(AccessToken):
    pass


class RefreshTokenRequest(BaseModel):
    refresh_token: str


def validate_password_strength(value: str) -> None:
    if len(value) < 8:
        raise ValueError("Password must be at least 8 characters")
    if not re.search(r"[A-Z]", value):
        raise ValueError("Password must contain at least one uppercase letter")
    if not re.search(r"[a-z]", value):
        raise ValueError("Password must contain at least one lowercase letter")
    if not re.search(r"\d", value):
        raise ValueError("Password must contain at least one number")
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', value):
        raise ValueError("Password must contain at least one special character")


def validate_ranking_variant_value(value: str) -> None:
    allowed = {"content_only", "hybrid_ml"}
    if value not in allowed:
        raise ValueError(f"ranking_variant must be one of: {', '.join(sorted(allowed))}")
