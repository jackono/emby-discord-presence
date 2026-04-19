#!/bin/zsh
set -euo pipefail

BASE_DIR="${0:A:h}"
APP_DIR="$HOME/.local/share/emby-discord-presence"
VENV_DIR="$APP_DIR/.venv"
CONFIG_DIR="$HOME/.config/emby-discord-presence"
LOG_DIR="$HOME/Library/Logs/emby-discord-presence"
PLIST_PATH="$HOME/Library/LaunchAgents/com.emby-discord-presence.plist"

mkdir -p "$APP_DIR" "$CONFIG_DIR" "$LOG_DIR" "$HOME/Library/LaunchAgents"
cp "$BASE_DIR/emby_discord_presence.py" "$APP_DIR/emby_discord_presence.py"
cp "$BASE_DIR/requirements.txt" "$APP_DIR/requirements.txt"
chmod 755 "$APP_DIR/emby_discord_presence.py"

if [[ ! -f "$CONFIG_DIR/config.json" ]]; then
  cp "$BASE_DIR/config.example.json" "$CONFIG_DIR/config.json"
  chmod 600 "$CONFIG_DIR/config.json"
fi

python3 -m venv "$VENV_DIR"
"$VENV_DIR/bin/pip" install --upgrade pip >/dev/null
"$VENV_DIR/bin/pip" install -r "$APP_DIR/requirements.txt"

cat > "$PLIST_PATH" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.emby-discord-presence</string>
  <key>ProgramArguments</key>
  <array>
    <string>$VENV_DIR/bin/python</string>
    <string>$APP_DIR/emby_discord_presence.py</string>
  </array>
  <key>EnvironmentVariables</key>
  <dict>
    <key>EMBY_DISCORD_PRESENCE_CONFIG</key>
    <string>$CONFIG_DIR/config.json</string>
  </dict>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>$LOG_DIR/stdout.log</string>
  <key>StandardErrorPath</key>
  <string>$LOG_DIR/stderr.log</string>
  <key>ProcessType</key>
  <string>Interactive</string>
  <key>WorkingDirectory</key>
  <string>$APP_DIR</string>
</dict>
</plist>
PLIST

launchctl bootout gui/$(id -u) "$PLIST_PATH" >/dev/null 2>&1 || true
launchctl bootstrap gui/$(id -u) "$PLIST_PATH"
launchctl enable gui/$(id -u)/com.emby-discord-presence
launchctl kickstart -k gui/$(id -u)/com.emby-discord-presence

echo "Installed launch agent: $PLIST_PATH"
echo "Config file: $CONFIG_DIR/config.json"
echo "Logs: $LOG_DIR"
