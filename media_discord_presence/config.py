import json
import os
import platform
from pathlib import Path


def default_config_path() -> str:
    if os.name == "nt":
        appdata = os.environ.get("APPDATA")
        if appdata:
            return str(Path(appdata) / "media-discord-presence" / "config.json")
        return str(Path.home() / "AppData" / "Roaming" / "media-discord-presence" / "config.json")

    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        return str(Path(xdg) / "media-discord-presence" / "config.json")
    return str(Path.home() / ".config" / "media-discord-presence" / "config.json")


DEFAULT_CONFIG_PATH = default_config_path()
DEFAULT_AUTH_HEADER = (
    f'MediaBrowser Client="Media Discord Presence", '
    f'Device="{platform.system() or "Unknown"}", '
    'DeviceId="media-discord-presence", Version="1.0.0"'
)


def load_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
