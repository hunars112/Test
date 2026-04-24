import 'dotenv/config';
import path from 'node:path';
import pLimit from 'p-limit';
import config from './config.json' with { type: 'json' };
import { ApiClient } from './lib/clients.js';
import { parseDryRunArg, writeText, writeJson } from './lib/utils.js';
import { recordTrackerEvent } from './tracker.js';

const rssDirectories = ['FeedBurner', 'RSS.com', 'Feedspot', 'BlogLovin', 'Alltop', 'RSSMicro', 'Bloglines'];
const pingServices = Array.from({ length: 44 }, (_, i) => `https://ping-service-${i + 1}.example.com/ping`);

function buildRssXml(site) {
  const items = Array.from({ length: 5 }, (_, i) => `
    <item>
      <title>${site.niche} article ${i + 1}</title>
      <link>https://${site.domain}/articles/${i + 1}</link>
      <description>${site.description}</description>
      <guid>https://${site.domain}/articles/${i + 1}</guid>
    </item>`).join('\n');

  return `<?xml version="1.0" encoding="UTF-8" ?>
<rss version="2.0">
  <channel>
    <title>${site.domain} Feed</title>
    <link>https://${site.domain}</link>
    <description>${site.description}</description>${items}
  </channel>
</rss>`;
}

export async function runSubmitRss({ dryRun = false } = {}) {
  const limit = pLimit(config.concurrency);
  const client = new ApiClient({ concurrency: config.concurrency, delayMs: config.delayMs, dryRun });

  await Promise.all(config.sites.map((site) => limit(async () => {
    const rssPath = path.resolve('output', site.domain, 'feed.xml');
    await writeText(rssPath, buildRssXml(site));

    const directoryPath = path.resolve('output', site.domain, 'rss-directory-packages.json');
    await writeJson(directoryPath, {
      site: site.domain,
      feedUrl: `https://${site.domain}/feed.xml`,
      platforms: rssDirectories
    });

    await recordTrackerEvent({ module: 'submit-rss', site: site.domain, target: rssPath, status: 'success', details: 'rss feed generated' });

    for (const pingService of pingServices) {
      try {
        await client.request({ url: `${pingService}?feed=${encodeURIComponent(`https://${site.domain}/feed.xml`)}`, method: 'GET' });
      } catch {
        // continue intentionally, this is best-effort pinging
      }
    }

    await recordTrackerEvent({ module: 'submit-rss', site: site.domain, target: '44-ping-services', status: 'success', details: dryRun ? 'dry-run ping simulation' : 'ping attempts completed' });
  })));
}

if (import.meta.url === `file://${process.argv[1]}`) {
  runSubmitRss({ dryRun: parseDryRunArg() });
}
