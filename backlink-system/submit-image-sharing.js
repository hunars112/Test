import 'dotenv/config';
import path from 'node:path';
import pLimit from 'p-limit';
import config from './config.json' with { type: 'json' };
import { parseDryRunArg, writeJson } from './lib/utils.js';
import { recordTrackerEvent } from './tracker.js';

const platforms = ['Flickr', 'Imgur', 'Pinterest', '500px', 'Unsplash'];

export async function runSubmitImageSharing({ dryRun = false } = {}) {
  const limit = pLimit(config.concurrency);
  await Promise.all(config.sites.map((site) => limit(async () => {
    const packages = Array.from({ length: 3 }, (_, idx) => ({
      imageIndex: idx + 1,
      title: `${site.niche} visual guide ${idx + 1}`,
      tags: [...site.keywords, ...site.anchors].slice(0, 8),
      altText: `Educational visual about ${site.niche}`,
      description: `Practical ${site.niche} insights and checklist. Learn more at https://${site.domain}`,
      targetUrl: `https://${site.domain}`,
      platforms
    }));

    const outputPath = path.resolve('output', site.domain, 'image-sharing-packages.json');
    await writeJson(outputPath, { dryRun, site: site.domain, packages });
    await recordTrackerEvent({ module: 'submit-image-sharing', site: site.domain, target: outputPath, status: 'success', details: 'image metadata packages generated' });
  })));
}

if (import.meta.url === `file://${process.argv[1]}`) {
  runSubmitImageSharing({ dryRun: parseDryRunArg() });
}
