from pydantic import BaseModel, ConfigDict, Field
from typing import List, Optional

class UnifiedContent(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(alias="_id")
    external_id: str = Field(alias="ext_id")
    type: str  # 'movie', 'book', or 'music'
    title: str
    subtitle: Optional[str] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    rating: Optional[float] = 0.0
    genres: List[str] = Field(default_factory=list)
    release_date: Optional[str] = None
    recommendation_reason: Optional[str] = None
    album_id: Optional[str] = None
    album_title: Optional[str] = None
    artist_name: Optional[str] = None
    preview_url: Optional[str] = None
    external_url: Optional[str] = None


class ContentPreview(BaseModel):
    content_type: str
    external_id: str
    provider: str
    preview_type: str
    title: str
    url: str
    embed_url: Optional[str] = None
    external_url: Optional[str] = None
    is_playable: bool = True


class PlaylistUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
