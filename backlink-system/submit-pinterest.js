import path from 'node:path';
import config from './config.json' with { type: 'json' };
import { parseDryRunArg, writeJson } from './lib/utils.js';
import { recordTrackerEvent } from './tracker.js';

function buildPin(site, idx) {
  const keyword = site.keywords[idx % site.keywords.length];
  return {
    title: `${keyword} tips #${idx + 1}`,
    description: `Save this guide for ${site.niche}. Practical, keyword-focused insights with step-by-step actions and resources: https://${site.domain}`,
    altText: `Infographic about ${keyword} and ${site.niche}`,
    targetUrl: `https://${site.domain}`
  };
}

export async function runSubmitPinterest({ dryRun = false } = {}) {
  for (const site of config.sites) {
    const pins = Array.from({ length: 5 }, (_, idx) => buildPin(site, idx));
    const outputPath = path.resolve('output', site.domain, 'pinterest-packages.json');
    await writeJson(outputPath, { site: site.domain, pins });
    await recordTrackerEvent({
      module: 'submit-pinterest',
      site: site.domain,
      target: outputPath,
      status: 'success',
      details: dryRun ? 'dry-run pinterest package generated' : 'pinterest package generated'
    });
  }
}

if (import.meta.url === `file://${process.argv[1]}`) {
  runSubmitPinterest({ dryRun: parseDryRunArg() });
}
