import sys
import time
import urllib.error

from .config import load_config
from .discord_rpc import DiscordRPC
from .providers import EmbyProvider


class EmbyDiscordPresenceApp:
    def __init__(self, config_path: str):
        self.config = load_config(config_path)
        self.poll_interval = int(self.config.get("poll_interval_seconds", 15))
        self.provider = EmbyProvider(self.config)
        self.discord = DiscordRPC(self.config.get("discord", {}))

    def run(self):
        print("Starting Emby Discord Rich Presence bridge", flush=True)
        while True:
            try:
                playback = self.provider.fetch_playback()
                if playback:
                    self.discord.update(playback)
                else:
                    self.discord.clear()
                time.sleep(self.poll_interval)
            except urllib.error.HTTPError as e:
                print(f"HTTP error: {e}", file=sys.stderr, flush=True)
                if e.code in (401, 403):
                    self.provider.token = None
                time.sleep(min(self.poll_interval, 15))
            except Exception as e:
                print(f"Bridge error: {e}", file=sys.stderr, flush=True)
                self.provider.token = None
                self.discord.reset()
                time.sleep(min(self.poll_interval, 15))
