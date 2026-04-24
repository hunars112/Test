import { mkdir, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { recordTrackerEvent } from './tracker.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const NICHE_BLOGS = {
  blood_sugar: [
    'wellnessmama.com',
    'draxe.com',
    'mindbodygreen.com',
    'nutritionfacts.org',
    'happymammoth.com',
  ],
  cbd: [
    'wellnessmama.com',
    'draxe.com',
    'mindbodygreen.com',
    'cbdtesters.co',
    'medicalmarijuanainc.com',
  ],
  air_purifier: [
    'wellnessmama.com',
    'draxe.com',
    'mindbodygreen.com',
    'housefresh.com',
    'breathesafeair.com',
  ],
  cooling: [
    'wellnessmama.com',
    'draxe.com',
    'mindbodygreen.com',
    'sleepadvisor.org',
    'sleepsherpa.com',
  ],
  pillow: [
    'wellnessmama.com',
    'draxe.com',
    'mindbodygreen.com',
    'eachnight.com',
    'sleepfoundation.org',
  ],
  nail_fungus: [
    'wellnessmama.com',
    'draxe.com',
    'mindbodygreen.com',
    'thehealthy.com',
    'organicauthority.com',
  ],
};

async function getFetch() {
  if (typeof globalThis.fetch === 'function') return globalThis.fetch.bind(globalThis);
  const mod = await import('node-fetch');
  return mod.default;
}

async function readConfig() {
  const configPath = path.join(__dirname, 'config.json');
  const raw = await readFile(configPath, 'utf8');
  return JSON.parse(raw);
}

function normalizeSites(config) {
  const raw = config?.sites ?? config?.domains ?? [];
  return (Array.isArray(raw) ? raw : []).map((site) => {
    if (typeof site === 'string') return { domain: site };
    return site;
  });
}

function detectNiche(site) {
  const value = `${site?.niche ?? ''} ${site?.category ?? ''} ${site?.vertical ?? ''}`.toLowerCase();
  if (value.includes('blood')) return 'blood_sugar';
  if (value.includes('cbd')) return 'cbd';
  if (value.includes('air')) return 'air_purifier';
  if (value.includes('cool')) return 'cooling';
  if (value.includes('pillow')) return 'pillow';
  if (value.includes('fungus') || value.includes('nail')) return 'nail_fungus';
  return 'blood_sugar';
}

function buildComment({ domain, postTitle }) {
  const local = Math.floor(Math.random() * 900000 + 100000);
  const email = `reader${local}@gmail.com`;
  const content = `Great breakdown on ${postTitle || 'this topic'}. I appreciate how you connected practical daily habits with longer-term results instead of pushing quick fixes. I have been testing similar routines and noticed that consistency really matters, especially with sleep, movement, and food quality. I also track what has been working for me on ${domain}, and your points reinforced several patterns I have seen. Thanks for sharing a balanced, evidence-aware perspective that is easy to apply in real life.`;
  return {
    author_name: 'Health Enthusiast',
    author_email: email,
    author_url: `https://${domain}`,
    content,
  };
}

export async function runSubmitWordpressComments({ dryRun = false } = {}) {
  const config = await readConfig();
  const sites = normalizeSites(config);
  const fetchFn = dryRun ? null : await getFetch();
  const finalResults = [];

  for (const site of sites) {
    const domain = String(site.domain || site.site || 'unknown').replace(/^https?:\/\//, '');
    const niche = detectNiche(site);
    const blogs = NICHE_BLOGS[niche] || NICHE_BLOGS.blood_sugar;
    const siteResults = [];

    for (const blog of blogs) {
      const base = `https://${blog}`;
      try {
        let result;
        if (dryRun) {
          result = {
            blog,
            postId: 123,
            commentStatus: 'queued_mock',
            timestamp: new Date().toISOString(),
            dryRun: true,
          };
        } else {
          // eslint-disable-next-line no-await-in-loop
          const postsRes = await fetchFn(`${base}/wp-json/wp/v2/posts?per_page=1`, {
            headers: { 'User-Agent': 'Mozilla/5.0 (compatible; BacklinkLiveBot/1.0)' },
          });

          if (!postsRes.ok) {
            throw new Error(`posts lookup failed (${postsRes.status})`);
          }

          // eslint-disable-next-line no-await-in-loop
          const posts = await postsRes.json();
          const post = Array.isArray(posts) ? posts[0] : null;
          if (!post?.id) {
            throw new Error('no recent post available');
          }

          const commentPayload = {
            post: post.id,
            ...buildComment({ domain, postTitle: post.title?.rendered ?? 'this post' }),
          };

          // eslint-disable-next-line no-await-in-loop
          const commentRes = await fetchFn(`${base}/wp-json/wp/v2/comments`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'User-Agent': 'Mozilla/5.0 (compatible; BacklinkLiveBot/1.0)',
            },
            body: JSON.stringify(commentPayload),
          });

          // eslint-disable-next-line no-await-in-loop
          const body = await commentRes.json().catch(() => ({}));
          if (![200, 201].includes(commentRes.status)) {
            if ([403, 404].includes(commentRes.status)) {
              throw new Error(`comments unavailable (${commentRes.status})`);
            }
            throw new Error(body?.message || `comment post failed (${commentRes.status})`);
          }

          result = {
            blog,
            postId: post.id,
            commentId: body?.id ?? null,
            commentStatus: body?.status ?? 'submitted',
            timestamp: new Date().toISOString(),
            dryRun: false,
          };
        }

        siteResults.push(result);
        finalResults.push({ domain, niche, ...result });
        // eslint-disable-next-line no-await-in-loop
        await recordTrackerEvent({ module: 'submit-wordpress-comments-live', domain, niche, ...result });
      } catch (error) {
        const failure = {
          blog,
          error: error.message,
          timestamp: new Date().toISOString(),
          dryRun,
        };
        siteResults.push(failure);
        finalResults.push({ domain, niche, ...failure });
        // eslint-disable-next-line no-await-in-loop
        await recordTrackerEvent({
          module: 'submit-wordpress-comments-live',
          domain,
          niche,
          ...failure,
        });
      }
    }

    const outDir = path.join(__dirname, 'output', domain);
    await mkdir(outDir, { recursive: true });
    await writeFile(path.join(outDir, 'wp-comment-submissions.json'), JSON.stringify(siteResults, null, 2));
  }

  return finalResults;
}
