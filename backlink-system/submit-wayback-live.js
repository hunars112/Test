import { mkdir, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { recordTrackerEvent } from './tracker.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

async function getFetch() {
  if (typeof globalThis.fetch === 'function') return globalThis.fetch.bind(globalThis);
  const mod = await import('node-fetch');
  return mod.default;
}

async function extractLiveUrls() {
  const reportPath = path.join(__dirname, 'LIVE-LINKS-REPORT.md');
  const content = await readFile(reportPath, 'utf8');
  const matches = [...content.matchAll(/\((https:\/\/[^)\s]+)\)/g)].map((m) => m[1]);
  return [...new Set(matches)];
}

function wait(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export async function runSubmitWayback({ dryRun = false } = {}) {
  const urls = await extractLiveUrls();
  const fetchFn = dryRun ? null : await getFetch();
  const results = [];

  for (const url of urls) {
    try {
      let archivedUrl = `https://web.archive.org/web/*/${url}`;
      if (!dryRun) {
        // eslint-disable-next-line no-await-in-loop
        const response = await fetchFn(`https://web.archive.org/save/${encodeURIComponent(url)}`, {
          method: 'POST',
          headers: {
            'User-Agent':
              'Mozilla/5.0 (compatible; BacklinkLiveBot/1.0; +https://example.com/bot-info)',
          },
        });

        const location = response.headers.get('content-location') || response.headers.get('location');
        if (location) {
          archivedUrl = location.startsWith('http') ? location : `https://web.archive.org${location}`;
        }
      }

      const result = {
        url,
        archived_url: archivedUrl,
        timestamp: new Date().toISOString(),
        dryRun,
      };
      results.push(result);
      // eslint-disable-next-line no-await-in-loop
      await recordTrackerEvent({ module: 'submit-wayback-live', ...result });
    } catch (error) {
      const result = {
        url,
        archived_url: null,
        error: error.message,
        timestamp: new Date().toISOString(),
        dryRun,
      };
      results.push(result);
      // eslint-disable-next-line no-await-in-loop
      await recordTrackerEvent({ module: 'submit-wayback-live', ...result });
    }

    if (!dryRun) {
      // eslint-disable-next-line no-await-in-loop
      await wait(2000);
    }
  }

  const outDir = path.join(__dirname, 'output');
  await mkdir(outDir, { recursive: true });
  await writeFile(path.join(outDir, 'wayback-submissions.json'), JSON.stringify(results, null, 2));
  return results;
}
