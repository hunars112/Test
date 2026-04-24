import OpenAI from 'openai';
import pLimit from 'p-limit';

const toJsonIfPossible = (text) => {
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
};

export class ApiClient {
  constructor({ concurrency = 2, delayMs = 2000, dryRun = false, retries = 3, userAgent = 'backlink-system/1.1' } = {}) {
    this.limit = pLimit(concurrency);
    this.delayMs = delayMs;
    this.dryRun = dryRun;
    this.retries = retries;
    this.userAgent = userAgent;
    this.nextAllowedAt = 0;
  }

  async schedule(task) {
    return this.limit(async () => {
      if (this.dryRun) return task();
      const now = Date.now();
      if (now < this.nextAllowedAt) {
        await new Promise((resolve) => setTimeout(resolve, this.nextAllowedAt - now));
      }
      const startedAt = Date.now();
      this.nextAllowedAt = startedAt + this.delayMs;
      return task();
    });
  }

  async request({ url, method = 'POST', headers = {}, body = undefined, form = undefined }) {
    return this.schedule(async () => {
      if (this.dryRun) {
        return { ok: true, dryRun: true, url, method, body, form };
      }

      let lastError;
      for (let attempt = 1; attempt <= this.retries; attempt += 1) {
        try {
          const finalHeaders = { 'User-Agent': this.userAgent, ...headers };
          let payload;

          if (form) {
            payload = new URLSearchParams(form).toString();
            finalHeaders['Content-Type'] = 'application/x-www-form-urlencoded';
          } else if (body !== undefined) {
            payload = JSON.stringify(body);
            finalHeaders['Content-Type'] = 'application/json';
          }

          const response = await fetch(url, {
            method,
            headers: finalHeaders,
            body: payload
          });

          const text = await response.text();
          const json = toJsonIfPossible(text);
          if (!response.ok) {
            throw new Error(`HTTP ${response.status} ${response.statusText} for ${url} | ${text.slice(0, 300)}`);
          }

          return { ok: true, status: response.status, data: json ?? text };
        } catch (error) {
          lastError = error;
          if (attempt < this.retries) {
            await new Promise((resolve) => setTimeout(resolve, attempt * 1000));
          }
        }
      }
      throw lastError;
    });
  }
}

export function createOpenAIClient() {
  if (!process.env.OPENAI_API_KEY) return null;
  return new OpenAI({ apiKey: process.env.OPENAI_API_KEY });
}
