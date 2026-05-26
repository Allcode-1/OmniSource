import asyncio

from pymongo.errors import DuplicateKeyError
from app.core.content_keys import (
    looks_like_content_key,
    make_content_key,
    split_content_key,
)
from app.core.redis import redis_client
from app.models.content_meta import ContentMetadata, Playlist
from app.models.interaction import Interaction
from app.schemas.content import UnifiedContent
from app.ml.vectorizer import get_vectorizer
from app.core.logging import get_logger

logger = get_logger(__name__)


class LibraryService:
    @staticmethod
    def _favorites_cache_key(user_id: str, content_type: str | None) -> str:
        return f"favorites:{user_id}:{content_type or 'all'}"

    @staticmethod
    def _playlist_details_cache_key(user_id: str, playlist_id: str) -> str:
        return f"playlist_details:{user_id}:{playlist_id}"

    @staticmethod
    def _to_unified(doc: ContentMetadata) -> UnifiedContent:
        return UnifiedContent(
            id=f"{doc.type}_{doc.ext_id}",
            external_id=doc.ext_id,
            type=doc.type,
            title=doc.title,
            subtitle=doc.subtitle or doc.type.capitalize(),
            description=getattr(doc, "description", None),
            image_url=doc.image_url,
            rating=doc.rating or 0.0,
            genres=doc.genres or [],
            release_date=doc.release_date,
        )

    @staticmethod
    def _doc_ref(doc: ContentMetadata) -> str:
        return (
            getattr(doc, "content_key", None)
            or make_content_key(doc.type, doc.ext_id)
            or doc.ext_id
        )

    @staticmethod
    def _supports_metadata_content_key() -> bool:
        return hasattr(ContentMetadata, "content_key")

    @staticmethod
    def _supports_interaction_content_key() -> bool:
        return hasattr(Interaction, "content_key")

    @staticmethod
    def _supports_interaction_content_type() -> bool:
        return hasattr(Interaction, "content_type")

    async def _resolve_metadata_ref(self, ref: str) -> ContentMetadata | None:
        normalized = (ref or "").strip()
        if not normalized:
            return None

        supports_content_key = self._supports_metadata_content_key()
        if looks_like_content_key(normalized):
            ref_type, ref_ext_id = split_content_key(normalized)
            if supports_content_key:
                doc = await ContentMetadata.find_one(ContentMetadata.content_key == normalized)
                if doc is not None:
                    return doc
            if ref_type and ref_ext_id:
                return await ContentMetadata.find_one(
                    ContentMetadata.ext_id == ref_ext_id,
                    ContentMetadata.type == ref_type,
                )
            return None

        return await ContentMetadata.find_one(ContentMetadata.ext_id == normalized)

    async def _get_or_create_metadata(self, content: UnifiedContent) -> ContentMetadata | None:
        ext_id = (content.external_id or "").strip()
        if not ext_id:
            return None

        content_key = make_content_key(content.type, ext_id)
        meta = None
        supports_content_key = self._supports_metadata_content_key()
        if supports_content_key and content_key:
            meta = await ContentMetadata.find_one(ContentMetadata.content_key == content_key)
        if meta is None:
            meta = await ContentMetadata.find_one(
                ContentMetadata.ext_id == ext_id,
                ContentMetadata.type == content.type,
            )
            if (
                meta is not None
                and supports_content_key
                and content_key
                and getattr(meta, "content_key", None) != content_key
            ):
                meta.content_key = content_key
                await meta.save()

        if meta is not None:
            return meta

        vectorizer = get_vectorizer()
        vector = await asyncio.to_thread(
            vectorizer.get_embedding,
            f"{content.title} {content.description or ''}",
        )
        payload = {
            "ext_id": ext_id,
            "type": content.type,
            "title": content.title,
            "subtitle": content.subtitle,
            "description": content.description,
            "image_url": content.image_url,
            "rating": content.rating or 0.0,
            "release_date": content.release_date,
            "genres": content.genres or [],
            "features_vector": vector,
            "vector_dim": len(vector) if vector else None,
            "vector_model": getattr(vectorizer, "active_model_name", "unknown")
            if vector
            else None,
        }
        if supports_content_key and content_key:
            payload["content_key"] = content_key
        meta = ContentMetadata(**payload)
        try:
            await meta.insert()
            return meta
        except DuplicateKeyError:
            logger.info(
                "Content metadata already exists (race): type=%s ext_id=%s",
                content.type,
                ext_id,
            )
            if supports_content_key and content_key:
                return await ContentMetadata.find_one(
                    ContentMetadata.content_key == content_key,
                )
            return await ContentMetadata.find_one(
                ContentMetadata.ext_id == ext_id,
                ContentMetadata.type == content.type,
            )

    async def _invalidate_user_library_cache(
        self,
        user_id: str,
        playlist_id: str | None = None,
    ) -> None:
        await redis_client.delete_by_prefix(f"favorites:{user_id}:")
        await redis_client.delete_by_prefix(f"user_recs:{user_id}:")
        if playlist_id:
            await redis_client.delete_cache(
                self._playlist_details_cache_key(user_id, playlist_id),
            )
        else:
            await redis_client.delete_by_prefix(f"playlist_details:{user_id}:")

    async def toggle_like(self, user_id: str, content: UnifiedContent):
        ext_id = (content.external_id or "").strip()
        if not ext_id:
            return {"status": "error", "message": "Invalid content id"}
        content_key = make_content_key(content.type, ext_id)

        # 1. guarantee metadata exists in db for ML
        await self._get_or_create_metadata(content)

        # 2. check if like already exists
        existing_like = None
        if self._supports_interaction_content_key() and content_key:
            existing_like = await Interaction.find_one(
                Interaction.user_id == user_id,
                Interaction.type == "like",
                Interaction.content_key == content_key,
            )
        if existing_like is None:
            conditions = [
                Interaction.user_id == user_id,
                Interaction.ext_id == ext_id,
                Interaction.type == "like",
            ]
            if self._supports_interaction_content_type():
                conditions.append(Interaction.content_type == content.type)
            existing_like = await Interaction.find_one(*conditions)

        if existing_like:
            await existing_like.delete()
            await self._invalidate_user_library_cache(user_id)
            logger.info(
                "Removed like user=%s type=%s ext_id=%s",
                user_id,
                content.type,
                ext_id,
            )
            return {"status": "removed", "message": "Removed from favorites"}
        
        # 3. create new like with weight 1.0 (important for ml)
        interaction_payload = {
            "user_id": user_id,
            "ext_id": ext_id,
            "type": "like",
            "weight": 1.0,
        }
        if self._supports_interaction_content_key() and content_key:
            interaction_payload["content_key"] = content_key
        if self._supports_interaction_content_type():
            interaction_payload["content_type"] = content.type
        new_like = Interaction(**interaction_payload)
        await new_like.insert()
        await self._invalidate_user_library_cache(user_id)
        logger.info("Added like user=%s type=%s ext_id=%s", user_id, content.type, ext_id)
        return {"status": "added", "message": "Added to favorites"}

    async def get_user_favorites(self, user_id: str, content_type: str = None):
        cache_key = self._favorites_cache_key(user_id, content_type)
        cached = await redis_client.get_cache(cache_key)
        if isinstance(cached, list):
            return [UnifiedContent.model_validate(item) for item in cached]

        # 1. get all likes of user
        interactions = await Interaction.find(
            Interaction.user_id == user_id,
            Interaction.type == "like",
        ).sort("-created_at").to_list()

        ordered_refs: list[str] = []
        seen_refs: set[str] = set()
        for interaction in interactions:
            interaction_type = getattr(interaction, "content_type", None)
            if (
                content_type
                and interaction_type
                and interaction_type != content_type
            ):
                continue
            ref = (
                getattr(interaction, "content_key", None)
                or make_content_key(interaction_type, interaction.ext_id)
                or interaction.ext_id
            )
            if not ref or ref in seen_refs:
                continue
            seen_refs.add(ref)
            ordered_refs.append(ref)

        if not ordered_refs:
            await redis_client.set_cache(cache_key, [], expire=120)
            return []  # if no likes - return empty list

        # 2. resolve metadata by content refs (content_key first, ext_id fallback)
        favorites: list[UnifiedContent] = []
        seen_doc_refs: set[str] = set()
        for ref in ordered_refs:
            doc = await self._resolve_metadata_ref(ref)
            if doc is None:
                continue
            if content_type and doc.type != content_type:
                continue
            doc_ref = self._doc_ref(doc)
            if doc_ref in seen_doc_refs:
                continue
            seen_doc_refs.add(doc_ref)
            favorites.append(self._to_unified(doc))

        await redis_client.set_cache(
            cache_key,
            [item.model_dump(by_alias=True) for item in favorites],
            expire=120,
        )
        return favorites

    
    async def create_playlist(self, user_id: str, title: str, description: str = None):
        # create new playlist 
        clean_title = title.strip()
        if not clean_title:
            return {"status": "error", "message": "Playlist title is required"}
        playlist = Playlist(
            user_id=user_id,
            title=clean_title,
            description=description,
            items=[]  # empty list for start
        )
        await playlist.insert()
        await self._invalidate_user_library_cache(user_id)
        logger.info("Playlist created user=%s playlist_id=%s", user_id, playlist.id)
        return playlist

    async def get_user_playlists(self, user_id: str):
        # get all playlists of user
        return await Playlist.find(Playlist.user_id == user_id).to_list()

    async def update_playlist(
        self,
        user_id: str,
        playlist_id: str,
        title: str | None = None,
        description: str | None = None,
    ):
        playlist = await Playlist.get(playlist_id)
        if not playlist or playlist.user_id != user_id:
            return {"status": "error", "message": "Playlist not found"}

        if title is not None:
            clean_title = title.strip()
            if not clean_title:
                return {"status": "error", "message": "Playlist title is required"}
            playlist.title = clean_title
        if description is not None:
            playlist.description = description

        await playlist.save()
        await self._invalidate_user_library_cache(user_id, playlist_id)
        logger.info("Playlist updated user=%s playlist_id=%s", user_id, playlist_id)
        return playlist

    async def get_playlist_details(self, user_id: str, playlist_id: str):
        cache_key = self._playlist_details_cache_key(user_id, playlist_id)
        cached = await redis_client.get_cache(cache_key)
        if isinstance(cached, dict):
            return cached

        playlist = await Playlist.get(playlist_id)
        if not playlist or playlist.user_id != user_id:
            return None

        refs = [ref.strip() for ref in playlist.items if ref and ref.strip()]
        ordered_items: list[UnifiedContent] = []
        seen_doc_refs: set[str] = set()
        for item_ref in refs:
            doc = await self._resolve_metadata_ref(item_ref)
            if doc is None:
                continue
            doc_ref = self._doc_ref(doc)
            if doc_ref in seen_doc_refs:
                continue
            seen_doc_refs.add(doc_ref)
            ordered_items.append(self._to_unified(doc))

        payload = {
            "id": str(playlist.id),
            "title": playlist.title,
            "description": playlist.description,
            "items": [item.model_dump(by_alias=True) for item in ordered_items],
        }
        await redis_client.set_cache(cache_key, payload, expire=120)
        return payload

    async def add_to_playlist(self, playlist_id: str, content: UnifiedContent):
        ext_id = (content.external_id or "").strip()
        if not ext_id:
            return {"status": "error", "message": "Invalid content id"}
        content_key = make_content_key(content.type, ext_id)
        storage_ref = content_key or ext_id

        # 1. make sure content metadata exists for ml
        await self._get_or_create_metadata(content)

        # 2. find playlist and add content if not already there
        playlist = await Playlist.get(playlist_id)
        if not playlist:
            return {"status": "error", "message": "Playlist not found"}
        
        if storage_ref not in playlist.items and ext_id not in playlist.items:
            playlist.items.append(storage_ref)
            await playlist.save()
            await self._invalidate_user_library_cache(playlist.user_id, playlist_id)
            logger.info(
                "Added content_ref=%s to playlist=%s",
                storage_ref,
                playlist_id,
            )
            return {"status": "success", "message": f"Added to {playlist.title}"}
        
        return {"status": "exists", "message": "Already in playlist"}

    async def remove_from_playlist(self, user_id: str, playlist_id: str, content_ref: str):
        playlist = await Playlist.get(playlist_id)
        if not playlist or playlist.user_id != user_id:
            return {"status": "error", "message": "Playlist not found"}

        normalized_ref = (content_ref or "").strip()
        if not normalized_ref:
            return {"status": "error", "message": "Invalid content id"}

        removed = 0
        if normalized_ref in playlist.items:
            playlist.items = [item for item in playlist.items if item != normalized_ref]
            removed += 1
        elif looks_like_content_key(normalized_ref):
            _, ext_id = split_content_key(normalized_ref)
            if ext_id:
                before = len(playlist.items)
                playlist.items = [
                    item
                    for item in playlist.items
                    if item != normalized_ref and item != ext_id
                ]
                removed = before - len(playlist.items)
        else:
            # backward compatibility: remove both raw ext_id and any typed refs ending with it.
            suffix = f":{normalized_ref}"
            before = len(playlist.items)
            playlist.items = [
                item
                for item in playlist.items
                if item != normalized_ref and not item.endswith(suffix)
            ]
            removed = before - len(playlist.items)

        if removed > 0:
            await playlist.save()
            await self._invalidate_user_library_cache(user_id, playlist_id)

        return {"status": "success", "removed": removed}

    async def delete_playlist(self, user_id: str, playlist_id: str):
        playlist = await Playlist.get(playlist_id)
        if not playlist or playlist.user_id != user_id:
            return {"status": "error", "message": "Playlist not found"}
        await playlist.delete()
        await self._invalidate_user_library_cache(user_id, playlist_id)
        return {"status": "success"}
