/**
 * Layer 3 build: assemble the offline bundle into release/electron-stage/,
 * then invoke electron-builder for the current platform.
 *
 * Output: release/electron/<artifact> (.dmg on macOS, .AppImage on Linux,
 * .exe installer on Windows).
 */

import { spawnSync } from 'child_process';
import { copyFileSync, mkdirSync, writeFileSync } from 'fs';
import { resolve, join } from 'path';
import { assembleOfflineBundle } from './build-offline-bundle';

const ROOT = resolve(import.meta.dirname, '..');
const STAGE = resolve(ROOT, 'release/electron-stage');

// Stamp the build with the current git commit hash so main.js can detect
// install-over-old-version on launch and trigger re-setup.
console.log('\n=== Stamp build-info.json ===');
const commitHash = (() => {
  const r = spawnSync('git', ['rev-parse', 'HEAD'], { cwd: ROOT, encoding: 'utf8' });
  if (r.status !== 0) {
    throw new Error(`git rev-parse HEAD failed: ${r.stderr}`);
  }
  return r.stdout.trim();
})();
writeFileSync(
  resolve(ROOT, 'electron/build-info.json'),
  JSON.stringify({ commitHash }, null, 2) + '\n'
);
console.log(`commitHash=${commitHash}`);

assembleOfflineBundle({ root: ROOT, stageDir: STAGE });

// Bundle the host Node binary so the packaged app runs without requiring
// Node on the user's machine. Uses the host's Node — the build platform's
// arch is what gets bundled in the artifact.
console.log('\n=== Bundle Node runtime ===');
const NODE_RUNTIME_DIR = join(STAGE, 'node-runtime');
mkdirSync(NODE_RUNTIME_DIR, { recursive: true });
const nodeBinName = process.platform === 'win32' ? 'node.exe' : 'node';
copyFileSync(process.execPath, join(NODE_RUNTIME_DIR, nodeBinName));
console.log(`Copied ${process.execPath} → ${join(NODE_RUNTIME_DIR, nodeBinName)}`);

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
