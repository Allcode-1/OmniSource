from app.schemas.content import UnifiedContent

class ContentMapper:
    TMDB_GENRES = {
        12: "adventure",
        14: "fantasy",
        16: "animation",
        18: "drama",
        27: "horror",
        28: "action",
        35: "comedy",
        36: "history",
        37: "western",
        53: "thriller",
        80: "crime",
        878: "sci-fi",
        9648: "mystery",
        10402: "music",
        10749: "romance",
        10751: "family",
        10752: "war",
    }

    @staticmethod
    def _first_image(images):
        if isinstance(images, list) and images:
            first = images[0]
            if isinstance(first, dict):
                return first.get("url")
        return None

    @classmethod
    def _tmdb_genres(cls, movie: dict) -> list[str]:
        raw_genres = movie.get("genres")
        if isinstance(raw_genres, list) and raw_genres:
            names = [
                item.get("name")
                for item in raw_genres
                if isinstance(item, dict) and item.get("name")
            ]
            if names:
                return [name.strip().lower() for name in names if name.strip()]

        raw_ids = movie.get("genre_ids")
        if not isinstance(raw_ids, list):
            return []
        return [
            cls.TMDB_GENRES[genre_id]
            for genre_id in raw_ids
            if genre_id in cls.TMDB_GENRES
        ]

    @classmethod
    def map_tmdb(cls, movie: dict) -> UnifiedContent:
        return UnifiedContent(
            id=f"movie_{movie.get('id')}",
            external_id=str(movie.get('id')),
            type="movie",
            title=movie.get('title', ''),
            subtitle="Movie", 
            description=movie.get('overview'),
            image_url=f"https://image.tmdb.org/t/p/w500{movie.get('poster_path')}" if movie.get('poster_path') else None,
            rating=movie.get('vote_average', 0.0),
            genres=cls._tmdb_genres(movie),
            release_date=movie.get('release_date'),
            external_url=f"https://www.themoviedb.org/movie/{movie.get('id')}" if movie.get("id") else None,
        )

    @staticmethod
    def map_google_books(book: dict) -> UnifiedContent:
        info = book.get('volumeInfo', {})
        thumbnail = info.get('imageLinks', {}).get('thumbnail')
        if isinstance(thumbnail, str):
            thumbnail = thumbnail.replace("http://", "https://")
        return UnifiedContent(
            id=f"book_{book.get('id')}",
            external_id=str(book.get('id') or ""),
            type="book",
            title=info.get('title', ''),
            subtitle=", ".join(info.get('authors', [])) if info.get('authors') else "Unknown author",
            description=info.get('description'),
            image_url=thumbnail,
            rating=info.get('averageRating', 0.0),
            genres=info.get('categories', []),
            release_date=info.get('publishedDate'),
            preview_url=info.get("previewLink"),
            external_url=info.get("infoLink") or info.get("canonicalVolumeLink"),
        )

    @staticmethod
    def map_spotify(track: dict) -> UnifiedContent:
        album = track.get("album", {})
        album_id = str(album.get("id") or "")
        album_name = album.get("name", "Unknown")
        artist_names = [a.get("name", "") for a in track.get("artists", []) if a.get("name")]
        genres = [
            str(genre).strip().lower()
            for genre in [
                *track.get("_artist_genres", []),
                *track.get("_seed_query_genres", []),
                album.get("album_type"),
                "music",
            ]
            if str(genre).strip()
        ]
        return UnifiedContent(
            id=f"music_{track.get('id')}",
            external_id=str(track.get('id') or ""),
            type="music",
            title=track.get('name', ''),
            subtitle=", ".join(artist_names),
            description=(
                f"{track.get('name', '')} by {', '.join(artist_names)}. "
                f"Album: {album_name}"
            ).strip(),
            image_url=ContentMapper._first_image(album.get("images")),
            rating=track.get('popularity', 0) / 10, # turn to 10grade rating
            genres=list(dict.fromkeys(genres))[:10],
            release_date=album.get('release_date'),
            album_id=album_id or None,
            album_title=album_name if album_name != "Unknown" else None,
            artist_name=", ".join(artist_names) or None,
            preview_url=track.get("preview_url"),
            external_url=(track.get("external_urls") or {}).get("spotify"),
        )
