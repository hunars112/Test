import path from 'node:path';
import config from './config.json' with { type: 'json' };
import { contextualBacklink, parseDryRunArg, writeJson } from './lib/utils.js';
import { recordTrackerEvent } from './tracker.js';

function buildLinkedinPosts(site) {
  const link = contextualBacklink(site);
  return [
    {
      title: `${site.keywords[0]}: Practical Beginner Framework`,
      body: `Many teams overcomplicate ${site.niche}. This post outlines a practical routine, common mistakes, and a checklist you can apply this week. Full resource: ${link.url}`
    },
    {
      title: `${site.keywords[1]}: 5 Actionable Improvements`,
      body: `We compiled five high-impact habits for people focused on ${site.niche}. Each step is measurable and realistic for busy schedules. Read more at ${link.url}`
    },
    {
      title: `${site.keywords[2]}: What to Track for Better Results`,
      body: `Progress improves when you track the right inputs and outcomes. Here is a simple scorecard approach and weekly review rhythm for ${site.niche}. Reference: ${link.url}`
    }
  ];
}

export async function runSubmitLinkedin({ dryRun = false } = {}) {
  for (const site of config.sites) {
    const link = contextualBacklink(site);
    const packageData = {
      site: site.domain,
      linkedinProfileBio: `${site.ownerName} | Educational publisher for ${site.niche}. We share practical frameworks, checklists, and implementation guides. Website: ${link.url}`,
      companyPageDescription: `${site.domain} is an educational resource focused on ${site.niche}. Our content helps readers apply evidence-informed routines through clear, actionable guidance. Explore resources at ${link.url}.`,
      articleDrafts: buildLinkedinPosts(site)
    };

    const outputPath = path.resolve('output', site.domain, 'linkedin-packages.json');
    await writeJson(outputPath, packageData);
    await recordTrackerEvent({
      module: 'submit-linkedin',
      site: site.domain,
      target: outputPath,
      status: 'success',
      details: dryRun ? 'dry-run linkedin package generated' : 'linkedin package generated'
    });
  }
}

if (import.meta.url === `file://${process.argv[1]}`) {
  runSubmitLinkedin({ dryRun: parseDryRunArg() });
}
