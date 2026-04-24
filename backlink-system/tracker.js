import { appendFile, mkdir } from 'node:fs/promises';
import { dirname, join } from 'node:path';

const TRACKER_LOG = join(process.cwd(), 'backlink-system', 'output', 'tracker-events.jsonl');

export async function recordTrackerEvent(event) {
  const payload = {
    timestamp: new Date().toISOString(),
    ...event,
  };

  await mkdir(dirname(TRACKER_LOG), { recursive: true });
  await appendFile(TRACKER_LOG, `${JSON.stringify(payload)}\n`, 'utf8');
}
