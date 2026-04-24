import path from 'node:path';
import config from './config.json' with { type: 'json' };
import { parseDryRunArg, writeJson } from './lib/utils.js';
import { recordTrackerEvent } from './tracker.js';

function buildMixSubmission(site, idx) {
  const keyword = site.keywords[idx % site.keywords.length];
  return {
    title: `${keyword} guide ${idx + 1}`,
    description: `Curated value-first resource on ${site.niche} with actionable steps and practical routines.`,
    tags: [keyword, site.niche, 'guide', 'wellness', 'tips'].map((v) => String(v).replace(/\s+/g, '-').toLowerCase()),
    url: `https://${site.domain}`
  };
}

export async function runSubmitMix({ dryRun = false } = {}) {
  for (const site of config.sites) {
    const submissions = Array.from({ length: 10 }, (_, idx) => buildMixSubmission(site, idx));
    const outputPath = path.resolve('output', site.domain, 'mix-packages.json');
    await writeJson(outputPath, { site: site.domain, submissions });
    await recordTrackerEvent({
      module: 'submit-mix',
      site: site.domain,
      target: outputPath,
      status: 'success',
      details: dryRun ? 'dry-run mix package generated' : 'mix package generated'
    });
  }
}

if (import.meta.url === `file://${process.argv[1]}`) {
  runSubmitMix({ dryRun: parseDryRunArg() });
}
