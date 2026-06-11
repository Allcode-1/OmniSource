import httpx
import base64
import asyncio
import time
from app.integrations.base import BaseIntegration
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

class SpotifyClient(BaseIntegration):
    def __init__(self):
        super().__init__('https://api.spotify.com/v1')
        self.token_url = 'https://accounts.spotify.com/api/token'
        self._access_token = None
        self._token_expires_at = 0.0
        self._token_lock = asyncio.Lock()

    def _token_is_valid(self) -> bool:
        return bool(self._access_token and time.time() < (self._token_expires_at - 5))

    async def _ensure_token(self, force_refresh: bool = False) -> None:
        if not force_refresh and self._token_is_valid():
            return

        async with self._token_lock:
            if not force_refresh and self._token_is_valid():
                return

            auth_string = f"{settings.SPOTIFY_CLIENT_ID}:{settings.SPOTIFY_CLIENT_SECRET}"
            auth_base64 = base64.b64encode(auth_string.encode()).decode()
            headers = {
                "Authorization": f"Basic {auth_base64}",
                "Content-Type": "application/x-www-form-urlencoded"
            }
            data = {"grant_type": "client_credentials"}
            proxy = settings.SPOTIFY_PROXY_URL

            for attempt in range(3):
                try:
                    async with httpx.AsyncClient(proxy=proxy) as client:
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
                        self._token_expires_at = time.time() + expires_in
                        logger.info("Spotify access token updated successfully via proxy.")
                        return
                    else:
                        logger.warning(f"Spotify token API status {response.status_code}: {response.text}")
                except Exception as e:
                    logger.error(f"Spotify token generation attempt {attempt + 1} failed: {e}")
                
                await asyncio.sleep(0.5 * (attempt + 1))

            self._access_token = None
            self._token_expires_at = 0.0
            logger.error("Failed to fetch Spotify access token after 3 attempts.")

    async def _get(self, endpoint: str, params: dict = None, headers: dict = None):
        await self._ensure_token()
        if not self._access_token:
            logger.error("Skipping Spotify GET request due to missing access token.")
            return None

        url = f"{self.base_url}{endpoint}"
        proxy = settings.SPOTIFY_PROXY_URL
        
        req_headers = headers.copy() if headers else {}
        req_headers["Authorization"] = f"Bearer {self._access_token}"

        try:
            async with httpx.AsyncClient(proxy=proxy) as client:
                res = await client.get(url, params=params, headers=req_headers, timeout=10.0)
                if res.status_code == 200:
                    return res.json()
                
                if res.status_code == 401:
                    logger.warning("Spotify token expired unexpectedly, retrying with forced refresh...")
                    await self._ensure_token(force_refresh=True)
                    if self._access_token:
                        req_headers["Authorization"] = f"Bearer {self._access_token}"
                        res = await client.get(url, params=params, headers=req_headers, timeout=10.0)
                        if res.status_code == 200:
                            return res.json()

                logger.warning(f"Spotify API returned status {res.status_code} for {endpoint}")
                return None
        except Exception as e:
            logger.error(f"Spotify proxy request to {endpoint} failed: {e}")
            return None

    async def search_tracks(self, query: str, offset: int = 0, limit: int = 20) -> dict:
        if not query:
            return {"tracks": {"items": []}}

        await self._ensure_token()
        if not self._access_token:
            return {"tracks": {"items": []}}

        params = {
            "q": query,
            "type": "track",
            "offset": offset,
            "limit": limit
        }

        data = await self._get("/search", params=params)
        if not data:
            await self._ensure_token(force_refresh=True)
            if self._access_token:
                data = await self._get("/search", params=params)
        return data if data else {"tracks": {"items": []}}

    async def get_track(self, track_id: str) -> dict | None:
        if not track_id:
            return None
        return await self._get(f"/tracks/{track_id}")
