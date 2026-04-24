import path from 'node:path';
import config from './config.json' with { type: 'json' };
import { parseDryRunArg, writeJson } from './lib/utils.js';
import { recordTrackerEvent } from './tracker.js';

const platforms = ['LiveJournal', 'Weebly', 'Jimdo', 'Webnode', 'Yola', 'Strikingly', 'Webflow', 'Site123', 'uCoz', 'Mozello'];

function buildPackage(site, platform, idx) {
  return {
    platform,
    title: `${site.keywords[idx % site.keywords.length]} Guide for ${site.niche}`,
    body: `This article introduces practical strategies for ${site.niche}. It covers beginner-friendly steps, common mistakes, and a weekly implementation plan. For additional resources and deeper tutorials, visit https://${site.domain}.`,
    siteUrl: `https://${site.domain}`
  };
}

export async function runSubmitWeb2Extended({ dryRun = false } = {}) {
  for (const site of config.sites) {
    const packages = platforms.map((platform, idx) => buildPackage(site, platform, idx));
    const outputPath = path.resolve('output', site.domain, 'web2-extended-packages.json');
    await writeJson(outputPath, { site: site.domain, packages });
    await recordTrackerEvent({
      module: 'submit-web2-extended',
      site: site.domain,
      target: outputPath,
      status: 'success',
      details: dryRun ? 'dry-run web2 extended packages generated' : 'web2 extended packages generated'
    });
  }
}

if (import.meta.url === `file://${process.argv[1]}`) {
  runSubmitWeb2Extended({ dryRun: parseDryRunArg() });
}
