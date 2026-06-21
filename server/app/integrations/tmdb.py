import httpx
import asyncio
from typing import Dict, Any
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class TMDBClient:
    def __init__(self):
        self.api_key = settings.TMDB_API_KEY
        self.base_url = "https://api.themoviedb.org/3"
        self.headers = {
            "accept": "application/json",
            "Content-Type": "application/json",
        }

        if self.api_key and len(self.api_key) > 50:
            self.headers["Authorization"] = f"Bearer {self.api_key}"

        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(10.0, connect=3.0, read=10.0),
            limits=httpx.Limits(max_connections=30, max_keepalive_connections=15),
        )

    async def _make_request(
        self, endpoint: str, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        default_params = {"language": "en-US"}

        if self.api_key and len(self.api_key) <= 50:
            default_params["api_key"] = self.api_key

        combined_params = {**default_params, **params}
        url = f"{self.base_url}/{endpoint}"

        for attempt in range(3):
            try:
                response = await self._client.get(
                    url,
                    headers=self.headers,
                    params=combined_params,
                )
                if response.status_code == 200:
                    return response.json()

                if response.status_code in (429, 500, 502, 503, 504) and attempt < 2:
                    await asyncio.sleep(0.3 * (attempt + 1))
                    continue

                logger.warning(
                    "TMDB API non-200 endpoint=%s status=%s body=%s",
                    endpoint,
                    response.status_code,
                    response.text[:200],
                )
                break
            except Exception as exc:
                if attempt < 2:
                    await asyncio.sleep(0.3 * (attempt + 1))
                    continue
                message = str(exc).strip() or type(exc).__name__
                logger.warning(
                    "TMDB request failed endpoint=%s error=%s", endpoint, message
                )

        return {"results": []}

    async def search_movies(
        self,
        query: str,
        page: int = 1,
        year: int | None = None,
    ) -> Dict[str, Any]:
        if not query:
            return {"results": []}
        params: Dict[str, Any] = {"query": query, "page": max(1, page)}
        if year is not None:
            params["year"] = year
        return await self._make_request("search/movie", params)

    async def get_popular_movies(self, page: int = 1) -> Dict[str, Any]:
        return await self._make_request("movie/popular", {"page": max(1, page)})

    async def get_top_rated_movies(self, page: int = 1) -> Dict[str, Any]:
        return await self._make_request("movie/top_rated", {"page": max(1, page)})

    async def discover_movies(
        self,
        page: int = 1,
        year: int | None = None,
        genre_id: int | None = None,
        sort_by: str = "popularity.desc",
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {
            "page": max(1, page),
            "sort_by": sort_by,
            "vote_count.gte": 50,
        }
        if year is not None:
            params["primary_release_year"] = year
        if genre_id is not None:
            params["with_genres"] = genre_id
        return await self._make_request("discover/movie", params)

    async def get_movie_details(self, movie_id: int) -> Dict[str, Any]:
        return await self._make_request(f"movie/{movie_id}", {})

    async def get_movie_videos(self, movie_id: int) -> Dict[str, Any]:
        return await self._make_request(f"movie/{movie_id}/videos", {})

    async def close(self) -> None:
        await self._client.aclose()


tmdb_client = TMDBClient()
