from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
from app.core.config import settings
from app.core.logging import get_logger
from app.models.user import User
from app.models.content_meta import ContentMetadata, Playlist
from app.models.interaction import Interaction
from app.models.auth import PasswordReset, RefreshSession

logger = get_logger(__name__)

async def init_db():
    client = AsyncIOMotorClient(settings.MONGODB_URL)
    await init_beanie(
        database=client.get_default_database(),
        document_models=[
            User,
            ContentMetadata,
            Interaction,
            Playlist,
            PasswordReset,
            RefreshSession,
        ]
    )
    logger.info("MongoDB initialized")
