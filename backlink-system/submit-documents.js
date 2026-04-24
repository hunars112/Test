import 'dotenv/config';
import path from 'node:path';
import { PDFDocument, StandardFonts } from 'pdf-lib';
import config from './config.json' with { type: 'json' };
import { parseDryRunArg, writeBinary, writeJson, writeText } from './lib/utils.js';
import { recordTrackerEvent } from './tracker.js';

async function createPdf(filePath, { title, body }) {
  const pdf = await PDFDocument.create();
  const page = pdf.addPage([595, 842]);
  const font = await pdf.embedFont(StandardFonts.Helvetica);
  page.drawText(title, { x: 40, y: 800, size: 18, font });
  page.drawText(body, { x: 40, y: 760, size: 11, font, maxWidth: 510, lineHeight: 14 });
  const bytes = await pdf.save();
  await writeBinary(filePath, bytes);
}

export async function runSubmitDocuments({ dryRun = false } = {}) {
  for (const site of config.sites) {
    const baseDir = path.resolve('output', site.domain, 'documents');
    const body = `${site.description}\n\nPrimary resource: https://${site.domain}\n\nThis package is formatted for publishing as educational documents.`;

    const documents = [
      { platform: 'slideshare', file: 'slideshare-package.pdf' },
      { platform: 'scribd', file: 'scribd-package.pdf' },
      { platform: 'issuu', file: 'issuu-package.pdf' }
    ];

    for (const doc of documents) {
      const filePath = path.join(baseDir, doc.file);
      await createPdf(filePath, { title: `${site.domain} | ${doc.platform}`, body });
      await recordTrackerEvent({ module: 'submit-documents', site: site.domain, target: doc.platform, status: 'success', details: filePath });
    }

    await writeJson(path.join(baseDir, 'metadata.json'), {
      dryRun,
      site: site.domain,
      documents: documents.map((d) => ({ platform: d.platform, file: d.file }))
    });
    await writeText(path.join(baseDir, 'README.txt'), 'Upload each PDF manually and keep anchor text contextual in titles/descriptions.');
  }
}

if (import.meta.url === `file://${process.argv[1]}`) {
  runSubmitDocuments({ dryRun: parseDryRunArg() });
}
