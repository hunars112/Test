#!/usr/bin/env node
import 'dotenv/config';
import path from 'node:path';
import config from './config.json' with { type: 'json' };
import { runGenerateContent } from './generate-content.js';
import { runSubmitWeb2 } from './submit-web2.js';
import { runSubmitSocial } from './submit-social.js';
import { runSubmitDirectories } from './submit-directories.js';
import { runSubmitPress } from './submit-press.js';
import { runSubmitDocuments } from './submit-documents.js';
import { runSubmitProfiles } from './submit-profiles.js';
import { runSubmitQa } from './submit-qa.js';
import { runSubmitImageSharing } from './submit-image-sharing.js';
import { runSubmitVideo } from './submit-video.js';
import { runSubmitRss } from './submit-rss.js';
import { runSubmitComments } from './submit-comments.js';
import { runSubmitCitations } from './submit-citations.js';
import { runSubmitWikis } from './submit-wikis.js';
import { runSubmitPodcast } from './submit-podcast.js';
import { runSubmitTiered } from './submit-tiered.js';
import { runSubmitGithubGist } from './submit-github-gist.js';
import { runSubmitPastebin } from './submit-pastebin.js';
import { runSubmitLinkedin } from './submit-linkedin.js';
import { runSubmitPinterest } from './submit-pinterest.js';
import { runSubmitTwitter } from './submit-twitter.js';
import { runSubmitReddit } from './submit-reddit.js';
import { runSubmitTumblr } from './submit-tumblr.js';
import { runSubmitMix } from './submit-mix.js';
import { runSubmitMedium } from './submit-medium.js';
import { runSubmitBloggerOutreach } from './submit-blogger-outreach.js';
import { runSubmitWeb2Extended } from './submit-web2-extended.js';
import { exportTrackerCsv } from './tracker.js';
import { writeText } from './lib/utils.js';

const moduleRuns = [
  { name: 'generate-content', run: () => runGenerateContent({ offline: true }) },
  { name: 'submit-web2', run: () => runSubmitWeb2({ offline: true }) },
  { name: 'submit-web2-extended', run: () => runSubmitWeb2Extended({ dryRun: false }) },
  { name: 'submit-medium', run: () => runSubmitMedium({ dryRun: false }) },
  { name: 'submit-social', run: () => runSubmitSocial({ offline: true }) },
  { name: 'submit-reddit', run: () => runSubmitReddit({ dryRun: false }) },
  { name: 'submit-twitter', run: () => runSubmitTwitter({ dryRun: false }) },
  { name: 'submit-tumblr', run: () => runSubmitTumblr({ dryRun: false }) },
  { name: 'submit-mix', run: () => runSubmitMix({ dryRun: false }) },
  { name: 'submit-directories', run: () => runSubmitDirectories({ dryRun: false }) },
  { name: 'submit-github-gist', run: () => runSubmitGithubGist({ dryRun: false }) },
  { name: 'submit-pastebin', run: () => runSubmitPastebin({ dryRun: false }) },
  { name: 'submit-linkedin', run: () => runSubmitLinkedin({ dryRun: false }) },
  { name: 'submit-pinterest', run: () => runSubmitPinterest({ dryRun: false }) },
  { name: 'submit-blogger-outreach', run: () => runSubmitBloggerOutreach({ dryRun: false }) },
  { name: 'submit-press', run: () => runSubmitPress({ dryRun: false }) },
  { name: 'submit-documents', run: () => runSubmitDocuments({ dryRun: false }) },
  { name: 'submit-profiles', run: () => runSubmitProfiles({ dryRun: false }) },
  { name: 'submit-qa', run: () => runSubmitQa({ dryRun: false }) },
  { name: 'submit-image-sharing', run: () => runSubmitImageSharing({ dryRun: false }) },
  { name: 'submit-video', run: () => runSubmitVideo({ dryRun: false }) },
  { name: 'submit-rss', run: () => runSubmitRss({ dryRun: false }) },
  { name: 'submit-comments', run: () => runSubmitComments({ dryRun: false }) },
  { name: 'submit-citations', run: () => runSubmitCitations({ dryRun: false }) },
  { name: 'submit-wikis', run: () => runSubmitWikis({ dryRun: false }) },
  { name: 'submit-podcast', run: () => runSubmitPodcast({ dryRun: false }) },
  { name: 'submit-tiered', run: () => runSubmitTiered({ dryRun: false }) },
  { name: 'tracker', run: () => exportTrackerCsv() }
];

