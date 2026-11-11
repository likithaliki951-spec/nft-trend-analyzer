import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

function ensureAllDirs() {
  const appDir = path.join(__dirname, 'app');
  const nextDir = path.join(__dirname, '.next');

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
      try {
        fs.mkdirSync(target, { recursive: true });
      } catch (e) {}
    }
  }
}

/** @type {import('next').NextConfig} */
const nextConfig = {
  eslint: {
    ignoreDuringBuilds: true,
  },
  typescript: {
    ignoreBuildErrors: false,
  },
  webpack: (config) => {
    ensureAllDirs();
    return config;
  },
};

export default nextConfig;
