import path from 'node:path';
import config from './config.json' with { type: 'json' };
import { parseDryRunArg, writeJson } from './lib/utils.js';
import { recordTrackerEvent } from './tracker.js';

function nicheSubreddits(site) {
  const niche = site.niche.toLowerCase();
  if (niche.includes('glucose') || niche.includes('metabolic')) return ['prediabetes', 'diabetes', 'nutrition', 'biohackers', 'supplements'];
  if (niche.includes('plantar') || niche.includes('foot')) return ['running', 'physicaltherapy', 'foothealth', 'chronicpain', 'walking'];
  if (niche.includes('air purifier') || niche.includes('air quality')) return ['AirQuality', 'allergies', 'homeimprovement', 'asthma', 'wildfire'];
  if (niche.includes('cooler')) return ['homeimprovement', 'HVAC', 'frugal', 'Appliances', 'DIY'];
  if (niche.includes('sleep') || niche.includes('pillow')) return ['sleep', 'insomnia', 'bedding', 'biohackers', 'selfimprovement'];
  if (niche.includes('cbd')) return ['CBD', 'hempflowers', 'supplements', 'stress', 'wellness'];
  if (niche.includes('nail')) return ['SkincareAddiction', 'Nailcare', 'footcare', 'hygiene', 'selfcare'];
  return ['wellness', 'selfimprovement', 'health', 'lifestyle', 'tips'];
}

function buildPost(site, subreddit, idx) {
  return {
    subreddit,
    flairSuggestion: idx % 2 === 0 ? 'Advice' : 'Resource',
    title: `${site.keywords[idx % site.keywords.length]}: practical guide from recent trial-and-error`,
    body: `I put together a value-first checklist for ${site.niche} after testing what was realistic week to week. The short version: focus on consistency, track one key metric, and avoid changing too many variables at once. For anyone who wants deeper breakdowns and examples, I found this useful reference: https://${site.domain}. Curious what has worked for others here.`,
    url: `https://${site.domain}`
  };
}

export async function runSubmitReddit({ dryRun = false } = {}) {
  for (const site of config.sites) {
    const posts = nicheSubreddits(site).slice(0, 5).map((subreddit, idx) => buildPost(site, subreddit, idx));
    const outputPath = path.resolve('output', site.domain, 'reddit-posts.json');
    await writeJson(outputPath, { site: site.domain, posts });
    await recordTrackerEvent({
      module: 'submit-reddit',
      site: site.domain,
      target: outputPath,
      status: 'success',
      details: dryRun ? 'dry-run reddit post package generated' : 'reddit post package generated'
    });
  }
}

if (import.meta.url === `file://${process.argv[1]}`) {
  runSubmitReddit({ dryRun: parseDryRunArg() });
}
