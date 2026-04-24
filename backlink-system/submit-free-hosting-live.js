import { generateArticleContent } from './generate-content.js';
import { recordTrackerEvent } from './tracker.js';
import { createZipWithIndexHtml, loadConfig, postForm, randomSlug, writeDomainOutput } from './utils.js';

function wrapHtml(site, body) {
  return `<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>${site.title || site.domain}</title>
    <meta name="description" content="${(site.description || '').replace(/"/g, '&quot;')}" />
    <style>body{font-family:system-ui,-apple-system,sans-serif;max-width:860px;margin:40px auto;padding:0 20px;line-height:1.6;color:#1f2937;}a{color:#2563eb;}</style>
  </head>
  <body>
    ${body}
    <footer><p>Source: <a href="https://${site.domain}" rel="nofollow">${site.domain}</a></p></footer>
  </body>
</html>`;
}

async function deployTiiny(zipBuffer, slug, dryRun) {
  if (dryRun) {
    return { platform: 'tiiny.host', ok: true, liveUrl: `https://${slug}.tiiny.site`, dryRun: true };
  }

  try {
    const form = new FormData();
    form.append('file', new Blob([zipBuffer], { type: 'application/zip' }), 'site.zip');
    form.append('subdomain', slug);
    form.append('email', 'anonymous@temp.com');

    const response = await postForm('https://tiiny.host/api/upload', form);
    return {
      platform: 'tiiny.host',
      ok: response.ok,
      status: response.status,
      liveUrl: `https://${slug}.tiiny.site`,
      responseSnippet: response.text?.slice(0, 250),
    };
  } catch (error) {
    return { platform: 'tiiny.host', ok: false, error: error.message };
  }
}

async function deployNetlifyDrop(zipBuffer, dryRun) {
  if (dryRun) {
    return { platform: 'netlify-drop', ok: true, liveUrl: 'https://example-live-site.netlify.app', dryRun: true };
  }

  try {
    const response = await fetch('https://api.netlify.com/api/v1/sites', {
      method: 'POST',
      headers: {
        'content-type': 'application/zip',
      },
      body: zipBuffer,
    });
    const text = await response.text();
    let liveUrl = null;
    try {
      const parsed = JSON.parse(text);
      liveUrl = parsed?.ssl_url || parsed?.url || null;
    } catch {
      // no-op parse fallback
    }

    return {
      platform: 'netlify-drop',
      ok: response.ok,
      status: response.status,
      liveUrl,
      responseSnippet: text?.slice(0, 250),
    };
  } catch (error) {
    return { platform: 'netlify-drop', ok: false, error: error.message };
  }
}

export async function runSubmitFreeHosting({ dryRun = false } = {}) {
  const { sites } = await loadConfig();
  const selectedSites = sites.slice(0, 8);

  for (const site of selectedSites) {
    const articleHtml = wrapHtml(site, generateArticleContent({ site }));
    let zipBuffer;

    try {
      zipBuffer = await createZipWithIndexHtml(articleHtml);
    } catch (error) {
      const failed = {
        domain: site.domain,
        generatedAt: new Date().toISOString(),
        deployments: [{ platform: 'zip-build', ok: false, error: error.message }],
      };
      await writeDomainOutput(site.domain, 'free-hosting-live.json', failed);
      await recordTrackerEvent({
        module: 'free-hosting-live',
        domain: site.domain,
        platform: 'zip-build',
        ok: false,
        dryRun,
        error: error.message,
      });
      continue;
    }

    const slug = randomSlug(site.niche || 'site');
    const deployments = [
      { platform: 'carrd.co', ok: false, skipped: true, reason: 'Requires account; intentionally skipped.' },
      { platform: 'strikingly-api', ok: false, skipped: true, reason: 'Requires account; intentionally skipped.' },
      await deployTiiny(zipBuffer, slug, dryRun),
      await deployNetlifyDrop(zipBuffer, dryRun),
      { platform: 'surge.sh', ok: false, skipped: true, reason: 'CLI flow; intentionally skipped.' },
    ];

    await writeDomainOutput(site.domain, 'free-hosting-live.json', {
      domain: site.domain,
      generatedAt: new Date().toISOString(),
      deployments,
    });

    for (const deployment of deployments) {
      await recordTrackerEvent({
        module: 'free-hosting-live',
        domain: site.domain,
        platform: deployment.platform,
        ok: Boolean(deployment.ok),
        skipped: Boolean(deployment.skipped),
        url: deployment.liveUrl || null,
        dryRun,
        error: deployment.error || null,
      });
    }
  }
}
