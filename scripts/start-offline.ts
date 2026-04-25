import { spawn, type ChildProcess } from 'child_process';
import { existsSync, readFileSync } from 'fs';
import { resolve } from 'path';

const ROOT = resolve(import.meta.dirname, '..');
const ENV_PATH = resolve(ROOT, '.env.local');
const SOLVER_BIN = resolve(ROOT, 'backend/dist/minigrid-solver');
const BACKEND_DIR = resolve(ROOT, 'backend');

function loadEnv(): Record<string, string> {
  if (!existsSync(ENV_PATH)) {
    console.error(`Missing ${ENV_PATH}. Run: pnpm run offline:init`);
    process.exit(1);
  }
  const env: Record<string, string> = {};
  for (const line of readFileSync(ENV_PATH, 'utf8').split('\n')) {
    const m = line.match(/^([A-Z0-9_]+)=(.*)$/);
    if (m) env[m[1]] = m[2];
  }
  return env;
}

function prefixed(name: string, color: string) {
  return (chunk: Buffer) => {
    const tag = `\x1b[${color}m[${name}]\x1b[0m`;
    process.stdout.write(
      chunk
        .toString()
        .split('\n')
        .filter((l) => l.length)
        .map((l) => `${tag} ${l}`)
        .join('\n') + '\n'
    );
  };
}

function spawnSolver(env: NodeJS.ProcessEnv): ChildProcess {
  if (existsSync(SOLVER_BIN)) {
    console.log(`Starting solver binary: ${SOLVER_BIN}`);
    return spawn(SOLVER_BIN, [], { env, cwd: BACKEND_DIR });
  }
  console.log('Solver binary not found, falling back to uv run uvicorn');
  return spawn(
    'uv',
    ['run', 'uvicorn', 'server:app', '--host', '0.0.0.0', '--port', '8000'],
    { env, cwd: BACKEND_DIR, shell: true }
  );
}

function spawnNext(env: NodeJS.ProcessEnv): ChildProcess {
  return spawn('pnpm', ['exec', 'next', 'dev'], {
    env,
    cwd: ROOT,
    shell: true,
  });
}

const fileEnv = loadEnv();
const childEnv = { ...process.env, ...fileEnv };

const solver = spawnSolver(childEnv);
solver.stdout?.on('data', prefixed('solver', '36'));
solver.stderr?.on('data', prefixed('solver', '36'));

const next = spawnNext(childEnv);
next.stdout?.on('data', prefixed('next', '32'));
next.stderr?.on('data', prefixed('next', '32'));

let shuttingDown = false;
function shutdown(signal: NodeJS.Signals) {
  if (shuttingDown) return;
  shuttingDown = true;
  console.log(`\nReceived ${signal}, stopping...`);
  solver.kill(signal);
  next.kill(signal);
}

process.on('SIGINT', () => shutdown('SIGINT'));
process.on('SIGTERM', () => shutdown('SIGTERM'));

solver.on('exit', (code) => {
  console.log(`solver exited (${code})`);
  if (!shuttingDown) shutdown('SIGTERM');
});
next.on('exit', (code) => {
  console.log(`next exited (${code})`);
  if (!shuttingDown) shutdown('SIGTERM');
  process.exit(code ?? 0);
});
