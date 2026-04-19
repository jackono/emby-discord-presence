import sys
import time
import urllib.error

from .config import load_config
from .discord_rpc import DiscordRPC
from .providers import ProviderFactory


class MediaDiscordPresenceApp:
    def __init__(self, config_path: str):
        self.config = load_config(config_path)
        self.poll_interval = int(self.config.get("poll_interval_seconds", 15))
        self.provider_name = str(self.config.get("provider", "auto")).strip().lower()
        self.providers = ProviderFactory.build_all(self.config)
        self.discord = DiscordRPC(self.config.get("discord", {}))
        self.active_provider_name = None

    def run(self):
        names = ", ".join(provider.provider_name for provider in self.providers)
        print(f"Starting media Discord Presence bridge ({self.provider_name}: {names})", flush=True)
        while True:
            try:
                playbacks = self._get_playbacks()
                if playbacks:
                    self.discord.update(playbacks[0])
                else:
                    self.discord.clear()
                time.sleep(self.poll_interval)
            except urllib.error.HTTPError as e:
                print(f"HTTP error: {e}", file=sys.stderr, flush=True)
                self._reset_provider_tokens()
                time.sleep(min(self.poll_interval, 15))
            except Exception as e:
                print(f"Bridge error: {e}", file=sys.stderr, flush=True)
                self._reset_provider_tokens()
                self.discord.reset()
                time.sleep(min(self.poll_interval, 15))

    def _get_playbacks(self):
        preferred = self._ordered_providers()
        first_error = None
        for provider in preferred:
            try:
                playbacks = provider.get_playbacks()
                if playbacks:
                    self.active_provider_name = provider.provider_name
                    return playbacks
            except Exception as e:
                if first_error is None:
                    first_error = e
        self.active_provider_name = None
        if first_error and len(preferred) == 1:
            raise first_error
        return []

    def _ordered_providers(self):
        if not self.active_provider_name:
            return self.providers
        active = [p for p in self.providers if p.provider_name == self.active_provider_name]
        others = [p for p in self.providers if p.provider_name != self.active_provider_name]
        return active + others

    def _reset_provider_tokens(self):
        for provider in self.providers:
            if hasattr(provider, "token"):
                setattr(provider, "token", None)
