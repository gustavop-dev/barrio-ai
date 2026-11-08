// Client error reports (POST /api/v1/app/errores): when an upload fails on the phone, the app tells the
// backend what failed so the team can diagnose it without the phone in hand. Only metadata goes: the
// error name and message, the HTTP status and the server's detail, each file part's field, type, URI
// scheme and size, the platform and the app version. Never the audio, the photos, the note text, a
// URI, a file name or a token. Reporting never throws and never retries.
import { ApiError } from '@compartido/api/client';
import { nativeUri } from '@compartido/api/capturas';
import { reportClientError, type ClientErrorReport, type ReportedPart } from '@compartido/api/errors';
import Constants from 'expo-constants';
import { Platform } from 'react-native';

/** A file part as the app knows it, before it is reduced to what may be reported. */
export interface LocalPart {
  field: string;
  uri: string;
  type: string;
  size: number | null;
}

/** At most this many reports per app run, and the same failure once per window. */
const MAX_PER_RUN = 20;
const SAME_FAILURE_MS = 30_000;
const MAX_PARTS = 12;

let sent = 0;
const lastSent = new Map<string, number>();

const clip = (text: string, max: number) => (text.length > max ? `${text.slice(0, max - 1)}…` : text);

/**
 * A native reason can name the file («Could not retrieve file for uri file:///…/recording-1.m4a»): keep
 * the scheme and the extension, which is what tells a missing scheme or a wrong type, and drop the rest.
 */
export function withoutPaths(text: string): string {
  const ext = (path: string) => /\.[a-z0-9]{1,5}$/i.exec(path)?.[0] ?? '';
  return text
    .replace(/\b([a-z][a-z0-9+.-]*):\/\/[^\s'"]+/gi, (whole: string, scheme: string) => (/^https?$/i.test(scheme) ? whole : `${scheme}://…${ext(whole)}`))
    .replace(/(^|[\s'"(])\/(?:data|storage|sdcard|private|var)\/[^\s'")]+/g, (whole: string, lead: string) => `${lead}…${ext(whole)}`);
}

function appVersion(): string {
  return Constants.expoConfig?.version ?? '';
}

/** Field, type, scheme (`file`, `content`, `none` for a bare path) and size: nothing that identifies the file. */
export function reportedPart({ field, uri, type, size }: LocalPart): ReportedPart {
  const scheme = /^([a-z][a-z0-9+.-]*):/i.exec(String(uri || '').trim())?.[1]?.toLowerCase() ?? 'none';
  return {
    field: clip(field, 20),
    type: clip(type || '', 80),
    scheme: clip(scheme, 16),
    size: typeof size === 'number' && Number.isFinite(size) && size >= 0 ? Math.round(size) : null,
  };
}

/** The report of one failure (exported for the tests). */
export function clientErrorReport(kind: string, error: unknown, parts: readonly LocalPart[] = []): ClientErrorReport {
  const name = error instanceof Error ? error.name || 'Error' : typeof error;
  const message = withoutPaths(error instanceof Error ? error.message : String(error));
  return {
    kind: clip(kind, 40),
    name: clip(name, 80),
    message: clip(message, 500),
    status: error instanceof ApiError ? error.status : null,
    detail: error instanceof ApiError ? clip(withoutPaths(error.detail), 500) : '',
    parts: parts.slice(0, MAX_PARTS).map(reportedPart),
    platform: Platform.OS,
    os_version: clip(String(Platform.Version ?? ''), 40),
    app_version: clip(appVersion(), 40),
  };
}

/**
 * Sends the report in the background. Skips an abort, a lost session (the login takes over) and the
 * same failure again within 30 s.
 */
export function reportError(kind: string, error: unknown, parts: readonly LocalPart[] = []): void {
  try {
    if (error instanceof Error && error.name === 'AbortError') return;
    if (error instanceof ApiError && error.status === 401) return;
    const report = clientErrorReport(kind, error, parts);
    const key = `${report.kind}|${report.name}|${report.status ?? ''}`;
    const now = Date.now();
    const last = lastSent.get(key);
    if (sent >= MAX_PER_RUN || (last !== undefined && now - last < SAME_FAILURE_MS)) return;
    lastSent.set(key, now);
    sent += 1;
    void reportClientError(report).catch(() => undefined);
  } catch {
    // Reporting must never break what the user is doing.
  }
}

/** The local parts of a native upload, for the report (the URI only yields its scheme). */
export function localPart(field: string, file: { uri: string; type: string; size?: number | null }): LocalPart {
  return { field, uri: nativeUri(file.uri), type: file.type, size: file.size ?? null };
}

/** For tests: a fresh run. */
export function resetErrorReportsForTests(): void {
  sent = 0;
  lastSent.clear();
}
