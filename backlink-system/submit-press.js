import 'dotenv/config';
import path from 'node:path';
import config from './config.json' with { type: 'json' };
import { parseDryRunArg, writeJson, writeText } from './lib/utils.js';
import { recordTrackerEvent } from './tracker.js';

const platforms = [
  'PRLog.org',
  'PR.com',
  'OpenPR.com',
  '1888PressRelease.com',
  'PRFree.com',
  'Free-Press-Release.com',
  'i-Newswire.com',
  '24-7PressRelease.com',
  'PRBuzz.com',
  'PressReleasePoint.com',
  'ClickPress.com',
  'PressAbout.com',
  'PRZoom.com'
];

function pressPackage(site, platform) {
  return {
    platform,
    headline: `${site.domain} Expands ${site.niche} Educational Resources for Better Consumer Outcomes`,
    subheadline: `${site.ownerName} releases practical guides, checklists, and reference content to support informed decisions in ${site.niche}.`,
    body: [
      `${site.ownerName} today announced the expansion of ${site.domain}, an educational platform focused on ${site.niche}. The update includes long-form tutorials, practical checklists, and implementation examples designed for everyday use.`,
      `The content strategy emphasizes value-first education. Readers can explore clear frameworks for evaluating options, applying sustainable routines, and tracking progress over time without relying on hype-driven claims.`,
      `According to the editorial team, the goal is to reduce trial-and-error by publishing structured, repeatable guidance. New resources include topic hubs, quick-start plans, and frequently asked question briefs to improve clarity for new visitors.`,
      `The expanded library is available at https://${site.domain}.`
    ].join('\n\n'),
    boilerplate: `${site.ownerName} is a digital publisher focused on ${site.niche}. Through ${site.domain}, the company provides practical educational content to help readers make informed, sustainable decisions.`,
    contact: {
      name: site.ownerName,
      email: `press@${site.domain}`,
      phone: site.phoneNumber,
      address: site.localAddress,
      website: `https://${site.domain}`
    }
  };
}

function toMarkdown(pkg) {
  return `# ${pkg.headline}\n\n## ${pkg.subheadline}\n\n${pkg.body}\n\n### Boilerplate\n${pkg.boilerplate}\n\n### Media Contact\n- Name: ${pkg.contact.name}\n- Email: ${pkg.contact.email}\n- Phone: ${pkg.contact.phone}\n- Address: ${pkg.contact.address}\n- Website: ${pkg.contact.website}\n`;
}

export async function runSubmitPress({ dryRun = false } = {}) {
  for (const site of config.sites) {
    const packages = [];

    for (const platform of platforms) {
      const pkg = pressPackage(site, platform);
      packages.push(pkg);

      const fileBase = platform.toLowerCase().replace(/[^a-z0-9]+/g, '-');
      const outputPath = path.resolve('output', site.domain, 'press-packages', `${fileBase}.md`);
      await writeText(outputPath, toMarkdown(pkg));
      await recordTrackerEvent({ module: 'submit-press', site: site.domain, target: platform, status: 'success', details: `press package generated at ${outputPath}${dryRun ? ' (dry-run)' : ''}` });
    }

    const jsonPath = path.resolve('output', site.domain, 'press-packages', 'press-packages.json');
    await writeJson(jsonPath, { site: site.domain, packages });
  }
}

if (import.meta.url === `file://${process.argv[1]}`) {
  runSubmitPress({ dryRun: parseDryRunArg() });
}
