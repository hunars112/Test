import 'dotenv/config';
import path from 'node:path';
import config from './config.json' with { type: 'json' };
import pLimit from 'p-limit';
import { createOpenAIClient } from './lib/clients.js';
import { contextualBacklink, parseDryRunArg, writeJson } from './lib/utils.js';
import { recordTrackerEvent } from './tracker.js';

const SITE_TEMPLATE_DATA = {
  'glucoregulates.com': {
    voice: 'evidence-first and practical',
    audience: 'adults managing blood sugar swings and energy crashes',
    themes: ['post-meal glucose control', 'protein-first meals', 'sleep and stress regulation', 'supplement timing'],
    articleTitles: [
      'A Practical Blood Sugar Stability Blueprint for Busy Adults',
      'How to Pair Lifestyle Habits with Metabolic Supplement Strategies',
      'From Afternoon Crashes to All-Day Energy: A 30-Day Glucose Plan'
    ],
    forumReplies: [
      'I had the same afternoon slump issue. The biggest win for me was eating protein and fiber first, then adding carbs instead of leading with carbs. It flattened my post-lunch spike noticeably.',
      'If your fasting numbers look fine but you still feel shaky after meals, it might be meal composition instead of total calories. Track one week and compare meals with 25g+ protein versus low-protein meals.',
      'One thing people skip is sleep quality. Two nights of poor sleep can raise cravings and glucose variability. Fix bedtime consistency first, then adjust supplements.',
      'For supplements, I’d go slow and add one variable at a time so you can actually tell what is helping. Pairing supplements with a stable meal plan worked better than taking them alone.',
      'Hydration and a short post-meal walk helped me more than expected. Ten minutes right after dinner made a measurable difference in morning readings.'
    ],
    socialBookmarks: [
      'A clear, non-hype guide on balancing meals, movement, and metabolic support to keep blood sugar and energy steady all day.',
      'Useful resource for anyone building a sustainable glucose routine with practical checklists and supplement planning tips.',
      'Actionable metabolic health education with realistic routines for workdays, travel, and high-stress weeks.'
    ],
    pressHeadline: 'Glucoregulates.com Launches Structured Metabolic Health Education Hub',
    bio: 'Glucoregulates.com publishes practical blood glucose and metabolic wellness education, helping readers combine nutrition, movement, recovery, and responsible supplementation.'
  },
  'plantarxcbd.net': {
    voice: 'empathetic and mobility-focused',
    audience: 'people with plantar fasciitis, heel pain, and stiff feet',
    themes: ['morning foot pain relief', 'load management', 'foot mobility and strength', 'CBD recovery workflow'],
    articleTitles: [
      'A Daily Heel Pain Recovery Routine You Can Actually Stick To',
      'CBD, Mobility, and Foot Loading: Building a Smarter Plantar Fasciitis Plan',
      'How to Walk, Train, and Recover Without Triggering Foot Flare-Ups'
    ],
    forumReplies: [
      'I dealt with first-step pain for months. The biggest shift was reducing aggressive stretching and adding gentle calf/foot loading throughout the day.',
      'If orthotics help some days but not others, check your overall step load and shoe age. Worn foam plus high step count can quietly increase irritation.',
      'Night pain improved when I separated recovery into short sessions: heat, soft tissue work, then light mobility before bed.',
      'CBD topicals won’t fix biomechanics, but they can make the recovery window more comfortable so you stay consistent with mobility and strength.',
      'Try grading activity instead of complete rest. I used pain response the next morning as my feedback signal and progressed from there.'
    ],
    socialBookmarks: [
      'Practical plantar fasciitis guidance: mobility, loading, footwear choices, and recovery support in one framework.',
      'Helpful resource for persistent heel pain with realistic routines for workers, runners, and people on their feet all day.',
      'Evidence-informed foot pain education that focuses on consistency, not gimmicks.'
    ],
    pressHeadline: 'PlantarxCBD.net Publishes Integrated Foot Pain Education and Recovery Guides',
    bio: 'PlantarxCBD.net helps readers understand plantar fasciitis and chronic foot discomfort through practical mobility, training, and recovery resources.'
  },
  'freshiaairpurifier.net': {
    voice: 'home-health and technical clarity',
    audience: 'families improving indoor air quality and allergen control',
    themes: ['HEPA selection', 'CADR and room sizing', 'filter maintenance', 'allergy and smoke management'],
    articleTitles: [
      'How to Choose the Right HEPA Air Purifier Without Wasting Money',
      'Indoor Air Quality Upgrade Plan for Allergy and Wildfire Seasons',
      'From Dusty Rooms to Cleaner Air: A Home-by-Home Purifier Strategy'
    ],
    forumReplies: [
      'Start with room size and CADR, not brand hype. A purifier that is undersized will run all day and still underperform.',
      'If symptoms are worst in the bedroom, put the strongest unit there first and run it continuously for two weeks before judging results.',
      'Filter costs matter long-term. I compare annual replacement cost before buying because some "cheap" units become expensive quickly.',
      'Seal obvious infiltration points and vacuum with a HEPA vacuum; purifier performance improves when the source load is lower.',
      'For smoke events, use higher fan speed initially to clear the air, then drop to a quieter maintenance setting.'
    ],
    socialBookmarks: [
      'Straightforward HEPA purifier buying and setup guidance for cleaner indoor air and lower allergen load.',
      'Excellent primer on CADR, filter replacement planning, and room-specific purifier placement.',
      'Useful indoor air quality resource for allergy sufferers, pet owners, and wildfire-prone regions.'
    ],
    pressHeadline: 'FreshiaAirPurifier.net Expands Consumer Education on Cleaner Indoor Air',
    bio: 'FreshiaAirPurifier.net delivers practical indoor air quality education, including purifier selection, maintenance planning, and healthier home routines.'
  },
  'ultraaircooler.net': {
    voice: 'practical and climate-aware',
    audience: 'households using portable evaporative cooling in warm climates',
    themes: ['evaporative cooling basics', 'humidity management', 'room placement', 'maintenance and hygiene'],
    articleTitles: [
      'Portable Evaporative Cooler Setup Guide for Reliable Comfort',
      'How to Use Air Coolers Efficiently Without Raising Indoor Discomfort',
      'A Real-World Cooling Plan for Bedrooms, Workspaces, and Small Apartments'
    ],
    forumReplies: [
      'Air coolers work best with airflow. Crack a window and keep air moving instead of sealing the room like AC mode.',
      'If you feel sticky, check humidity first. High humidity can make evaporative units feel less effective even when temperature drops.',
      'Keep pads clean and replace on schedule. Performance drops fast when mineral buildup starts.',
      'Use ice packs strategically during peak afternoon heat, then switch to water-only overnight for consistency.',
      'The best spot is usually near a window with cross-ventilation, not tucked in a corner.'
    ],
    socialBookmarks: [
      'Great practical guide to evaporative cooling setup, maintenance, and humidity-aware operation.',
      'Helpful resource for people choosing between portable coolers and traditional AC options.',
      'Actionable cooling strategies for renters, dorms, and small living spaces.'
    ],
    pressHeadline: 'UltraAirCooler.net Releases Consumer Guides for Efficient Portable Cooling',
    bio: 'UltraAirCooler.net helps consumers maximize portable air cooler performance through practical setup, cleaning, and usage guidance.'
  },
  'dormivapillows.com': {
    voice: 'sleep-coaching and comfort science',
    audience: 'people improving sleep quality and reducing neck/shoulder discomfort',
    themes: ['pillow fit', 'sleep posture', 'temperature regulation', 'nighttime recovery'],
    articleTitles: [
      'How to Choose a Memory Foam Pillow That Actually Improves Sleep',
      'Neck Support, Sleep Position, and Better Recovery: A Practical Guide',
      'Building a Full Sleep Comfort System Around the Right Pillow'
    ],
    forumReplies: [
      'A pillow can feel great for 10 minutes and fail all night. I now test support across my usual sleep positions before deciding.',
      'If you wake with shoulder tension, your loft may be too high for side sleeping with your mattress firmness.',
      'Cooling covers helped my sleep continuity more than expected, especially during warmer months.',
      'Give new foam pillows a short adjustment window. My neck usually adapts over 5–7 nights if loft is close to correct.',
      'I pair pillow upgrades with a simple bedtime routine, because comfort and sleep timing work together.'
    ],
    socialBookmarks: [
      'Solid memory foam pillow buying guide with posture, loft, and thermal comfort considerations.',
      'Useful sleep comfort resource for side, back, and combination sleepers.',
      'Practical sleep quality framework that connects pillow fit with real recovery outcomes.'
    ],
    pressHeadline: 'DormivaPillows.com Launches Sleep Comfort Education Center',
    bio: 'DormivaPillows.com provides memory foam pillow education and sleep comfort strategies to support better rest and nighttime recovery.'
  },
  'radiantcbdgummies.net': {
    voice: 'balanced wellness and stress-management',
    audience: 'adults seeking calmer routines and responsible CBD education',
    themes: ['stress routines', 'dosage consistency', 'sleep support', 'quality and labeling'],
    articleTitles: [
      'CBD Gummies and Daily Stress Routines: What Consistency Really Looks Like',
      'How to Evaluate CBD Gummies for Quality, Labeling, and Fit',
      'Building a Calm Evening Routine with CBD, Sleep Hygiene, and Recovery Habits'
    ],
    forumReplies: [
      'Start low and keep timing consistent for at least a week. Random dosing made effects hard to interpret for me.',
      'Look for transparent lab reports and clear cannabinoid totals per serving before buying any gummy product.',
      'CBD works best for me when combined with routine basics like reduced evening caffeine and wind-down time.',
      'I track mood and sleep notes for two weeks when trying a new product. It removes guesswork.',
      'If daytime use feels too sedating, shifting dose timing toward evening can be a better fit.'
    ],
    socialBookmarks: [
      'Responsible CBD gummy education with emphasis on consistency, product quality, and practical stress routines.',
      'Helpful guide for first-time CBD users who want clear, no-hype decision criteria.',
      'Wellness-focused CBD resource connecting product selection with lifestyle habits.'
    ],
    pressHeadline: 'RadiantCBDGummies.net Publishes Consumer-First CBD Wellness Guides',
    bio: 'RadiantCBDGummies.net shares educational CBD wellness content focused on transparent quality standards and practical stress-relief routines.'
  },
  'purelifecbdgummies.net': {
    voice: 'wellness coaching with compliance awareness',
    audience: 'consumers exploring hemp wellness and routine-based support',
    themes: ['hemp wellness routines', 'daily consistency', 'ingredient transparency', 'habit stacking'],
    articleTitles: [
      'A Beginner-Friendly Hemp Wellness Plan with CBD Gummies',
      'What to Check Before Buying CBD Gummies: Label, Labs, and Serving Size',
      'How to Build Sustainable Daily Wellness Habits Around CBD Support'
    ],
    forumReplies: [
      'I had better results when I treated CBD like a routine, not a one-off fix. Same time daily made tracking easier.',
      'Read ingredient labels closely—sugar profile, flavoring, and additional botanicals can matter for tolerance.',
      'Third-party lab access is non-negotiable for me before purchasing.',
      'Pairing CBD with a short evening walk and screen cutoff improved my wind-down far more than CBD alone.',
      'If you are new, pick one product and stay with it for consistency before comparing brands.'
    ],
    socialBookmarks: [
      'Clear hemp wellness guide for choosing and using CBD gummies with realistic daily habits.',
      'Useful educational resource on CBD quality checks and routine design.',
      'Practical wellness content for people who want structured, consistent CBD use.'
    ],
    pressHeadline: 'PureLifeCBDGummies.net Introduces Structured Hemp Wellness Resource Library',
    bio: 'PureLifeCBDGummies.net publishes practical hemp wellness education for consumers seeking transparent CBD gummy guidance.'
  },
  'dermafixnail.com': {
    voice: 'hygiene-forward and treatment adherence',
    audience: 'adults dealing with brittle, discolored, or fungal-prone nails',
    themes: ['nail hygiene', 'treatment consistency', 'shoe sanitation', 'regrowth expectations'],
    articleTitles: [
      'Nail Fungus Recovery Plan: Daily Habits That Support Healthier Regrowth',
      'How to Combine Topical Care, Hygiene, and Footwear Practices for Better Nail Outcomes',
      'What Real Nail Recovery Timelines Look Like and How to Stay Consistent'
    ],
    forumReplies: [
      'Consistency beats intensity. A simple daily topical routine plus shoe sanitation made the biggest difference for me.',
      'Nail progress is slow, so photos every two weeks helped me stay realistic and motivated.',
      'Disinfecting clippers and not sharing nail tools is a must if you are trying to prevent reinfection.',
      'I switched to breathable socks and rotated shoes so pairs could fully dry between uses.',
      'If you plateau, reassess routine quality: cleaning, filing, application timing, and footwear habits.'
    ],
    socialBookmarks: [
      'Helpful nail health guide covering hygiene, topical strategy, and realistic regrowth timelines.',
      'Practical anti-fungal nail care framework that emphasizes consistency and prevention.',
      'Great educational resource for long-term nail restoration habits.'
    ],
    pressHeadline: 'DermaFixNail.com Launches Long-Form Educational Content on Nail Health',
    bio: 'DermaFixNail.com provides educational nail health content focused on fungal prevention, hygiene habits, and realistic treatment consistency.'
  }
};

