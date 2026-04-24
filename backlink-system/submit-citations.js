import 'dotenv/config';
import path from 'node:path';
import config from './config.json' with { type: 'json' };
import { parseDryRunArg, writeCsv, writeJson } from './lib/utils.js';
import { recordTrackerEvent } from './tracker.js';

const directories = ['Yelp', 'Yellow Pages', 'Manta', 'MerchantCircle', 'Foursquare', 'Hotfrog', 'Cylex', 'n49', 'Brownbook', 'Tupalo', '2findlocal', 'eLocal', 'Opendi'];

export async function runSubmitCitations({ dryRun = false } = {}) {
  const rows = [];

  for (const site of config.sites) {
    const perSite = directories.map((directory) => ({
      directory,
      businessName: `${site.ownerName} ${site.niche}`,
      website: `https://${site.domain}`,
      address: site.localAddress,
      phone: site.phoneNumber,
      foundedYear: site.foundedYear,
      ownerName: site.ownerName,
      category: site.niche
    }));

    rows.push(...perSite);

    const outputPath = path.resolve('output', site.domain, 'citations.json');
    await writeJson(outputPath, { dryRun, site: site.domain, entries: perSite });
    await recordTrackerEvent({ module: 'submit-citations', site: site.domain, target: outputPath, status: 'success', details: 'citation package generated' });
  }

  const masterPath = path.resolve('citations-master.csv');
  await writeCsv(masterPath, rows);
  await recordTrackerEvent({ module: 'submit-citations', site: 'all', target: masterPath, status: 'success', details: `${rows.length} citation rows exported` });
}

if (import.meta.url === `file://${process.argv[1]}`) {
  runSubmitCitations({ dryRun: parseDryRunArg() });
}
