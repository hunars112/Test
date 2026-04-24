import 'dotenv/config';
import path from 'node:path';
import config from './config.json' with { type: 'json' };
import { ApiClient } from './lib/clients.js';
import { parseDryRunArg, readJson, writeJson } from './lib/utils.js';
import { recordTrackerEvent } from './tracker.js';
import { runGenerateContent } from './generate-content.js';

const PASTEBIN_DEV_KEY = process.env.PASTEBIN_DEV_KEY ?? 'guest';

async function ensureContent(site) {
  const contentPath = path.resolve('output', site.domain, 'content.json');
  let content = await readJson(contentPath, null);
  if (!content) {
    await runGenerateContent({ offline: true });
    content = await readJson(contentPath, null);
  }
  return content;
}

function pasteBody(site, article) {
  return `# ${article.title}\n\n${article.content}\n\nSource link: [https://${site.domain}](https://${site.domain})`;
}

export async function runSubmitPastebin({ dryRun = false } = {}) {
  const client = new ApiClient({ concurrency: config.concurrency, delayMs: config.delayMs, dryRun });

  for (const site of config.sites) {
    const content = await ensureContent(site);
    const articles = (content?.blogArticles ?? []).slice(0, 2);
    const links = [];

    for (let i = 0; i < 2; i += 1) {
      const article = articles[i] ?? { title: `${site.niche} paste ${i + 1}`, content: `Learn more at https://${site.domain}` };

      if (dryRun) {
        const fakeUrl = `https://pastebin.com/${site.domain.replace(/\./g, '').slice(0, 8)}${i + 1}`;
        links.push({ title: article.title, pasteUrl: fakeUrl });
        await recordTrackerEvent({ module: 'submit-pastebin', site: site.domain, target: fakeUrl, status: 'success', details: 'dry-run paste prepared' });
        continue;
      }

      try {
        const response = await client.request({
          url: 'https://pastebin.com/api/api_post.php',
          method: 'POST',
          form: {
            api_dev_key: PASTEBIN_DEV_KEY,
            api_option: 'paste',
            api_paste_private: '0',
            api_paste_format: 'markdown',
            api_paste_name: `${site.domain} resource ${i + 1}`,
            api_paste_code: pasteBody(site, article)
          }
        });

        const pasteUrl = typeof response?.data === 'string' ? response.data.trim() : null;
        if (!pasteUrl || !pasteUrl.startsWith('http')) throw new Error(`Pastebin response invalid: ${String(response?.data).slice(0, 120)}`);

        links.push({ title: article.title, pasteUrl });
        await recordTrackerEvent({ module: 'submit-pastebin', site: site.domain, target: pasteUrl, status: 'success', details: 'public paste created' });
      } catch (error) {
        await recordTrackerEvent({ module: 'submit-pastebin', site: site.domain, target: 'pastebin api_post', status: 'failed', details: error.message });
      }
    }

    const outputPath = path.resolve('output', site.domain, 'pastebin-links.json');
    await writeJson(outputPath, { site: site.domain, links });
  }
}

if (import.meta.url === `file://${process.argv[1]}`) {
  runSubmitPastebin({ dryRun: parseDryRunArg() });
}
