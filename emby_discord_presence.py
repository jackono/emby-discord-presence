#!/usr/bin/env python3
import json
import os
import platform
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

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
    f'MediaBrowser Client="Emby Discord Presence", '
    f'Device="{platform.system() or "Unknown"}", '
    'DeviceId="emby-discord-presence", Version="1.0.0"'
)


class EmbyDiscordPresence:
    def __init__(self, config_path: str):
        self.config_path = config_path
        self.config = self._load_config(config_path)
        self.base_url = self.config["emby"]["url"].rstrip("/")
        self.username = self.config["emby"]["username"]
        self.password = self.config["emby"]["password"]
        self.user_id = self.config["emby"].get("user_id")
        self.client_filters = [x.lower() for x in self.config.get("client_filters", [])]
        self.poll_interval = int(self.config.get("poll_interval_seconds", 15))
        self.client_id = str(self.config.get("discord", {}).get("client_id", ""))
        self.auth_header = self.config.get("emby", {}).get("authorization_header", DEFAULT_AUTH_HEADER)
        self.token = None
        self.rpc = None
        self.last_payload = None
        self.last_session_id = None

    def _load_config(self, path: str):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

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
        return result

    def ensure_rpc(self):
        if self.rpc is not None:
            return
        if not self.client_id:
            raise RuntimeError("discord.client_id is missing in config.json")
        self.rpc = Presence(self.client_id)
        self.rpc.connect()

    def fetch_sessions(self):
        query = urllib.parse.urlencode({"ActiveWithinSeconds": 300})
        return self._request(f"/Sessions?{query}")

    def session_matches(self, session: dict) -> bool:
        if session.get("UserId") != self.user_id:
            return False
        if not self.client_filters:
            return True
        combined = " ".join([
            str(session.get("Client", "")),
            str(session.get("DeviceName", "")),
            str(session.get("ApplicationVersion", "")),
        ]).lower()
        return any(token in combined for token in self.client_filters)

    def select_session(self, sessions):
        candidates = []
        for session in sessions:
            if not self.session_matches(session):
                continue
            item = session.get("NowPlayingItem")
            if not item:
                continue
            candidates.append(session)
        if not candidates:
            return None
        candidates.sort(key=lambda s: s.get("LastActivityDate", ""), reverse=True)
        return candidates[0]

    @staticmethod
    def _ticks_to_seconds(value):
        try:
            return int(value) / 10_000_000
        except Exception:
            return 0

    def build_payload(self, session: dict):
        item = session.get("NowPlayingItem", {})
        playstate = session.get("PlayState", {})
        title = item.get("Name") or "Something"
        series = item.get("SeriesName")
        media_type = item.get("Type") or "Video"
        season = item.get("ParentIndexNumber")
        episode = item.get("IndexNumber")
        year = item.get("ProductionYear")
        paused = bool(playstate.get("IsPaused"))
        client_name = session.get("Client") or "Infuse"
        device_name = session.get("DeviceName") or "Unknown device"
        verb = "Paused" if paused else "Watching"

        episode_code = None
        if season is not None and episode is not None:
            episode_code = f"S{int(season):02d}E{int(episode):02d}"

        if media_type == "Episode" and series:
            details = series
            parts = [p for p in [device_name, episode_code, title] if p]
            state = " • ".join(parts)
        elif media_type == "Movie":
            details = f"{title}{f' ({year})' if year else ''}"
            state = device_name
        else:
            details = title
            state = device_name

        payload = {
            "details": details[:128],
            "state": state[:128],
            "large_text": f"Watching from {device_name} ({client_name})"[:128],
        }

        discord_cfg = self.config.get("discord", {})
        large_image = discord_cfg.get("large_image")
        small_image = discord_cfg.get("small_image")
        small_text = discord_cfg.get("small_text") or f"{verb} via {client_name}"
        if large_image:
            payload["large_image"] = large_image
        if small_image:
            payload["small_image"] = small_image
            payload["small_text"] = small_text[:128]

        runtime = self._ticks_to_seconds(item.get("RunTimeTicks"))
        position = self._ticks_to_seconds(playstate.get("PositionTicks"))
        if runtime > 0 and position >= 0 and not paused:
            now = int(time.time())
            payload["start"] = int(now - position)

        buttons = discord_cfg.get("buttons", [])
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
        print("Starting Emby Discord Rich Presence bridge", flush=True)
        while True:
            try:
                if not self.token:
                    self.authenticate()
                    print("Authenticated to Emby", flush=True)
                sessions = self.fetch_sessions()
                session = self.select_session(sessions)
                if session:
                    payload = self.build_payload(session)
                    self.update_presence(payload, session.get("Id"))
                else:
                    self.clear_presence()
                time.sleep(self.poll_interval)
            except urllib.error.HTTPError as e:
                print(f"HTTP error: {e}", file=sys.stderr, flush=True)
                if e.code in (401, 403):
                    self.token = None
                time.sleep(min(self.poll_interval, 15))
            except Exception as e:
                print(f"Bridge error: {e}", file=sys.stderr, flush=True)
                self.token = None
                try:
                    if self.rpc is not None:
                        self.rpc.close()
                except Exception:
                    pass
                self.rpc = None
                time.sleep(min(self.poll_interval, 15))


if __name__ == "__main__":
    path = os.environ.get("EMBY_DISCORD_PRESENCE_CONFIG", DEFAULT_CONFIG_PATH)
    EmbyDiscordPresence(path).run()
