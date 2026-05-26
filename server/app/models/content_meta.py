from beanie import Document, Indexed
from datetime import datetime, timezone
from typing import List, Annotated, Optional
from pydantic import Field

class ContentMetadata(Document):
    content_key: Annotated[Optional[str], Indexed(unique=True, sparse=True)] = None
    ext_id: Annotated[str, Indexed()]
    type: Annotated[str, Indexed()]  # movie, music, book
    title: str
    subtitle: Optional[str] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    rating: float = 0.0
    release_date: Optional[str] = None
    genres: List[str] = Field(default_factory=list)
    features_vector: List[float] = Field(default_factory=list)
    vector_dim: Optional[int] = None
    vector_model: Optional[str] = None

    class Settings:
        name = "content_metadata"

class Playlist(Document):
    user_id: Annotated[str, Indexed()]
    title: str
    description: Optional[str] = None
    items: List[str] = Field(default_factory=list)
    is_public: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "playlists"
