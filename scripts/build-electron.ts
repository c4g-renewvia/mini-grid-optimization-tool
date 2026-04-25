/**
 * Layer 3 build: assemble the offline bundle into release/electron-stage/,
 * then invoke electron-builder for the current platform.
 *
 * Output: release/electron/<artifact> (.dmg on macOS, .AppImage on Linux,
 * .exe installer on Windows).
 */

import { spawnSync } from 'child_process';
import { resolve } from 'path';
import { assembleOfflineBundle } from './build-offline-bundle';

const ROOT = resolve(import.meta.dirname, '..');
const STAGE = resolve(ROOT, 'release/electron-stage');

assembleOfflineBundle({ root: ROOT, stageDir: STAGE });

console.log('\n=== electron-builder ===');
const r = spawnSync('pnpm', ['exec', 'electron-builder'], {
  stdio: 'inherit',
  cwd: resolve(ROOT, 'electron'),
  shell: process.platform === 'win32',
});
if (r.status !== 0) {
  throw new Error(`electron-builder exited with ${r.status}`);
}

console.log('\nDone. Artifacts in release/electron/');
