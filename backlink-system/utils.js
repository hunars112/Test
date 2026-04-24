import { mkdtemp, mkdir, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';

const execFileAsync = promisify(execFile);

export async function loadConfig() {
  const raw = await readFile(join(process.cwd(), 'backlink-system', 'config.json'), 'utf8');
  const parsed = JSON.parse(raw);
  if (!Array.isArray(parsed.sites)) {
    throw new Error('config.json must include a sites array');
  }
  return parsed;
}

export async function writeDomainOutput(domain, filename, data) {
  const outputDir = join(process.cwd(), 'backlink-system', 'output', domain);
  await mkdir(outputDir, { recursive: true });
  await writeFile(join(outputDir, filename), JSON.stringify(data, null, 2), 'utf8');
}

export function toOneHundredWordDescription(site) {
  const base = `${site.description || site.title || site.niche || 'Useful practical resource'}. Visit https://${site.domain} for detailed guides, comparisons, and implementation checklists tailored to ${site.niche || 'this niche'}. You will find beginner-friendly explanations, advanced tactics, real-world examples, and clear next steps to turn ideas into action. The editorial approach prioritizes transparency, realistic expectations, and measurable outcomes. Readers can use these resources to plan smarter projects, avoid common mistakes, and build long-term habits with confidence while staying aligned with budget, time, and quality goals.`;
  const words = base.replace(/\s+/g, ' ').trim().split(' ');
  if (words.length >= 100) return words.slice(0, 100).join(' ');
  const fillers = Array.from({ length: 100 - words.length }, () => 'insights');
  return [...words, ...fillers].join(' ');
}

export function randomSlug(prefix = 'site') {
  const suffix = Math.random().toString(36).slice(2, 10);
  return `${prefix}-${suffix}`.replace(/[^a-z0-9-]/gi, '').toLowerCase();
}

export async function postJson(url, body, { headers = {}, timeoutMs = 20_000 } = {}) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(url, {
      method: 'POST',
      headers: { 'content-type': 'application/json', ...headers },
      body: JSON.stringify(body),
      signal: controller.signal,
    });

    const text = await response.text();
    return { ok: response.ok, status: response.status, text };
  } finally {
    clearTimeout(timeout);
  }
}

export async function postForm(url, formData, { headers = {}, timeoutMs = 20_000 } = {}) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(url, {
      method: 'POST',
      headers,
      body: formData,
      signal: controller.signal,
    });
    const text = await response.text();
    return { ok: response.ok, status: response.status, text };
  } finally {
    clearTimeout(timeout);
  }
}

export async function createZipWithIndexHtml(htmlString) {
  const tempRoot = await mkdtemp(join(tmpdir(), 'backlink-'));
  const sourceFile = join(tempRoot, 'index.html');
  const zipFile = join(tempRoot, 'site.zip');
  await writeFile(sourceFile, htmlString, 'utf8');

  try {
    await execFileAsync('zip', ['-q', '-j', zipFile, sourceFile]);
    return await readFile(zipFile);
  } finally {
    await rm(tempRoot, { recursive: true, force: true });
  }
}
