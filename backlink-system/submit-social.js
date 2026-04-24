import 'dotenv/config';
import path from 'node:path';
import config from './config.json' with { type: 'json' };
import { ApiClient } from './lib/clients.js';
import { contextualBacklink, parseDryRunArg, writeJson } from './lib/utils.js';
import { recordTrackerEvent } from './tracker.js';

const subreddits = ['supplements', 'biohackers', 'airquality', 'sleep', 'wellness'];

async function getRedditToken(client) {
  if (!process.env.REDDIT_CLIENT_ID || !process.env.REDDIT_CLIENT_SECRET || !process.env.REDDIT_USERNAME || !process.env.REDDIT_PASSWORD) {
    return null;
  }

  const auth = Buffer.from(`${process.env.REDDIT_CLIENT_ID}:${process.env.REDDIT_CLIENT_SECRET}`).toString('base64');
  const response = await client.request({
    url: 'https://www.reddit.com/api/v1/access_token',
    method: 'POST',
    headers: { Authorization: `Basic ${auth}` },
    form: {
      grant_type: 'password',
      username: process.env.REDDIT_USERNAME,
      password: process.env.REDDIT_PASSWORD
    }
  });

  return response?.data?.access_token ?? null;
}

function buildRedditPackage(site) {
  const link = contextualBacklink(site);
  return subreddits.slice(0, 5).map((sub, idx) => ({
    subreddit: sub,
    title: `${site.niche} practical tips ${idx + 1}: what actually helped`,
    body: `I collected practical lessons for ${site.niche} and summarized the highest-impact actions here. If anyone wants a deeper walkthrough, this resource is a helpful starting point: ${link.url}`,
    url: link.url,
    submitType: 'link_or_text'
  }));
}

export async function runSubmitSocial({ dryRun = false, offline = false } = {}) {
  const client = new ApiClient({ concurrency: config.concurrency, delayMs: config.delayMs, dryRun });
  const redditToken = (!offline && !dryRun) ? await getRedditToken(client) : null;

  for (const site of config.sites) {
    const link = contextualBacklink(site);
    const redditReady = buildRedditPackage(site);
    const redditReadyPath = path.resolve('output', site.domain, 'reddit-ready.json');
    await writeJson(redditReadyPath, { site: site.domain, posts: redditReady });
    await recordTrackerEvent({ module: 'submit-social', site: site.domain, target: redditReadyPath, status: 'success', details: 'reddit manual-ready package written' });

    if (redditToken) {
      for (const post of redditReady) {
        try {
          await client.request({
            url: 'https://oauth.reddit.com/api/submit',
            method: 'POST',
            headers: { Authorization: `Bearer ${redditToken}` },
            form: {
              api_type: 'json',
              sr: post.subreddit,
              kind: 'link',
              title: post.title,
              url: post.url
            }
          });
          await recordTrackerEvent({ module: 'submit-social', site: site.domain, target: `reddit/${post.subreddit}`, status: 'success', details: 'reddit submission sent' });
        } catch (error) {
          await recordTrackerEvent({ module: 'submit-social', site: site.domain, target: `reddit/${post.subreddit}`, status: 'failed', details: error.message });
        }
      }
    } else {
      await recordTrackerEvent({ module: 'submit-social', site: site.domain, target: 'reddit-api', status: 'success', details: 'api credentials unavailable; generated manual package only' });
    }

    try {
      if (!offline && process.env.PINBOARD_TOKEN) {
        await client.request({
          url: 'https://api.pinboard.in/v1/posts/add',
          method: 'GET'
        });
      }
      if (!offline && process.env.POCKET_CONSUMER_KEY && process.env.POCKET_ACCESS_TOKEN) {
        await client.request({
          url: 'https://getpocket.com/v3/add',
          method: 'POST',
          headers: { 'X-Accept': 'application/json' },
          body: {
            consumer_key: process.env.POCKET_CONSUMER_KEY,
            access_token: process.env.POCKET_ACCESS_TOKEN,
            url: link.url,
            title: `${site.niche} guide`
          }
        });
      }
      await recordTrackerEvent({ module: 'submit-social', site: site.domain, target: 'pinboard+pocket', status: 'success', details: (offline || dryRun) ? 'manual package mode' : 'social API requests sent' });
    } catch (error) {
      await recordTrackerEvent({ module: 'submit-social', site: site.domain, target: 'pinboard+pocket', status: 'failed', details: error.message });
    }

    const packagePath = path.resolve('output', site.domain, 'social-submission-packages.json');
    await writeJson(packagePath, {
      mix: { title: `${site.niche} essentials`, url: link.url, description: site.description },
      flipboard: { title: `${site.domain} insight`, url: link.url, category: site.niche },
      scoopit: { title: `${site.domain} topic hub`, url: link.url },
      digg: { title: `${site.niche}: what to know`, url: link.url }
    });
    await recordTrackerEvent({ module: 'submit-social', site: site.domain, target: packagePath, status: 'success', details: 'manual submission packages written' });
  }
}

if (import.meta.url === `file://${process.argv[1]}`) {
  runSubmitSocial({ dryRun: parseDryRunArg(), offline: process.argv.includes('--offline') });
}
