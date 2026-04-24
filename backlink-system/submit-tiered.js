import 'dotenv/config';
import path from 'node:path';
import config from './config.json' with { type: 'json' };
import { parseDryRunArg, readJson, writeJson } from './lib/utils.js';
import { recordTrackerEvent } from './tracker.js';

function collectTier1Targets(events, site) {
  return events
    .filter((e) => e.module === 'submit-web2' && e.site === site.domain && e.status === 'success')
    .map((e, idx) => ({
      referenceId: idx + 1,
      platform: e.target,
      tier1UrlPlaceholder: `https://example.com/${site.domain}/${e.target}`
    }));
}

export async function runSubmitTiered({ dryRun = false } = {}) {
  const tracker = await readJson(path.resolve('tracker.json'), { events: [] });

  for (const site of config.sites) {
    const tier1 = collectTier1Targets(tracker.events ?? [], site);
    const amplification = tier1.map((item) => ({
      ...item,
      socialBookmarkTemplate: `Share this resource page with summary and source context: ${item.tier1UrlPlaceholder}`,
      pingTemplate: `Ping target URL for recrawl: ${item.tier1UrlPlaceholder}`
    }));

    const outputPath = path.resolve('output', site.domain, 'tier2-amplification.json');
    await writeJson(outputPath, { dryRun, site: site.domain, tier1Count: tier1.length, amplification });
    await recordTrackerEvent({ module: 'submit-tiered', site: site.domain, target: outputPath, status: 'success', details: 'tier2 amplification plan generated' });
  }
}

if (import.meta.url === `file://${process.argv[1]}`) {
  runSubmitTiered({ dryRun: parseDryRunArg() });
}
