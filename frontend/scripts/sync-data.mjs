// Copy pipeline products into public/data so the static site can fetch them.
//   ../data/demo      -> public/data/demo   (synthetic, always present)
//   ../data/products  -> public/data/real   (real SPHEREx, when built)
import { cpSync, existsSync, mkdirSync, readFileSync, rmSync } from 'node:fs';
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
  const manifestPath = resolve(from, 'manifest.json');
  if (!existsSync(manifestPath)) continue;
  // Real products only count once they have fields (`errante systems` alone writes a fields-less manifest).
  let fields = [];
  try {
    fields = JSON.parse(readFileSync(manifestPath, 'utf8')).fields ?? [];
  } catch {
    console.warn(`sync-data: could not parse ${src}/manifest.json, skipping`);
    continue;
  }
  if (name === 'real' && fields.length === 0) {
    console.log(`sync-data: ${src} has no fields yet, skipping`);
    continue;
  }
  cpSync(from, resolve(out, name), { recursive: true });
  console.log(`sync-data: ${src} -> public/data/${name}`);
}
