from datetime import datetime
from typing import Dict, Any, Optional, List

from pydantic import BaseModel, Field, field_validator


ALLOWED_EVENT_TYPES = {
    "view",
    "open_detail",
    "dwell_time",
    "search",
    "preview_open",
    "preview_play",
    "external_open",
    "like",
    "playlist_add",
}


class TrackEventRequest(BaseModel):
    type: str
    ext_id: Optional[str] = None
    content_type: Optional[str] = None
    weight: Optional[float] = None
    meta: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("type")
    @classmethod
    def validate_event_type(cls, value: str):
        if value not in ALLOWED_EVENT_TYPES:
            raise ValueError(f"Unsupported event type: {value}")
        return value


class TimelineItem(BaseModel):
    id: str
    type: str
    ext_id: str
    content_type: Optional[str] = None
    weight: float
    title: Optional[str] = None
    image_url: Optional[str] = None
    created_at: datetime
    meta: Dict[str, Any] = Field(default_factory=dict)


class UserStats(BaseModel):
    total_events: int
    counts_by_type: Dict[str, int] = Field(default_factory=dict)
    ctr: float = 0.0
    save_rate: float = 0.0
    avg_dwell_seconds: float = 0.0
    top_content_types: Dict[str, int] = Field(default_factory=dict)
    ab_metrics: Dict[str, Dict[str, float]] = Field(default_factory=dict)


class NotificationItem(BaseModel):
    id: str
    title: str
    body: str
    level: str = "info"
    created_at: datetime


class NotificationsResponse(BaseModel):
    items: List[NotificationItem]
