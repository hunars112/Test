import 'dotenv/config';
import path from 'node:path';
import pLimit from 'p-limit';
import config from './config.json' with { type: 'json' };
import { parseDryRunArg, writeCsv, writeJson } from './lib/utils.js';
import { recordTrackerEvent } from './tracker.js';

const sampleBlogs = Array.from({ length: 20 }, (_, i) => ({
  blogName: `Niche Blog ${i + 1}`,
  blogUrl: `https://niche-blog-${i + 1}.example.com`,
  notes: 'Verify moderation policy and link attributes manually before posting.'
}));

export async function runSubmitComments({ dryRun = false } = {}) {
  const limit = pLimit(config.concurrency);
  await Promise.all(config.sites.map((site) => limit(async () => {
    const comments = Array.from({ length: 10 }, (_, i) => ({
      templateId: i + 1,
      text: `Thanks for sharing this perspective on ${site.niche}. One additional practical angle is to compare options based on evidence and user context.`,
      websiteField: `https://${site.domain}`
    }));

    const outputPath = path.resolve('output', site.domain, 'comment-templates.json');
    await writeJson(outputPath, { dryRun, site: site.domain, comments });

    const csvPath = path.resolve('output', site.domain, 'blog-comment-opportunities.csv');
    await writeCsv(csvPath, sampleBlogs.map((b) => ({ ...b, category: site.niche })));

    await recordTrackerEvent({ module: 'submit-comments', site: site.domain, target: outputPath, status: 'success', details: 'comment templates and blog list generated' });
  })));
}

if (import.meta.url === `file://${process.argv[1]}`) {
  runSubmitComments({ dryRun: parseDryRunArg() });
}