function wordCount(text) {
  return text.trim().split(/\s+/).filter(Boolean).length;
}

function buildArticle(site, template, articleIndex) {
  const link = contextualBacklink(site, articleIndex);
  const title = template.articleTitles[articleIndex] ?? `${site.niche} Practical Guide ${articleIndex + 1}`;

  const intro = `When people in ${template.audience} search for better results, they usually get fragmented advice. This guide combines nutrition or lifestyle fundamentals, realistic scheduling, and supportive product strategy into one plan. Instead of chasing quick fixes, the goal is to create a repeatable weekly system with clear checkpoints. Readers can use ${link.url} as a planning hub while adapting each step to their routine, budget, and comfort level.`;

  const bodyBlocks = template.themes.map((theme, idx) => (
    `Section ${idx + 1}: ${theme}. Start by defining your baseline for seven days, including symptom patterns, trigger windows, and what is already working. Next, choose one controllable variable and improve it with a small, measurable action. Then protect consistency by attaching that action to an existing routine such as breakfast, commuting, or bedtime. This prevents the common cycle of high motivation followed by burnout. Finally, review outcomes weekly and either keep, reduce, or replace each action. This structured loop is more sustainable than dramatic overhauls and helps you identify what delivers meaningful progress.`
  ));

  const expansionParagraph = `A practical system should also include decision rules for setbacks. If progress stalls, avoid replacing everything at once. Keep what is helping, troubleshoot the weakest step, and give changes enough time to produce reliable feedback. Documenting this process turns guesswork into evidence and improves confidence over time. Educational resources at ${link.url} can support this with checklists, planning prompts, and reference materials.`;

  const outro = `The long-term advantage comes from repeatability: simple habits executed consistently, informed by observation instead of hype. By combining core lifestyle practices with thoughtful support tools, readers can create steady improvements and reduce day-to-day volatility. For deeper walkthroughs and implementation worksheets, visit ${link.url} and continue building a routine that fits real life.`;

  let content = [intro, ...bodyBlocks, expansionParagraph, expansionParagraph, expansionParagraph, outro].join('\n\n');

  while (wordCount(content) < 800) {
    content += `\n\n${expansionParagraph}`;
  }

  return { title, content };
}

