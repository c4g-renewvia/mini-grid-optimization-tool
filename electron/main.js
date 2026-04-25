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
const NODE_BIN = path.join(
  RESOURCES,
  'node-runtime',
  process.platform === 'win32' ? 'node.exe' : 'node'
);

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
        googleClientId: partial.googleClientId || undefined,
        googleClientSecret: partial.googleClientSecret || undefined,
        authSecret:
          existing?.authSecret ?? crypto.randomBytes(32).toString('base64'),
      };
      writeConfig(config);
      setupWin.close();
      resolve(config);
    });
  });
}

function teeChildOutput(child, logPath, onLine) {
  const stream = fs.createWriteStream(logPath, { flags: 'a' });
  let buffer = '';
  const pipe = (chunk) => {
    stream.write(chunk);
    buffer += chunk.toString();
    let idx;
    while ((idx = buffer.indexOf('\n')) >= 0) {
      const line = buffer.slice(0, idx);
      buffer = buffer.slice(idx + 1);
      try {
        onLine(line);
      } catch {
        // status updates are best-effort
      }
    }
  };
  child.stdout?.on('data', pipe);
  child.stderr?.on('data', pipe);
  child.on('exit', () => stream.end());
}

function spawnSolver() {
  solverProc = spawn(SOLVER_BIN, [], {
    env: {
      ...process.env,
      MPLCONFIGDIR: path.join(CACHE_DIR, 'mpl'),
      SOLVER_HOST: '127.0.0.1',
      SOLVER_PORT: '8000',
      PYTHONUNBUFFERED: '1',
    },
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  teeChildOutput(solverProc, path.join(LOGS_DIR, 'solver.log'), (line) => {
    if (line.includes('Application startup complete') || line.includes('Uvicorn running')) {
      markStepComplete(2);
    }
  });
  solverProc.on('exit', (code) => {
    console.log(`solver exited (${code})`);
    solverProc = null;
  });
}

function spawnServer(config) {
  const env = {
    ...process.env,
    OFFLINE_MODE: 'true',
    DATABASE_URL: `file:${DB_PATH}`,
    GOOGLE_MAPS_API_KEY: config.mapsKey,
    AUTH_SECRET: config.authSecret,
    NEXTAUTH_URL: `http://localhost:${PORT}`,
    AUTH_TRUST_HOST: 'true',
    PORT: String(PORT),
    HOSTNAME: '127.0.0.1',
  };
  if (config.googleClientId && config.googleClientSecret) {
    env.AUTH_GOOGLE_ID = config.googleClientId;
    env.AUTH_GOOGLE_SECRET = config.googleClientSecret;
  }
  serverProc = spawn(NODE_BIN, [SERVER_ENTRY], {
    env,
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  teeChildOutput(serverProc, path.join(LOGS_DIR, 'server.log'), (line) => {
    if (line.includes('Ready in')) {
      markStepComplete(3);
    }
  });
  serverProc.on('exit', (code) => {
    console.log(`server exited (${code})`);
    serverProc = null;
  });
}

function waitForServer(timeoutMs = 180_000) {
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
  mainWindow.loadFile(path.join(__dirname, 'loading.html'));
}

function runInLoading(js) {
  if (!mainWindow || mainWindow.isDestroyed()) return;
  mainWindow.webContents.executeJavaScript(js).catch(() => {});
}

function markStepComplete(index) {
  runInLoading(
    `(() => { const el = document.querySelector('.step[data-step="${index}"]'); if (el) el.classList.add('done'); })()`
  );
}

function setLogHint(logDir) {
  const safe = JSON.stringify(`Logs: ${logDir}`);
  runInLoading(
    `(() => { const el = document.getElementById('hint'); if (el) el.textContent = ${safe}; })()`
  );
}

function showLoadingError(message) {
  const safe = JSON.stringify(message);
  runInLoading(
    `(() => {
      document.getElementById('root').classList.add('has-err');
      document.getElementById('err').textContent = ${safe};
    })()`
  );
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
  createMainWindow();
  // wait for the loading window to finish loading before any DOM updates
  await new Promise((resolve) => mainWindow.webContents.once('did-finish-load', resolve));
  setLogHint(LOGS_DIR);
  markStepComplete(1);
  spawnSolver();
  spawnServer(config);
  try {
    await waitForServer();
    markStepComplete(4);
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.loadURL(`http://localhost:${PORT}`);
    }
  } catch (err) {
    console.error('Server failed to come up:', err);
    showLoadingError(String(err));
  }
});

app.on('window-all-closed', () => {
  shutdown();
  app.quit();
});

app.on('before-quit', shutdown);
