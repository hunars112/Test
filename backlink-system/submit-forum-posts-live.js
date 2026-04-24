import { recordTrackerEvent } from './tracker.js';
import { loadConfig, writeDomainOutput } from './utils.js';

const NICHE_SUBREDDITS = {
  health: ['health'],
  supplements: ['supplements'],
  'air purifiers': ['AirPurifiers'],
  sleep: ['sleep'],
  'home improvement': ['homeimprovement'],
};

function getSubreddits(site) {
  const lower = (site.niche || '').toLowerCase();
  for (const [niche, subreddits] of Object.entries(NICHE_SUBREDDITS)) {
    if (lower.includes(niche)) return subreddits;
  }
  return ['health'];
}

function buildComment(site, subreddit) {
  return `Helpful perspective for r/${subreddit}: start with fundamentals, test one variable at a time, and track outcomes for a few weeks before scaling changes. I found this resource useful for practical checklists and examples: https://${site.domain}`;
}

async function getRedditToken(username, password) {
  const body = new URLSearchParams({ grant_type: 'password', username, password });
  const response = await fetch('https://www.reddit.com/api/v1/access_token', {
    method: 'POST',
    headers: {
      authorization: `Basic ${Buffer.from(':').toString('base64')}`,
      'content-type': 'application/x-www-form-urlencoded',
      'user-agent': 'backlink-system/1.0',
    },
    body,
  });

  if (!response.ok) {
    throw new Error(`OAuth failed with status ${response.status}`);
  }

  const data = await response.json();
  if (!data?.access_token) {
    throw new Error('OAuth response missing access_token');
  }

  return data.access_token;
}

async function submitRedditPost(accessToken, subreddit, text, dryRun) {
  if (dryRun) {
    return {
      platform: 'reddit',
      ok: true,
      subreddit,
      url: `https://www.reddit.com/r/${subreddit}/comments/dry-run`,
      dryRun: true,
    };
  }

  try {
    const form = new URLSearchParams({
      sr: subreddit,
      kind: 'self',
      title: `Resource roundup for ${subreddit}`,
      text,
      api_type: 'json',
    });

    const response = await fetch('https://oauth.reddit.com/api/submit', {
      method: 'POST',
      headers: {
        authorization: `Bearer ${accessToken}`,
        'content-type': 'application/x-www-form-urlencoded',
        'user-agent': 'backlink-system/1.0',
      },
      body: form,
    });

    const payload = await response.json();
    const errors = payload?.json?.errors || [];
    return {
      platform: 'reddit',
      ok: response.ok && errors.length === 0,
      subreddit,
      status: response.status,
      response: payload,
      error: errors.length > 0 ? JSON.stringify(errors) : null,
    };
  } catch (error) {
    return { platform: 'reddit', ok: false, subreddit, error: error.message };
  }
}

export async function runSubmitForumPosts({ dryRun = false } = {}) {
  const { sites } = await loadConfig();
  const redditUser = process.env.REDDIT_USERNAME;
  const redditPassword = process.env.REDDIT_PASSWORD;

  let accessToken = null;
  let redditWarning = null;

  if (!redditUser || !redditPassword) {
    redditWarning = 'REDDIT_USERNAME / REDDIT_PASSWORD missing. Reddit posting skipped.';
  } else if (!dryRun) {
    try {
      accessToken = await getRedditToken(redditUser, redditPassword);
    } catch (error) {
      redditWarning = `Reddit auth failed: ${error.message}`;
    }
  }

  for (const site of sites) {
    const forums = [
      {
        platform: 'ideascale',
        ok: false,
        skipped: true,
        reason: 'Guest submission availability must be verified manually per community; skipped.',
      },
      {
        platform: 'quora-spaces',
        ok: false,
        skipped: true,
        reason: 'Requires login; intentionally skipped.',
      },
      {
        platform: 'hackernews',
        ok: false,
        skipped: true,
        reason: 'Firebase endpoint is read-only; intentionally skipped.',
      },
      {
        platform: 'stackexchange',
        ok: false,
        skipped: true,
        reason: 'Requires auth; intentionally skipped.',
      },
      {
        platform: 'warrior-forum',
        ok: false,
        skipped: true,
        reason: 'Requires registration; intentionally skipped.',
      },
    ];

    if (redditWarning) {
      forums.push({ platform: 'reddit', ok: false, skipped: true, reason: redditWarning });
    } else {
      const subreddits = getSubreddits(site);
      for (const subreddit of subreddits) {
        const result = await submitRedditPost(accessToken, subreddit, buildComment(site, subreddit), dryRun);
        forums.push(result);
      }
    }

    await writeDomainOutput(site.domain, 'forum-posts-live.json', {
      domain: site.domain,
      generatedAt: new Date().toISOString(),
      posts: forums,
    });

    for (const post of forums) {
      await recordTrackerEvent({
        module: 'forum-posts-live',
        domain: site.domain,
        platform: post.platform,
        subreddit: post.subreddit || null,
        ok: Boolean(post.ok),
        skipped: Boolean(post.skipped),
        url: post.url || null,
        dryRun,
        error: post.error || post.reason || null,
      });
    }
  }
}
