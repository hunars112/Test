import { promises as fs } from 'node:fs';
import path from 'node:path';

const DB_PATH = path.resolve(process.cwd(), 'output', 'wins-database.json');
const COOLDOWN_MS = 48 * 60 * 60 * 1000;

function nowIso() {
  return new Date().toISOString();
}

function defaultDb() {
  return {
    version: 1,
    entries: [],
    updatedAt: nowIso(),
  };
}

function makeKey(targetUrl, siteDomain) {
  return `${String(targetUrl || '').trim()}|${String(siteDomain || '').trim()}`;
}

function normalizeEntry(entry = {}) {
  const ts = nowIso();
  return {
    targetUrl: entry.targetUrl ?? '',
    siteDomain: entry.siteDomain ?? '',
    engine: entry.engine ?? 'unknown',
    type: entry.type ?? 'unknown',
    firstSeen: entry.firstSeen ?? ts,
    lastPosted: entry.lastPosted ?? null,
    postCount: Number(entry.postCount ?? 0),
    successCount: Number(entry.successCount ?? 0),
    lastResult: entry.lastResult ?? 'unknown',
    cooldownUntil: entry.cooldownUntil ?? null,
  };
}

export async function loadWinsDb() {
  try {
    const raw = await fs.readFile(DB_PATH, 'utf8');
    const parsed = JSON.parse(raw);
    if (!parsed || !Array.isArray(parsed.entries)) {
      return defaultDb();
    }
    return {
      version: Number(parsed.version ?? 1),
      entries: parsed.entries.map(normalizeEntry),
      updatedAt: parsed.updatedAt ?? nowIso(),
    };
  } catch (error) {
    if (error && error.code !== 'ENOENT') {
      console.warn('[wins-db] Failed to read DB, starting fresh:', error.message);
    }
    return defaultDb();
  }
}

export async function saveWinsDb(db) {
  const safeDb = {
    version: Number(db?.version ?? 1),
    entries: Array.isArray(db?.entries) ? db.entries.map(normalizeEntry) : [],
    updatedAt: nowIso(),
  };

  await fs.mkdir(path.dirname(DB_PATH), { recursive: true });
  await fs.writeFile(DB_PATH, JSON.stringify(safeDb, null, 2), 'utf8');
}

export function addOrUpdateEntry(db, entry) {
  if (!db || !Array.isArray(db.entries)) {
    throw new Error('Invalid wins DB object.');
  }

  const normalized = normalizeEntry(entry);
  const key = makeKey(normalized.targetUrl, normalized.siteDomain);
  const idx = db.entries.findIndex(
    (item) => makeKey(item.targetUrl, item.siteDomain) === key,
  );

  if (idx === -1) {
    db.entries.push(normalized);
    return normalized;
  }

  const merged = normalizeEntry({ ...db.entries[idx], ...normalized, firstSeen: db.entries[idx].firstSeen });
  db.entries[idx] = merged;
  return merged;
}

export function getProvenWins(db, siteDomain, engine) {
  if (!db || !Array.isArray(db.entries)) return [];

  return db.entries
    .filter((entry) => {
      const domainMatch = entry.siteDomain === siteDomain;
      const engineMatch = engine ? entry.engine === engine : true;
      return domainMatch && engineMatch && Number(entry.successCount) > 0;
    })
    .sort((a, b) => Number(b.successCount) - Number(a.successCount));
}

export function markSuccess(db, targetUrl, siteDomain) {
  const existing = addOrUpdateEntry(db, {
    targetUrl,
    siteDomain,
    lastResult: 'success',
  });

  const now = new Date();
  existing.lastPosted = now.toISOString();
  existing.postCount = Number(existing.postCount || 0) + 1;
  existing.successCount = Number(existing.successCount || 0) + 1;
  existing.lastResult = 'success';
  existing.cooldownUntil = new Date(now.getTime() + COOLDOWN_MS).toISOString();
  return existing;
}

export function markFailed(db, targetUrl, siteDomain) {
  const existing = addOrUpdateEntry(db, {
    targetUrl,
    siteDomain,
    lastResult: 'failed',
  });

  const now = new Date();
  existing.lastPosted = now.toISOString();
  existing.postCount = Number(existing.postCount || 0) + 1;
  existing.lastResult = 'failed';
  return existing;
}

export function isKnown(db, targetUrl, siteDomain) {
  if (!db || !Array.isArray(db.entries)) return false;
  const key = makeKey(targetUrl, siteDomain);
  return db.entries.some((entry) => makeKey(entry.targetUrl, entry.siteDomain) === key);
}

export function isOnCooldown(db, targetUrl, siteDomain) {
  if (!db || !Array.isArray(db.entries)) return false;
  const key = makeKey(targetUrl, siteDomain);
  const entry = db.entries.find((item) => makeKey(item.targetUrl, item.siteDomain) === key);
  if (!entry || !entry.cooldownUntil) return false;
  return new Date(entry.cooldownUntil).getTime() > Date.now();
}
