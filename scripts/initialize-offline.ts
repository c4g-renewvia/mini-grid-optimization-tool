import { spawn } from 'child_process';
import { randomBytes } from 'crypto';
import { existsSync, readFileSync, writeFileSync } from 'fs';
import { createInterface } from 'readline/promises';
import { stdin as input, stdout as output } from 'process';
import { resolve } from 'path';

const ROOT = resolve(import.meta.dirname, '..');
const ENV_PATH = resolve(ROOT, '.env.local');
const SCHEMA_PATH = 'prisma/schema-offline';
const DB_PATH = 'file:./prisma/offline.db';

function readEnv(): Record<string, string> {
  if (!existsSync(ENV_PATH)) return {};
  const env: Record<string, string> = {};
  for (const line of readFileSync(ENV_PATH, 'utf8').split('\n')) {
    const m = line.match(/^([A-Z0-9_]+)=(.*)$/);
    if (m) env[m[1]] = m[2];
  }
  return env;
}

function writeEnv(env: Record<string, string>) {
  const out = Object.entries(env)
    .map(([k, v]) => `${k}=${v}`)
    .join('\n');
  writeFileSync(ENV_PATH, out + '\n');
}

function run(cmd: string, args: string[]): Promise<void> {
  return new Promise((resolveP, reject) => {
    const child = spawn(cmd, args, { stdio: 'inherit', shell: true, cwd: ROOT });
    child.on('exit', (code) =>
      code === 0 ? resolveP() : reject(new Error(`${cmd} ${args.join(' ')} exited ${code}`))
    );
  });
}

async function main() {
  const env = readEnv();

  env.OFFLINE_MODE = 'true';
  env.DATABASE_URL = DB_PATH;
  env.NEXTAUTH_URL ||= 'http://localhost:3000';
  env.AUTH_TRUST_HOST ||= 'true';
  env.AUTH_SECRET ||= randomBytes(32).toString('base64');

  if (!env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY) {
    const rl = createInterface({ input, output });
    const key = (
      await rl.question('Enter your NEXT_PUBLIC_GOOGLE_MAPS_API_KEY: ')
    ).trim();
    rl.close();
    if (!key) {
      console.error('Google Maps API key is required.');
      process.exit(1);
    }
    env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY = key;
  }

  writeEnv(env);
  console.log(`Wrote ${ENV_PATH}`);

  const childEnv = { ...process.env, ...env };

  console.log('Pushing schema to SQLite...');
  await new Promise<void>((resolveP, reject) => {
    const child = spawn(
      'pnpm',
      ['exec', 'prisma', 'db', 'push', `--schema=${SCHEMA_PATH}`, '--skip-generate'],
      { stdio: 'inherit', shell: true, cwd: ROOT, env: childEnv }
    );
    child.on('exit', (code) =>
      code === 0 ? resolveP() : reject(new Error(`prisma db push exited ${code}`))
    );
  });

  console.log('Generating Prisma client...');
  await new Promise<void>((resolveP, reject) => {
    const child = spawn(
      'pnpm',
      ['exec', 'prisma', 'generate', `--schema=${SCHEMA_PATH}`],
      { stdio: 'inherit', shell: true, cwd: ROOT, env: childEnv }
    );
    child.on('exit', (code) =>
      code === 0 ? resolveP() : reject(new Error(`prisma generate exited ${code}`))
    );
  });

  console.log('Upserting offline user...');
  const seedScript = `
    import { PrismaClient } from '${resolve(ROOT, 'prisma/generated/prisma/client.js').replace(/\\\\/g, '/')}';
    const prisma = new PrismaClient();
    await prisma.user.upsert({
      where: { id: 'offline-user' },
      update: {},
      create: {
        id: 'offline-user',
        email: 'offline@localhost',
        name: 'Offline User',
        role: 'ADMIN',
        emailVerified: new Date(),
      },
    });
    await prisma.$disconnect();
  `;
  await new Promise<void>((resolveP, reject) => {
    const child = spawn('pnpm', ['exec', 'tsx', '-e', seedScript], {
      stdio: 'inherit',
      shell: true,
      cwd: ROOT,
      env: childEnv,
    });
    child.on('exit', (code) =>
      code === 0 ? resolveP() : reject(new Error(`seed exited ${code}`))
    );
  });

  console.log('Offline initialization complete.');
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
