/**
 * Shared offline-bundle assembly. Used by both Layer 2 (zip distribution) and
 * Layer 3 (Electron). Produces a directory tree containing the solver binary,
 * the Next.js standalone server, a seeded migrated SQLite DB, and the
 * Prisma offline schema.
 *
 *   <stageDir>/
 *     solver/minigrid-solver
 *     server/                       (Next.js standalone)
 *     prisma/schema-offline/
 *     prisma/offline.db             (migrated, seeded with offline-user)
 *
 * Caller is responsible for whatever wraps this:
 *   - Layer 2 adds setup.sh, start.sh, README.txt, then zips
 *   - Layer 3 hands the dir to electron-builder as extraResources
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
import { resolve, join } from 'path';
import { tmpdir } from 'os';

export interface AssembleOptions {
  /** Repo root (where package.json lives). */
  root: string;
  /** Output directory; will be wiped and recreated. */
  stageDir: string;
}

function run(
  cmd: string,
  args: string[],
  opts: { cwd?: string; env?: NodeJS.ProcessEnv } = {}
) {
  console.log(`> ${cmd} ${args.join(' ')}`);
  const r = spawnSync(cmd, args, {
    stdio: 'inherit',
    cwd: opts.cwd,
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

export function assembleOfflineBundle({ root, stageDir }: AssembleOptions) {
  if (!existsSync(resolve(root, 'prisma/schema-offline'))) {
    throw new Error('prisma/schema-offline/ not found. Run from the repo root.');
  }

  // 1. Next.js standalone build (offline mode env, no NEXT_PUBLIC maps key).
  step('Build Next.js standalone (OFFLINE_MODE=true)');
  // Placeholder DATABASE_URL so src/lib/prisma.ts doesn't throw at module load
  // during `next build`'s page-data collection. Nothing actually queries; the
  // empty file is created and removed below.
  const buildPlaceholderDb = join(tmpdir(), `minigrid-build-${process.pid}.db`);
  const buildEnv = {
    ...process.env,
    OFFLINE_MODE: 'true',
    NEXT_PUBLIC_GOOGLE_MAPS_API_KEY: '',
    DATABASE_URL: `file:${buildPlaceholderDb}`,
  };
  // Inject `export const dynamic = 'force-dynamic'` into layout.tsx for the
  // offline build only. Next 16 rejects non-literal `dynamic` exports, so we
  // can't express this conditionally in source. Restore on success or failure.
  const LAYOUT_PATH = resolve(root, 'src/app/layout.tsx');
  const layoutOriginal = readFileSync(LAYOUT_PATH, 'utf8');
  const layoutWithDynamic = layoutOriginal.replace(
    /(export default async function RootLayout)/,
    "export const dynamic = 'force-dynamic';\n\n$1"
  );
  if (layoutWithDynamic === layoutOriginal) {
    throw new Error(
      'build-offline-bundle: failed to inject dynamic export into layout.tsx'
    );
  }
  writeFileSync(LAYOUT_PATH, layoutWithDynamic);
  try {
    run(
      'pnpm',
      ['exec', 'prisma', 'generate', '--schema=prisma/schema-offline'],
      { cwd: root, env: buildEnv }
    );
    run('pnpm', ['run', 'build'], { cwd: root, env: buildEnv });
  } finally {
    writeFileSync(LAYOUT_PATH, layoutOriginal);
    if (existsSync(buildPlaceholderDb)) rmSync(buildPlaceholderDb);
  }

  // 2. Solver binary (skip if it already exists).
  step('Build PyInstaller solver binary (if missing)');
  const solverBin = resolve(root, 'backend/dist/minigrid-solver');
  if (existsSync(solverBin)) {
    console.log(`Reusing ${solverBin}`);
  } else {
    run('bash', ['build-solver.sh'], { cwd: resolve(root, 'backend') });
  }

  // 3. Migrated SQLite DB seeded with the anonymous user.
  step('Create offline.db (migrated, seeded with anonymous user)');
  const releaseDir = resolve(root, 'release');
  mkdirSync(releaseDir, { recursive: true });
  const tmpDb = resolve(releaseDir, '_tmp-offline.db');
  if (existsSync(tmpDb)) rmSync(tmpDb);
  run(
    'pnpm',
    ['exec', 'prisma', 'db', 'push', '--schema=prisma/schema-offline'],
    {
      cwd: root,
      env: { ...process.env, DATABASE_URL: `file:${tmpDb}` },
    }
  );
  const seedFileRel = 'scripts/.seed-bundle-tmp.mts';
  const seedFile = resolve(root, seedFileRel);
  writeFileSync(
    seedFile,
    `import { PrismaClient } from '../prisma/generated/prisma/client.ts';
import { PrismaBetterSqlite3 } from '@prisma/adapter-better-sqlite3';
const prisma = new PrismaClient({ adapter: new PrismaBetterSqlite3({ url: process.env.DATABASE_URL! }) });
await prisma.user.upsert({
  where: { id: 'anonymous-user' },
  update: {},
  create: {
    id: 'anonymous-user',
    email: 'anonymous@localhost',
    name: 'Anonymous User',
    role: 'ADMIN',
    emailVerified: new Date(),
  },
});
await prisma.$disconnect();
`
  );
  try {
    run('pnpm', ['exec', 'tsx', seedFileRel], {
      cwd: root,
      env: { ...process.env, DATABASE_URL: `file:${tmpDb}` },
    });
  } finally {
    rmSync(seedFile, { force: true });
  }

  // 4. Assemble the staging tree.
  step(`Assemble staging directory at ${stageDir}`);
  if (existsSync(stageDir)) rmSync(stageDir, { recursive: true, force: true });
  mkdirSync(stageDir, { recursive: true });
  mkdirSync(join(stageDir, 'solver'));
  mkdirSync(join(stageDir, 'server'));
  mkdirSync(join(stageDir, 'prisma'));

  cpSync(solverBin, join(stageDir, 'solver/minigrid-solver'));

  // pnpm's node_modules uses relative symlinks; preserve them verbatim so the
  // standalone resolves correctly at the install site. Don't dereference
  // (would flatten the .pnpm peer-dep layout and break Node's resolution).
  cpSync(resolve(root, '.next/standalone'), join(stageDir, 'server'), {
    recursive: true,
    verbatimSymlinks: true,
  });
  // Strip any .env files Next.js's standalone copied from the project root —
  // those would leak the dev's Postgres/OAuth/Maps credentials.
  for (const leaked of [
    '.env',
    '.env.local',
    '.env.production',
    '.env.development',
  ]) {
    const p = join(stageDir, 'server', leaked);
    if (existsSync(p)) {
      rmSync(p);
      console.log(`stripped ${leaked} from server/`);
    }
  }

  // Backstop styled-jsx — Next loads it via a require-hook the static tracer
  // misses under pnpm's hoisted layout.
  const TRACER_MISSED_DEPS = ['styled-jsx'];
  for (const dep of TRACER_MISSED_DEPS) {
    const src = resolve(root, 'node_modules', dep);
    const dst = join(stageDir, 'server/node_modules', dep);
    if (existsSync(src) && !existsSync(dst)) {
      cpSync(src, dst, { recursive: true, dereference: true });
      console.log(`backfilled missing dep: ${dep}`);
    }
  }
  cpSync(resolve(root, '.next/static'), join(stageDir, 'server/.next/static'), {
    recursive: true,
  });
  cpSync(resolve(root, 'public'), join(stageDir, 'server/public'), {
    recursive: true,
  });

  cpSync(
    resolve(root, 'prisma/schema-offline'),
    join(stageDir, 'prisma/schema-offline'),
    { recursive: true }
  );
  cpSync(tmpDb, join(stageDir, 'prisma/offline.db'));
  rmSync(tmpDb);

  console.log(`\nBundle assembled at ${stageDir}`);
}
