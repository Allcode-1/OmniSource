from app.integrations.base import BaseIntegration
from app.core.config import settings

class GoogleBooksClient(BaseIntegration):
    def __init__(self):
        super().__init__("https://www.googleapis.com/books/v1")
        self.api_key = settings.GOOGLE_BOOKS_API_KEY

    async def search_books(
        self,
        query: str,
        start_index: int = 0,
        max_results: int = 10,
    ):
        params = {
            "q": query,
            "key": self.api_key,
            "maxResults": max(1, min(max_results, 40)),
            "startIndex": max(0, start_index),
            "langRestrict": "en",
        }
        return await self._get("/volumes", params=params) or {"items": []}
