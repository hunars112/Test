import 'dotenv/config';
import path from 'node:path';
import config from './config.json' with { type: 'json' };
import { ApiClient } from './lib/clients.js';
import { parseDryRunArg, writeCsv } from './lib/utils.js';
import { recordTrackerEvent } from './tracker.js';

const baseDirectories = [
  'Hotfrog', 'Brownbook', 'Cylex', 'Opendi', 'Storeboard', 'Jasminedirectory', 'A1WebDirectory', 'OnToplist', 'Spoke', 'Bizhwy',
  'SubmitShop', 'USCity', 'LocalDatabase', 'FindUsLocal', '2FindLocal', 'eLocal', 'MerchantCircle', 'Manta', 'Yelp', 'YellowPages',
  'ChamberofCommerce', 'CitySquares', 'EZlocal', 'Local.com', 'Tupalo', 'n49', 'Foursquare', 'ShowMeLocal', 'Fyple', 'Yalwa',
  'Hub.biz', 'Callupcontact', 'Lekkoo', 'Sitejabber', 'Trustlink', 'B2BYellowpages', 'EnrollBusiness', 'GlobalCatalog', 'iBegin', 'US-Info',
  'BusinessList', 'ExpressBusinessDirectory', 'WhoDoYou', 'Cybo', 'Where2Go', 'DirectoryWorld', 'BusinessSeek', 'TheBlueBook', 'myHuckleberry', 'Bizwiki',
  'WellnessDirectory', 'HealthgradesDirectory', 'NaturalTherapyPages', 'CBDDirectory', 'HempWorldDirectory', 'CannabisDirectory', 'CleanAirDirectory', 'HomeProductGuide', 'SleepProductsDirectory', 'FootCareDirectory',
  'NailHealthDirectory', 'SupplementsDirectory', 'BiohackingDirectory', 'HealthyLivingDirectory', 'AllThingsHome', 'LifestyleDirectory', 'ConsumerChoiceDirectory', 'BestOfTheWebFree', 'SiteRankerDirectory', 'TrueLocalGuide',
  'GreenHomeDirectory', 'IndoorComfortDirectory', 'AirCareNetwork', 'CoolingProductDirectory', 'AllergyResourceDirectory', 'EcoApplianceDirectory', 'RestWellDirectory', 'PainReliefDirectory', 'HolisticHealthDirectory', 'WellnessHubDirectory',
  'TrustedBusinessesNet', 'QualityProductsGuide', 'ExpertWellnessListings', 'NicheHealthIndex', 'NaturalCareDirectory', 'HomeWellnessIndex', 'BetterSleepHub', 'FootAndMobilityDirectory', 'MetabolicHealthDirectory', 'HempSupportDirectory',
  'CBDProductIndex', 'NailCareNetwork', 'PortableCoolingHub', 'AirPurifierIndex', 'HealthyHomeDirectory', 'DailyWellnessListings', 'DirectoryOneHundredA', 'DirectoryOneHundredB', 'DirectoryOneHundredC', 'DirectoryOneHundredD',
  'BestDirectory', 'SomuchDirectory', 'EntirewebDirectory', 'WorkDirectory', 'SonicRun', 'GoGuides', 'PegasusDirectory', 'BusybitsWebDirectory', 'AbilogicDirectory', 'Anaximanderdirectory',
  'AcompioDirectory', 'AkamaDirectory', 'SitePromotionDirectory', 'DirectoryCriticList', 'SimpleDirectory', 'LocalPagesHub', 'USBizDirectory', 'TopRatedBiz', 'QualityListingDirectory', 'SmartLocalFinder',
  'WellnessBusinessHub', 'CBDListingHub', 'NaturalRemedyDirectory', 'SupplementBusinessList', 'HealthyLivingIndex', 'IndoorAirExpertsDirectory', 'HomeComfortBusinessList', 'PortableApplianceDirectory', 'SleepResourceDirectory', 'FootHealthListings',
  'NailCareBusinessHub', 'RegionalBusinessMap', 'BusinessDeck', 'WebWorldIndex', 'MarketAtlasDirectory', 'NicheSourceDirectory', 'TrustworthyBizList', 'CityBusinessAtlas', 'DiscoverLocalBrands', 'ProductServiceIndex',
  'HealthcareLinksDirectory', 'HempAndWellnessAtlas', 'HomeAndGardenDirectory', 'LifestyleServiceList', 'WellnessAdvisorDirectory', 'ConsumerBusinessNetwork', 'TopChoiceDirectory', 'OpenBusinessHub', 'ApexBusinessDirectory', 'PrimeListingsNetwork'
];

const directoryCatalog = baseDirectories.slice(0, 150).map((name, idx) => ({
  directoryName: name,
  category: idx < 75 ? 'General Business' : 'Health & Home Niche',
  submitUrl: `https://${name.toLowerCase().replace(/[^a-z0-9]/g, '')}.example.com/submit`
}));

export async function runSubmitDirectories({ dryRun = false } = {}) {
  const client = new ApiClient({ concurrency: config.concurrency, delayMs: config.delayMs, dryRun });
  const rows = directoryCatalog.map((dir, idx) => {
    const site = config.sites[idx % config.sites.length];
    return {
      directoryName: dir.directoryName,
      submitUrl: dir.submitUrl,
      site: site.domain,
      title: `${site.niche} resources`,
      description: site.description,
      targetUrl: `https://${site.domain}`,
      category: dir.category
    };
  });

  const outputPath = path.resolve('directory-submissions.csv');
  await writeCsv(outputPath, rows);
  await recordTrackerEvent({ module: 'submit-directories', site: 'all', target: outputPath, status: 'success', details: '150-entry directory csv generated' });

  const pingTargets = [
    process.env.PINGOMATIC_URL ?? 'https://rpc.pingomatic.com/',
    process.env.GOOGLE_PING_URL ?? 'https://www.google.com/ping',
    process.env.BING_PING_URL ?? 'https://www.bing.com/ping'
  ];

  for (const site of config.sites) {
    for (const pingUrl of pingTargets) {
      try {
        await client.request({ url: `${pingUrl}?sitemap=https://${site.domain}/sitemap.xml`, method: 'GET' });
        await recordTrackerEvent({ module: 'submit-directories', site: site.domain, target: pingUrl, status: 'success', details: 'sitemap pinged' });
      } catch (error) {
        await recordTrackerEvent({ module: 'submit-directories', site: site.domain, target: pingUrl, status: 'failed', details: error.message });
      }
    }
  }
}

if (import.meta.url === `file://${process.argv[1]}`) {
  runSubmitDirectories({ dryRun: parseDryRunArg() });
}