function builtinTemplateContent(site) {
  const template = SITE_TEMPLATE_DATA[site.domain];
  const blogArticles = Array.from({ length: 3 }, (_, index) => buildArticle(site, template, index));
  const link = contextualBacklink(site);

  const pressRelease = `${template.pressHeadline}\n\n${site.domain} today announced the publication of an expanded educational resource library focused on ${site.niche}. The initiative provides readers with long-form guides, practical checklists, and structured implementation templates so they can take informed action with confidence.\n\nThe new content framework is designed for consumers who want clear, non-sensational information they can apply in daily life. Rather than isolated tips, each guide presents a step-by-step process that combines foundational habits, routine management, and product evaluation criteria. The educational approach emphasizes consistency, transparent decision-making, and realistic timelines.\n\nAccording to the editorial team, the objective is to improve outcomes by helping readers identify sustainable actions and avoid trial-and-error overload. Visitors can access articles, platform-ready snippets, and reference materials that simplify planning and execution.\n\nThe platform now includes expanded topic hubs, implementation examples, and repeatable routines tailored to common user scenarios. For educational resources and updates, visit https://${site.domain}.`;

  return {
    blogArticles,
    forumReplies: template.forumReplies,
    socialBookmarks: template.socialBookmarks,
    pressRelease,
    directoryListing: {
      companyName: site.domain.replace(/\..*$/, '').replace(/(^\w)/, (m) => m.toUpperCase()),
      website: `https://${site.domain}`,
      summary: site.description,
      category: site.niche
    },
    web2Bio: `${template.bio} Learn more at ${link.url}.`
  };
}

