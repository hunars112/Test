import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import { runGenerateContent } from '../generate-content.js';
import { runSubmitDocuments } from '../submit-documents.js';
import { runSubmitPress } from '../submit-press.js';
import { runSubmitDirectories } from '../submit-directories.js';
import { runSubmitImageSharing } from '../submit-image-sharing.js';
import { runSubmitCitations } from '../submit-citations.js';
import { runSubmitSocial } from '../submit-social.js';
import { runSubmitQa } from '../submit-qa.js';
import { runSubmitGithubGist } from '../submit-github-gist.js';
import { runSubmitPastebin } from '../submit-pastebin.js';
import { runSubmitLinkedin } from '../submit-linkedin.js';
import { runSubmitPinterest } from '../submit-pinterest.js';
import { runSubmitTwitter } from '../submit-twitter.js';
import { runSubmitReddit } from '../submit-reddit.js';
import { runSubmitTumblr } from '../submit-tumblr.js';
import { runSubmitMix } from '../submit-mix.js';
import { runSubmitMedium } from '../submit-medium.js';
import { runSubmitBloggerOutreach } from '../submit-blogger-outreach.js';
import { runSubmitWeb2Extended } from '../submit-web2-extended.js';

const base = path.resolve(process.cwd());

const countWords = (text) => text.trim().split(/\s+/).filter(Boolean).length;

test('generate-content offline mode creates long-form content json', async () => {
  await runGenerateContent({ offline: true });
  const raw = await fs.readFile(path.resolve(base, 'output/glucoregulates.com/content.json'), 'utf-8');
  const parsed = JSON.parse(raw);
  assert.equal(parsed.blogArticles.length, 3);
  assert.equal(parsed.forumReplies.length, 5);
  assert.ok(countWords(parsed.blogArticles[0].content) >= 800);
});

test('submit-documents generates PDFs', async () => {
  await runSubmitDocuments({ dryRun: true });
  const stat = await fs.stat(path.resolve(base, 'output/glucoregulates.com/documents/slideshare-package.pdf'));
  assert.ok(stat.size > 0);
});

test('submit-directories writes 150 entries', async () => {
  await runSubmitDirectories({ dryRun: true });
  const csv = await fs.readFile(path.resolve(base, 'directory-submissions.csv'), 'utf-8');
  const lines = csv.trim().split('\n');
  assert.equal(lines.length, 151);
});

test('submit-social creates reddit ready package', async () => {
  await runSubmitSocial({ dryRun: true, offline: true });
  const raw = await fs.readFile(path.resolve(base, 'output/glucoregulates.com/reddit-ready.json'), 'utf-8');
  const parsed = JSON.parse(raw);
  assert.equal(parsed.posts.length, 5);
});

test('submit-image-sharing creates 3 packages', async () => {
  await runSubmitImageSharing({ dryRun: true });
  const raw = await fs.readFile(path.resolve(base, 'output/glucoregulates.com/image-sharing-packages.json'), 'utf-8');
  const parsed = JSON.parse(raw);
  assert.equal(parsed.packages.length, 3);
});

test('submit-citations exports master csv', async () => {
  await runSubmitCitations({ dryRun: true });
  const csv = await fs.readFile(path.resolve(base, 'citations-master.csv'), 'utf-8');
  const lines = csv.trim().split('\n');
  assert.ok(lines.length > 10);
});


test('submit-github-gist creates 2 gist links per site in dry-run mode', async () => {
  await runSubmitGithubGist({ dryRun: true });
  const raw = await fs.readFile(path.resolve(base, 'output/glucoregulates.com/gist-links.json'), 'utf-8');
  const parsed = JSON.parse(raw);
  assert.equal(parsed.links.length, 2);
});

test('submit-pastebin creates 2 paste links per site in dry-run mode', async () => {
  await runSubmitPastebin({ dryRun: true });
  const raw = await fs.readFile(path.resolve(base, 'output/glucoregulates.com/pastebin-links.json'), 'utf-8');
  const parsed = JSON.parse(raw);
  assert.equal(parsed.links.length, 2);
});

