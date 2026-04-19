# media-discord-presence

![Preview](docs/preview.png)

A small cross-platform bridge that shows your current **Emby**, **Jellyfin**, or **Plex** playback as Discord Rich Presence.

It works well with **Infuse**, native Plex clients, web clients, and other players that show up properly in your media server's active sessions.

## Features

- Cleaner package structure, so the entry script stays small
- Shows what you're currently watching on Discord
- Supports **Emby**, **Jellyfin**, and **Plex**
- Strong **Infuse** support
- Also works with **Emby Web**, **Jellyfin Web**, Plex clients, and other supported clients reported by the media server
- Shows device names like `iPhone`, `iPad`, `Apple TV`, browser names, and other client/device labels reported by the server
- Shows elapsed playback time
- Optional Discord image assets and buttons
- Runs locally on macOS, Linux, and Windows
- No external server required

## How it works

1. The script connects to your configured media servers
2. It polls active playback sessions for your configured user
3. In `provider: "auto"` mode, it picks whichever server currently has an active playback
4. It normalizes the playback metadata into one internal format
5. It updates Discord Rich Presence through the local Discord desktop app

## Requirements

- macOS, Linux, or Windows
- Python 3.10+
- Discord desktop app installed and running
- An Emby, Jellyfin, or Plex server you can access locally or remotely
- A Discord Developer application with an **Application ID**

## Provider support

### Emby
- Fully supported
- Best-tested path so far
- Works especially well with **Infuse**

### Jellyfin
- Supported through the same session-polling model as Emby
- The API shape is very similar to Emby, so support is straightforward
- Still worth treating as less battle-tested unless more people try it

### Plex
- Supported through `/status/sessions`
- Uses `X-Plex-Token`
- Parses Plex XML session data and maps it into the same internal playback model
- More likely to need edge-case feedback because Plex metadata/session shapes vary more by client

## Supported clients

Known good / intended support:
- **Infuse**
- **Emby Web**
- **Jellyfin Web**
- Plex clients that appear in Plex active sessions

It should also work with other clients as long as the selected media server reports them properly as active playback sessions for your user.

## Install

### macOS

```bash
git clone https://github.com/jackono/media-discord-presence.git
cd media-discord-presence
mkdir -p ~/.config/media-discord-presence ~/.local/share/media-discord-presence
cp -R media_discord_presence ~/.local/share/media-discord-presence/
cp requirements.txt ~/.local/share/media-discord-presence/
cp config.example.json ~/.config/media-discord-presence/config.json
python3 -m venv ~/.local/share/media-discord-presence/.venv
~/.local/share/media-discord-presence/.venv/bin/pip install -r ~/.local/share/media-discord-presence/requirements.txt
```

### Linux

```bash
git clone https://github.com/jackono/media-discord-presence.git
cd media-discord-presence
mkdir -p ~/.config/media-discord-presence ~/.local/share/media-discord-presence
cp -R media_discord_presence ~/.local/share/media-discord-presence/
cp requirements.txt ~/.local/share/media-discord-presence/
cp config.example.json ~/.config/media-discord-presence/config.json
python3 -m venv ~/.local/share/media-discord-presence/.venv
~/.local/share/media-discord-presence/.venv/bin/pip install -r ~/.local/share/media-discord-presence/requirements.txt
```

### Windows (PowerShell)

```powershell
git clone https://github.com/jackono/media-discord-presence.git
cd media-discord-presence
New-Item -ItemType Directory -Force "$env:APPDATA\media-discord-presence" | Out-Null
New-Item -ItemType Directory -Force "$env:USERPROFILE\media-discord-presence" | Out-Null
Copy-Item .\requirements.txt "$env:USERPROFILE\media-discord-presence\"
Copy-Item .\config.example.json "$env:APPDATA\media-discord-presence\config.json"
Copy-Item .\media_discord_presence -Destination "$env:USERPROFILE\media-discord-presence\media_discord_presence" -Recurse
python -m venv "$env:USERPROFILE\media-discord-presence\.venv"
& "$env:USERPROFILE\media-discord-presence\.venv\Scripts\pip.exe" install -r "$env:USERPROFILE\media-discord-presence\requirements.txt"
```

Then edit your config.

### If you use multiple macOS users

You only need the extra copy step if the repo or script lives inside another user's home directory and your current user cannot read it.

In the normal case, install and run this under the **same macOS user that runs Discord**.

## Config

Example:

```json
{
  "provider": "auto",
  "client_filters": [],
  "poll_interval_seconds": 15,
  "discord": {
    "client_id": "YOUR_DISCORD_APP_ID",
    "large_image": "optional_uploaded_asset_key",
    "small_image": "optional_uploaded_asset_key",
    "small_text": "Watching via media server",
    "buttons": []
  },
  "emby": {
    "url": "http://127.0.0.1:8096",
    "username": "your-emby-username",
    "password": "your-emby-password"
  },
  "jellyfin": {
    "url": "http://127.0.0.1:8096",
    "username": "your-jellyfin-username",
    "password": "your-jellyfin-password"
  },
  "plex": {
    "url": "http://127.0.0.1:32400",
    "token": "PLEX_TOKEN_HERE",
    "username": "your-plex-username"
  }
}
```

