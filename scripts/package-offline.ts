/**
 * Assemble the offline-mode distribution zip.
 *
 *   release/minigrid-tool-<platform>.zip
 *     solver/minigrid-solver           (PyInstaller --onefile binary)
 *     server/                          (Next.js standalone build)
 *       server.js
 *       .next/static/
 *       public/
 *       node_modules/
 *       package.json
 *     prisma/
 *       schema-offline/                (so the user can re-migrate if needed)
 *       offline.db                     (empty, migrated)
 *     setup.sh                         (first-run prompt for Maps API key)
 *     start.sh                         (launcher: solver + node server.js)
 *     README.txt                       (one-page user instructions)
 *
 * The zip is produced by running:
 *   1. OFFLINE_MODE=true pnpm run build  (Next.js standalone)
 *   2. bash backend/build-solver.sh      (PyInstaller solver, if missing)
 *   3. prisma db push --schema=...       (against a fresh empty offline.db)
 *   4. assemble the directory tree
 *   5. zip it
 *
 * Step 1's bundle is built WITHOUT any NEXT_PUBLIC_GOOGLE_MAPS_API_KEY set,
 * because the offline path reads the key from window.__APP_CONFIG__ at
 * runtime (injected by the server component RootLayout from process.env).
 */

import { spawnSync } from 'child_process';
import {
  cpSync,
  existsSync,
  mkdirSync,
  readFileSync,
  rmSync,
  writeFileSync,
} from 'fs';
import { platform } from 'os';
import { resolve, join } from 'path';

const ROOT = resolve(import.meta.dirname, '..');
const RELEASE = resolve(ROOT, 'release');
const STAGE = resolve(RELEASE, 'minigrid-tool');
const PLATFORM_MAP: Partial<Record<NodeJS.Platform, string>> = {
  darwin: 'mac',
  linux: 'linux',
  win32: 'windows',
};
const PLATFORM_TAG = PLATFORM_MAP[platform()] ?? platform();
const ZIP_PATH = resolve(RELEASE, `minigrid-tool-${PLATFORM_TAG}.zip`);

function run(cmd: string, args: string[], opts: { cwd?: string; env?: NodeJS.ProcessEnv } = {}) {
  console.log(`> ${cmd} ${args.join(' ')}`);
  const r = spawnSync(cmd, args, {
    stdio: 'inherit',
    cwd: opts.cwd ?? ROOT,
    env: opts.env ?? process.env,
    shell: process.platform === 'win32',
  });
  if (r.status !== 0) {
    throw new Error(`${cmd} ${args.join(' ')} exited with ${r.status}`);
  }
}

function step(label: string) {
  console.log(`\n=== ${label} ===`);
}

if (!existsSync(resolve(ROOT, 'prisma/schema-offline'))) {
  throw new Error(
    'prisma/schema-offline/ not found. Run from the repo root.'
  );
}

// 1. Next.js standalone build (offline mode env, no NEXT_PUBLIC maps key).
step('Build Next.js standalone (OFFLINE_MODE=true)');
const buildEnv = {
  ...process.env,
  OFFLINE_MODE: 'true',
  // Strip any inherited Maps key so it doesn't get inlined into the bundle.
  NEXT_PUBLIC_GOOGLE_MAPS_API_KEY: '',
};
// Inject `export const dynamic = 'force-dynamic'` into layout.tsx for the
// offline build only. Next 16 rejects non-literal `dynamic` exports, so we
// can't express this conditionally in source. Restore on success or failure.
const LAYOUT_PATH = resolve(ROOT, 'src/app/layout.tsx');
const layoutOriginal = readFileSync(LAYOUT_PATH, 'utf8');
const layoutWithDynamic = layoutOriginal.replace(
  /(export default async function RootLayout)/,
  "export const dynamic = 'force-dynamic';\n\n$1"
);
if (layoutWithDynamic === layoutOriginal) {
  throw new Error(
    'package-offline: failed to inject dynamic export into layout.tsx'
  );
}
writeFileSync(LAYOUT_PATH, layoutWithDynamic);
try {
  run('pnpm', ['exec', 'prisma', 'generate', '--schema=prisma/schema-offline'], {
    env: buildEnv,
  });
  run('pnpm', ['run', 'build'], { env: buildEnv });
} finally {
  writeFileSync(LAYOUT_PATH, layoutOriginal);
}

// 2. Solver binary (skip if it already exists).
step('Build PyInstaller solver binary (if missing)');
const solverBin = resolve(ROOT, 'backend/dist/minigrid-solver');
if (existsSync(solverBin)) {
  console.log(`Reusing ${solverBin}`);
} else {
  run('bash', ['build-solver.sh'], { cwd: resolve(ROOT, 'backend') });
}

// 3. Empty migrated SQLite DB seeded with the offline user.
step('Create offline.db (migrated, seeded with offline user)');
const tmpDb = resolve(ROOT, 'release/_tmp-offline.db');
if (existsSync(tmpDb)) rmSync(tmpDb);
mkdirSync(RELEASE, { recursive: true });
run(
  'pnpm',
  ['exec', 'prisma', 'db', 'push', '--schema=prisma/schema-offline'],
  {
    env: {
      ...process.env,
      DATABASE_URL: `file:${tmpDb}`,
    },
  }
);
const seedFileRel = 'scripts/.seed-package-tmp.mts';
const seedFile = resolve(ROOT, seedFileRel);
writeFileSync(
  seedFile,
  `import { PrismaClient } from '../prisma/generated/prisma/client.ts';
import { PrismaBetterSqlite3 } from '@prisma/adapter-better-sqlite3';
const prisma = new PrismaClient({ adapter: new PrismaBetterSqlite3({ url: process.env.DATABASE_URL! }) });
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
`
);
try {
  run('pnpm', ['exec', 'tsx', seedFileRel], {
    env: { ...process.env, DATABASE_URL: `file:${tmpDb}` },
  });
} finally {
  rmSync(seedFile, { force: true });
}

