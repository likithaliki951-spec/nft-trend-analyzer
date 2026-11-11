const fs = require('fs');
const path = require('path');

// Ensure parent directories in .next exist before webpack worker threads
// write to them simultaneously on Windows, preventing libuv EPERM mkdir race conditions.
const frontendDir = path.resolve(__dirname, '..');
const appDir = path.join(frontendDir, 'app');
const nextDir = path.join(frontendDir, '.next');

const baseDirs = [
  path.join(nextDir, 'static', 'chunks', 'app'),
  path.join(nextDir, 'static', 'chunks', 'pages'),
  path.join(nextDir, 'static', 'css'),
  path.join(nextDir, 'static', 'media'),
  path.join(nextDir, 'server', 'app'),
  path.join(nextDir, 'server', 'pages'),
  path.join(nextDir, 'server', 'chunks'),
  path.join(nextDir, 'cache', 'webpack'),
  path.join(nextDir, 'types', 'app'),
];

for (const dir of baseDirs) {
  try {
    fs.mkdirSync(dir, { recursive: true });
  } catch (e) {}
}

function getAllDirs(dir) {
  let results = [];
  try {
    const list = fs.readdirSync(dir, { withFileTypes: true });
    for (const item of list) {
      if (item.isDirectory()) {
        const fullPath = path.join(dir, item.name);
        results.push(fullPath);
        results = results.concat(getAllDirs(fullPath));
      }
    }
  } catch (err) {}
  return results;
}

try {
  const dirs = getAllDirs(appDir);
  const targets = [
    path.join(nextDir, 'server', 'app'),
    path.join(nextDir, 'types', 'app'),
    path.join(nextDir, 'static', 'chunks', 'app'),
  ];

  for (const baseTarget of targets) {
    for (const d of dirs) {
      const rel = path.relative(appDir, d);
      const target = path.join(baseTarget, rel);
      fs.mkdirSync(target, { recursive: true });
    }
  }
} catch (e) {}
