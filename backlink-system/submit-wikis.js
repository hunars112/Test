import 'dotenv/config';
import path from 'node:path';
import pLimit from 'p-limit';
import config from './config.json' with { type: 'json' };
import { parseDryRunArg, writeJson } from './lib/utils.js';
import { recordTrackerEvent } from './tracker.js';

export async function runSubmitWikis({ dryRun = false } = {}) {
  const limit = pLimit(config.concurrency);
  await Promise.all(config.sites.map((site) => limit(async () => {
    const articles = Array.from({ length: 3 }, (_, i) => ({
      title: `${site.niche} fundamentals ${i + 1}`,
      format: i % 2 === 0 ? 'Wikipedia-style' : 'WikiHow/eHow-style',
      body: `== Overview ==\n${site.description}\n== Key Considerations ==\n- Evidence quality\n- User context\n- Practical constraints\n== References ==\n[https://${site.domain} ${site.domain}]`
    }));

    const outputPath = path.resolve('output', site.domain, 'wiki-packages.json');
    await writeJson(outputPath, { dryRun, site: site.domain, articles });
    await recordTrackerEvent({ module: 'submit-wikis', site: site.domain, target: outputPath, status: 'success', details: 'wiki templates generated' });
  })));
}

if (import.meta.url === `file://${process.argv[1]}`) {
  runSubmitWikis({ dryRun: parseDryRunArg() });
}