### Config fields

#### Top-level
- `provider`: `auto`, `emby`, `jellyfin`, or `plex`
- `client_filters`: optional list of client-name filters. Use `[]` to allow any supported client for that user
- `poll_interval_seconds`: how often to check sessions

When `provider` is `auto`, the bridge checks configured providers in this order: `plex`, `jellyfin`, then `emby`, and uses whichever one currently has an active session.

#### Discord
- `discord.client_id`: your Discord Developer Application ID
- `discord.large_image`: optional uploaded Discord asset key
- `discord.small_image`: optional uploaded Discord asset key
- `discord.small_text`: optional tooltip for the small image
- `discord.buttons`: optional Discord buttons, up to 2

#### Emby
- `emby.url`: Emby base URL
- `emby.username`: Emby username
- `emby.password`: Emby password
- `emby.user_id`: optional fixed Emby user id
- `emby.authorization_header`: optional auth header override

#### Jellyfin
- `jellyfin.url`: Jellyfin base URL
- `jellyfin.username`: Jellyfin username
- `jellyfin.password`: Jellyfin password
- `jellyfin.user_id`: optional fixed Jellyfin user id
- `jellyfin.authorization_header`: optional auth header override

#### Plex
- `plex.url`: Plex base URL
- `plex.token`: Plex token
- `plex.username`: Plex username to match active sessions
- `plex.user_id`: optional Plex user id if you prefer matching by id
- `plex.client_identifier`: optional client identifier override
- `plex.product`: optional product name override for Plex headers
- `plex.version`: optional version override for Plex headers
- `plex.device_name`: optional device name override for Plex headers

## Run

### macOS / Linux

Foreground:

```bash
cd ~/.local/share/media-discord-presence && ./.venv/bin/python -m media_discord_presence
```

Background:

```bash
cd ~/.local/share/media-discord-presence && nohup ./.venv/bin/python -m media_discord_presence > media-discord-presence.log 2>&1 &
```

### Windows (PowerShell)

Foreground:

```powershell
Push-Location "$env:USERPROFILE\media-discord-presence"
& "$env:USERPROFILE\media-discord-presence\.venv\Scripts\python.exe" -m media_discord_presence
Pop-Location
```

Background:

```powershell
Start-Process -WorkingDirectory "$env:USERPROFILE\media-discord-presence" -FilePath "$env:USERPROFILE\media-discord-presence\.venv\Scripts\python.exe" -ArgumentList "-m media_discord_presence"
```

## Example output

Typical Discord card:
- App name: `Watching` or whatever you name your Discord app
- Line 1: `Frieren: Beyond Journey's End`
- Line 2: `iPhone • Infuse • S01E14 • Privilege of the Young`

## Troubleshooting

- See [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) for LaunchAgent fixes, config-path mismatches, Plex token issues, and Tailscale/Plex discovery notes.

## Notes

- Discord caches app metadata sometimes. If you rename your Discord app, restart Discord.
- Rich Presence must run under the **same logged-in desktop user/session** as Discord.
- The top app title comes from your Discord Developer application name, not from the script.
- Discord will not fetch poster art directly from Emby/Jellyfin/Plex URLs for RPC. Use uploaded Discord assets instead.
- Plex support uses XML session parsing instead of the Emby/Jellyfin JSON flow.
- In `provider: "auto"` mode, keep each provider block filled in if you want that server to be considered during detection.
- Jellyfin and Plex support are newer than the original Emby path, so feedback is especially useful.

## Startup

### macOS

A helper installer is included:

```bash
./install-launch-agent.sh
```

This copies the script into your user directory, installs dependencies, and creates a LaunchAgent so it can start automatically when you log in.

Manual LaunchAgent flow, if you do not want to use the installer:

1. Copy `examples/com.media-discord-presence.plist` to `~/Library/LaunchAgents/com.media-discord-presence.plist`
2. Replace `YOUR_USER` with your actual username
3. Load it with:

```bash
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.media-discord-presence.plist
launchctl kickstart -k gui/$(id -u)/com.media-discord-presence
```

### Linux (systemd user service example)

Copy `examples/media-discord-presence.service` to `~/.config/systemd/user/media-discord-presence.service`, then enable it:

```bash
systemctl --user daemon-reload
systemctl --user enable --now media-discord-presence.service
```

### Windows (Startup folder)

Use `examples/start-media-discord-presence.bat`, then place a shortcut to that batch file in:

```text
%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup
```

If you prefer Task Scheduler instead, create a task that runs at logon with:

```text
%USERPROFILE%\media-discord-presence\.venv\Scripts\python.exe
```

and argument:

```text
-m media_discord_presence
```

## Project structure

```text
media_discord_presence/
  __init__.py
  __main__.py                     # module entry point
  app.py                          # app loop
  config.py                       # config path + loading
  discord_rpc.py                  # Discord RPC update logic
  models.py                       # shared playback model
  providers.py                    # media server session fetching
```

## Security

- Do **not** commit your real `config.json`
- Use `config.example.json` as the template
- Use a dedicated Emby/Jellyfin/Plex user if you want tighter separation
- Treat Plex tokens like secrets

## License

MIT
