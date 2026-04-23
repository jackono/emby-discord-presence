import json
import urllib.parse
import urllib.request


OMDB_API_BASE = "https://www.omdbapi.com/"
JIKAN_API_BASE = "https://api.jikan.moe/v4/anime"


class ExternalLinksResolver:
    def __init__(self, omdb_api_key: str = "", auto_buttons: dict | None = None):
        self.omdb_api_key = str(omdb_api_key or "").strip()
        self.auto_buttons = auto_buttons or {}
        self._imdb_cache: dict[tuple[str, int | None, bool], str | None] = {}
        self._mal_cache: dict[str, str | None] = {}

    def resolve_imdb_url(self, title: str, year: int | None, is_movie: bool) -> str | None:
        title = (title or "").strip()
        if not title or not self.omdb_api_key or not self.auto_buttons.get("imdb"):
            return None

        cache_key = (title.lower(), year, is_movie)
        if cache_key in self._imdb_cache:
            return self._imdb_cache[cache_key]

        media_type = "movie" if is_movie else "series"
        params = {"t": title, "type": media_type, "apikey": self.omdb_api_key}
        if year:
            params["y"] = year

        result = None
        try:
            data = _get_json(f"{OMDB_API_BASE}?{urllib.parse.urlencode(params)}")
            imdb_id = (data or {}).get("imdbID")
            if imdb_id:
                result = f"https://www.imdb.com/title/{imdb_id}/"
        except Exception:
            result = None

        self._imdb_cache[cache_key] = result
        return result

    def resolve_mal_url(self, title: str) -> str | None:
        title = (title or "").strip()
        if not title or not self.auto_buttons.get("mal"):
            return None

        cache_key = title.lower()
        if cache_key in self._mal_cache:
            return self._mal_cache[cache_key]

        result = None
        try:
            params = {"q": title, "limit": 1}
            data = _get_json(f"{JIKAN_API_BASE}?{urllib.parse.urlencode(params)}")
            results = (data or {}).get("data") or []
            if results:
                result = results[0].get("url")
        except Exception:
            result = None

        self._mal_cache[cache_key] = result
        return result


def _get_json(url: str) -> dict | None:
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        raw = resp.read().decode("utf-8")
        return json.loads(raw) if raw else None
