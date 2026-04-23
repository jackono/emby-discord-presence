"use strict";

const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { spawn, spawnSync } = require("node:child_process");
const { Confirm, Input, Password, Select } = require("enquirer");

const APP_NAME = "media-discord-presence";
const LAUNCH_AGENT_LABEL = "com.media-discord-presence";
const EMBY_AUTH_HEADER = 'MediaBrowser Client="Media Discord Presence", Device="Node", DeviceId="media-discord-presence", Version="1.0.0"';

function ensureSupportedPlatform() {
  if (!["darwin", "linux", "win32"].includes(process.platform)) {
    throw new Error("This npm wrapper currently supports macOS, Linux, and Windows.");
  }
}

function getPaths() {
  const home = os.homedir();
  const repoRoot = path.resolve(__dirname, "..");
  const shared = {
    repoRoot,
    sourcePackageDir: path.join(repoRoot, "src", "media_discord_presence"),
    sourceRequirementsPath: path.join(repoRoot, "requirements.txt"),
    sourceConfigExamplePath: path.join(repoRoot, "config.example.json"),
  };

  if (process.platform === "darwin") {
    const appDir = path.join(home, ".local", "share", APP_NAME);
    const configDir = path.join(home, ".config", APP_NAME);
    const logDir = path.join(home, "Library", "Logs", APP_NAME);
    const launchAgentsDir = path.join(home, "Library", "LaunchAgents");
    return finalizePaths({
      ...shared,
      serviceMode: "launchd",
      appDir,
      configDir,
      configPath: path.join(configDir, "config.json"),
      logDir,
      stdoutLogPath: path.join(logDir, "stdout.log"),
      stderrLogPath: path.join(logDir, "stderr.log"),
      pidPath: path.join(appDir, "service.pid"),
      launchAgentsDir,
      launchAgentPath: path.join(launchAgentsDir, `${LAUNCH_AGENT_LABEL}.plist`),
    });
  }

  if (process.platform === "linux") {
    const xdgConfig = process.env.XDG_CONFIG_HOME || path.join(home, ".config");
    const xdgData = process.env.XDG_DATA_HOME || path.join(home, ".local", "share");
    const appDir = path.join(xdgData, APP_NAME);
    const configDir = path.join(xdgConfig, APP_NAME);
    const logDir = path.join(appDir, "logs");
    const systemdUserDir = path.join(xdgConfig, "systemd", "user");
    return finalizePaths({
      ...shared,
      serviceMode: commandExists("systemctl") ? "systemd" : "detached",
      appDir,
      configDir,
      configPath: path.join(configDir, "config.json"),
      logDir,
      stdoutLogPath: path.join(logDir, "stdout.log"),
      stderrLogPath: path.join(logDir, "stderr.log"),
      pidPath: path.join(appDir, "service.pid"),
      systemdUserDir,
      systemdServiceName: APP_NAME,
      systemdServicePath: path.join(systemdUserDir, `${APP_NAME}.service`),
    });
  }

  const appData = process.env.APPDATA || path.join(home, "AppData", "Roaming");
  const appDir = path.join(home, APP_NAME);
  const configDir = path.join(appData, APP_NAME);
  const logDir = path.join(appDir, "logs");
  const startupDir = path.join(appData, "Microsoft", "Windows", "Start Menu", "Programs", "Startup");
  return finalizePaths({
    ...shared,
    serviceMode: "windows-startup",
    appDir,
    configDir,
    configPath: path.join(configDir, "config.json"),
    logDir,
    stdoutLogPath: path.join(logDir, "stdout.log"),
    stderrLogPath: path.join(logDir, "stderr.log"),
    pidPath: path.join(appDir, "service.pid"),
    startupDir,
    startupScriptPath: path.join(startupDir, `${APP_NAME}.cmd`),
  });
}

function finalizePaths(paths) {
  const scriptsDir = process.platform === "win32" ? "Scripts" : "bin";
  const pythonName = process.platform === "win32" ? "python.exe" : "python";
  const pipName = process.platform === "win32" ? "pip.exe" : "pip";
  return {
    ...paths,
    installedPackageDir: path.join(paths.appDir, "media_discord_presence"),
    installedPythonPath: path.join(paths.appDir, ".venv", scriptsDir, pythonName),
    installedPipPath: path.join(paths.appDir, ".venv", scriptsDir, pipName),
  };
}

