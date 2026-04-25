const DDG_URL = 'https://html.duckduckgo.com/html/';
const BING_URL = 'https://www.bing.com/search';

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function normalizeUrl(candidate) {
  if (!candidate) return null;
  const cleaned = String(candidate)
    .replace(/^\/+/, '')
    .replace(/^uddg=/, '')
    .trim();

  try {
    const decoded = decodeURIComponent(cleaned);
    const url = new URL(decoded.startsWith('http') ? decoded : `https://${decoded}`);
    return `${url.origin}${url.pathname}`.replace(/\/$/, '');
  } catch {
    return null;
  }
}

function parseDdg(html = '') {
  const matches = [...html.matchAll(/<a[^>]*class="result__url"[^>]*>(.*?)<\/a>/gims)];
  return matches
    .map((m) => m[1].replace(/<[^>]*>/g, '').trim())
    .map(normalizeUrl)
    .filter(Boolean);
}

function parseBing(html = '') {
  const matches = [...html.matchAll(/<li class="b_algo"[\s\S]*?<a href="([^"]+)"/gim)];
  return matches.map((m) => normalizeUrl(m[1])).filter(Boolean);
}

async function ddgSearch(fetchFn, query) {
  const body = new URLSearchParams({ q: query, b: '' });
  const response = await fetchFn(DDG_URL, {
    method: 'POST',
    headers: {
      'content-type': 'application/x-www-form-urlencoded',
      'user-agent': 'Mozilla/5.0',
    },
    body: body.toString(),
  });
  if (!response.ok) {
    throw new Error(`DDG search failed (${response.status})`);
  }
  return parseDdg(await response.text());
}

async function bingSearch(fetchFn, query) {
  const url = `${BING_URL}?q=${encodeURIComponent(query)}`;
  const response = await fetchFn(url, {
    headers: { 'user-agent': 'Mozilla/5.0' },
  });
  if (!response.ok) {
    throw new Error(`Bing search failed (${response.status})`);
  }
  return parseBing(await response.text());
}

export async function discoverTargets(fetchFn, queries, { sleepBetween = 3000 } = {}) {
  if (typeof fetchFn !== 'function') {
    throw new Error('discoverTargets requires a fetchFn function');
  }

  const list = Array.isArray(queries) ? queries : [];
  const discovered = new Set();

  for (let i = 0; i < list.length; i += 1) {
    const query = String(list[i] ?? '').trim();
    if (!query) continue;

    let results = [];
    try {
      results = await ddgSearch(fetchFn, query);
    } catch (error) {
      console.warn(`[discover-targets] DDG failed for "${query}":`, error.message);
    }

    if (results.length < 3) {
      try {
        const fallback = await bingSearch(fetchFn, query);
        results = [...results, ...fallback];
      } catch (error) {
        console.warn(`[discover-targets] Bing fallback failed for "${query}":`, error.message);
      }
    }

    for (const url of results) {
      discovered.add(url);
    }

    if (i < list.length - 1 && sleepBetween > 0) {
      await sleep(sleepBetween);
    }
  }

  return Array.from(discovered);
}
