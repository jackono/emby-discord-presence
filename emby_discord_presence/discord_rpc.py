import json
import time

from pypresence import Presence

from .models import PlaybackState


class DiscordRPC:
    def __init__(self, discord_config: dict):
        self.discord_config = discord_config
        self.client_id = str(discord_config.get("client_id", ""))
        self.rpc = None
        self.last_payload = None
        self.last_session_id = None

    def ensure_connected(self):
        if self.rpc is not None:
            return
        if not self.client_id:
            raise RuntimeError("discord.client_id is missing in config.json")
        self.rpc = Presence(self.client_id)
        self.rpc.connect()

    def build_payload(self, playback: PlaybackState) -> dict:
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

        large_image = self.discord_config.get("large_image")
        small_image = self.discord_config.get("small_image")
        small_text = self.discord_config.get("small_text") or f"{verb} via {playback.client_name}"
        if large_image:
            payload["large_image"] = large_image
        if small_image:
            payload["small_image"] = small_image
            payload["small_text"] = small_text[:128]

        if playback.duration_seconds > 0 and playback.position_seconds >= 0 and not playback.paused:
            payload["start"] = int(time.time() - playback.position_seconds)

        buttons = self.discord_config.get("buttons", [])
        if buttons:
            payload["buttons"] = buttons[:2]

        return payload

    def update(self, playback: PlaybackState):
        payload = self.build_payload(playback)
        self.ensure_connected()
        if payload == self.last_payload and playback.session_id == self.last_session_id:
            return
        self.rpc.update(**payload)
        self.last_payload = payload
        self.last_session_id = playback.session_id
        print(f"Updated presence: {json.dumps(payload, ensure_ascii=False)}", flush=True)

    def clear(self):
        if self.rpc is None:
            return
        try:
            self.rpc.clear()
        except Exception:
            pass
        self.last_payload = None
        self.last_session_id = None

    def reset(self):
        try:
            if self.rpc is not None:
                self.rpc.close()
        except Exception:
            pass
        self.rpc = None
