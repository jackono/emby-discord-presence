# Troubleshooting

## LaunchAgent starts but crashes with `ImportError` from `media_discord_presence.py`

Symptom:
- macOS LaunchAgent keeps restarting
- `stderr.log` shows an import error mentioning `media_discord_presence.py`

Cause:
- An older install left behind a top-level `media_discord_presence.py` file that shadows the real `media_discord_presence/` package.

Fix:
```bash
launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.media-discord-presence.plist 2>/dev/null || true
rm -f ~/.local/share/media-discord-presence/media_discord_presence.py
rm -rf ~/.local/share/media-discord-presence/media_discord_presence
cd /path/to/media-discord-presence
./install-launch-agent.sh
launchctl kickstart -k gui/$(id -u)/com.media-discord-presence
```

Verify:
```bash
ls -la ~/.local/share/media-discord-presence
```
You should see:
- `media_discord_presence/`

You should not see:
- `media_discord_presence.py`

The LaunchAgent should run:
```bash
python -m media_discord_presence
```

## Foreground run works, but background LaunchAgent does not update

Cause:
- The LaunchAgent reads `~/.config/media-discord-presence/config.json`
- Your manual foreground run may be using the repo's local `./config.json`

Fix:
```bash
cp /path/to/media-discord-presence/config.json ~/.config/media-discord-presence/config.json
launchctl kickstart -k gui/$(id -u)/com.media-discord-presence
```

Check logs:
```bash
tail -f ~/Library/Logs/media-discord-presence/stdout.log
tail -f ~/Library/Logs/media-discord-presence/stderr.log
```

## How to run manually from the repo directory

With an explicit config file:
```bash
MEDIA_DISCORD_PRESENCE_CONFIG=./config.json ./.venv/bin/python -m media_discord_presence
```

If your venv is already activated:
```bash
python -m media_discord_presence
```

## Plex token works for `/identity` but not `/status/sessions`

Symptom:
- Plex provider starts but shows `HTTP Error 401: Unauthorized`

Cause:
- Some Plex tokens work for basic identity checks but not for active session APIs.

Fix:
- Use a token verified against `/status/sessions`
- A local admin token may work better than an older Plex online token in some setups

Quick test:
```bash
python3 - <<'PY'
import urllib.request
base='http://127.0.0.1:32400'
token='YOUR_TOKEN'
for path in [f'/identity?X-Plex-Token={token}', f'/status/sessions?X-Plex-Token={token}']:
    try:
        with urllib.request.urlopen(base + path, timeout=10) as r:
            print(path, r.status)
    except Exception as e:
        print(path, 'ERR', e)
PY
```

## Plex is reachable only on Tailscale, but other Tailscale devices cannot see it

Cause:
- Plex may advertise an incomplete custom connection URL to clients.
- A hostname without `http://` and `:32400` can break discovery even when Tailscale itself works.

Fix in Plex network settings:
```text
http://100.x.y.z:32400,http://your-hostname.tailnet.ts.net:32400
```

Tips:
- Use full URLs, not just the hostname
- Set `Secure connections` to `Preferred` while testing
- Fully quit and reopen the Plex client after changing server network settings

## Plex playback shows `Playback Error` even though the title appears in the library

Possible causes:
- Plex auth or web session issue
- stale metadata or play queue failure
- permissions issue in Plex cache/config directories

What to check:
```bash
tail -n 200 "/path/to/Plex Media Server.log"
```

Look for:
- `401 POST /playQueues`
- permission errors such as failure to write into `Cache/PhotoTranscoder`

If Plex can see the media item and art but fails to play, the issue is usually not the Riven library itself.

## Riven library vs Zurg mount, which should Plex use?

Recommended setup:
- Plex points to the **Riven library**
- Riven symlinks point into the **Zurg/rclone mount**

Why:
- Riven provides the curated library structure
- Zurg/rclone provide the underlying file paths

In a containerized setup, Plex can still follow Riven symlinks as long as both the Riven library path and the Zurg mount are available inside the Plex container.

## No Discord updates appear at all

Check these first:
- Discord desktop app is running
- the bridge is running under the same macOS user as Discord
- `provider` is `auto` or the correct provider
- `client_filters` is `[]` unless you intentionally want filtering
- provider credentials and usernames are correct
- Plex token still works for `/status/sessions`

If in doubt, run in the foreground first:
```bash
MEDIA_DISCORD_PRESENCE_CONFIG=./config.json ./.venv/bin/python -m media_discord_presence
```

If that works and the LaunchAgent does not, the problem is almost always the background config path or an old install layout.
