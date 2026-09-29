// Builds a ready-to-upload package for Hostido (cPanel "Setup Node.js App" / CloudLinux).
// CloudLinux keeps node_modules in its own virtual environment, so the package ships
// WITHOUT node_modules — the panel installs them ("Run NPM Install") from package.json.
import { cpSync, existsSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { execSync } from 'node:child_process';

const out = 'dist/q4-leaderboard';
if (!existsSync('.next/standalone/server.js')) {
  console.error('Run "npm run build" first.');
  process.exit(1);
}
rmSync('dist', { recursive: true, force: true });
cpSync('.next/standalone', out, { recursive: true });
cpSync('.next/static', `${out}/.next/static`, { recursive: true });
cpSync('public', `${out}/public`, { recursive: true });
for (const f of ['node_modules', '.env', '.env.local']) rmSync(`${out}/${f}`, { recursive: true, force: true });

// Pin the exact versions that were used for the build.
const pkg = JSON.parse(readFileSync('package.json', 'utf8'));
const dependencies = Object.fromEntries(
  Object.keys(pkg.dependencies).map((name) => [name, JSON.parse(readFileSync(`node_modules/${name}/package.json`, 'utf8')).version]),
);
writeFileSync(
  `${out}/package.json`,
  JSON.stringify({ name: pkg.name, version: pkg.version, private: true, scripts: { start: 'node server.js' }, engines: { node: '>=20' }, dependencies }, null, 2) + '\n',
);
cpSync('.env.example', `${out}/.env.example`);
writeFileSync(`${out}/WERSJA.txt`, `Zbudowano: ${new Date().toISOString()}\n`);
try {
  execSync('cd dist && zip -qr q4-leaderboard.zip q4-leaderboard');
  console.log('Gotowe: dist/q4-leaderboard.zip');
} catch {
  console.log(`Gotowe: ${out} (brak programu zip — spakuj folder ręcznie)`);
}
