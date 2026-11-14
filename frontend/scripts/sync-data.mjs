// Copy pipeline products into public/data so the static site can fetch them.
//   ../data/demo      -> public/data/demo   (synthetic, always present)
//   ../data/products  -> public/data/real   (real SPHEREx, when built)
import { cpSync, existsSync, mkdirSync, rmSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const repo = resolve(here, '..', '..');
const out = resolve(here, '..', 'public', 'data');

rmSync(out, { recursive: true, force: true });
mkdirSync(out, { recursive: true });

for (const [src, name] of [
  ['data/demo', 'demo'],
  ['data/products', 'real'],
]) {
  const from = resolve(repo, src);
  if (existsSync(resolve(from, 'manifest.json'))) {
    cpSync(from, resolve(out, name), { recursive: true });
    console.log(`sync-data: ${src} -> public/data/${name}`);
  }
}
