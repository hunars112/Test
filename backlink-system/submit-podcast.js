import 'dotenv/config';
import path from 'node:path';
import pLimit from 'p-limit';
import config from './config.json' with { type: 'json' };
import { parseDryRunArg, writeJson } from './lib/utils.js';
import { recordTrackerEvent } from './tracker.js';

const platforms = ['Anchor/Spotify', 'Podbean', 'Buzzsprout', 'Spreaker'];

export async function runSubmitPodcast({ dryRun = false } = {}) {
  const limit = pLimit(config.concurrency);
  await Promise.all(config.sites.map((site) => limit(async () => {
    const profilePackages = platforms.map((platform) => ({
      platform,
      podcastName: `${site.domain} Insights`,
      bio: `Educational discussions around ${site.niche}. Learn more at https://${site.domain}`,
      website: `https://${site.domain}`
    }));

    const outputPath = path.resolve('output', site.domain, 'podcast-packages.json');
    await writeJson(outputPath, { dryRun, site: site.domain, profilePackages });
    await recordTrackerEvent({ module: 'submit-podcast', site: site.domain, target: outputPath, status: 'success', details: 'podcast packages generated' });
  })));
}

if (import.meta.url === `file://${process.argv[1]}`) {
  runSubmitPodcast({ dryRun: parseDryRunArg() });
}
