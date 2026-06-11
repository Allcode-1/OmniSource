from dataclasses import dataclass
from typing import Dict

@dataclass
class TagMapping:
    tmdb_keyword: str
    spotify_genre: str
    google_books_subject: str

MASTER_TAGS: Dict[str, TagMapping] = {
    # main ganres
    "cyberpunk": TagMapping("cyberpunk", "synthwave", "fiction+cyberpunk"),
    "horror": TagMapping("horror", "horror", "horror"),
    "comedy": TagMapping("comedy", "comedy", "humor"),
    "sci-fi": TagMapping("science fiction", "ambient", "fiction+science+fiction"),
    "fantasy": TagMapping("fantasy", "soundtrack", "fiction+fantasy"),
    "romance": TagMapping("romance", "romance", "romance+fiction"),
    "thriller": TagMapping("thriller", "crime", "thriller+fiction"),
    "mystery": TagMapping("mystery", "mystery", "detective+fiction"),
    "drama": TagMapping("drama", "acoustic", "drama"),
    "action": TagMapping("action", "rock", "adventure+fiction"),
    "adventure": TagMapping("adventure", "rock", "adventure+fiction"),
    "animation": TagMapping("animation", "pop", "animation"),
    "family": TagMapping("family", "pop", "family"),
    "documentary": TagMapping("documentary", "classical", "documentary"),
    "biography": TagMapping("biography", "classical", "biography"),
    "musical": TagMapping("musical", "show-tunes", "music"),
    
    # atmosphere and style
    "noir": TagMapping("film noir", "jazz", "detective"),
    "post-apocalyptic": TagMapping("post-apocalyptic", "industrial", "dystopian"),
    "dystopian": TagMapping("dystopian", "industrial", "dystopian+fiction"),
    "western": TagMapping("western", "country", "western+fiction"),
    "anime": TagMapping("anime", "j-pop", "manga"),
    "superhero": TagMapping("superhero", "power+metal", "comics"),
    "space": TagMapping("space", "space+ambient", "astronomy+fiction"),
    "cyber": TagMapping("hacker", "techno", "technology"),
    "medieval": TagMapping("medieval", "medieval", "history+europe"),
    "steampunk": TagMapping("steampunk", "victorian", "steampunk+fiction"),
    "urban": TagMapping("urban", "hip-hop", "urban+fiction"),
    "detective": TagMapping("detective", "jazz", "detective+fiction"),
    "spy": TagMapping("spy", "electronic", "spy+fiction"),
    "heist": TagMapping("heist", "funk", "crime+fiction"),
    "courtroom": TagMapping("courtroom", "classical", "legal+thriller"),
    "martial-arts": TagMapping("martial arts", "rock", "martial+arts"),
    "survival": TagMapping("survival", "ambient", "survival"),
    "gothic": TagMapping("gothic", "goth", "gothic+fiction"),
    "vampire": TagMapping("vampire", "goth", "vampire+fiction"),
    "zombie": TagMapping("zombie", "metal", "zombie+fiction"),

    # mood
    "dark": TagMapping("dark", "dark+ambient", "gothic"),
    "chill": TagMapping("relax", "chill", "self-help"),
    "epic": TagMapping("epic", "orchestral", "heroic+fantasy"),
    "retro": TagMapping("80s", "80s", "history+20th+century"),
    "sad": TagMapping("sad", "sad", "psychology"),
    "mind-bending": TagMapping("psychological", "psychedelic", "philosophy"),
    "psychological": TagMapping("psychological thriller", "psychedelic", "psychology"),
    "surreal": TagMapping("surreal", "psychedelic", "surrealism"),
    "dreamy": TagMapping("dream", "ambient", "dreams"),
    "lofi": TagMapping("indie", "lo-fi", "poetry"),
    "melancholy": TagMapping("melancholy", "sad", "literary+fiction"),
    "uplifting": TagMapping("feel good", "happy", "inspiration"),
    "cozy": TagMapping("cozy", "acoustic", "cozy+mystery"),
    "tense": TagMapping("suspense", "electronic", "suspense"),
    "weird": TagMapping("weird", "experimental", "weird+fiction"),
    
    # another
    "crime": TagMapping("crime", "hip-hop", "true+crime"),
    "history": TagMapping("history", "classical", "biography"),
    "war": TagMapping("war", "military", "military+history"),
    "magic": TagMapping("magic", "new+age", "occult"),
    "mythology": TagMapping("mythology", "folk", "mythology"),
    "folklore": TagMapping("folklore", "folk", "folklore"),
    "occult": TagMapping("occult", "dark+ambient", "occult"),
    "science": TagMapping("science", "ambient", "science"),
    "technology": TagMapping("technology", "techno", "technology"),
    "politics": TagMapping("politics", "spoken-word", "politics"),
    "travel": TagMapping("travel", "world-music", "travel"),
    "nature": TagMapping("nature", "ambient", "nature"),
    "sports": TagMapping("sports", "rock", "sports"),
    "medical": TagMapping("medical", "classical", "medical"),
    "food": TagMapping("food", "jazz", "cooking"),
    "art": TagMapping("art", "indie", "art"),
    "philosophy": TagMapping("philosophy", "ambient", "philosophy"),
    "coming-of-age": TagMapping("coming of age", "indie", "coming+of+age"),
    "slice-of-life": TagMapping("slice of life", "indie", "slice+of+life"),
    "satire": TagMapping("satire", "comedy", "satire"),
    "paranormal": TagMapping("paranormal", "dark+ambient", "paranormal")
}

def get_tag_queries(tag_name: str) -> TagMapping:
    # retunrs tag mapping or def tag if nothing found
    return MASTER_TAGS.get(
        tag_name.lower(), 
        TagMapping(tag_name, tag_name, tag_name)
    )
