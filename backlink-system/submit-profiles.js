import 'dotenv/config';
import path from 'node:path';
import config from './config.json' with { type: 'json' };
import { parseDryRunArg, writeJson } from './lib/utils.js';
import { recordTrackerEvent } from './tracker.js';

const platforms = ['About.me', 'Disqus', 'ProductHunt', 'Crunchbase', 'AngelList'];

export async function runSubmitProfiles({ dryRun = false } = {}) {
  for (const site of config.sites) {
    const profiles = platforms.map((platform) => ({
      platform,
      displayName: site.domain,
      tagline: `${site.niche} insights and educational resources`,
      bio: `${site.description} Visit https://${site.domain}`,
      website: `https://${site.domain}`,
      dryRun
    }));

    const outputPath = path.resolve('output', site.domain, 'profile-packages.json');
    await writeJson(outputPath, { site: site.domain, profiles });
    await recordTrackerEvent({ module: 'submit-profiles', site: site.domain, target: outputPath, status: 'success', details: 'profile package generated' });
  }
}

if (import.meta.url === `file://${process.argv[1]}`) {
  runSubmitProfiles({ dryRun: parseDryRunArg() });
}
