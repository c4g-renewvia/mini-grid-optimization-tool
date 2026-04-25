// electron-builder filters node_modules out of extraResources even with an
// explicit `filter: ["**/*"]`. Copy them in directly after pack so the
// platform installer picks up the patched layout.
const fs = require('fs');
const path = require('path');

function destServerDir({ appOutDir, productFilename, electronPlatformName }) {
  if (electronPlatformName === 'darwin' || electronPlatformName === 'mas') {
    return path.join(
      appOutDir,
      `${productFilename}.app`,
      'Contents/Resources/server'
    );
  }
  // linux (AppImage / deb / etc.) and win32 (nsis / portable) both put
  // extraResources at <appOutDir>/resources/.
  return path.join(appOutDir, 'resources/server');
}

exports.default = async function (context) {
  const { appOutDir, packager, electronPlatformName } = context;
  const stage = path.resolve(
    packager.projectDir,
    '..',
    'release',
    'electron-stage'
  );
  const src = path.join(stage, 'server/node_modules');
  const serverDir = destServerDir({
    appOutDir,
    productFilename: packager.appInfo.productFilename,
    electronPlatformName,
  });
  const dst = path.join(serverDir, 'node_modules');
  if (!fs.existsSync(src)) {
    throw new Error(`afterPack: missing source ${src}`);
  }
  if (!fs.existsSync(serverDir)) {
    throw new Error(
      `afterPack: expected server dir not found at ${serverDir} (platform=${electronPlatformName})`
    );
  }
  if (fs.existsSync(dst)) {
    console.log(`afterPack: ${dst} exists, skipping`);
    return;
  }
  console.log(`afterPack: copying node_modules → ${dst}`);
  fs.cpSync(src, dst, { recursive: true, verbatimSymlinks: true });
};
