import json
import platform
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

from .config import DEFAULT_AUTH_HEADER
from .models import PlaybackState


class ProviderBase:
    def __init__(self, app_config: dict, provider_config: dict, client_filters: list[str]):
        self.app_config = app_config
        self.config = provider_config
        self.client_filters = [x.lower() for x in client_filters]

    def get_playbacks(self) -> list[PlaybackState]:
        raise NotImplementedError

    def _matches_client_filters(self, client_name: str, device_name: str, extra: str = "") -> bool:
        if not self.client_filters:
            return True
        combined = " ".join([client_name or "", device_name or "", extra or ""]).lower()
        return any(token in combined for token in self.client_filters)


class EmbyLikeProvider(ProviderBase):
    def __init__(self, app_config: dict, provider_config: dict, client_filters: list[str], server_label: str):
        super().__init__(app_config, provider_config, client_filters)
        self.server_label = server_label
        self.base_url = self.config["url"].rstrip("/")
        self.username = self.config["username"]
        self.password = self.config["password"]
        self.user_id = self.config.get("user_id")
        self.auth_header = self.config.get("authorization_header", DEFAULT_AUTH_HEADER)
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

    def get_playbacks(self) -> list[PlaybackState]:
        if not self.token:
            self.authenticate()
        query = urllib.parse.urlencode({"ActiveWithinSeconds": 300})
        sessions = self._request(f"/Sessions?{query}")
        playbacks: list[PlaybackState] = []
        for session in sessions:
            item = session.get("NowPlayingItem")
            if not item:
                continue
            if session.get("UserId") != self.user_id:
                continue
            client_name = session.get("Client") or self.server_label
            device_name = session.get("DeviceName") or "Unknown device"
            if not self._matches_client_filters(client_name, device_name, str(session.get("ApplicationVersion", ""))):
                continue
            playbacks.append(
                PlaybackState(
                    session_id=session.get("Id") or f"{client_name}:{device_name}:{item.get('Id', '')}",
                    media_type=item.get("Type") or "Video",
                    title=item.get("Name") or "Something",
                    series=item.get("SeriesName"),
                    season=_safe_int(item.get("ParentIndexNumber")),
                    episode=_safe_int(item.get("IndexNumber")),
                    year=_safe_int(item.get("ProductionYear")),
                    paused=bool((session.get("PlayState") or {}).get("IsPaused")),
                    position_seconds=_ticks_to_seconds((session.get("PlayState") or {}).get("PositionTicks")),
                    duration_seconds=_ticks_to_seconds(item.get("RunTimeTicks")),
                    device_name=device_name,
                    client_name=client_name,
                    last_activity=session.get("LastActivityDate") or "",
                )
            )
        playbacks.sort(key=lambda p: p.last_activity, reverse=True)
        return playbacks


class EmbyProvider(EmbyLikeProvider):
    def __init__(self, app_config: dict, provider_config: dict, client_filters: list[str]):
        super().__init__(app_config, provider_config, client_filters, server_label="Emby")


class JellyfinProvider(EmbyLikeProvider):
    def __init__(self, app_config: dict, provider_config: dict, client_filters: list[str]):
        super().__init__(app_config, provider_config, client_filters, server_label="Jellyfin")


class PlexProvider(ProviderBase):
    def __init__(self, app_config: dict, provider_config: dict, client_filters: list[str]):
        super().__init__(app_config, provider_config, client_filters)
        self.base_url = self.config["url"].rstrip("/")
        self.token = self.config["token"]
        self.username = self.config.get("username", "")
        self.user_id = str(self.config.get("user_id", "")).strip()
        self.client_identifier = self.config.get("client_identifier", "media-discord-presence")
        self.product = self.config.get("product", "media-discord-presence")
        self.version = self.config.get("version", "1.0.0")
        self.device_name = self.config.get("device_name", platform.system() or "Unknown")

    def _request_xml(self, path: str):
        params = {
            "X-Plex-Token": self.token,
            "X-Plex-Client-Identifier": self.client_identifier,
            "X-Plex-Product": self.product,
            "X-Plex-Version": self.version,
            "X-Plex-Device-Name": self.device_name,
        }
        url = f"{self.base_url}{path}"
        separator = "&" if "?" in url else "?"
        url = f"{url}{separator}{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(url, headers={"Accept": "application/xml"}, method="GET")
        with urllib.request.urlopen(req, timeout=30) as resp:
            return ET.fromstring(resp.read())

    def _user_matches(self, user_el) -> bool:
        if user_el is None:
            return not self.username and not self.user_id
        title = (user_el.attrib.get("title") or "").strip().lower()
        user_id = (user_el.attrib.get("id") or "").strip()
        if self.user_id and user_id == self.user_id:
            return True
        if self.username and title == self.username.lower():
            return True
        return not self.username and not self.user_id

    def get_playbacks(self) -> list[PlaybackState]:
        root = self._request_xml("/status/sessions")
        playbacks: list[PlaybackState] = []
        for item in root:
            if item.tag not in {"Video", "Track", "Episode", "Movie"}:
                continue
            player = item.find("Player")
            if player is None:
                continue
            user = item.find("User")
            if not self._user_matches(user):
                continue
            client_name = player.attrib.get("product") or player.attrib.get("title") or "Plex"
            device_name = player.attrib.get("title") or player.attrib.get("platform") or "Unknown device"
            if not self._matches_client_filters(client_name, device_name, player.attrib.get("platform", "")):
                continue
            media_type = item.attrib.get("type", "video").lower()
            playbacks.append(
                PlaybackState(
                    session_id=item.attrib.get("sessionKey") or item.attrib.get("ratingKey") or f"{client_name}:{device_name}",
                    media_type=_plex_media_type(media_type),
                    title=item.attrib.get("title") or "Something",
                    series=item.attrib.get("grandparentTitle"),
                    season=_safe_int(item.attrib.get("parentIndex")),
                    episode=_safe_int(item.attrib.get("index")),
                    year=_safe_int(item.attrib.get("year")),
                    paused=(player.attrib.get("state") == "paused"),
                    position_seconds=_millis_to_seconds(item.attrib.get("viewOffset")),
                    duration_seconds=_millis_to_seconds(item.attrib.get("duration")),
                    device_name=device_name,
                    client_name=client_name,
                    last_activity=item.attrib.get("updatedAt") or item.attrib.get("addedAt") or "",
                )
            )
        playbacks.sort(key=lambda p: p.last_activity, reverse=True)
        return playbacks


class ProviderFactory:
    @staticmethod
    def build(config: dict):
        provider_name = str(config.get("provider", "emby")).strip().lower()
        client_filters = [x.lower() for x in config.get("client_filters", [])]
        if provider_name == "emby":
            return EmbyProvider(config, config["emby"], client_filters)
        if provider_name == "jellyfin":
            return JellyfinProvider(config, config["jellyfin"], client_filters)
        if provider_name == "plex":
            return PlexProvider(config, config["plex"], client_filters)
        raise RuntimeError(f"Unsupported provider: {provider_name}")


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


def _millis_to_seconds(value):
    try:
        return int(value) / 1000
    except Exception:
        return 0


def _plex_media_type(value: str) -> str:
    value = (value or "video").lower()
    if value == "episode":
        return "Episode"
    if value == "movie":
        return "Movie"
    return value.title()
