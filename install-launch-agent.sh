#!/bin/zsh
set -euo pipefail

BASE_DIR="${0:A:h}"
APP_DIR="$HOME/.local/share/media-discord-presence"
VENV_DIR="$APP_DIR/.venv"
REPO_VENV_DIR="$BASE_DIR/.venv"
CONFIG_DIR="$HOME/.config/media-discord-presence"
LOG_DIR="$HOME/Library/Logs/media-discord-presence"
PLIST_PATH="$HOME/Library/LaunchAgents/com.media-discord-presence.plist"

mkdir -p "$APP_DIR" "$CONFIG_DIR" "$LOG_DIR" "$HOME/Library/LaunchAgents"
cp "$BASE_DIR/requirements.txt" "$APP_DIR/requirements.txt"
rm -rf "$APP_DIR/media_discord_presence"
cp -R "$BASE_DIR/src/media_discord_presence" "$APP_DIR/media_discord_presence"

if [[ ! -f "$CONFIG_DIR/config.json" ]]; then
  cp "$BASE_DIR/config.example.json" "$CONFIG_DIR/config.json"
  chmod 600 "$CONFIG_DIR/config.json"
fi

python3 -m venv "$VENV_DIR"
"$VENV_DIR/bin/pip" install --upgrade pip >/dev/null
"$VENV_DIR/bin/pip" install -r "$APP_DIR/requirements.txt"

python3 -m venv "$REPO_VENV_DIR"
"$REPO_VENV_DIR/bin/pip" install --upgrade pip >/dev/null
"$REPO_VENV_DIR/bin/pip" install -r "$BASE_DIR/requirements.txt"

cat > "$PLIST_PATH" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.media-discord-presence</string>
  <key>ProgramArguments</key>
  <array>
    <string>$VENV_DIR/bin/python</string>
    <string>-m</string>
    <string>media_discord_presence</string>
  </array>
  <key>EnvironmentVariables</key>
  <dict>
    <key>MEDIA_DISCORD_PRESENCE_CONFIG</key>
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
launchctl enable gui/$(id -u)/com.media-discord-presence
launchctl kickstart -k gui/$(id -u)/com.media-discord-presence

echo "Installed launch agent: $PLIST_PATH"
echo "Config file: $CONFIG_DIR/config.json"
echo "Logs: $LOG_DIR"
echo "Repo venv: $REPO_VENV_DIR"
