import os

from . import DEFAULT_CONFIG_PATH, MediaDiscordPresenceApp


if __name__ == "__main__":
    path = os.environ.get("MEDIA_DISCORD_PRESENCE_CONFIG", DEFAULT_CONFIG_PATH)
    MediaDiscordPresenceApp(path).run()
