import { mkdir, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { recordTrackerEvent } from './tracker.js';
import * as contentGenerator from './generate-content.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

async function getFetch() {
  if (typeof globalThis.fetch === 'function') {
    return globalThis.fetch.bind(globalThis);
  }
  const mod = await import('node-fetch');
  return mod.default;
}

async function readConfig() {
  const configPath = path.join(__dirname, 'config.json');
  const raw = await readFile(configPath, 'utf8');
  return JSON.parse(raw);
}

function normalizeSites(config) {
  const raw = config?.sites ?? config?.domains ?? config?.projects ?? [];
  if (Array.isArray(raw)) {
    return raw
      .map((entry) => {
        if (typeof entry === 'string') return { domain: entry };
        if (entry && typeof entry === 'object') return entry;
        return null;
      })
      .filter(Boolean)
      .map((site) => ({ ...site, domain: site.domain ?? site.site ?? site.name }))
      .filter((site) => Boolean(site.domain));
  }
  return [];
}

function sanitizeDomain(domain) {
  return String(domain).replace(/^https?:\/\//, '').replace(/[^a-zA-Z0-9.-]/g, '_');
}

async function generateArticles(site, count = 2) {
  if (typeof contentGenerator.generateArticlesForSite === 'function') {
    return contentGenerator.generateArticlesForSite(site, { count });
  }
  if (typeof contentGenerator.generateContentForSite === 'function') {
    return contentGenerator.generateContentForSite(site, { count });
  }
  if (typeof contentGenerator.generateContent === 'function') {
    const generated = [];
    for (let i = 0; i < count; i += 1) {
      // eslint-disable-next-line no-await-in-loop
      const result = await contentGenerator.generateContent(site, { index: i + 1 });
      generated.push(result);
    }
    return generated;
  }

  return Array.from({ length: count }, (_, idx) =>
    `Article ${idx + 1} for ${site.domain}\n\nInsights and practical tips relevant to ${site.domain}.`,
  );
}

function articleToText(article) {
  if (typeof article === 'string') return article;
  if (article && typeof article === 'object') {
    return article.content ?? article.markdown ?? JSON.stringify(article, null, 2);
  }
  return String(article ?? '');
}

async function submitToPasteRs(fetchFn, content) {
  const response = await fetchFn('https://paste.rs/', {
    method: 'POST',
    headers: { 'Content-Type': 'text/plain' },
    body: content,
  });
  const text = (await response.text()).trim();
  if (!response.ok) throw new Error(`paste.rs failed: ${response.status} ${text}`);
  return { platform: 'paste.rs', url: text };
}

async function submitToBpaSt(fetchFn, content) {
  const response = await fetchFn('https://bpa.st/documents', {
    method: 'POST',
    headers: { 'Content-Type': 'text/plain' },
    body: content,
  });
  const json = await response.json().catch(() => ({}));
  if (!response.ok || !json?.key) {
    throw new Error(`bpa.st failed: ${response.status} ${JSON.stringify(json)}`);
  }
  return { platform: 'bpa.st', url: `https://bpa.st/${json.key}` };
}

async function submitToIxIo(fetchFn, content) {
  const form = new URLSearchParams({ 'f:1': content });
  const response = await fetchFn('http://ix.io/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: form,
  });
  const text = (await response.text()).trim();
  if (!response.ok) throw new Error(`ix.io failed: ${response.status} ${text}`);
  return { platform: 'ix.io', url: text };
}

async function submitToPasteMozilla(fetchFn, content) {
  const response = await fetchFn('https://paste.mozilla.org/api/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      content,
      filename: 'article.md',
      syntax: 'text',
      expires: 'never',
    }),
  });
  const json = await response.json().catch(() => ({}));
  if (!response.ok || !json?.url) {
    throw new Error(`paste.mozilla.org failed: ${response.status} ${JSON.stringify(json)}`);
  }
  return { platform: 'paste.mozilla.org', url: json.url };
}

export async function runSubmitPasteExtraLive({ dryRun = false } = {}) {
  const config = await readConfig();
  const sites = normalizeSites(config);
  const fetchFn = dryRun ? null : await getFetch();
  const results = [];

  for (const site of sites) {
    const domain = sanitizeDomain(site.domain);
    const siteArticles = await generateArticles(site, 2);
    const siteResults = [];

    for (let i = 0; i < siteArticles.length; i += 1) {
      const content = articleToText(siteArticles[i]);
      const articleIndex = i + 1;
      const platforms = [
        { name: 'paste.rs', submit: submitToPasteRs },
        { name: 'bpa.st', submit: submitToBpaSt },
        { name: 'ix.io', submit: submitToIxIo },
        { name: 'paste.mozilla.org', submit: submitToPasteMozilla },
      ];

      for (const platform of platforms) {
        try {
          let submission;
          if (dryRun) {
            submission = {
              platform: platform.name,
              url: `https://${platform.name}/mock-${domain}-${articleIndex}`,
              dryRun: true,
            };
          } else {
            // eslint-disable-next-line no-await-in-loop
            submission = await platform.submit(fetchFn, content);
          }

          const event = {
            module: 'submit-paste-extra-live',
            domain,
            articleIndex,
            ...submission,
            timestamp: new Date().toISOString(),
          };
          siteResults.push(event);
          results.push(event);
          // eslint-disable-next-line no-await-in-loop
          await recordTrackerEvent(event);
        } catch (error) {
          const failure = {
            module: 'submit-paste-extra-live',
            domain,
            articleIndex,
            platform: platform.name,
            error: error.message,
            timestamp: new Date().toISOString(),
          };
          siteResults.push(failure);
          results.push(failure);
          // eslint-disable-next-line no-await-in-loop
          await recordTrackerEvent(failure);
        }
      }
    }

    const outDir = path.join(__dirname, 'output', domain);
    await mkdir(outDir, { recursive: true });
    await writeFile(path.join(outDir, 'paste-extra-live.json'), JSON.stringify(siteResults, null, 2));
  }

  return results;
}
