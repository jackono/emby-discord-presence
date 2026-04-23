"use strict";

const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { spawnSync } = require("node:child_process");
const { Confirm, Input, Password, Select } = require("enquirer");

const APP_NAME = "media-discord-presence";
const LAUNCH_AGENT_LABEL = "com.media-discord-presence";
const EMBY_AUTH_HEADER = 'MediaBrowser Client="Media Discord Presence", Device="Node", DeviceId="media-discord-presence", Version="1.0.0"';

function ensureSupportedPlatform() {
  if (process.platform !== "darwin") {
    throw new Error("This npm wrapper currently supports macOS only.");
  }
}

function getPaths() {
  const home = os.homedir();
  const repoRoot = path.resolve(__dirname, "..");
  const appDir = path.join(home, ".local", "share", APP_NAME);
  const configDir = path.join(home, ".config", APP_NAME);
  const logDir = path.join(home, "Library", "Logs", APP_NAME);
  const launchAgentsDir = path.join(home, "Library", "LaunchAgents");
  const launchAgentPath = path.join(launchAgentsDir, `${LAUNCH_AGENT_LABEL}.plist`);
  return {
    repoRoot,
    appDir,
    configDir,
    configPath: path.join(configDir, "config.json"),
    logDir,
    stdoutLogPath: path.join(logDir, "stdout.log"),
    stderrLogPath: path.join(logDir, "stderr.log"),
    launchAgentsDir,
    launchAgentPath,
    installedPackageDir: path.join(appDir, "media_discord_presence"),
    installedPythonPath: path.join(appDir, ".venv", "bin", "python"),
    installedPipPath: path.join(appDir, ".venv", "bin", "pip"),
    sourcePackageDir: path.join(repoRoot, "src", "media_discord_presence"),
    sourceRequirementsPath: path.join(repoRoot, "requirements.txt"),
    sourceConfigExamplePath: path.join(repoRoot, "config.example.json"),
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
  return spawnSync("sh", ["-lc", `command -v ${command}`], { stdio: "ignore" }).status === 0;
}

function ensurePythonAvailable() {
  if (!commandExists("python3")) {
    throw new Error("python3 is required but was not found in PATH.");
  }
}

function mkdirp(dirPath) {
  fs.mkdirSync(dirPath, { recursive: true });
}

function copyRecursive(source, destination) {
  fs.rmSync(destination, { recursive: true, force: true });
  fs.cpSync(source, destination, { recursive: true });
}

function ensureInstalled() {
  ensurePythonAvailable();
  const paths = getPaths();
  const venvPath = path.join(paths.appDir, ".venv");
  const needsBootstrap = !fs.existsSync(paths.installedPythonPath);
  mkdirp(paths.appDir);
  mkdirp(paths.configDir);
  mkdirp(paths.logDir);
  mkdirp(paths.launchAgentsDir);

  fs.copyFileSync(paths.sourceRequirementsPath, path.join(paths.appDir, "requirements.txt"));
  copyRecursive(paths.sourcePackageDir, paths.installedPackageDir);

  if (!fs.existsSync(paths.configPath)) {
    fs.copyFileSync(paths.sourceConfigExamplePath, paths.configPath);
    fs.chmodSync(paths.configPath, 0o600);
  }

  if (needsBootstrap) {
    run("python3", ["-m", "venv", venvPath]);
    run(paths.installedPipPath, ["install", "--upgrade", "pip"], { stdio: "ignore" });
    run(paths.installedPipPath, ["install", "-r", path.join(paths.appDir, "requirements.txt")], { stdio: "ignore" });
  }

  fs.writeFileSync(paths.launchAgentPath, buildPlist(paths), "utf8");
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

function startService() {
  const paths = getPaths();
  tryRun("launchctl", ["bootout", `gui/${process.getuid()}/${LAUNCH_AGENT_LABEL}`], { stdio: "ignore" });
  tryRun("launchctl", ["bootout", `gui/${process.getuid()}`, paths.launchAgentPath], { stdio: "ignore" });
  run("launchctl", ["bootstrap", `gui/${process.getuid()}`, paths.launchAgentPath], { stdio: "ignore" });
  run("launchctl", ["enable", `gui/${process.getuid()}/${LAUNCH_AGENT_LABEL}`], { stdio: "ignore" });
  run("launchctl", ["kickstart", "-k", `gui/${process.getuid()}/${LAUNCH_AGENT_LABEL}`], { stdio: "ignore" });
}

function stopService() {
  const paths = getPaths();
  tryRun("launchctl", ["bootout", `gui/${process.getuid()}/${LAUNCH_AGENT_LABEL}`], { stdio: "ignore" });
  tryRun("launchctl", ["bootout", `gui/${process.getuid()}`, paths.launchAgentPath], { stdio: "ignore" });
}

function restartService() {
  stopService();
  startService();
}

function uninstall() {
  const paths = getPaths();
  stopService();
  fs.rmSync(paths.launchAgentPath, { force: true });
  fs.rmSync(paths.appDir, { recursive: true, force: true });
}

function printStatus() {
  const paths = getPaths();
  const agent = tryRun("launchctl", ["list"], { stdio: "pipe" });
  const listed = agent.stdout.includes(LAUNCH_AGENT_LABEL);
  console.log(`Config: ${paths.configPath} ${fs.existsSync(paths.configPath) ? "(exists)" : "(missing)"}`);
  console.log(`LaunchAgent: ${paths.launchAgentPath} ${fs.existsSync(paths.launchAgentPath) ? "(exists)" : "(missing)"}`);
  console.log(`Loaded: ${listed ? "yes" : "no"}`);
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
      `${message}`,
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
  return new Input({
    message,
    initial,
    validate,
  }).run();
}

async function askConfirm(message, initial = true) {
  return new Confirm({
    message,
    initial,
  }).run();
}

async function askSelect(message, choices, initialName) {
  const initial = Math.max(0, choices.findIndex((choice) => choice.name === initialName));
  return new Select({
    message,
    choices,
    initial,
  }).run();
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
