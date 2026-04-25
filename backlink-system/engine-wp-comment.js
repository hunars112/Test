import { promises as fs } from 'node:fs';
import path from 'node:path';
import { loadConfig, writeDomainOutput } from './lib/utils.js';
import { recordTrackerEvent } from './tracker.js';
import {
  loadWinsDb,
  saveWinsDb,
  addOrUpdateEntry,
  getProvenWins,
  markSuccess,
  markFailed,
  isKnown,
  isOnCooldown,
} from './wins-db.js';
import { discoverTargets } from './discover-targets.js';

const AUTHORS = [
  { name: 'Ava Bennett', email: 'ava.reader1@example.com' },
  { name: 'Mason Carter', email: 'mason.reader2@example.com' },
  { name: 'Olivia Hayes', email: 'olivia.reader3@example.com' },
  { name: 'Liam Foster', email: 'liam.reader4@example.com' },
  { name: 'Sophia Reed', email: 'sophia.reader5@example.com' },
  { name: 'Noah Mills', email: 'noah.reader6@example.com' },
  { name: 'Emma Lane', email: 'emma.reader7@example.com' },
  { name: 'Ethan Brooks', email: 'ethan.reader8@example.com' },
];

const COMMENT_VARIATIONS = [
  'Helpful perspective—this lines up with what I found while researching options on SITE_DOMAIN. Appreciate the practical detail here.',
  'Thanks for posting this. I recently compared similar ideas and SITE_DOMAIN had a useful breakdown that complements your points.',
  'Great write-up. I was looking into this topic and found extra examples at SITE_DOMAIN; your tips here made it easier to understand.',
  'Really solid explanation. I had related questions and SITE_DOMAIN had more context that paired well with your article.',
  'Valuable post—this is the kind of detail people need. I also bookmarked SITE_DOMAIN for additional references on the same topic.',
];

const WP_QUERY_TEMPLATES = [
  '"leave a reply" "your email address will not be published" {niche}',
  '"Leave a Reply" "Name *" "Email *" {niche}',
  '"wp-comments-post.php" "leave a reply" {niche}',
];

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

function getFetch() {
  if (typeof globalThis.fetch === 'function') {
    return globalThis.fetch.bind(globalThis);
  }
  throw new Error('Fetch API not available in runtime.');
}

function toSites(config) {
  if (Array.isArray(config)) return config;
  if (Array.isArray(config?.sites)) return config.sites;
  if (Array.isArray(config?.domains)) return config.domains;
  return [];
}

