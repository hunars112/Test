import 'dotenv/config';
import path from 'node:path';
import pLimit from 'p-limit';
import config from './config.json' with { type: 'json' };
import { parseDryRunArg, writeJson } from './lib/utils.js';
import { recordTrackerEvent } from './tracker.js';

export async function runSubmitVideo({ dryRun = false } = {}) {
  const limit = pLimit(config.concurrency);
  await Promise.all(config.sites.map((site) => limit(async () => {
    const packages = {
      youtube: {
        titleTemplates: site.keywords.map((k, idx) => `${site.niche}: ${k} explained (${idx + 1})`),
        descriptionTemplate: `${site.description} Explore additional resources at https://${site.domain}`
      },
      dailymotion: {
        channelBio: `Educational channel focused on ${site.niche}. Website: https://${site.domain}`,
        descriptionTemplate: `This episode covers ${site.niche}. Resource link: https://${site.domain}`
      },
      vimeo: {
        profileBio: `Publishing educational video explainers for ${site.niche}.`,
        website: `https://${site.domain}`
      }
    };

    const outputPath = path.resolve('output', site.domain, 'video-packages.json');
    await writeJson(outputPath, { dryRun, site: site.domain, packages });
    await recordTrackerEvent({ module: 'submit-video', site: site.domain, target: outputPath, status: 'success', details: 'video packages generated' });
  })));
}

if (import.meta.url === `file://${process.argv[1]}`) {
  runSubmitVideo({ dryRun: parseDryRunArg() });
}
