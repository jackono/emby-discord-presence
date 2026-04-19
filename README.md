# emby-discord-presence

A small macOS bridge that shows your current Emby playback as Discord Rich Presence.

It works especially well with **Infuse**, since Infuse is one of the most reliable Emby clients for exposing clean playback sessions, but it can also work with **Emby Web** and other Emby-connected clients.

## Features

- Shows what you're currently watching on Discord
- Uses your active **Emby user** only
- Supports **Infuse**, **Emby Web**, and other Emby-connected clients
- Shows device name like `iPhone`, `iPad`, `Apple TV`, or browser/device names reported by Emby
- Shows elapsed playback time
- Optional Discord image assets and buttons
- Runs locally on macOS, no external server required

## How it works

1. The script authenticates to your Emby server
2. It polls active playback sessions for your user
3. It picks the current playing item
4. It updates Discord Rich Presence through the local Discord desktop app

## Requirements

- macOS
- Python 3.10+
- Discord desktop app installed and running
- An Emby server you can access locally or remotely
- A Discord Developer application with an **Application ID**

## Supported clients

Known good:
- **Infuse**
- **Emby Web**

Also works with other Emby-connected clients as long as Emby reports them as active playback sessions under your user.

## Install

Normal install, recommended:

```bash
git clone https://github.com/jackono/emby-discord-presence.git
cd emby-discord-presence
mkdir -p ~/.config/emby-discord-presence ~/.local/share/emby-discord-presence
cp emby_discord_presence.py ~/.local/share/emby-discord-presence/
cp requirements.txt ~/.local/share/emby-discord-presence/
cp config.example.json ~/.config/emby-discord-presence/config.json
python3 -m venv ~/.local/share/emby-discord-presence/.venv
~/.local/share/emby-discord-presence/.venv/bin/pip install -r ~/.local/share/emby-discord-presence/requirements.txt
```

Then edit your config.

### If you use multiple macOS users

You only need the extra copy step if the repo or script lives inside another user's home directory and your current user cannot read it.

In the normal case, install and run this under the **same macOS user that runs Discord**.

## Config

Example:

```json
{
  "emby": {
    "url": "http://127.0.0.1:8096",
    "username": "your-emby-username",
    "password": "your-emby-password"
  },
  "client_filters": [],
  "poll_interval_seconds": 15,
  "discord": {
    "client_id": "YOUR_DISCORD_APP_ID",
    "large_image": "optional_uploaded_asset_key",
    "small_image": "optional_uploaded_asset_key",
    "small_text": "Watching via Emby",
    "buttons": []
  }
}
```

### Config fields

- `emby.url`: Emby base URL
- `emby.username`: Emby username
- `emby.password`: Emby password
- `emby.user_id`: optional fixed Emby user id, if omitted the script resolves it after login
- `emby.authorization_header`: optional override for the Emby auth header
- `client_filters`: optional list of client-name filters. Use `[]` to allow any Emby client for that user
- `poll_interval_seconds`: how often to check Emby sessions
- `discord.client_id`: your Discord Developer Application ID
- `discord.large_image`: optional uploaded Discord asset key
- `discord.small_image`: optional uploaded Discord asset key
- `discord.small_text`: optional tooltip for the small image
- `discord.buttons`: optional Discord buttons, up to 2

## Run

```bash
~/.local/share/emby-discord-presence/.venv/bin/python ~/.local/share/emby-discord-presence/emby_discord_presence.py
```

## Example output

Typical Discord card:
- App name: `Watching` or whatever you name your Discord app
- Line 1: `Frieren: Beyond Journey's End`
- Line 2: `iPhone • S01E14 • Privilege of the Young`

## Notes

- Discord caches app metadata sometimes. If you rename your Discord app, restart Discord.
- Rich Presence must run under the **same macOS user** as the Discord app.
- The top app title comes from your Discord Developer application name, not from the script.
- Discord will not fetch poster art directly from Emby URLs for RPC. Use uploaded Discord assets instead.

## LaunchAgent

A helper installer is included:

```bash
./install-launch-agent.sh
```

This copies the script into your user directory, installs dependencies, and creates a LaunchAgent so it can start automatically when you log in.

## Security

- Do **not** commit your real `config.json`
- Use `config.example.json` as the template
- Create a dedicated Emby user if you want tighter separation

## License

MIT
