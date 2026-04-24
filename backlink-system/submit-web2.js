import 'dotenv/config';
import path from 'node:path';
import config from './config.json' with { type: 'json' };
import { ApiClient } from './lib/clients.js';
import { contextualBacklink, parseDryRunArg, writeText } from './lib/utils.js';
import { recordTrackerEvent } from './tracker.js';

function createTargets(site, link) {
  const mediumUserId = process.env.MEDIUM_USER_ID ?? 'me';
  const wpSite = process.env.WORDPRESS_SITE_ID ?? 'me';
  const bloggerBlogId = process.env.BLOGGER_BLOG_ID ?? '';
  const tumblrBlog = process.env.TUMBLR_BLOG_IDENTIFIER ?? '';

  const title = `${site.niche} practical primer`;
  const html = `<h2>${title}</h2><p>${site.description}</p><p>Read more: <a href="${link.url}">${link.anchor}</a></p>`;

  return [
    {
      name: 'medium',
      hasApiCredentials: Boolean(process.env.MEDIUM_TOKEN),
      url: `https://api.medium.com/v1/users/${mediumUserId}/posts`,
      method: 'POST',
      headers: { Authorization: `Bearer ${process.env.MEDIUM_TOKEN ?? ''}` },
      body: { title, contentFormat: 'html', content: html, publishStatus: 'draft' },
      title,
      html
    },
    {
      name: 'wordpress',
      hasApiCredentials: Boolean(process.env.WORDPRESS_TOKEN),
      url: `https://public-api.wordpress.com/rest/v1.1/sites/${wpSite}/posts/new`,
      method: 'POST',
      headers: { Authorization: `Bearer ${process.env.WORDPRESS_TOKEN ?? ''}` },
      body: { title, content: html, status: 'draft' },
      title,
      html
    },
    {
      name: 'blogger',
      hasApiCredentials: Boolean(process.env.BLOGGER_API_KEY && bloggerBlogId),
      url: `https://www.googleapis.com/blogger/v3/blogs/${bloggerBlogId}/posts?key=${process.env.BLOGGER_API_KEY ?? ''}`,
      method: 'POST',
      body: { title, content: html },
      title,
      html
    },
    {
      name: 'tumblr',
      hasApiCredentials: Boolean(process.env.TUMBLR_API_KEY && tumblrBlog),
      url: `https://api.tumblr.com/v2/blog/${tumblrBlog}/post`,
      method: 'POST',
      form: { type: 'text', title, body: html },
      title,
      html
    },
    {
      name: 'telegraph',
      hasApiCredentials: Boolean(process.env.TELEGRAPH_ACCESS_TOKEN),
      url: 'https://api.telegra.ph/createPage',
      method: 'POST',
      body: {
        access_token: process.env.TELEGRAPH_ACCESS_TOKEN ?? '',
        title,
        author_name: site.domain,
        content: [{ tag: 'p', children: [`${site.description} ${link.url}`] }],
        return_content: false
      },
      title,
      html
    }
  ];
}

async function writeManualWeb2File(siteDomain, target) {
  const filePath = path.resolve('output', siteDomain, 'web2-manual', `${target.name}.html`);
  const content = `<!doctype html><html><head><meta charset="utf-8"><title>${target.title}</title></head><body>${target.html}</body></html>`;
  await writeText(filePath, content);
  return filePath;
}

export async function runSubmitWeb2({ dryRun = false, offline = false } = {}) {
  const client = new ApiClient({ concurrency: config.concurrency, delayMs: config.delayMs, dryRun });

  for (const site of config.sites) {
    const link = contextualBacklink(site);
    const targets = createTargets(site, link);

    for (const target of targets) {
      const shouldUseApi = !offline && target.hasApiCredentials;
      if (shouldUseApi) {
        try {
          await client.request(target);
          await recordTrackerEvent({ module: 'submit-web2', site: site.domain, target: target.name, status: 'success', details: dryRun ? 'dry-run request prepared' : 'request sent' });
          continue;
        } catch (error) {
          await recordTrackerEvent({ module: 'submit-web2', site: site.domain, target: target.name, status: 'failed', details: error.message });
        }
      }

      const filePath = await writeManualWeb2File(site.domain, target);
      await recordTrackerEvent({ module: 'submit-web2', site: site.domain, target: filePath, status: 'success', details: shouldUseApi ? 'api failed; fallback manual html generated' : 'manual html generated (no credentials/offline)' });
    }
  }
}

if (import.meta.url === `file://${process.argv[1]}`) {
  runSubmitWeb2({ dryRun: parseDryRunArg(), offline: process.argv.includes('--offline') });
}