function run(command, args, options = {}) {
  const result = spawnSync(command, args, {
    stdio: options.stdio || "pipe",
    encoding: "utf8",
    cwd: options.cwd,
    env: options.env,
  });
  if (result.status !== 0) {
    const stderrText = (result.stderr || "").trim();
    throw new Error(stderrText || `${command} exited with code ${result.status}`);
  }
  return result.stdout || "";
}

function tryRun(command, args, options = {}) {
  const result = spawnSync(command, args, {
    stdio: options.stdio || "pipe",
    encoding: "utf8",
    cwd: options.cwd,
    env: options.env,
  });
  return {
    ok: result.status === 0,
    stdout: result.stdout || "",
    stderr: result.stderr || "",
    status: result.status,
  };
}

function commandExists(command) {
  if (process.platform === "win32") {
    return spawnSync("where", [command], { stdio: "ignore" }).status === 0;
  }
  return spawnSync("sh", ["-lc", `command -v ${command}`], { stdio: "ignore" }).status === 0;
}

function ensurePythonAvailable() {
  const python = getPythonInvocation();
  if (!python) {
    throw new Error("A Python 3 interpreter is required but was not found in PATH.");
  }
  return python;
}

function getPythonInvocation() {
  if (process.platform === "win32") {
    if (commandExists("py")) {
      return { command: "py", baseArgs: ["-3"] };
    }
    if (commandExists("python")) {
      return { command: "python", baseArgs: [] };
    }
    if (commandExists("python3")) {
      return { command: "python3", baseArgs: [] };
    }
    return null;
  }
  if (commandExists("python3")) {
    return { command: "python3", baseArgs: [] };
  }
  if (commandExists("python")) {
    return { command: "python", baseArgs: [] };
  }
  return null;
}

function runPython(python, args, options = {}) {
  return run(python.command, [...python.baseArgs, ...args], options);
}

function tryRunPython(python, args, options = {}) {
  return tryRun(python.command, [...python.baseArgs, ...args], options);
}

function mkdirp(dirPath) {
  fs.mkdirSync(dirPath, { recursive: true });
}

function copyRecursive(source, destination) {
  fs.rmSync(destination, { recursive: true, force: true });
  fs.cpSync(source, destination, { recursive: true });
}

function ensureInstalled() {
  const python = ensurePythonAvailable();
  const paths = getPaths();
  const venvPath = path.join(paths.appDir, ".venv");
  const needsBootstrap = !fs.existsSync(paths.installedPythonPath);

  mkdirp(paths.appDir);
  mkdirp(paths.configDir);
  mkdirp(paths.logDir);
  if (paths.launchAgentsDir) {
    mkdirp(paths.launchAgentsDir);
  }
  if (paths.systemdUserDir) {
    mkdirp(paths.systemdUserDir);
  }
  if (paths.startupDir) {
    mkdirp(paths.startupDir);
  }

  fs.copyFileSync(paths.sourceRequirementsPath, path.join(paths.appDir, "requirements.txt"));
  copyRecursive(paths.sourcePackageDir, paths.installedPackageDir);

  if (!fs.existsSync(paths.configPath)) {
    fs.copyFileSync(paths.sourceConfigExamplePath, paths.configPath);
    fs.chmodSync(paths.configPath, 0o600);
  }

  if (needsBootstrap) {
    bootstrapVirtualenv(python, venvPath);
    run(paths.installedPipPath, ["install", "--upgrade", "pip"], { stdio: "ignore" });
    run(paths.installedPipPath, ["install", "-r", path.join(paths.appDir, "requirements.txt")], { stdio: "ignore" });
  }

  writeServiceDefinition(paths);
}

function bootstrapVirtualenv(python, venvPath) {
  const directVenv = tryRunPython(python, ["-m", "venv", venvPath], { stdio: "pipe" });
  if (directVenv.ok) {
    return;
  }

  ensurePipAvailable(python);
  const virtualenvInstalled = tryRunPython(python, ["-m", "virtualenv", "--version"], { stdio: "pipe" });
  if (!virtualenvInstalled.ok) {
    runPython(python, ["-m", "pip", "install", "--user", "virtualenv"], { stdio: "ignore" });
  }
  runPython(python, ["-m", "virtualenv", venvPath], { stdio: "ignore" });
}

