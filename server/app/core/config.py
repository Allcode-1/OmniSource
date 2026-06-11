from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str
    MONGODB_URL: str
    REDIS_URL: str | None = None
    REDIS_ENABLED: bool = True
    REDIS_CONNECT_TIMEOUT_SECONDS: float = 2.0
    REDIS_SOCKET_TIMEOUT_SECONDS: float = 2.0
    REDIS_OPERATION_TIMEOUT_SECONDS: float = 2.5
    SLOW_REQUEST_THRESHOLD_MS: float = 2000.0
    ML_VECTOR_INDEX_ENABLED: bool = False
    ML_VECTOR_INDEX_TTL_SECONDS: int = 600
    ML_VECTOR_INDEX_MAX_ITEMS: int = 0
    ML_VECTOR_BACKEND: str = "hash"
    ML_VECTOR_SEARCH_MULTIPLIER: int = 120
    ML_EVAL_HOLDOUT_MIN_POSITIVES: int = 2
    ML_EVENT_WEIGHT_VIEW: float = 0.2
    ML_EVENT_WEIGHT_OPEN_DETAIL: float = 0.5
    ML_EVENT_WEIGHT_DWELL_TIME: float = 0.3
    ML_EVENT_WEIGHT_SEARCH: float = 0.1
    ML_EVENT_WEIGHT_PREVIEW_OPEN: float = 0.65
    ML_EVENT_WEIGHT_PREVIEW_PLAY: float = 1.15
    ML_EVENT_WEIGHT_EXTERNAL_OPEN: float = 0.55
    ML_EVENT_WEIGHT_LIKE: float = 1.0
    ML_EVENT_WEIGHT_PLAYLIST_ADD: float = 0.8
    ML_HYBRID_SIMILARITY_WEIGHT: float = 0.78
    ML_HYBRID_RATING_WEIGHT: float = 0.14
    ML_HYBRID_GENRE_WEIGHT: float = 0.08
    ML_INTEREST_SIMILARITY_WEIGHT: float = 0.8
    ML_INTEREST_RATING_WEIGHT: float = 0.12
    ML_INTEREST_TAG_WEIGHT: float = 0.08
    CACHE_WARMUP_TAG_LIMIT: int = 30
    CACHE_WARMUP_USER_LIMIT: int = 500
    AUTH_LOGIN_RATE_LIMIT_ATTEMPTS: int = 12
    AUTH_LOGIN_RATE_LIMIT_WINDOW_SECONDS: int = 300
    AUTH_PASSWORD_RESET_RATE_LIMIT_ATTEMPTS: int = 5
    AUTH_PASSWORD_RESET_RATE_LIMIT_WINDOW_SECONDS: int = 900

    IMAGE_PROXY_CACHE_TTL_SECONDS: int = 3600
    IMAGE_PROXY_CACHE_MAX_ITEMS: int = 500
    IMAGE_PROXY_MAX_BYTES_PER_ITEM: int = 5 * 1024 * 1024
    IMAGE_PROXY_CACHE_MAX_TOTAL_BYTES: int = 64 * 1024 * 1024
    IMAGE_PROXY_MAX_REDIRECTS: int = 4
    AUTH_JWT_ALGORITHM: str = "RS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    AUTH_JWT_PRIVATE_KEY_PATH: Path = Path("certs/private.pem")
    AUTH_JWT_PUBLIC_KEY_PATH: Path = Path("certs/public.pem")
    AUTH_JWT_ALLOW_EPHEMERAL_KEYS: bool = True
    LOG_LEVEL: str = "INFO"

    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ]
    CORS_ALLOW_CREDENTIALS: bool = True

    SMTP_HOST: str
    SMTP_PORT: int
    SMTP_USER: str
    SMTP_PASSWORD: str
    EMAILS_FROM_EMAIL: str

    STOP_WORDS_TITLES: list[str] = [
        "white noise",
        "baby sleep",
        "relaxing sounds",
        "taras bulba",
        "rapeman",
    ]
    STOP_WORDS_SUBTITLES: list[str] = ["dream supplier"]
    
    TMDB_API_KEY: str
    SPOTIFY_CLIENT_ID: str
    SPOTIFY_CLIENT_SECRET: str
    SPOTIFY_PROXY_URL: str | None = None
    GOOGLE_BOOKS_API_KEY: str

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
