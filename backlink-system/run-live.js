import { runSubmitFreeHosting } from './submit-free-hosting-live.js';
import { runSubmitForumPosts } from './submit-forum-posts-live.js';
import { runSubmitSocialBookmarks } from './submit-social-bookmarks-live.js';

const pipeline = [
  { name: 'Social Bookmarks', run: runSubmitSocialBookmarks },
  { name: 'Free Hosting Pages', run: runSubmitFreeHosting },
  { name: 'Forum Posts', run: runSubmitForumPosts },
];

export async function runLive({ dryRun = false } = {}) {
  const summary = [];

  for (const step of pipeline) {
    const startedAt = new Date().toISOString();
    try {
      await step.run({ dryRun });
      summary.push({ name: step.name, ok: true, startedAt, finishedAt: new Date().toISOString() });
    } catch (error) {
      summary.push({
        name: step.name,
        ok: false,
        startedAt,
        finishedAt: new Date().toISOString(),
        error: error.message,
      });
    }
  }

  return summary;
}
