import path from 'node:path';
import config from './config.json' with { type: 'json' };
import { parseDryRunArg, readJson, writeText } from './lib/utils.js';
import { recordTrackerEvent } from './tracker.js';
import { runGenerateContent } from './generate-content.js';

async function ensureArticles(site) {
  const contentPath = path.resolve('output', site.domain, 'content.json');
  let content = await readJson(contentPath, null);
  if (!content) {
    await runGenerateContent({ offline: true });
    content = await readJson(contentPath, null);
  }
  return (content?.blogArticles ?? []).slice(0, 3);
}

function toMediumMarkdown(site, article) {
  return `# ${article.title}\n\n${article.content}\n\n---\n\nIf you want more practical resources on ${site.niche}, visit [${site.domain}](https://${site.domain}).`;
}

export async function runSubmitMedium({ dryRun = false } = {}) {
  for (const site of config.sites) {
    const articles = await ensureArticles(site);
    for (let i = 0; i < 3; i += 1) {
      const article = articles[i] ?? {
        title: `${site.niche} Medium article ${i + 1}`,
        content: `This article provides practical guidance for ${site.niche}. Learn more at https://${site.domain}.`
      };

      const outputPath = path.resolve('output', site.domain, 'medium-articles', `medium-article-${i + 1}.md`);
      await writeText(outputPath, toMediumMarkdown(site, article));
      await recordTrackerEvent({ module: 'submit-medium', site: site.domain, target: outputPath, status: 'success', details: dryRun ? 'dry-run medium article package generated' : 'medium article package generated' });
    }
  }
}

if (import.meta.url === `file://${process.argv[1]}`) {
  runSubmitMedium({ dryRun: parseDryRunArg() });
}
