#!/usr/bin/env node
import 'dotenv/config';
import inquirer from 'inquirer';
import chalk from 'chalk';
import ora from 'ora';
import { parseDryRunArg } from './lib/utils.js';
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

const moduleMap = {
  'generate-content': runGenerateContent,
  'submit-web2': runSubmitWeb2,
  'submit-social': runSubmitSocial,
  'submit-directories': runSubmitDirectories,
  'submit-press': runSubmitPress,
  'submit-documents': runSubmitDocuments,
  'submit-profiles': runSubmitProfiles,
  'submit-qa': runSubmitQa,
  'submit-image-sharing': runSubmitImageSharing,
  'submit-video': runSubmitVideo,
  'submit-rss': runSubmitRss,
  'submit-comments': runSubmitComments,
  'submit-citations': runSubmitCitations,
  'submit-wikis': runSubmitWikis,
  'submit-podcast': runSubmitPodcast,
  'submit-tiered': runSubmitTiered,
  'submit-github-gist': runSubmitGithubGist,
  'submit-pastebin': runSubmitPastebin,
  'submit-linkedin': runSubmitLinkedin,
  'submit-pinterest': runSubmitPinterest,
  'submit-twitter': runSubmitTwitter,
  'submit-reddit': runSubmitReddit,
  'submit-tumblr': runSubmitTumblr,
  'submit-mix': runSubmitMix,
  'submit-medium': runSubmitMedium,
  'submit-blogger-outreach': runSubmitBloggerOutreach,
  'submit-web2-extended': runSubmitWeb2Extended,
  tracker: async () => exportTrackerCsv()
};

async function resolveModules(argv) {
  const explicit = argv.find((arg) => arg.startsWith('--modules='));
  if (explicit) {
    const value = explicit.split('=')[1] ?? '';
    return value.split(',').map((v) => v.trim()).filter(Boolean);
  }

  const { selected } = await inquirer.prompt([
    {
      type: 'checkbox',
      name: 'selected',
      message: 'Choose modules to run',
      choices: [...Object.keys(moduleMap), 'all'],
      validate: (arr) => (arr.length > 0 ? true : 'Pick at least one module')
    }
  ]);
  return selected.includes('all') ? Object.keys(moduleMap) : selected;
}

async function main() {
  const argv = process.argv.slice(2);
  const dryRun = parseDryRunArg(process.argv);
  const offline = process.argv.includes('--offline');
  const selectedModules = await resolveModules(argv);

  console.log(chalk.cyan(`Backlink automation | dry-run=${dryRun} | offline=${offline}`));
  for (const name of selectedModules) {
    const fn = moduleMap[name];
    if (!fn) {
      console.log(chalk.yellow(`Skipping unknown module: ${name}`));
      continue;
    }

    const spinner = ora(`Running ${name}`).start();
    try {
      await fn({ dryRun, offline });
      spinner.succeed(`${name} complete`);
    } catch (error) {
      spinner.fail(`${name} failed: ${error.message}`);
      process.exitCode = 1;
    }
  }
}

main();