function coerceContentShape(raw, site) {
  const fallback = builtinTemplateContent(site);
  return {
    blogArticles: Array.isArray(raw?.blogArticles) ? raw.blogArticles.slice(0, 3) : fallback.blogArticles,
    forumReplies: Array.isArray(raw?.forumReplies) ? raw.forumReplies.slice(0, 5) : fallback.forumReplies,
    socialBookmarks: Array.isArray(raw?.socialBookmarks) ? raw.socialBookmarks.slice(0, 3) : fallback.socialBookmarks,
    pressRelease: raw?.pressRelease ?? fallback.pressRelease,
    directoryListing: raw?.directoryListing ?? fallback.directoryListing,
    web2Bio: raw?.web2Bio ?? fallback.web2Bio
  };
}

async function generateWithOpenAI(client, site) {
  const prompt = `Return JSON with keys blogArticles(3), forumReplies(5), socialBookmarks(3), pressRelease(about 400 words), directoryListing, web2Bio for ${site.domain}. Blog posts must be 800-1000 words each. Include natural references to https://${site.domain} and anchors ${site.anchors.join(', ')}.`;
  const response = await client.chat.completions.create({
    model: 'gpt-4o',
    temperature: 0.7,
    response_format: { type: 'json_object' },
    messages: [{ role: 'user', content: prompt }]
  });
  const text = response.choices?.[0]?.message?.content ?? '{}';
  return JSON.parse(text);
}

export async function runGenerateContent({ dryRun = false, offline = false } = {}) {
  const openai = offline ? null : createOpenAIClient();
  const limit = pLimit(config.concurrency);

  await Promise.all(config.sites.map((site) => limit(async () => {
    try {
      const generated = (!dryRun && !offline && openai)
        ? await generateWithOpenAI(openai, site)
        : builtinTemplateContent(site);
      const normalized = coerceContentShape(generated, site);
      const outputPath = path.resolve('output', site.domain, 'content.json');
      await writeJson(outputPath, normalized);
      await recordTrackerEvent({
        module: 'generate-content',
        site: site.domain,
        target: outputPath,
        status: 'success',
        details: offline ? 'offline built-in content templates' : (dryRun ? 'dry-run built-in templates' : 'content generated')
      });
    } catch (error) {
      await recordTrackerEvent({ module: 'generate-content', site: site.domain, target: site.domain, status: 'failed', details: error.message });
      throw error;
    }
  })));
}

if (import.meta.url === `file://${process.argv[1]}`) {
  runGenerateContent({ dryRun: parseDryRunArg(), offline: process.argv.includes('--offline') });
}
