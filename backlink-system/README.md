# Backlink System (Node.js ES Modules)

A modular Node.js automation toolkit for generating content assets, building submission packages, and tracking outcomes across 8 target sites.

## What this project does

- Generates site-specific content bundles into `output/{domain}/content.json`
- Prepares Web2 / social / directory / press / document / profile / Q&A assets
- Uses `p-limit` (max concurrency from config) and 2-second API pacing
- Supports `--dry-run` mode for safe testing without real API side effects
- Supports `--offline`/`run-offline.js` so the system works without API keys
- Tracks every action in `tracker.json` and `backlinks-tracker.csv`

## Modules

- `generate-content.js`
- `submit-web2.js`
- `submit-social.js`
- `submit-directories.js`
- `submit-press.js`
- `submit-documents.js`
- `submit-profiles.js`
- `submit-qa.js`
- `submit-image-sharing.js`
- `submit-video.js`
- `submit-rss.js`
- `submit-comments.js`
- `submit-citations.js`
- `submit-wikis.js`
- `submit-podcast.js`
- `submit-tiered.js`
- `tracker.js`
- `run.js` (interactive / non-interactive orchestrator)
- `run-offline.js` (full offline pipeline with built-in templates)

## Setup

```bash
cd backlink-system
npm install
cp .env.example .env
```

Populate `.env` with your API keys.

## Usage

### Interactive

```bash
npm start
```

### Run selected modules (non-interactive)

```bash
node run.js --dry-run --modules=generate-content,submit-documents,tracker
```

### Full offline run (zero API keys)

```bash
node run-offline.js
```

This generates all content and submission artifacts using built-in templates, pings search services, and writes:
- `SUBMISSION-GUIDE.md`
- `BACKLINK-COUNT.md`

### Run single modules

```bash
node generate-content.js --dry-run
node generate-content.js --offline
node submit-web2.js --dry-run
node submit-social.js --dry-run
node submit-directories.js --dry-run
node submit-press.js --dry-run
node submit-documents.js --dry-run
node submit-profiles.js --dry-run
node submit-qa.js --dry-run
node submit-image-sharing.js --dry-run
node submit-video.js --dry-run
node submit-rss.js --dry-run
node submit-comments.js --dry-run
node submit-citations.js --dry-run
node submit-wikis.js --dry-run
node submit-podcast.js --dry-run
node submit-tiered.js --dry-run
```

## Output

- `output/{domain}/content.json`
- `output/{domain}/press-releases/*.html`
- `output/{domain}/documents/*.pdf`
- `output/{domain}/social-submission-packages.json`
- `output/{domain}/profile-packages.json`
- `output/{domain}/qa-packages.json`
- `directory-submissions.csv`
- `citations-master.csv`
- `tracker.json`
- `backlinks-tracker.csv`

## Testing

```bash
npm test
```
