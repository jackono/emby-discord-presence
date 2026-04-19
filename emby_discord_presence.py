#!/usr/bin/env python3
import os

from emby_discord_presence import DEFAULT_CONFIG_PATH, EmbyDiscordPresenceApp


if __name__ == "__main__":
    path = os.environ.get("EMBY_DISCORD_PRESENCE_CONFIG", DEFAULT_CONFIG_PATH)
    EmbyDiscordPresenceApp(path).run()
