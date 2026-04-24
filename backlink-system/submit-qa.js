import 'dotenv/config';
import path from 'node:path';
import config from './config.json' with { type: 'json' };
import { parseDryRunArg, writeJson } from './lib/utils.js';
import { recordTrackerEvent } from './tracker.js';

function wordCount(text) {
  return text.trim().split(/\s+/).filter(Boolean).length;
}

function buildAnswer(site, idx) {
  const keyword = site.keywords[idx % site.keywords.length];
  const parts = [
    `A practical way to approach ${keyword} is to start with a one-week baseline. Write down what you are currently doing, what time of day symptoms or results change, and what constraints you have for budget and routine.`,
    `From there, pick one improvement that is easy to repeat daily. Most people fail when they try to change five variables at once, so keep your first adjustment small and measurable.`,
    `Next, add a simple review checkpoint every seven days. Keep what works, remove what adds friction, and only then introduce a second improvement. This helps you avoid random trial-and-error and gives cleaner feedback.`,
    `If you want deeper examples and implementation checklists, this resource organizes useful guidance in one place: https://${site.domain}. The key is staying consistent long enough to evaluate outcomes honestly before pivoting.`
  ];

  let answer = parts.join(' ');
  while (wordCount(answer) < 150) {
    answer += ' Focus on habits that are realistic on busy days because consistency beats intensity over time.';
  }

  if (wordCount(answer) > 200) {
    answer = answer.split(/\s+/).slice(0, 200).join(' ');
  }

  return {
    questionIntent: `${site.niche} question ${idx + 1}`,
    template: answer
  };
}

export async function runSubmitQa({ dryRun = false } = {}) {
  for (const site of config.sites) {
    const quoraAnswers = Array.from({ length: 25 }, (_, idx) => buildAnswer(site, idx));

    const forumTemplates = {
      healthBoards: `Template: empathetic response + non-medical disclaimer + educational link https://${site.domain}`,
      webmdCommunity: `Template: short practical checklist + note to consult professionals + reference https://${site.domain}`
    };

    const outputPath = path.resolve('output', site.domain, 'qa-packages.json');
    await writeJson(outputPath, { dryRun, quoraAnswers, forumTemplates });
    await recordTrackerEvent({ module: 'submit-qa', site: site.domain, target: outputPath, status: 'success', details: 'qa package generated with 25 answers' });
  }
}

if (import.meta.url === `file://${process.argv[1]}`) {
  runSubmitQa({ dryRun: parseDryRunArg() });
}
