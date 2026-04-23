import json
import urllib.parse
import urllib.request
from time import monotonic

from .models import PlaybackState


TMDB_API_BASE = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/w500"
ART_CACHE_TTL_SECONDS = 8 * 60 * 60


class TmdbArtworkResolver:
    def __init__(self, tmdb_config: dict | None = None):
        config = tmdb_config or {}
        self.api_key = str(config.get("api_key", "")).strip()
        self.bearer_token = str(config.get("bearer_token", "")).strip()
        self.enabled = bool(self.api_key or self.bearer_token)
        self._cache: dict[tuple, tuple[float, str | None]] = {}

    def enrich(self, playbacks: list[PlaybackState]) -> list[PlaybackState]:
        if not self.enabled:
            return playbacks

        self._cleanup_cache()
        for playback in playbacks:
            if playback.artwork_url or playback.media_type == "Track":
                continue
            playback.artwork_url = self.resolve(playback)
        return playbacks

    def resolve(self, playback: PlaybackState) -> str | None:
        cache_key = (
            playback.media_type,
            (playback.tmdb_id or "").strip(),
            (playback.series or "").strip().lower(),
            (playback.title or "").strip().lower(),
            playback.year,
            playback.season,
        )
        cached = self._cache.get(cache_key)
        if cached and monotonic() - cached[0] < ART_CACHE_TTL_SECONDS:
            return cached[1]

        result = self._resolve_uncached(playback)
        self._cache[cache_key] = (monotonic(), result)
        return result

    def _resolve_uncached(self, playback: PlaybackState) -> str | None:
        if playback.media_type == "Movie":
            return self._resolve_movie(playback)
        if playback.media_type == "Episode":
            return self._resolve_episode(playback)
        return None

    def _resolve_movie(self, playback: PlaybackState) -> str | None:
        tmdb_id = playback.tmdb_id or self._search_tmdb_id("movie", playback.title, playback.year)
        if not tmdb_id:
            return None
        return self._fetch_image_from_path(f"/movie/{tmdb_id}/images")

    def _resolve_episode(self, playback: PlaybackState) -> str | None:
        lookup_title = playback.series or playback.title
        tmdb_id = playback.tmdb_id or self._search_tmdb_id("tv", lookup_title, playback.year)
        if not tmdb_id:
            return None

        season = playback.season or 1
        return (
            self._fetch_image_from_path(f"/tv/{tmdb_id}/season/{season}/images")
            or self._fetch_image_from_path(f"/tv/{tmdb_id}/images")
        )

    def _search_tmdb_id(self, media_kind: str, title: str, year: int | None) -> str | None:
        title = (title or "").strip()
        if not title:
            return None

        params = {"query": title}
        if year:
            if media_kind == "movie":
                params["year"] = year
            elif media_kind == "tv":
                params["first_air_date_year"] = year

        data = self._get_json(f"/search/{media_kind}", params=params)
        results = (data or {}).get("results") or []
        first = results[0] if results else None
        if not first:
            return None
        value = first.get("id")
        return str(value) if value is not None else None

    def _fetch_image_from_path(self, path: str) -> str | None:
        data = self._get_json(path)
        if not data:
            return None

        posters = data.get("posters") or []
        backdrops = data.get("backdrops") or []
        image = (posters[:1] + backdrops[:1])[:1]
        if not image:
            return None
        file_path = image[0].get("file_path")
        if not file_path:
            return None
        return f"{TMDB_IMAGE_BASE}{file_path}"

    def _get_json(self, path: str, params: dict | None = None) -> dict | None:
        url = f"{TMDB_API_BASE}{path}"
        query = dict(params or {})
        headers = {"Accept": "application/json"}
        if self.bearer_token:
            headers["Authorization"] = f"Bearer {self.bearer_token}"
        elif self.api_key:
            query["api_key"] = self.api_key
        else:
            return None

        if query:
            url = f"{url}?{urllib.parse.urlencode(query)}"

        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else None

    def _cleanup_cache(self):
        now = monotonic()
        stale_keys = [key for key, (ts, _) in self._cache.items() if now - ts >= ART_CACHE_TTL_SECONDS]
        for key in stale_keys:
            self._cache.pop(key, None)
