#!/usr/bin/env python3
import json
import os
import platform
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from pypresence import Presence


def default_config_path() -> str:
    if os.name == "nt":
        appdata = os.environ.get("APPDATA")
        if appdata:
            return str(Path(appdata) / "emby-discord-presence" / "config.json")
        return str(Path.home() / "AppData" / "Roaming" / "emby-discord-presence" / "config.json")

    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        return str(Path(xdg) / "emby-discord-presence" / "config.json")
    return str(Path.home() / ".config" / "emby-discord-presence" / "config.json")


DEFAULT_CONFIG_PATH = default_config_path()
DEFAULT_AUTH_HEADER = (
    f'MediaBrowser Client="Media Discord Presence", '
    f'Device="{platform.system() or "Unknown"}", '
    'DeviceId="media-discord-presence", Version="1.0.0"'
)


@dataclass
class PlaybackState:
    session_id: str
    media_type: str
    title: str
    series: Optional[str]
    season: Optional[int]
    episode: Optional[int]
    year: Optional[int]
    paused: bool
    position_seconds: float
    duration_seconds: float
    device_name: str
    client_name: str
    last_activity: str = ""


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

    def _user_matches(self, user_el: Optional[ET.Element]) -> bool:
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


class DiscordPresenceApp:
    def __init__(self, config_path: str):
        self.config_path = config_path
        self.config = self._load_config(config_path)
        self.poll_interval = int(self.config.get("poll_interval_seconds", 15))
        self.discord_cfg = self.config.get("discord", {})
        self.client_id = str(self.discord_cfg.get("client_id", ""))
        self.provider_name = str(self.config.get("provider", "emby")).strip().lower()
        self.client_filters = [x.lower() for x in self.config.get("client_filters", [])]
        self.provider = self._build_provider()
        self.rpc = None
        self.last_payload = None
        self.last_session_id = None

    def _load_config(self, path: str):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _build_provider(self) -> ProviderBase:
        if self.provider_name == "emby":
            return EmbyProvider(self.config, self.config["emby"], self.client_filters)
        if self.provider_name == "jellyfin":
            return JellyfinProvider(self.config, self.config["jellyfin"], self.client_filters)
        if self.provider_name == "plex":
            return PlexProvider(self.config, self.config["plex"], self.client_filters)
        raise RuntimeError(f"Unsupported provider: {self.provider_name}")

    def ensure_rpc(self):
        if self.rpc is not None:
            return
        if not self.client_id:
            raise RuntimeError("discord.client_id is missing in config.json")
        self.rpc = Presence(self.client_id)
        self.rpc.connect()

    def select_playback(self, playbacks: list[PlaybackState]) -> Optional[PlaybackState]:
        return playbacks[0] if playbacks else None

    def build_payload(self, playback: PlaybackState):
        verb = "Paused" if playback.paused else "Watching"
        episode_code = None
        if playback.season is not None and playback.episode is not None:
            episode_code = f"S{int(playback.season):02d}E{int(playback.episode):02d}"

        if playback.media_type == "Episode" and playback.series:
            details = playback.series
            parts = [p for p in [playback.device_name, episode_code, playback.title] if p]
            state = " • ".join(parts)
        elif playback.media_type == "Movie":
            details = f"{playback.title}{f' ({playback.year})' if playback.year else ''}"
            state = playback.device_name
        else:
            details = playback.title
            state = playback.device_name

        payload = {
            "details": details[:128],
            "state": state[:128],
            "large_text": f"Watching from {playback.device_name} ({playback.client_name})"[:128],
        }

        large_image = self.discord_cfg.get("large_image")
        small_image = self.discord_cfg.get("small_image")
        small_text = self.discord_cfg.get("small_text") or f"{verb} via {playback.client_name}"
        if large_image:
            payload["large_image"] = large_image
        if small_image:
            payload["small_image"] = small_image
            payload["small_text"] = small_text[:128]

        if playback.duration_seconds > 0 and playback.position_seconds >= 0 and not playback.paused:
            payload["start"] = int(time.time() - playback.position_seconds)

        buttons = self.discord_cfg.get("buttons", [])
        if buttons:
            payload["buttons"] = buttons[:2]

        return payload

    def clear_presence(self):
        if self.rpc is None:
            return
        try:
            self.rpc.clear()
        except Exception:
            pass
        self.last_payload = None
        self.last_session_id = None

    def update_presence(self, payload: dict, session_id: str):
        self.ensure_rpc()
        if payload == self.last_payload and session_id == self.last_session_id:
            return
        self.rpc.update(**payload)
        self.last_payload = payload
        self.last_session_id = session_id
        print(f"Updated presence: {json.dumps(payload, ensure_ascii=False)}", flush=True)

    def run(self):
        print(f"Starting media Discord Presence bridge ({self.provider_name})", flush=True)
        while True:
            try:
                playbacks = self.provider.get_playbacks()
                playback = self.select_playback(playbacks)
                if playback:
                    self.update_presence(self.build_payload(playback), playback.session_id)
                else:
                    self.clear_presence()
                time.sleep(self.poll_interval)
            except urllib.error.HTTPError as e:
                print(f"HTTP error: {e}", file=sys.stderr, flush=True)
                if e.code in (401, 403) and hasattr(self.provider, "token"):
                    setattr(self.provider, "token", None)
                time.sleep(min(self.poll_interval, 15))
            except Exception as e:
                print(f"Bridge error: {e}", file=sys.stderr, flush=True)
                if hasattr(self.provider, "token"):
                    setattr(self.provider, "token", None)
                try:
                    if self.rpc is not None:
                        self.rpc.close()
                except Exception:
                    pass
                self.rpc = None
                time.sleep(min(self.poll_interval, 15))


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


if __name__ == "__main__":
    path = os.environ.get("EMBY_DISCORD_PRESENCE_CONFIG", DEFAULT_CONFIG_PATH)
    DiscordPresenceApp(path).run()
