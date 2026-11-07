// Shared by the service worker and the tests: no DOM or worker globals here.

export interface PushPayload {
  title: string;
  body: string;
  url: string;
  tag: string | undefined;
}

const DEFAULT_TITLE = '0ff1ce';

/** Push data is JSON `{title, body, url, tag}`; tolerate plain text or junk. */
export function parsePushPayload(raw: string | null | undefined): PushPayload {
  let data: Record<string, unknown> = {};
  if (raw) {
    try {
      const parsed: unknown = JSON.parse(raw);
      if (parsed && typeof parsed === 'object') data = parsed as Record<string, unknown>;
      else data = { body: String(parsed) };
    } catch {
      data = { body: raw };
    }
  }
  const text = (value: unknown) => (typeof value === 'string' ? value.trim() : '');
  return {
    title: text(data.title) || DEFAULT_TITLE,
    body: text(data.body),
    url: text(data.url) || '/',
    tag: text(data.tag) || undefined,
  };
}

/** Only same-origin destinations are opened from a notification. */
export function safeTargetUrl(url: unknown, origin: string): string {
  try {
    const target = new URL(typeof url === 'string' && url ? url : '/', origin);
    return target.origin === origin ? target.href : new URL('/', origin).href;
  } catch {
    return new URL('/', origin).href;
  }
}
