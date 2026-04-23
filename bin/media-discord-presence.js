#!/usr/bin/env node

const {
  ensureInstalled,
  ensureConfigured,
  ensureSupportedPlatform,
  getPaths,
  printStatus,
  restartService,
  runServiceInForeground,
  startService,
  stopService,
  uninstall,
} = require("../lib/cli");

async function main() {
  ensureSupportedPlatform();
  const command = process.argv[2] || "run";

  if (command === "setup") {
    await ensureConfigured({ force: true });
    return;
  }

  if (command === "edit") {
    await ensureConfigured({ force: true });
    return;
  }

  if (command === "install") {
    await ensureConfigured({ force: false });
    ensureInstalled();
    startService();
    console.log(`Installed service with config at ${getPaths().configPath}`);
    return;
  }

  if (command === "start") {
    await ensureConfigured({ force: false });
    ensureInstalled();
    startService();
    console.log("Service started.");
    return;
  }

  if (command === "stop") {
    stopService();
    console.log("Service stopped.");
    return;
  }

  if (command === "restart") {
    await ensureConfigured({ force: false });
    ensureInstalled();
    restartService();
    console.log("Service restarted.");
    return;
  }

  if (command === "status") {
    printStatus();
    return;
  }

  if (command === "foreground") {
    await ensureConfigured({ force: false });
    ensureInstalled();
    runServiceInForeground();
    return;
  }

  if (command === "uninstall") {
    uninstall();
    console.log("Service uninstalled.");
    return;
  }

  if (command === "run") {
    await ensureConfigured({ force: false });
    ensureInstalled();
    startService();
    console.log("Service is ready and running.");
    return;
  }

  console.error(`Unknown command: ${command}`);
  console.error("Available commands: run, setup, edit, install, start, stop, restart, status, foreground, uninstall");
  process.exit(1);
}

main().catch((error) => {
  console.error(error.message || String(error));
  process.exit(1);
});