function getDomain(site) {
  return site?.domain || site?.siteDomain || site?.url?.replace(/^https?:\/\//, '').replace(/\/.*/, '');
}

function resolveSiteUrl(site, domain) {
  return site?.url || `https://${domain}`;
}

function pickByIndex(arr, idx) {
  return arr[idx % arr.length];
}

function makeComment(siteDomain, index) {
  const base = pickByIndex(COMMENT_VARIATIONS, index);
  return base.replaceAll('SITE_DOMAIN', siteDomain);
}

function makeSearchQueries(niche) {
  const label = niche || 'wellness';
  return WP_QUERY_TEMPLATES.map((tpl) => tpl.replace('{niche}', label));
}

function maybeBlocked(html = '') {
  const lower = html.toLowerCase();
  return (
    lower.includes('g-recaptcha') ||
    lower.includes('h-captcha') ||
    lower.includes('cloudflare') ||
    lower.includes('comments are closed') ||
    lower.includes('commenting has been disabled')
  );
}

async function fetchJson(fetchFn, url, init) {
  const response = await fetchFn(url, init);
  const text = await response.text();
  let json = null;
  try {
    json = JSON.parse(text);
  } catch {
    json = null;
  }
  return { response, text, json };
}

async function tryWpRestComment(fetchFn, targetUrl, author, comment, siteUrl) {
  const base = new URL(targetUrl);
  const postsUrl = `${base.origin}/wp-json/wp/v2/posts?per_page=1&_fields=id`;
  const postsData = await fetchJson(fetchFn, postsUrl, { headers: { accept: 'application/json' } });
  if (!postsData.response.ok || !Array.isArray(postsData.json) || !postsData.json[0]?.id) {
    return { ok: false, reason: 'no-post-id' };
  }

  const payload = {
    post: postsData.json[0].id,
    author_name: author.name,
    author_email: author.email,
    author_url: siteUrl,
    content: comment,
  };

  const commentRes = await fetchJson(fetchFn, `${base.origin}/wp-json/wp/v2/comments`, {
    method: 'POST',
    headers: {
      'content-type': 'application/json',
      accept: 'application/json',
    },
    body: JSON.stringify(payload),
  });

  return {
    ok: commentRes.response.ok && !!commentRes.json?.id,
    reason: commentRes.response.ok ? 'accepted' : `rest-${commentRes.response.status}`,
    raw: commentRes.json ?? commentRes.text,
  };
}

function parseCommentForm(html, pageUrl) {
  const actionMatch = html.match(/<form[^>]+id=["']commentform["'][^>]*action=["']([^"']+)["']/i)
    || html.match(/<form[^>]+action=["']([^"']*wp-comments-post\.php[^"']*)["'][^>]*>/i);
  if (!actionMatch) return null;

  const actionUrl = new URL(actionMatch[1], pageUrl).toString();
  const hiddenInputs = [...html.matchAll(/<input[^>]+type=["']hidden["'][^>]*>/gi)]
    .map((m) => m[0])
    .map((tag) => {
      const name = tag.match(/name=["']([^"']+)["']/i)?.[1];
      const value = tag.match(/value=["']([^"']*)["']/i)?.[1] ?? '';
      return name ? [name, value] : null;
    })
    .filter(Boolean);

  const formData = new URLSearchParams();
  for (const [k, v] of hiddenInputs) {
    formData.set(k, v);
  }

  return { actionUrl, formData };
}

async function tryWpHtmlComment(fetchFn, targetUrl, author, comment, siteUrl) {
  const page = await fetchFn(targetUrl, { headers: { 'user-agent': 'Mozilla/5.0' } });
  const html = await page.text();
  if (!page.ok) {
    return { ok: false, reason: `html-load-${page.status}` };
  }
  if (maybeBlocked(html)) {
    return { ok: false, reason: 'blocked-or-closed' };
  }

  const parsed = parseCommentForm(html, targetUrl);
  if (!parsed) {
    return { ok: false, reason: 'no-comment-form' };
  }

  parsed.formData.set('author', author.name);
  parsed.formData.set('email', author.email);
  parsed.formData.set('url', siteUrl);
  parsed.formData.set('comment', comment);
  parsed.formData.set('submit', 'Post Comment');

  const submit = await fetchFn(parsed.actionUrl, {
    method: 'POST',
    headers: {
      'content-type': 'application/x-www-form-urlencoded',
      origin: new URL(targetUrl).origin,
      referer: targetUrl,
      'user-agent': 'Mozilla/5.0',
    },
    body: parsed.formData.toString(),
    redirect: 'manual',
  });

  const success = [200, 201, 302, 303].includes(submit.status);
  return { ok: success, reason: success ? 'submitted' : `html-submit-${submit.status}` };
}

async function tryPostComment(fetchFn, targetUrl, author, comment, siteUrl) {
  try {
    const rest = await tryWpRestComment(fetchFn, targetUrl, author, comment, siteUrl);
    if (rest.ok) return rest;
  } catch (error) {
    // Fall through to HTML form fallback.
  }

  try {
    return await tryWpHtmlComment(fetchFn, targetUrl, author, comment, siteUrl);
  } catch (error) {
    return { ok: false, reason: `exception:${error.message}` };
  }
}

async function writeFallback(domain, payload) {
  const targetDir = path.resolve(process.cwd(), 'output', domain);
  await fs.mkdir(targetDir, { recursive: true });
  await fs.writeFile(path.join(targetDir, 'engine-wp-comment.json'), JSON.stringify(payload, null, 2), 'utf8');
}

export async function runEngineWpComment({ dryRun = false } = {}) {
  const fetchFn = getFetch();
  const cfg = await loadConfig();
  const sites = toSites(cfg);
  const winsDb = await loadWinsDb();
  const globalRaw = [];

  for (let siteIndex = 0; siteIndex < sites.length; siteIndex += 1) {
    const site = sites[siteIndex];
    const domain = getDomain(site);
    if (!domain) continue;

    const siteUrl = resolveSiteUrl(site, domain);
    const niche = site.niche || site.category || 'wellness';

    const links = [];
    const raw = [];

    const proven = getProvenWins(winsDb, domain, 'wp-comment')
      .filter((entry) => !isOnCooldown(winsDb, entry.targetUrl, domain))
      .slice(0, 10);

    for (let i = 0; i < proven.length; i += 1) {
      const author = pickByIndex(AUTHORS, i);
      const comment = makeComment(domain, i);
      const targetUrl = proven[i].targetUrl;

      if (dryRun) {
        raw.push({ targetUrl, mode: 'proven', status: 'dry-run' });
        continue;
      }

      const result = await tryPostComment(fetchFn, targetUrl, author, comment, siteUrl);
      raw.push({ targetUrl, mode: 'proven', ...result });

      if (result.ok) {
        markSuccess(winsDb, targetUrl, domain);
        links.push({ url: targetUrl, title: 'WP Comment', platform: 'wp-comment' });
      } else {
        markFailed(winsDb, targetUrl, domain);
      }

      await sleep(2000);
    }

    const discovered = await discoverTargets(fetchFn, makeSearchQueries(niche), { sleepBetween: 3000 });
    const candidates = discovered
      .filter((url) => !isKnown(winsDb, url, domain))
      .slice(0, 5);

    for (let i = 0; i < candidates.length; i += 1) {
      const targetUrl = candidates[i];
      const author = pickByIndex(AUTHORS, i + proven.length);
      const comment = makeComment(domain, i + proven.length);

      addOrUpdateEntry(winsDb, {
        targetUrl,
        siteDomain: domain,
        engine: 'wp-comment',
        type: 'comment',
        firstSeen: new Date().toISOString(),
      });

      if (dryRun) {
        raw.push({ targetUrl, mode: 'new', status: 'dry-run' });
        continue;
      }

      const result = await tryPostComment(fetchFn, targetUrl, author, comment, siteUrl);
      raw.push({ targetUrl, mode: 'new', ...result });
      if (result.ok) {
        markSuccess(winsDb, targetUrl, domain);
        links.push({ url: targetUrl, title: 'WP Comment', platform: 'wp-comment' });
      } else {
        markFailed(winsDb, targetUrl, domain);
      }

      await sleep(2000);
    }

    const payload = { links, raw };
    try {
      await writeDomainOutput(domain, 'engine-wp-comment.json', payload);
    } catch {
      await writeFallback(domain, payload);
    }

    globalRaw.push({ domain, links: links.length, attempts: raw.length });
    if (typeof recordTrackerEvent === 'function') {
      try {
        await recordTrackerEvent({
          engine: 'wp-comment',
          domain,
          dryRun,
          links: links.length,
          attempts: raw.length,
        });
      } catch {
        // Ignore tracker failures.
      }
    }
  }

  await saveWinsDb(winsDb);
  return { ok: true, dryRun, summary: globalRaw };
}