// 4. Assemble the staging tree.
step('Assemble staging directory');
if (existsSync(STAGE)) rmSync(STAGE, { recursive: true, force: true });
mkdirSync(STAGE, { recursive: true });
mkdirSync(join(STAGE, 'solver'));
mkdirSync(join(STAGE, 'server'));
mkdirSync(join(STAGE, 'prisma'));

// solver binary
cpSync(solverBin, join(STAGE, 'solver/minigrid-solver'));

// Next standalone: standalone/server.js + standalone/.next/* + standalone/node_modules
// Plus we manually copy .next/static and public/ (Next doesn't copy these).
// pnpm's node_modules uses *relative* symlinks (next -> .pnpm/next@.../...).
// cpSync preserves them verbatim and zip -y stores them as symlinks; on
// unzip they reconstruct the layout intact. Don't dereference — that would
// flatten the .pnpm peer-dep layout and break Node's resolution chain.
cpSync(resolve(ROOT, '.next/standalone'), join(STAGE, 'server'), {
  recursive: true,
  verbatimSymlinks: true,
});
// SECURITY: Next.js's standalone build copies any .env files it finds in the
// project root into the bundle. We do NOT want the dev's Postgres credentials,
// AUTH_SECRET, OAuth secrets, or Maps API key shipped in the zip — the offline
// distribution gets its own .env at install time via setup.sh. Strip them.
for (const leaked of ['.env', '.env.local', '.env.production', '.env.development']) {
  const p = join(STAGE, 'server', leaked);
  if (existsSync(p)) {
    rmSync(p);
    console.log(`stripped ${leaked} from server/`);
  }
}

// BACKSTOP: Next.js's standalone tracer misses some runtime deps under pnpm
// (the hoisted .pnpm/ store + symlink layout confuses it). styled-jsx is the
// canonical one — Next loads it via a require-hook at server start, so the
// static tracer doesn't see the require. Copy known-missing deps from the
// root node_modules over the standalone's so server.js boots cleanly.
const TRACER_MISSED_DEPS = ['styled-jsx'];
for (const dep of TRACER_MISSED_DEPS) {
  const src = resolve(ROOT, 'node_modules', dep);
  const dst = join(STAGE, 'server/node_modules', dep);
  if (existsSync(src) && !existsSync(dst)) {
    cpSync(src, dst, { recursive: true, dereference: true });
    console.log(`backfilled missing dep: ${dep}`);
  }
}
cpSync(
  resolve(ROOT, '.next/static'),
  join(STAGE, 'server/.next/static'),
  { recursive: true }
);
cpSync(resolve(ROOT, 'public'), join(STAGE, 'server/public'), {
  recursive: true,
});

// prisma: schema (so user can re-migrate) + empty db
cpSync(
  resolve(ROOT, 'prisma/schema-offline'),
  join(STAGE, 'prisma/schema-offline'),
  { recursive: true }
);
cpSync(tmpDb, join(STAGE, 'prisma/offline.db'));
rmSync(tmpDb);

// setup.sh + start.sh from the templates kept in scripts/
cpSync(resolve(ROOT, 'scripts/offline-setup.sh'), join(STAGE, 'setup.sh'));
cpSync(resolve(ROOT, 'scripts/offline-start.sh'), join(STAGE, 'start.sh'));
run('chmod', ['+x', join(STAGE, 'setup.sh'), join(STAGE, 'start.sh')]);

// One-page README.
writeFileSync(
  join(STAGE, 'README.txt'),
  [
    'Mini-Grid Optimization Tool — offline distribution',
    '',
    'Requirements: Node.js 24+ on the host. No Python, no Postgres, no Docker.',
    '',
    'First-time setup:',
    '  ./setup.sh        # prompts for your Google Maps API key, writes .env',
    '',
    'Every launch:',
    '  ./start.sh        # spawns the solver + the Next.js server, opens browser',
    '',
    'Persistent state lives outside this folder:',
    '  database  ~/Library/Application Support/minigrid-solver/ (macOS)',
    '            ~/.local/share/minigrid-solver/ (Linux)',
    '  cache     ~/Library/Caches/minigrid-solver/ (macOS)',
    '            ~/.cache/minigrid-solver/ (Linux)',
    '  logs      ~/Library/Logs/minigrid-solver/ (macOS)',
    '            ~/.local/state/minigrid-solver/logs/ (Linux)',
    '',
  ].join('\n')
);

// 5. Zip.
step(`Create ${ZIP_PATH}`);
if (existsSync(ZIP_PATH)) rmSync(ZIP_PATH);
// -y preserves symlinks (essential — pnpm's node_modules layout uses them).
run('zip', ['-ry', ZIP_PATH, 'minigrid-tool'], { cwd: RELEASE });

console.log(`\nDone: ${ZIP_PATH}`);