function buildSubmissionGuide() {
  return `# SUBMISSION GUIDE\n\nGenerated: ${new Date().toISOString()}\n\n## Priority 1 — Highest Authority / Fastest Impact\n1. **Web2 + Medium + Live Zero-Auth Links**\n   - Web2 drafts: \`output/{domain}/web2-manual/*.html\`\n   - Extended Web2: \`output/{domain}/web2-extended-packages.json\`\n   - Medium drafts: \`output/{domain}/medium-articles/*.md\`\n   - Gist links: \`output/{domain}/gist-links.json\`\n   - Pastebin links: \`output/{domain}/pastebin-links.json\`\n2. **Reddit + Twitter + Social Bookmarks + Pinterest + Tumblr + Mix**\n   - Open: \`output/{domain}/reddit-posts.json\`, \`output/{domain}/twitter-packages.json\`, \`social-submission-packages.json\`, \`pinterest-packages.json\`, \`tumblr-packages.json\`, and \`mix-packages.json\`.\n3. **Directory + Citation Listings**\n   - Use \`directory-submissions.csv\` (150 rows) and \`citations-master.csv\` for high-volume submissions.\n\n## Priority 2 — Authority Support Layer\n4. **Press + Outreach + RSS + Documents**\n   - Press files: \`output/{domain}/press-packages/*.md\`\n   - Outreach templates: \`output/{domain}/blogger-outreach.json\`\n   - RSS feed: \`output/{domain}/feed.xml\`\n   - PDFs: \`output/{domain}/documents/\`\n5. **Profiles + LinkedIn + Podcast + Video**\n   - LinkedIn: \`output/{domain}/linkedin-packages.json\`\n   - Profiles: \`output/{domain}/profile-packages.json\`\n   - Podcast: \`output/{domain}/podcast-packages.json\`\n   - Video: \`output/{domain}/video-packages.json\`\n\n## Priority 3 — Long-Tail Link Diversity\n6. **Image + Wiki + Q/A + Comments + Tier-2**\n   - Image packages: \`output/{domain}/image-sharing-packages.json\`\n   - Wiki templates: \`output/{domain}/wiki-packages.json\`\n   - Q/A templates: \`output/{domain}/qa-packages.json\`\n   - Comments: \`output/{domain}/comment-templates.json\`\n   - Tier-2: \`output/{domain}/tier2-packages.json\`\n\n## Site Output Locations\n${config.sites.map((s) => `- ${s.domain}: \`output/${s.domain}/\``).join('\n')}\n`;
}

function buildBacklinkCount() {
  const perSite = {
    web2: 5,
    web2Extended: 10,
    medium: 3,
    githubGists: 2,
    pastebin: 2,
    linkedin: 4,
    pinterest: 5,
    twitter: 25,
    redditStandalone: 5,
    tumblr: 5,
    mix: 10,
    social: 9,
    directories: Math.floor(150 / config.sites.length),
    press: 13,
    bloggerOutreach: 10,
    documents: 3,
    profiles: 5,
    qa: 27,
    imageSharing: 3,
    video: 3,
    rss: 7,
    comments: 10,
    citations: 13,
    wikis: 3,
    podcast: 4,
    tier2: 25
  };

  const total = Object.values(perSite).reduce((sum, n) => sum + n, 0);
  const rows = config.sites.map((site) => {
    const details = Object.entries(perSite).map(([k, v]) => `- ${k}: ${v}`).join('\n');
    return `## ${site.domain}\n${details}\n- **Estimated total per site:** ${total}\n`;
  }).join('\n');

  const globalTotal = total * config.sites.length;

  return `# BACKLINK COUNT\n\nEstimated opportunities generated by offline system output.\n\n${rows}\n## Overall estimate\n- Sites: ${config.sites.length}\n- Estimated backlinks per site: ${total}\n- Added from Round 5: GitHub Gists +16 total, Pastebin +16 total\n- Added from Round 6: Twitter +200 total tweet/thread opportunities, Reddit +40, Tumblr +40, Mix +80\n- Added from Round 7: Medium +24, Blogger Outreach +80, Extended Web2 +80, Press Expansion +72\n- **Estimated total opportunities:** ${globalTotal}\n`;
}

async function main() {
  for (const mod of moduleRuns) {
    // eslint-disable-next-line no-console
    console.log(`Running ${mod.name}...`);
    await mod.run();
  }

  await writeText(path.resolve('SUBMISSION-GUIDE.md'), buildSubmissionGuide());
  await writeText(path.resolve('BACKLINK-COUNT.md'), buildBacklinkCount());
  // eslint-disable-next-line no-console
  console.log('Offline run complete. Review SUBMISSION-GUIDE.md and BACKLINK-COUNT.md');
}

main().catch((error) => {
  // eslint-disable-next-line no-console
  console.error(error);
  process.exit(1);
});