function ensurePipAvailable(python) {
  const pipCheck = tryRunPython(python, ["-m", "pip", "--version"], { stdio: "pipe" });
  if (pipCheck.ok) {
    return;
  }

  const getPipPath = path.join(os.tmpdir(), "media-discord-presence-get-pip.py");
  run("curl", ["-fsSL", "https://bootstrap.pypa.io/get-pip.py", "-o", getPipPath], { stdio: "ignore" });
  runPython(python, [getPipPath, "--user"], { stdio: "ignore" });
}

function writeServiceDefinition(paths) {
  if (paths.serviceMode === "launchd") {
    fs.writeFileSync(paths.launchAgentPath, buildPlist(paths), "utf8");
    return;
  }
  if (paths.serviceMode === "systemd") {
    fs.writeFileSync(paths.systemdServicePath, buildSystemdService(paths), "utf8");
    return;
  }
  if (paths.serviceMode === "windows-startup") {
    fs.writeFileSync(paths.startupScriptPath, buildWindowsStartupScript(paths), "utf8");
  }
}

function buildPlist(paths) {
  return `<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${LAUNCH_AGENT_LABEL}</string>
  <key>ProgramArguments</key>
  <array>
    <string>${paths.installedPythonPath}</string>
    <string>-m</string>
    <string>media_discord_presence</string>
  </array>
  <key>EnvironmentVariables</key>
  <dict>
    <key>MEDIA_DISCORD_PRESENCE_CONFIG</key>
    <string>${paths.configPath}</string>
  </dict>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>${paths.stdoutLogPath}</string>
  <key>StandardErrorPath</key>
  <string>${paths.stderrLogPath}</string>
  <key>ProcessType</key>
  <string>Interactive</string>
  <key>WorkingDirectory</key>
  <string>${paths.appDir}</string>
</dict>
</plist>
`;
}

function buildSystemdService(paths) {
  return `[Unit]
Description=Media Discord Presence
After=graphical-session.target

[Service]
WorkingDirectory=${paths.appDir}
ExecStart=${paths.installedPythonPath} -m media_discord_presence
Restart=always
RestartSec=5
Environment=MEDIA_DISCORD_PRESENCE_CONFIG=${paths.configPath}

[Install]
WantedBy=default.target
`;
}

function buildWindowsStartupScript(paths) {
  return `@echo off
set "MEDIA_DISCORD_PRESENCE_CONFIG=${paths.configPath}"
start "" /B "${paths.installedPythonPath}" -m media_discord_presence 1>>"${paths.stdoutLogPath}" 2>>"${paths.stderrLogPath}"
`;
}

function startService() {
  const paths = getPaths();
  if (paths.serviceMode === "launchd") {
    tryRun("launchctl", ["bootout", `gui/${process.getuid()}/${LAUNCH_AGENT_LABEL}`], { stdio: "ignore" });
    tryRun("launchctl", ["bootout", `gui/${process.getuid()}`, paths.launchAgentPath], { stdio: "ignore" });
    run("launchctl", ["bootstrap", `gui/${process.getuid()}`, paths.launchAgentPath], { stdio: "ignore" });
    run("launchctl", ["enable", `gui/${process.getuid()}/${LAUNCH_AGENT_LABEL}`], { stdio: "ignore" });
    run("launchctl", ["kickstart", "-k", `gui/${process.getuid()}/${LAUNCH_AGENT_LABEL}`], { stdio: "ignore" });
    return;
  }
  if (paths.serviceMode === "systemd") {
    run("systemctl", ["--user", "daemon-reload"], { stdio: "ignore" });
    run("systemctl", ["--user", "enable", "--now", paths.systemdServiceName], { stdio: "ignore" });
    return;
  }
  spawnDetachedService(paths);
}

function stopService() {
  const paths = getPaths();
  if (paths.serviceMode === "launchd") {
    tryRun("launchctl", ["bootout", `gui/${process.getuid()}/${LAUNCH_AGENT_LABEL}`], { stdio: "ignore" });
    tryRun("launchctl", ["bootout", `gui/${process.getuid()}`, paths.launchAgentPath], { stdio: "ignore" });
    return;
  }
  if (paths.serviceMode === "systemd") {
    tryRun("systemctl", ["--user", "stop", paths.systemdServiceName], { stdio: "ignore" });
    return;
  }
  stopDetachedService(paths);
}