test('submit-linkedin creates profile and 3 post drafts', async () => {
  await runSubmitLinkedin({ dryRun: true });
  const raw = await fs.readFile(path.resolve(base, 'output/glucoregulates.com/linkedin-packages.json'), 'utf-8');
  const parsed = JSON.parse(raw);
  assert.equal(parsed.articleDrafts.length, 3);
  assert.ok(parsed.companyPageDescription.includes('glucoregulates.com'));
});

test('submit-pinterest creates 5 pin packages', async () => {
  await runSubmitPinterest({ dryRun: true });
  const raw = await fs.readFile(path.resolve(base, 'output/glucoregulates.com/pinterest-packages.json'), 'utf-8');
  const parsed = JSON.parse(raw);
  assert.equal(parsed.pins.length, 5);
});


test('submit-qa generates 25 answers per site and target length', async () => {
  await runSubmitQa({ dryRun: true });
  const raw = await fs.readFile(path.resolve(base, 'output/glucoregulates.com/qa-packages.json'), 'utf-8');
  const parsed = JSON.parse(raw);
  assert.equal(parsed.quoraAnswers.length, 25);
  const words = countWords(parsed.quoraAnswers[0].template);
  assert.ok(words >= 150 && words <= 200);
});

test('submit-twitter creates 10 tweets and 3 thread outlines', async () => {
  await runSubmitTwitter({ dryRun: true });
  const raw = await fs.readFile(path.resolve(base, 'output/glucoregulates.com/twitter-packages.json'), 'utf-8');
  const parsed = JSON.parse(raw);
  assert.equal(parsed.tweetTemplates.length, 10);
  assert.equal(parsed.threadOutlines.length, 3);
  assert.equal(parsed.threadOutlines[0].tweets.length, 5);
});

test('submit-reddit creates 5 standalone reddit posts', async () => {
  await runSubmitReddit({ dryRun: true });
  const raw = await fs.readFile(path.resolve(base, 'output/glucoregulates.com/reddit-posts.json'), 'utf-8');
  const parsed = JSON.parse(raw);
  assert.equal(parsed.posts.length, 5);
  assert.ok(parsed.posts[0].flairSuggestion.length > 0);
});

test('submit-tumblr creates 5 post templates', async () => {
  await runSubmitTumblr({ dryRun: true });
  const raw = await fs.readFile(path.resolve(base, 'output/glucoregulates.com/tumblr-packages.json'), 'utf-8');
  const parsed = JSON.parse(raw);
  assert.equal(parsed.posts.length, 5);
});

test('submit-mix creates 10 submission packages', async () => {
  await runSubmitMix({ dryRun: true });
  const raw = await fs.readFile(path.resolve(base, 'output/glucoregulates.com/mix-packages.json'), 'utf-8');
  const parsed = JSON.parse(raw);
  assert.equal(parsed.submissions.length, 10);
});


test('submit-press generates expanded press packages', async () => {
  await runSubmitPress({ dryRun: true });
  const raw = await fs.readFile(path.resolve(base, 'output/glucoregulates.com/press-packages/press-packages.json'), 'utf-8');
  const parsed = JSON.parse(raw);
  assert.equal(parsed.packages.length, 13);
});

test('submit-medium generates 3 markdown articles per site', async () => {
  await runSubmitMedium({ dryRun: true });
  const article = await fs.readFile(path.resolve(base, 'output/glucoregulates.com/medium-articles/medium-article-1.md'), 'utf-8');
  assert.ok(countWords(article) >= 800);
});

test('submit-blogger-outreach generates 10 outreach templates', async () => {
  await runSubmitBloggerOutreach({ dryRun: true });
  const raw = await fs.readFile(path.resolve(base, 'output/glucoregulates.com/blogger-outreach.json'), 'utf-8');
  const parsed = JSON.parse(raw);
  assert.equal(parsed.templates.length, 10);
});

test('submit-web2-extended generates 10 platform packages', async () => {
  await runSubmitWeb2Extended({ dryRun: true });
  const raw = await fs.readFile(path.resolve(base, 'output/glucoregulates.com/web2-extended-packages.json'), 'utf-8');
  const parsed = JSON.parse(raw);
  assert.equal(parsed.packages.length, 10);
});
