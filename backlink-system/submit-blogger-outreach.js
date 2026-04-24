import path from 'node:path';
import config from './config.json' with { type: 'json' };
import { parseDryRunArg, writeJson } from './lib/utils.js';
import { recordTrackerEvent } from './tracker.js';

const outreachAngles = [
  'data-backed beginner guide',
  'myth vs reality article',
  'routine checklist for busy readers',
  'expert roundup collaboration',
  'case-study style tutorial',
  'seasonal trend analysis',
  'toolkit/resource compilation',
  'comparison framework',
  'common mistakes and fixes',
  'long-term maintenance roadmap'
];

function outreachTemplate(site, idx) {
  const angle = outreachAngles[idx % outreachAngles.length];
  return {
    subject: `Guest post idea: ${site.keywords[idx % site.keywords.length]} (${angle})`,
    angle,
    emailBody: `Hi {{BloggerName}},\n\nI have been reading {{BlogName}} and especially enjoyed your recent post on ${site.niche}. I’d love to contribute a guest article with a ${angle} angle tailored to your audience.\n\nI can provide an original draft, include practical takeaways, and cite credible references. If helpful, I can also include one contextual reference to our resource library at https://${site.domain} where we publish educational content on ${site.niche}.\n\nIf you’re open to this, I can send 2-3 title options and an outline this week.\n\nBest,\n${site.ownerName}`,
    mentionUrl: `https://${site.domain}`
  };
}

export async function runSubmitBloggerOutreach({ dryRun = false } = {}) {
  for (const site of config.sites) {
    const templates = Array.from({ length: 10 }, (_, idx) => outreachTemplate(site, idx));
    const outputPath = path.resolve('output', site.domain, 'blogger-outreach.json');
    await writeJson(outputPath, { site: site.domain, templates });
    await recordTrackerEvent({
      module: 'submit-blogger-outreach',
      site: site.domain,
      target: outputPath,
      status: 'success',
      details: dryRun ? 'dry-run blogger outreach templates generated' : 'blogger outreach templates generated'
    });
  }
}

if (import.meta.url === `file://${process.argv[1]}`) {
  runSubmitBloggerOutreach({ dryRun: parseDryRunArg() });
}
