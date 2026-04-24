import fs from 'node:fs/promises';
import path from 'node:path';

export async function ensureDir(dirPath) {
  await fs.mkdir(dirPath, { recursive: true });
}

export async function readJson(filePath, fallback = null) {
  try {
    const raw = await fs.readFile(filePath, 'utf-8');
    return JSON.parse(raw);
  } catch {
    return fallback;
  }
}

export async function writeJson(filePath, value) {
  await ensureDir(path.dirname(filePath));
  await fs.writeFile(filePath, JSON.stringify(value, null, 2));
}

export async function writeText(filePath, text) {
  await ensureDir(path.dirname(filePath));
  await fs.writeFile(filePath, text, 'utf-8');
}

export async function writeBinary(filePath, bytes) {
  await ensureDir(path.dirname(filePath));
  await fs.writeFile(filePath, bytes);
}

function csvEscape(value) {
  const s = String(value ?? '');
  return /[",\n]/.test(s) ? `"${s.replaceAll('"', '""')}"` : s;
}

export async function writeCsv(filePath, rows) {
  const headers = Object.keys(rows[0] ?? {});
  const lines = [headers.join(',')];
  for (const row of rows) {
    lines.push(headers.map((h) => csvEscape(row[h])).join(','));
  }
  await writeText(filePath, `${lines.join('\n')}\n`);
}

export function parseDryRunArg(argv = process.argv) {
  return argv.includes('--dry-run');
}

export function contextualBacklink(site, idx = 0) {
  const anchor = site.anchors[idx % site.anchors.length] ?? site.domain;
  return { anchor, url: `https://${site.domain}` };
}

export function words(n, sentence = 'This educational paragraph explains practical considerations and links to further resources.') {
  return Array.from({ length: n }, () => sentence).join(' ');
}
