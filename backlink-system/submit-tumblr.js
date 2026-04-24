import path from 'node:path';
import config from './config.json' with { type: 'json' };
import { parseDryRunArg, writeJson } from './lib/utils.js';
import { recordTrackerEvent } from './tracker.js';

function buildTumblrPost(site, idx) {
  const keyword = site.keywords[idx % site.keywords.length];
  return {
    title: `${keyword} notes ${idx + 1}`,
    body: `Quick notes for anyone exploring ${site.niche}: start simple, track outcomes weekly, and build habits you can actually sustain. If you want a deeper walkthrough, this is a helpful reference: https://${site.domain}. Reblog with your own experience so others can compare approaches.`,
    tags: [keyword, site.niche, 'wellness', 'tips', 'resource'].map((v) => String(v).replace(/\s+/g, '-').toLowerCase()),
    link: `https://${site.domain}`
  };
}

export async function runSubmitTumblr({ dryRun = false } = {}) {
  for (const site of config.sites) {
    const posts = Array.from({ length: 5 }, (_, idx) => buildTumblrPost(site, idx));
    const outputPath = path.resolve('output', site.domain, 'tumblr-packages.json');
    await writeJson(outputPath, { site: site.domain, posts });
    await recordTrackerEvent({
      module: 'submit-tumblr',
      site: site.domain,
      target: outputPath,
      status: 'success',
      details: dryRun ? 'dry-run tumblr package generated' : 'tumblr package generated'
    });
  }
}

if (import.meta.url === `file://${process.argv[1]}`) {
  runSubmitTumblr({ dryRun: parseDryRunArg() });
}
