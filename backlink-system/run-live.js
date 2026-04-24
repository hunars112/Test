import { runSubmitPasteExtraLive } from './submit-paste-extra-live.js';
import { runSubmitWayback } from './submit-wayback-live.js';
import { runSubmitWordpressComments } from './submit-wordpress-comments-live.js';

export async function runLive({ dryRun = false } = {}) {
  const modules = [
    { name: 'Extra Paste Platforms', run: runSubmitPasteExtraLive },
    { name: 'Wayback Machine Archive', run: runSubmitWayback },
    { name: 'WordPress Blog Comments', run: runSubmitWordpressComments },
  ];

  const results = [];
  for (const module of modules) {
    try {
      // eslint-disable-next-line no-await-in-loop
      const output = await module.run({ dryRun });
      results.push({ name: module.name, status: 'ok', output });
    } catch (error) {
      results.push({ name: module.name, status: 'error', error: error.message });
    }
  }

  return results;
}
