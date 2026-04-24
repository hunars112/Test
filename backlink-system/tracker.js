import path from 'node:path';
import { readJson, writeCsv, writeJson } from './lib/utils.js';

const TRACKER_PATH = path.resolve('tracker.json');
const CSV_PATH = path.resolve('backlinks-tracker.csv');

export async function getTracker() {
  return (await readJson(TRACKER_PATH, { events: [] })) ?? { events: [] };
}

export async function recordTrackerEvent(event) {
  const tracker = await getTracker();
  tracker.events.push({
    timestamp: new Date().toISOString(),
    module: event.module,
    site: event.site,
    target: event.target,
    status: event.status,
    details: event.details ?? ''
  });
  await writeJson(TRACKER_PATH, tracker);
  await exportTrackerCsv(tracker.events);
}

export async function exportTrackerCsv(events = null) {
  const list = events ?? (await getTracker()).events;
  const rows = list.length > 0
    ? list
    : [{ timestamp: '', module: '', site: '', target: '', status: '', details: '' }];
  await writeCsv(CSV_PATH, rows);
}
