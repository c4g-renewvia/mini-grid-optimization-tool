/**
 * Layer 2 distribution: assemble the offline bundle, drop in the POSIX
 * setup/start scripts and a README, then zip.
 *
 *   release/minigrid-tool-<platform>.zip
 *     solver/minigrid-solver
 *     server/                       (Next.js standalone)
 *     prisma/schema-offline/
 *     prisma/offline.db             (migrated, seeded with offline-user)
 *     setup.sh                      (first-run prompt for Maps API key)
 *     start.sh                      (launcher: solver + node server.js)
 *     README.txt
 */

import { spawnSync } from 'child_process';
import {
  cpSync,
  existsSync,
  rmSync,
  writeFileSync,
} from 'fs';
import { platform } from 'os';
import { resolve, join } from 'path';
import { assembleOfflineBundle } from './build-offline-bundle';

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

assembleOfflineBundle({ root: ROOT, stageDir: STAGE });

cpSync(resolve(ROOT, 'scripts/offline-setup.sh'), join(STAGE, 'setup.sh'));
cpSync(resolve(ROOT, 'scripts/offline-start.sh'), join(STAGE, 'start.sh'));
spawnSync('chmod', ['+x', join(STAGE, 'setup.sh'), join(STAGE, 'start.sh')], {
  stdio: 'inherit',
});

writeFileSync(
  join(STAGE, 'README.txt'),
  [
    'Mini-Grid Optimizer',
    'Offline distribution',
    '',
    'Requirements',
    '  Node.js 24 or later. No Python, PostgreSQL, or Docker required.',
    '',
    'First-time setup',
    '  ./setup.sh        Two prompts:',
    '                      1. Google Maps API key (required).',
    '                      2. Google OAuth credentials (optional). Leave',
    '                         blank to use a single local anonymous',
    '                         account; provide both to enable Google',
    '                         sign-in.',
    '                    Writes a local .env file.',
    '',
    'Run',
    '  ./start.sh        Starts the solver and application server. Opens',
    '                    the application in your default browser.',
    '',
    'Data locations',
    '  Database  ~/Library/Application Support/minigrid-solver/   (macOS)',
    '            ~/.local/share/minigrid-solver/                  (Linux)',
    '  Cache     ~/Library/Caches/minigrid-solver/                (macOS)',
    '            ~/.cache/minigrid-solver/                        (Linux)',
    '  Logs      ~/Library/Logs/minigrid-solver/                  (macOS)',
    '            ~/.local/state/minigrid-solver/logs/             (Linux)',
    '',
    'Notes',
    '  Updates: Replace this folder with a newer release. Saved data is',
    '  preserved in the user data directory above.',
    '',
    '  Code signing: This distribution is unsigned. On macOS, the system',
    '  may block first launch; right-click the application and select',
    '  Open. On Windows, SmartScreen may show a warning; select More',
    '  info, then Run anyway. Production signing requires an Apple',
    '  Developer ID or Authenticode certificate.',
    '',
  ].join('\n')
);

console.log(`\n=== Create ${ZIP_PATH} ===`);
if (existsSync(ZIP_PATH)) rmSync(ZIP_PATH);
const zipResult = spawnSync('zip', ['-ry', ZIP_PATH, 'minigrid-tool'], {
  stdio: 'inherit',
  cwd: RELEASE,
});
if (zipResult.status !== 0) {
  throw new Error(`zip exited with ${zipResult.status}`);
}

console.log(`\nDone: ${ZIP_PATH}`);
