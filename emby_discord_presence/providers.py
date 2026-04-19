import json
import urllib.parse
import urllib.request

from .config import DEFAULT_AUTH_HEADER
from .models import PlaybackState


class EmbyProvider:
    def __init__(self, config: dict):
        self.base_url = config["emby"]["url"].rstrip("/")
        self.username = config["emby"]["username"]
        self.password = config["emby"]["password"]
        self.user_id = config["emby"].get("user_id")
        self.client_filters = [x.lower() for x in config.get("client_filters", [])]
        self.auth_header = config.get("emby", {}).get("authorization_header", DEFAULT_AUTH_HEADER)
        self.token = None

    def _request(self, path: str, method: str = "GET", data=None, with_token: bool = True):
        url = f"{self.base_url}{path}"
        headers = {
            "Content-Type": "application/json",
            "X-Emby-Authorization": self.auth_header,
        }
        if with_token and self.token:
            headers["X-Emby-Token"] = self.token
        body = None if data is None else json.dumps(data).encode("utf-8")
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else None

    def authenticate(self):
        result = self._request(
            "/Users/AuthenticateByName",
            method="POST",
            data={"Username": self.username, "Pw": self.password},
            with_token=False,
        )
        self.token = result["AccessToken"]
        if not self.user_id:
            self.user_id = result["User"]["Id"]

    def fetch_playback(self) -> PlaybackState | None:
        if not self.token:
            self.authenticate()
        query = urllib.parse.urlencode({"ActiveWithinSeconds": 300})
        sessions = self._request(f"/Sessions?{query}")
        candidates = []
        for session in sessions:
            item = session.get("NowPlayingItem")
            if not item or session.get("UserId") != self.user_id:
                continue
            if not self._session_matches(session):
                continue
            candidates.append(session)
        if not candidates:
            return None
        candidates.sort(key=lambda s: s.get("LastActivityDate", ""), reverse=True)
        session = candidates[0]
        item = session.get("NowPlayingItem", {})
        playstate = session.get("PlayState", {})
        return PlaybackState(
            session_id=session.get("Id") or "unknown-session",
            media_type=item.get("Type") or "Video",
            title=item.get("Name") or "Something",
            series=item.get("SeriesName"),
            season=_safe_int(item.get("ParentIndexNumber")),
            episode=_safe_int(item.get("IndexNumber")),
            year=_safe_int(item.get("ProductionYear")),
            paused=bool(playstate.get("IsPaused")),
            position_seconds=_ticks_to_seconds(playstate.get("PositionTicks")),
            duration_seconds=_ticks_to_seconds(item.get("RunTimeTicks")),
            device_name=session.get("DeviceName") or "Unknown device",
            client_name=session.get("Client") or "Infuse",
        )

    def _session_matches(self, session: dict) -> bool:
        if not self.client_filters:
            return True
        combined = " ".join([
            str(session.get("Client", "")),
            str(session.get("DeviceName", "")),
            str(session.get("ApplicationVersion", "")),
        ]).lower()
        return any(token in combined for token in self.client_filters)



def _safe_int(value):
    try:
        if value is None or value == "":
            return None
        return int(value)
    except Exception:
        return None



def _ticks_to_seconds(value):
    try:
        return int(value) / 10_000_000
    except Exception:
        return 0
