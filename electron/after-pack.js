// electron-builder filters node_modules out of extraResources even with an
// explicit `filter: ["**/*"]`. Copy them in directly after pack so the .dmg
// picks up the patched .app.
const fs = require('fs');
const path = require('path');

exports.default = async function (context) {
  const { appOutDir, packager } = context;
  const stage = path.resolve(
    packager.projectDir,
    '..',
    'release',
    'electron-stage'
  );
  const appName = `${packager.appInfo.productFilename}.app`;
  const serverDir = path.join(
    appOutDir,
    appName,
    'Contents/Resources/server'
  );
  const src = path.join(stage, 'server/node_modules');
  const dst = path.join(serverDir, 'node_modules');
  if (!fs.existsSync(src)) {
    throw new Error(`afterPack: missing source ${src}`);
  }
  if (fs.existsSync(dst)) {
    console.log(`afterPack: ${dst} exists, skipping`);
    return;
  }
  console.log(`afterPack: copying node_modules → ${dst}`);
  fs.cpSync(src, dst, { recursive: true, verbatimSymlinks: true });
};
