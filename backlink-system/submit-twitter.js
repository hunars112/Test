import path from 'node:path';
import config from './config.json' with { type: 'json' };
import { parseDryRunArg, writeJson } from './lib/utils.js';
import { recordTrackerEvent } from './tracker.js';

function hashtags(site) {
  return site.keywords
    .map((k) => `#${k.replace(/[^a-z0-9]/gi, '')}`)
    .concat(['#wellness', '#resources'])
    .slice(0, 5);
}

function buildTweet(site, idx) {
  const tags = hashtags(site).join(' ');
  return {
    text: `${site.keywords[idx % site.keywords.length]} tip ${idx + 1}: practical, value-first guidance for ${site.niche}. Learn more at https://${site.domain} ${tags}`,
    url: `https://${site.domain}`
  };
}

function buildThread(site, idx) {
  const tags = hashtags(site).join(' ');
  const tweets = Array.from({ length: 5 }, (_, i) => {
    if (i === 4) {
      return `Tweet ${i + 1}: Recap + resource link for deeper reading: https://${site.domain} ${tags}`;
    }
    return `Tweet ${i + 1}: ${site.keywords[(idx + i) % site.keywords.length]} insight with a concise action step for better ${site.niche}.`;
  });

  return { title: `${site.niche} thread ${idx + 1}`, tweets };
}

export async function runSubmitTwitter({ dryRun = false } = {}) {
  for (const site of config.sites) {
    const tweetTemplates = Array.from({ length: 10 }, (_, idx) => buildTweet(site, idx));
    const threadOutlines = Array.from({ length: 3 }, (_, idx) => buildThread(site, idx));
    const outputPath = path.resolve('output', site.domain, 'twitter-packages.json');

    await writeJson(outputPath, { site: site.domain, tweetTemplates, threadOutlines });
    await recordTrackerEvent({
      module: 'submit-twitter',
      site: site.domain,
      target: outputPath,
      status: 'success',
      details: dryRun ? 'dry-run twitter templates generated' : 'twitter templates generated'
    });
  }
}

if (import.meta.url === `file://${process.argv[1]}`) {
  runSubmitTwitter({ dryRun: parseDryRunArg() });
}