function restartService() {
  stopService();
  startService();
}

function uninstall() {
  const paths = getPaths();
  stopService();
  if (paths.launchAgentPath) {
    fs.rmSync(paths.launchAgentPath, { force: true });
  }
  if (paths.systemdServicePath) {
    tryRun("systemctl", ["--user", "disable", paths.systemdServiceName], { stdio: "ignore" });
    fs.rmSync(paths.systemdServicePath, { force: true });
    tryRun("systemctl", ["--user", "daemon-reload"], { stdio: "ignore" });
  }
  if (paths.startupScriptPath) {
    fs.rmSync(paths.startupScriptPath, { force: true });
  }
  fs.rmSync(paths.appDir, { recursive: true, force: true });
}

function printStatus() {
  const paths = getPaths();
  console.log(`Config: ${paths.configPath} ${fs.existsSync(paths.configPath) ? "(exists)" : "(missing)"}`);
  console.log(`Service mode: ${paths.serviceMode}`);
  if (paths.launchAgentPath) {
    const agent = tryRun("launchctl", ["list"], { stdio: "pipe" });
    console.log(`LaunchAgent: ${paths.launchAgentPath} ${fs.existsSync(paths.launchAgentPath) ? "(exists)" : "(missing)"}`);
    console.log(`Loaded: ${agent.stdout.includes(LAUNCH_AGENT_LABEL) ? "yes" : "no"}`);
  } else if (paths.systemdServicePath) {
    const active = tryRun("systemctl", ["--user", "is-active", paths.systemdServiceName], { stdio: "pipe" });
    console.log(`systemd unit: ${paths.systemdServicePath} ${fs.existsSync(paths.systemdServicePath) ? "(exists)" : "(missing)"}`);
    console.log(`Loaded: ${active.ok ? active.stdout.trim() : "no"}`);
  } else if (paths.startupScriptPath) {
    console.log(`Startup script: ${paths.startupScriptPath} ${fs.existsSync(paths.startupScriptPath) ? "(exists)" : "(missing)"}`);
    console.log(`Loaded: ${isDetachedServiceRunning(paths) ? "yes" : "no"}`);
  }
  if (fs.existsSync(paths.stdoutLogPath)) {
    console.log(`Stdout log: ${paths.stdoutLogPath}`);
  }
  if (fs.existsSync(paths.stderrLogPath)) {
    console.log(`Stderr log: ${paths.stderrLogPath}`);
  }
}

function runServiceInForeground() {
  const paths = getPaths();
  const child = spawnSync(paths.installedPythonPath, ["-m", "media_discord_presence"], {
    stdio: "inherit",
    cwd: paths.appDir,
    env: {
      ...process.env,
      MEDIA_DISCORD_PRESENCE_CONFIG: paths.configPath,
    },
  });
  process.exit(child.status || 0);
}

function spawnDetachedService(paths) {
  stopDetachedService(paths);
  const out = fs.openSync(paths.stdoutLogPath, "a");
  const err = fs.openSync(paths.stderrLogPath, "a");
  const child = spawn(paths.installedPythonPath, ["-m", "media_discord_presence"], {
    cwd: paths.appDir,
    detached: true,
    stdio: ["ignore", out, err],
    env: {
      ...process.env,
      MEDIA_DISCORD_PRESENCE_CONFIG: paths.configPath,
    },
    windowsHide: true,
  });
  fs.writeFileSync(paths.pidPath, `${child.pid}\n`, "utf8");
  child.unref();
}

function stopDetachedService(paths) {
  if (!fs.existsSync(paths.pidPath)) {
    return;
  }
  const pid = Number(fs.readFileSync(paths.pidPath, "utf8").trim());
  if (Number.isFinite(pid) && pid > 0) {
    if (process.platform === "win32") {
      tryRun("taskkill", ["/PID", String(pid), "/T", "/F"], { stdio: "ignore" });
    } else {
      try {
        process.kill(pid, "SIGTERM");
      } catch {}
    }
  }
  fs.rmSync(paths.pidPath, { force: true });
}

function isDetachedServiceRunning(paths) {
  if (!fs.existsSync(paths.pidPath)) {
    return false;
  }
  const pid = Number(fs.readFileSync(paths.pidPath, "utf8").trim());
  if (!Number.isFinite(pid) || pid <= 0) {
    return false;
  }
  try {
    process.kill(pid, 0);
    return true;
  } catch {
    return false;
  }
}

