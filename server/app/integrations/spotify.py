import httpx
import base64
import asyncio
import time
from app.integrations.base import BaseIntegration
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_MUSIC_QUERY_GENRES = {
    "ambient",
    "classical",
    "country",
    "dance",
    "electronic",
    "hip-hop",
    "indie",
    "jazz",
    "k-pop",
    "metal",
    "pop",
    "punk",
    "r&b",
    "rap",
    "rock",
    "soul",
    "synthwave",
}


class SpotifyClient(BaseIntegration):
    def __init__(self):
        super().__init__("https://api.spotify.com/v1")
        self.token_url = "https://accounts.spotify.com/api/token"
        self._access_token = None
        self._token_expires_at = 0.0
        self._token_lock = asyncio.Lock()

    def _token_is_valid(self) -> bool:
        if not self._access_token:
            return False
        # refresh slightly before actual expiration
        return time.time() < (self._token_expires_at - 30)

    async def _get_token(self):
        auth_string = f"{settings.SPOTIFY_CLIENT_ID}:{settings.SPOTIFY_CLIENT_SECRET}"
        auth_base64 = base64.b64encode(auth_string.encode()).decode()
        headers = {"Authorization": f"Basic {auth_base64}", "Content-Type": "application/x-www-form-urlencoded"}
        data = {"grant_type": "client_credentials"}

        for attempt in range(3):
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        self.token_url,
                        headers=headers,
                        data=data,
                        timeout=8.0,
                    )
                if response.status_code == 200:
                    payload = response.json()
                    self._access_token = payload.get("access_token")
                    expires_in = int(payload.get("expires_in", 3600))
                    self._token_expires_at = time.time() + max(60, expires_in)
                    return
            except Exception:
                pass
            await asyncio.sleep(0.25 * (attempt + 1))

        logger.warning("Spotify token request failed")
        self._access_token = None
        self._token_expires_at = 0.0

    async def _ensure_token(self, force_refresh: bool = False) -> None:
        if not force_refresh and self._token_is_valid():
            return
        async with self._token_lock:
            if not force_refresh and self._token_is_valid():
                return
            await self._get_token()

    async def _get_artists(self, ids: list[str], headers: dict[str, str]) -> dict[str, dict]:
        unique_ids = list(dict.fromkeys([artist_id for artist_id in ids if artist_id]))
        if not unique_ids:
            return {}

        result: dict[str, dict] = {}
        for index in range(0, len(unique_ids), 50):
            chunk = unique_ids[index : index + 50]
            payload = await self._get(
                "/artists",
                params={"ids": ",".join(chunk)},
                headers=headers,
            )
            if not isinstance(payload, dict):
                continue
            for artist in payload.get("artists", []) or []:
                if isinstance(artist, dict) and artist.get("id"):
                    result[str(artist["id"])] = artist
        return result

    @staticmethod
    def _query_genres(query: str) -> list[str]:
        normalized = query.lower().replace("genre:", " ")
        tokens = {
            token.strip(" ,.;:/\\|()[]{}")
            for token in normalized.replace("_", " ").split()
        }
        return sorted(token for token in tokens if token in _MUSIC_QUERY_GENRES)

    async def _enrich_track_genres(
        self,
        payload: dict,
        *,
        query: str,
        headers: dict[str, str],
    ) -> dict:
        tracks = payload.get("tracks")
        items = tracks.get("items", []) if isinstance(tracks, dict) else []
        if not items:
            return payload

        artist_ids: list[str] = []
        for track in items:
            if not isinstance(track, dict):
                continue
            for artist in track.get("artists", []) or []:
                if isinstance(artist, dict) and artist.get("id"):
                    artist_ids.append(str(artist["id"]))

        artists_by_id = await self._get_artists(artist_ids, headers)
        seed_genres = self._query_genres(query)
        for track in items:
            if not isinstance(track, dict):
                continue
            genres: list[str] = []
            for artist in track.get("artists", []) or []:
                artist_id = artist.get("id") if isinstance(artist, dict) else None
                artist_payload = artists_by_id.get(str(artist_id))
                if not artist_payload:
                    continue
                genres.extend(
                    str(genre).strip().lower()
                    for genre in artist_payload.get("genres", []) or []
                    if str(genre).strip()
                )
            track["_artist_genres"] = list(dict.fromkeys(genres))[:8]
            track["_seed_query_genres"] = seed_genres
        return payload

    async def search_tracks(
        self,
        query: str,
        offset: int = 0,
        limit: int = 20,
    ):
        await self._ensure_token()
        if not self._access_token:
            return {"tracks": {"items": []}}

        headers = {"Authorization": f"Bearer {self._access_token}"}
        params = {
            "q": query,
            "type": "track",
            "limit": max(1, min(limit, 50)),
            "offset": max(0, offset),
            "market": "US",
        }
        res = await self._get("/search", params=params, headers=headers)

        # token may expire or request may fail transiently
        if not res:
            await self._ensure_token(force_refresh=True)
            if not self._access_token:
                return {"tracks": {"items": []}}
            headers = {"Authorization": f"Bearer {self._access_token}"}
            res = await self._get("/search", params=params, headers=headers)
        if isinstance(res, dict):
            return await self._enrich_track_genres(res, query=query, headers=headers)
        return {"tracks": {"items": []}}
