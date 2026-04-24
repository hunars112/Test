import { loadConfig, postForm, postJson, toOneHundredWordDescription, writeDomainOutput } from './utils.js';
import { recordTrackerEvent } from './tracker.js';

function extractFirstUrl(text, fallback) {
  const match = text?.match(/https?:\/\/[^\s"'<>]+/i);
  return match?.[0] || fallback;
}

async function submitMix(site, description, dryRun) {
  const targetUrl = `https://${site.domain}`;
  if (dryRun) {
    return { platform: 'mix', ok: true, publicUrl: `https://mix.com/saves/${site.domain}`, dryRun: true };
  }

  try {
    const payload = { url: targetUrl, description };
    let response = await postJson('https://mix.com/api/v1/saves', payload);

    if (!response.ok) {
      const form = new URLSearchParams({ url: targetUrl, description });
      response = await postForm('https://mix.com/submit', form);
    }

    return {
      platform: 'mix',
      ok: response.ok,
      status: response.status,
      publicUrl: extractFirstUrl(response.text, `https://mix.com`),
      responseSnippet: response.text?.slice(0, 250),
    };
  } catch (error) {
    return { platform: 'mix', ok: false, error: error.message };
  }
}

async function submitFolkd(site, title, description, dryRun) {
  const targetUrl = `https://${site.domain}`;
  if (dryRun) {
    return { platform: 'folkd', ok: true, publicUrl: `https://www.folkd.com/bookmark/${site.domain}`, dryRun: true };
  }

  try {
    const form = new URLSearchParams({
      url: targetUrl,
      title,
      description,
      tags: site.niche || 'resource',
    });
    const response = await postForm('https://www.folkd.com/submit/url', form, {
      headers: { 'content-type': 'application/x-www-form-urlencoded' },
    });

    return {
      platform: 'folkd',
      ok: response.ok,
      status: response.status,
      publicUrl: extractFirstUrl(response.text, 'https://www.folkd.com/'),
      responseSnippet: response.text?.slice(0, 250),
    };
  } catch (error) {
    return { platform: 'folkd', ok: false, error: error.message };
  }
}

async function submitBizSugar(site, title, description, dryRun) {
  const targetUrl = `https://${site.domain}`;
  if (dryRun) {
    return { platform: 'bizsugar', ok: true, publicUrl: `https://www.bizsugar.com/story/${site.domain}`, dryRun: true };
  }

  try {
    const form = new URLSearchParams({
      url: targetUrl,
      title,
      description,
      category: site.niche || 'business',
    });

    const response = await postForm('https://www.bizsugar.com/add-link', form, {
      headers: { 'content-type': 'application/x-www-form-urlencoded' },
    });

    return {
      platform: 'bizsugar',
      ok: response.ok,
      status: response.status,
      publicUrl: extractFirstUrl(response.text, 'https://www.bizsugar.com/'),
      responseSnippet: response.text?.slice(0, 250),
    };
  } catch (error) {
    return { platform: 'bizsugar', ok: false, error: error.message };
  }
}

export async function runSubmitSocialBookmarks({ dryRun = false } = {}) {
  const { sites } = await loadConfig();

  for (const site of sites) {
    const title = `${site.title || site.domain} | ${site.niche || 'Resource'}`;
    const description = toOneHundredWordDescription(site);
    const submissions = [
      await submitMix(site, description, dryRun),
      {
        platform: 'diigo',
        ok: false,
        skipped: true,
        reason: 'Requires login; intentionally skipped.',
      },
      await submitFolkd(site, title, description, dryRun),
      await submitBizSugar(site, title, description, dryRun),
      {
        platform: 'slashdot-firehose',
        ok: false,
        skipped: true,
        reason: 'Outdated; intentionally skipped.',
      },
    ];

    await writeDomainOutput(site.domain, 'social-bookmarks-live.json', {
      domain: site.domain,
      generatedAt: new Date().toISOString(),
      submissions,
    });

    for (const result of submissions) {
      await recordTrackerEvent({
        module: 'social-bookmarks-live',
        domain: site.domain,
        platform: result.platform,
        ok: Boolean(result.ok),
        skipped: Boolean(result.skipped),
        url: result.publicUrl || null,
        dryRun,
        error: result.error || null,
      });
    }
  }
}