async function ensureConfigured(options = {}) {
  const paths = getPaths();
  mkdirp(paths.configDir);
  if (fs.existsSync(paths.configPath) && !options.force) {
    return;
  }

  const existingConfig = fs.existsSync(paths.configPath)
    ? JSON.parse(fs.readFileSync(paths.configPath, "utf8"))
    : null;
  const config = await promptForConfig(existingConfig);
  fs.writeFileSync(paths.configPath, `${JSON.stringify(config, null, 2)}\n`, "utf8");
  fs.chmodSync(paths.configPath, 0o600);
  console.log(`Wrote config to ${paths.configPath}`);
}

async function promptForConfig(existingConfig = null) {
  printSection("Discord");
  const discordClientId = await askDiscordClientId(existingConfig?.discord?.client_id || "");
  const providerMode = await askSelect(
    "Preferred provider mode",
    [
      { name: "auto", message: "Auto-detect between configured providers" },
      { name: "plex", message: "Plex only" },
      { name: "jellyfin", message: "Jellyfin only" },
      { name: "emby", message: "Emby only" },
    ],
    existingConfig?.provider || "auto"
  );
  const pollIntervalValue = await askInput(
    "Poll interval in seconds",
    String(existingConfig?.poll_interval_seconds || 15),
    validatePositiveInteger
  );

  printSection("Metadata");
  const tmdbApiKey = await askInput("TMDB API key (optional, for artwork)", existingConfig?.tmdb?.api_key || "");
  const omdbApiKey = await askInput("OMDb API key (optional, for IMDb buttons)", existingConfig?.discord?.omdb_api_key || "");

  const config = {
    provider: providerMode,
    client_filters: Array.isArray(existingConfig?.client_filters) ? existingConfig.client_filters : [],
    poll_interval_seconds: Number(pollIntervalValue),
    discord: {
      client_id: discordClientId,
      large_image: existingConfig?.discord?.large_image || "optional_uploaded_asset_key",
      small_image: existingConfig?.discord?.small_image || "optional_uploaded_asset_key",
      small_text: existingConfig?.discord?.small_text || "Watching via media server",
      buttons: Array.isArray(existingConfig?.discord?.buttons) ? existingConfig.discord.buttons : [],
      status_display: "auto",
      omdb_api_key: omdbApiKey,
      auto_buttons: {
        imdb: Boolean(omdbApiKey),
        mal: Boolean(existingConfig?.discord?.auto_buttons?.mal),
      },
      templates: {
        episode_details: "{title}",
        episode_state: "{show} • {se} • {device_client}",
        movie_details: "{title}{year_suffix}",
        movie_state: "{device_client}",
        track_details: "{title}",
        track_state: "{artist} • {album} • {device_client}",
        default_details: "{title}",
        default_state: "{device_client}",
      },
    },
    tmdb: {
      api_key: tmdbApiKey,
      bearer_token: "",
    },
  };

  const requestedProviders = providerMode === "auto"
    ? ["plex", "jellyfin", "emby"]
    : [providerMode];

  printSection("Providers");
  for (const provider of requestedProviders) {
    const enabled = providerMode === provider
      ? true
      : await askConfirm(`Configure ${capitalize(provider)}?`, Boolean(existingConfig?.[provider] || provider === "plex"));
    if (!enabled) {
      continue;
    }
    config[provider] = await promptForProvider(provider, existingConfig?.[provider] || null);
    const testResult = await testProvider(provider, config[provider]);
    if (!testResult.ok) {
      const continueAnyway = await askConfirm(
        `${capitalize(provider)} test failed: ${testResult.message}. Save this provider anyway?`,
        false
      );
      if (!continueAnyway) {
        config[provider] = await promptForProvider(provider, config[provider]);
        const retryResult = await testProvider(provider, config[provider]);
        if (!retryResult.ok) {
          throw new Error(`${capitalize(provider)} validation failed: ${retryResult.message}`);
        }
      }
    } else {
      console.log(`✓ ${capitalize(provider)} connection looks valid.`);
    }
  }

  if (!config.plex && !config.jellyfin && !config.emby) {
    throw new Error("At least one provider must be configured.");
  }

  return config;
}

