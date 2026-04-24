import 'dotenv/config';
import path from 'node:path';
import config from './config.json' with { type: 'json' };
import { ApiClient } from './lib/clients.js';
import { parseDryRunArg, readJson, writeJson } from './lib/utils.js';
import { recordTrackerEvent } from './tracker.js';
import { runGenerateContent } from './generate-content.js';

async function ensureContent(site) {
  const contentPath = path.resolve('output', site.domain, 'content.json');
  let content = await readJson(contentPath, null);
  if (!content) {
    await runGenerateContent({ offline: true });
    content = await readJson(contentPath, null);
  }
  return content;
}

function gistBody(site, article) {
  return `# ${article.title}\n\n${article.content}\n\nReference: [${site.domain}](https://${site.domain})`;
}

export async function runSubmitGithubGist({ dryRun = false } = {}) {
  const client = new ApiClient({ concurrency: config.concurrency, delayMs: config.delayMs, dryRun });

  for (const site of config.sites) {
    const content = await ensureContent(site);
    const articles = (content?.blogArticles ?? []).slice(0, 2);
    const links = [];

    for (let i = 0; i < 2; i += 1) {
      const article = articles[i] ?? { title: `${site.niche} article ${i + 1}`, content: `Learn more at https://${site.domain}` };

      if (dryRun) {
        const fakeUrl = `https://gist.github.com/anonymous/${site.domain.replace(/\./g, '')}-${i + 1}`;
        links.push({ title: article.title, gistUrl: fakeUrl });
        await recordTrackerEvent({ module: 'submit-github-gist', site: site.domain, target: fakeUrl, status: 'success', details: 'dry-run gist prepared' });
        continue;
      }

      try {
        const response = await client.request({
          url: 'https://api.github.com/gists',
          method: 'POST',
          headers: { Accept: 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28' },
          body: {
            description: `${site.niche} resource for ${site.domain}`,
            public: true,
            files: {
              [`${site.domain}-article-${i + 1}.md`]: {
                content: gistBody(site, article)
              }
            }
          }
        });

        const gistUrl = response?.data?.html_url;
        if (!gistUrl) throw new Error('GitHub Gist API returned no html_url');
        links.push({ title: article.title, gistUrl });
        await recordTrackerEvent({ module: 'submit-github-gist', site: site.domain, target: gistUrl, status: 'success', details: 'anonymous public gist created' });
      } catch (error) {
        await recordTrackerEvent({ module: 'submit-github-gist', site: site.domain, target: 'api.github.com/gists', status: 'failed', details: error.message });
      }
    }

    const outputPath = path.resolve('output', site.domain, 'gist-links.json');
    await writeJson(outputPath, { site: site.domain, links });
  }
}

if (import.meta.url === `file://${process.argv[1]}`) {
  runSubmitGithubGist({ dryRun: parseDryRunArg() });
}
