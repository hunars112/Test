'use strict';

const BING_SEARCH_ENDPOINT = 'https://www.bing.com/search';

function normalizeUrl(rawUrl) {
  if (!rawUrl || typeof rawUrl !== 'string') {
    return null;
  }

  try {
    const parsed = new URL(rawUrl);
    parsed.hash = '';

    if ((parsed.protocol === 'http:' && parsed.port === '80') || (parsed.protocol === 'https:' && parsed.port === '443')) {
      parsed.port = '';
    }

    if (parsed.pathname !== '/' && parsed.pathname.endsWith('/')) {
      parsed.pathname = parsed.pathname.slice(0, -1);
    }

    return parsed.toString();
  } catch {
    return null;
  }
}

function isLikelyWpPost(rawUrl) {
  try {
    const url = new URL(rawUrl);
    const path = url.pathname.toLowerCase();

    if (!path || path === '/') {
      return false;
    }

    if (path.includes('/wp-content/') || path.includes('/wp-admin/') || path.includes('/wp-json/')) {
      return false;
    }

    if (/\.(jpg|jpeg|png|gif|webp|svg|pdf|xml|txt|zip)$/i.test(path)) {
      return false;
    }

    return true;
  } catch {
    return false;
  }
}

function decodeBingRedirect(rawHref) {
  try {
    const parsed = new URL(rawHref);

    if (!parsed.hostname.endsWith('bing.com') || !parsed.pathname.startsWith('/ck/a')) {
      return normalizeUrl(rawHref);
    }

    const encoded = parsed.searchParams.get('u');
    if (!encoded) {
      return null;
    }

    const withoutPrefix = encoded.startsWith('a1') ? encoded.slice(2) : encoded;
    const standardBase64 = withoutPrefix.replace(/-/g, '+').replace(/_/g, '/');
    const decoded = Buffer.from(standardBase64, 'base64').toString('utf8');

    return normalizeUrl(decoded);
  } catch {
    return null;
  }
}

function parseBing(html) {
  if (!html || typeof html !== 'string') {
    return [];
  }

  const urls = [];
  const hrefRegex = /<a[^>]+href=["']([^"']+)["']/gi;
  let match;

  while ((match = hrefRegex.exec(html)) !== null) {
    const href = match[1];
    const decoded = decodeBingRedirect(href);
    if (decoded) {
      urls.push(decoded);
    }
  }

  return urls;
}

async function bingSearch(query, fetchImpl = fetch) {
  const searchUrl = `${BING_SEARCH_ENDPOINT}?q=${encodeURIComponent(query)}`;
  const response = await fetchImpl(searchUrl, {
    method: 'GET',
    headers: {
      'User-Agent': 'Mozilla/5.0 backlink-discovery-bot',
      Accept: 'text/html,application/xhtml+xml',
    },
  });

  if (!response.ok) {
    return [];
  }

  const html = await response.text();
  return parseBing(html);
}

async function discoverTargets(query, fetchImpl = fetch) {
  const [primary, secondary] = await Promise.all([
    bingSearch(query, fetchImpl),
    bingSearch(`${query} site:wordpress.com`, fetchImpl),
  ]);

  const deduped = new Set([...primary, ...secondary]);
  return [...deduped].filter(isLikelyWpPost);
}

module.exports = {
  normalizeUrl,
  isLikelyWpPost,
  parseBing,
  bingSearch,
  discoverTargets,
};