async function promptForProvider(provider, existingProvider = null) {
  if (provider === "plex") {
    return {
      url: await askRequiredInput("Plex URL", validateUrl, existingProvider?.url || ""),
      token: await askSecretWithExisting("Plex token", existingProvider?.token || ""),
      username: await askRequiredInput("Plex username", null, existingProvider?.username || ""),
    };
  }

  return {
    url: await askRequiredInput(`${capitalize(provider)} URL`, validateUrl, existingProvider?.url || ""),
    username: await askRequiredInput(`${capitalize(provider)} username`, null, existingProvider?.username || ""),
    password: await askSecretWithExisting(`${capitalize(provider)} password`, existingProvider?.password || ""),
  };
}

async function askDiscordClientId(initial = "") {
  return askRequiredInput("Discord application client ID", validateDiscordClientId, initial);
}

async function askRequiredInput(message, validate = null, initial = "") {
  return askInput(message, initial, (value) => {
    if (!String(value || "").trim()) {
      return "This field is required.";
    }
    if (validate) {
      return validate(value);
    }
    return true;
  });
}

async function askRequiredSecret(message) {
  while (true) {
    const value = (await new Password({ message }).run()).trim();
    if (value) {
      return value;
    }
  }
}

async function askSecretWithExisting(message, existingValue = "") {
  if (existingValue) {
    const action = await askSelect(
      message,
      [
        { name: "keep", message: "Keep existing value" },
        { name: "replace", message: "Enter a new value" },
      ],
      "keep"
    );
    if (action === "keep") {
      return existingValue;
    }
  }
  return askRequiredSecret(message);
}

async function askInput(message, initial = "", validate = null) {
  return new Input({ message, initial, validate }).run();
}

async function askConfirm(message, initial = true) {
  return new Confirm({ message, initial }).run();
}

async function askSelect(message, choices, initialName) {
  const initial = Math.max(0, choices.findIndex((choice) => choice.name === initialName));
  return new Select({ message, choices, initial }).run();
}

function validateDiscordClientId(value) {
  const text = String(value || "").trim();
  if (!/^\d{17,20}$/.test(text)) {
    return "Discord client ID should be a numeric application ID, usually 17-20 digits.";
  }
  return true;
}

function validatePositiveInteger(value) {
  const text = String(value || "").trim();
  if (!/^\d+$/.test(text) || Number(text) <= 0) {
    return "Enter a positive whole number.";
  }
  return true;
}

function validateUrl(value) {
  try {
    const url = new URL(String(value || "").trim());
    if (!["http:", "https:"].includes(url.protocol)) {
      return "URL must start with http:// or https://";
    }
    return true;
  } catch {
    return "Enter a valid URL.";
  }
}

function printSection(title) {
  console.log(`\n== ${title} ==`);
}

async function testProvider(provider, providerConfig) {
  try {
    if (provider === "plex") {
      const url = new URL("/identity", providerConfig.url.endsWith("/") ? providerConfig.url : `${providerConfig.url}/`);
      url.searchParams.set("X-Plex-Token", providerConfig.token);
      const response = await fetch(url, {
        headers: { Accept: "application/xml" },
        signal: AbortSignal.timeout(10_000),
      });
      if (!response.ok) {
        return { ok: false, message: `HTTP ${response.status}` };
      }
      return { ok: true };
    }

    const url = new URL("/Users/AuthenticateByName", providerConfig.url.endsWith("/") ? providerConfig.url : `${providerConfig.url}/`);
    const response = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Emby-Authorization": EMBY_AUTH_HEADER,
      },
      body: JSON.stringify({ Username: providerConfig.username, Pw: providerConfig.password }),
      signal: AbortSignal.timeout(10_000),
    });
    if (!response.ok) {
      return { ok: false, message: `HTTP ${response.status}` };
    }
    const data = await response.json().catch(() => null);
    if (!data || !data.AccessToken) {
      return { ok: false, message: "No access token returned" };
    }
    return { ok: true };
  } catch (error) {
    return { ok: false, message: error.message || String(error) };
  }
}

function capitalize(value) {
  return value.slice(0, 1).toUpperCase() + value.slice(1);
}

module.exports = {
  ensureConfigured,
  ensureInstalled,
  ensureSupportedPlatform,
  getPaths,
  printStatus,
  restartService,
  runServiceInForeground,
  startService,
  stopService,
  uninstall,
};
