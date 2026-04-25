const { app, BrowserWindow, ipcMain } = require('electron');
const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');
const crypto = require('crypto');
const http = require('http');

const USER_DATA = app.getPath('userData');
const CACHE_DIR = app.getPath('cache');
const LOGS_DIR = app.getPath('logs');
const CONFIG_PATH = path.join(USER_DATA, 'config.json');
const DB_PATH = path.join(USER_DATA, 'offline.db');
const PORT = 3000;

const RESOURCES = app.isPackaged
  ? process.resourcesPath
  : path.join(__dirname, '..', 'release', 'minigrid-tool');
const SOLVER_BIN = path.join(RESOURCES, 'solver', 'minigrid-solver');
const SERVER_ENTRY = path.join(RESOURCES, 'server', 'server.js');
const SEED_DB = path.join(RESOURCES, 'prisma', 'offline.db');

let mainWindow = null;
let solverProc = null;
let serverProc = null;

function ensureDirs() {
  for (const d of [USER_DATA, CACHE_DIR, LOGS_DIR, path.join(CACHE_DIR, 'mpl')]) {
    fs.mkdirSync(d, { recursive: true });
  }
  if (!fs.existsSync(DB_PATH) && fs.existsSync(SEED_DB)) {
    fs.copyFileSync(SEED_DB, DB_PATH);
  }
}

function readConfig() {
  if (!fs.existsSync(CONFIG_PATH)) return null;
  try {
    return JSON.parse(fs.readFileSync(CONFIG_PATH, 'utf8'));
  } catch {
    return null;
  }
}

function writeConfig(config) {
  fs.writeFileSync(CONFIG_PATH, JSON.stringify(config, null, 2));
}

function getOrPromptConfig() {
  return new Promise((resolve, reject) => {
    const existing = readConfig();
    if (existing?.mapsKey) {
      resolve(existing);
      return;
    }
    const setupWin = new BrowserWindow({
      width: 540,
      height: 360,
      resizable: false,
      title: 'Mini-Grid — Setup',
      webPreferences: {
        preload: path.join(__dirname, 'preload.js'),
        contextIsolation: true,
      },
    });
    setupWin.loadFile(path.join(__dirname, 'setup.html'));
    setupWin.on('closed', () => {
      if (!readConfig()) reject(new Error('Setup cancelled'));
    });
    ipcMain.handleOnce('save-config', (_e, partial) => {
      const config = {
        mapsKey: partial.mapsKey,
        authSecret:
          existing?.authSecret ?? crypto.randomBytes(32).toString('base64'),
      };
      writeConfig(config);
      setupWin.close();
      resolve(config);
    });
  });
}

function spawnSolver() {
  const log = fs.openSync(path.join(LOGS_DIR, 'solver.log'), 'a');
  solverProc = spawn(SOLVER_BIN, [], {
    env: {
      ...process.env,
      MPLCONFIGDIR: path.join(CACHE_DIR, 'mpl'),
      SOLVER_HOST: '127.0.0.1',
      SOLVER_PORT: '8000',
    },
    stdio: ['ignore', log, log],
  });
  solverProc.on('exit', (code) => {
    console.log(`solver exited (${code})`);
    solverProc = null;
  });
}

function spawnServer(config) {
  const log = fs.openSync(path.join(LOGS_DIR, 'server.log'), 'a');
  serverProc = spawn(process.execPath, [SERVER_ENTRY], {
    env: {
      ...process.env,
      ELECTRON_RUN_AS_NODE: '1',
      OFFLINE_MODE: 'true',
      DATABASE_URL: `file:${DB_PATH}`,
      GOOGLE_MAPS_API_KEY: config.mapsKey,
      AUTH_SECRET: config.authSecret,
      NEXTAUTH_URL: `http://localhost:${PORT}`,
      AUTH_TRUST_HOST: 'true',
      PORT: String(PORT),
      HOSTNAME: '127.0.0.1',
    },
    stdio: ['ignore', log, log],
  });
  serverProc.on('exit', (code) => {
    console.log(`server exited (${code})`);
    serverProc = null;
  });
}

function waitForServer(timeoutMs = 60_000) {
  const start = Date.now();
  return new Promise((resolve, reject) => {
    const tick = () => {
      const req = http.get(
        { host: '127.0.0.1', port: PORT, path: '/api/health' },
        (res) => {
          res.resume();
          if (res.statusCode === 200) return resolve();
          if (Date.now() - start > timeoutMs) return reject(new Error('timeout'));
          setTimeout(tick, 500);
        }
      );
      req.on('error', () => {
        if (Date.now() - start > timeoutMs) return reject(new Error('timeout'));
        setTimeout(tick, 500);
      });
      req.setTimeout(2000, () => req.destroy());
    };
    tick();
  });
}

function createMainWindow() {
  mainWindow = new BrowserWindow({
    width: 1440,
    height: 900,
    title: 'Mini-Grid Optimization Tool',
    webPreferences: { contextIsolation: true },
  });
  mainWindow.loadURL(`http://localhost:${PORT}`);
}

function shutdown() {
  for (const p of [solverProc, serverProc]) {
    if (p && !p.killed) p.kill();
  }
}

app.whenReady().then(async () => {
  ensureDirs();
  let config;
  try {
    config = await getOrPromptConfig();
  } catch (err) {
    console.error('Setup error:', err);
    app.quit();
    return;
  }
  spawnSolver();
  spawnServer(config);
  try {
    await waitForServer();
  } catch (err) {
    console.error('Server failed to come up:', err);
    shutdown();
    app.quit();
    return;
  }
  createMainWindow();
});

app.on('window-all-closed', () => {
  shutdown();
  app.quit();
});

app.on('before-quit', shutdown);
