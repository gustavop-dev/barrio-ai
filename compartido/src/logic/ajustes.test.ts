// The pure rules of Ajustes and Galería both apps draw: caps and reads never turn «sin dato» into 0,
// the spend rows, the push switches and what the photo sheet PATCHes.
import type { PushType } from '../api/capturas';
import { ApiError } from '../api/client';
import type { AccountCanary, Ajustes, Overview, RedSummary } from '../api/types';
import { padHour } from './format';
import { canaryLine, capLines, controlReason, disabledKinds, factsLabel, isAjustesSection, isUnavailable, monthAlert, readLines, spacingLabel, spendLine, spendRows } from './ajustes';
import { inUseWarning, isFiltro, photoPatch, rejectedMessage, uploadedMessage } from './galeria';
import { linkedinReconnected, linkedinReturnMessage } from './linkedin';

const overview = { accounts: [{ provider: 'unipile', capacity: { 'INT-03': { daily: 3, weekly: 12, daily_used: 1, weekly_used: 4, left: 2 } } }] } as unknown as Overview;
const ajustes = { limits: { 'INT-02': { daily: 20, weekly: 80 } } } as unknown as Ajustes;

describe('Ajustes', () => {
  const now = Date.parse('2026-11-14T15:00:00Z');
  const canary = (fields: Partial<AccountCanary>): AccountCanary => ({
    state: 'ok', started_at: '2026-11-14T11:58:00Z', finished_at: '2026-11-14T12:00:00Z', calls: 16, failing: [],
    error_kind: '', error: '', ...fields,
  });

  it('tells the last daily canary of a directo account, and nothing without one', () => {
    expect(canaryLine({ canary: canary({}), paused: false }, now)).toEqual({ text: 'Prueba diaria: todo bien, hace 3 h.', tone: 'ok', detail: '' });
    expect(canaryLine({ canary: canary({ state: 'roto', failing: ['list_chats', 'get_post'] }), paused: false }, now)).toEqual({
      text: 'Prueba diaria: algo cambió en LinkedIn (falla list_chats, get_post), hace 3 h.', tone: 'bad', detail: '',
    });
    expect(canaryLine({ canary: canary({ state: 'no_corrio', finished_at: null, error: 'El servicio no responde.' }), paused: false }, now)).toEqual({
      text: 'Prueba diaria: no pudo correr, hace 3 h.', tone: 'warn', detail: 'El servicio no responde.',
    });
    // A stop pauses the account with the same reason: the pause note tells it.
    expect(canaryLine({ canary: canary({ state: 'alto', error: 'Sin sesión.' }), paused: true }, now)?.detail).toBe('');
    expect(canaryLine({ canary: canary({ state: 'alto', error: 'Sin sesión.' }), paused: false }, now)).toEqual({
      text: 'Prueba diaria: se detuvo, hace 3 h.', tone: 'bad', detail: 'Sin sesión.',
    });
    expect(canaryLine({ canary: canary({ state: 'nuevo' }), paused: false }, now)?.tone).toBe('muted');
    expect(canaryLine({ canary: null, paused: false }, now)).toBeNull();
    expect(canaryLine({ paused: false }, now)).toBeNull();
  });

  it('builds the caps from the usage, or the cap alone without usage', () => {
    expect(capLines(ajustes, overview, undefined, 'daily')).toEqual([
      { key: 'INT-03', label: 'Comentarios', used: 1, max: 3 },
      { key: 'INT-02', label: 'Reacciones', text: 'Tope 20 · sin dato de uso' },
    ]);
    expect(capLines(undefined, undefined, undefined, 'weekly')).toEqual([]);
  });

  it.each([5, 0])('shows the effective invitation cap (%s), including a paused or weekend limit', (daily) => {
    const general = { daily: 20, weekly: 100, daily_used: 1, weekly_used: 2, left: 19 };
    const accountOverview = { accounts: [{ capacity: { 'RED-02': general } }] } as unknown as Overview;
    const network = { capacity: { 'RED-02': { ...general, daily, weekly: 20, left: Math.max(0, daily - 1) } } } as unknown as RedSummary;
    expect(capLines(undefined, accountOverview, network, 'daily')).toEqual([
      { key: 'RED-02', label: 'Invitaciones', used: 1, max: daily },
    ]);
    expect(capLines(undefined, accountOverview, network, 'weekly')).toEqual([
      { key: 'RED-02', label: 'Invitaciones', used: 2, max: 20 },
    ]);
    expect(capLines(undefined, accountOverview, undefined, 'daily')).toEqual([
      { key: 'RED-02', label: 'Invitaciones', used: 1, max: 20 },
    ]);
  });

  it('keeps a zero invitation limit when usage is unavailable', () => {
    const settings = { limits: { 'RED-02': { daily: 0, weekly: 100 } } } as unknown as Ajustes;
    expect(capLines(settings, undefined, undefined, 'daily')).toEqual([
      { key: 'RED-02', label: 'Invitaciones', text: 'Tope 0 · sin dato de uso' },
    ]);
  });

  it('builds the network reads and the checks around every write', () => {
    const red = { read_caps: { comments: 60, search: 20, profile: 0 }, reads_today: { comments: 4, execution: 6 } } as unknown as RedSummary;
    expect(readLines(red)).toEqual({
      lines: [
        { key: 'comments', label: 'Comentarios leídos', used: 4, max: 60 },
        { key: 'search', label: 'Búsquedas', text: 'Tope 20 · sin dato de uso' },
      ],
      execution: '6 hoy · cuentan en el tope compartido de perfiles',
    });
  });

  it('says the spend, never 0 for what is unknown', () => {
    expect(spendLine({ budget: 'red', label: 'Red', spent_usd: 0.3, limit_usd: 0 })).toEqual({ label: 'Red', text: '0,30 USD' });
    expect(spendRows({ today: [], month_usd: null, total_usd: 98, limit_usd: 120, lead_month_usd: null })).toEqual([
      { label: 'Este mes', text: 'sin dato' },
      { label: 'Desde el inicio', text: '98,00 USD' },
    ]);
  });

  it('pads a lone hour digit, as Hermes does not (backlog #12)', () => {
    expect(padHour('8:30')).toBe('08:30');
    expect(padHour('Hoy, 8:05')).toBe('Hoy, 08:05');
    expect(padHour('jueves, 12 de noviembre, 9:00')).toBe('jueves, 12 de noviembre, 09:00');
    expect(padHour('18:30')).toBe('18:30');
    expect(padHour('08:30')).toBe('08:30');
  });

  it('flags the month near or over its limit (backlog #19)', () => {
    const month = (month_usd: number | null, limit_usd: number | null) => ({ today: [], month_usd, total_usd: 0, limit_usd, lead_month_usd: null });
    expect(monthAlert(month(61, 120))).toBeNull();
    expect(monthAlert(month(85, 100))).toEqual({ tone: 'warn', text: 'Cerca del límite del mes' });
    expect(monthAlert(month(1.04, 1))).toEqual({ tone: 'bad', text: 'Límite del mes alcanzado' });
    expect(monthAlert(month(null, 100))).toBeNull();
    expect(monthAlert(month(50, null))).toBeNull();
  });

  it('lists every push kind switched off', () => {
    const types = [
      { kind: 'a', enabled: true },
      { kind: 'b', enabled: false },
      { kind: 'c', enabled: true },
    ] as PushType[];
    expect(disabledKinds(types, { a: false, b: true })).toEqual(['a']);
  });

  it('knows the anchors, the unavailable endpoints and the small labels', () => {
    expect(isAjustesSection('maquina')).toBe(true);
    expect(isAjustesSection('nada')).toBe(false);
    expect(isUnavailable(new ApiError(501, 'x'))).toBe(true);
    expect(isUnavailable(new ApiError(500, 'x'))).toBe(false);
    expect(spacingLabel(1200)).toBe('20 min entre acciones');
    expect(controlReason({ reason: 'Revisando.' })).toBe('Motivo: Revisando.');
    expect(factsLabel(1)).toBe('1 dato confirmado');
    expect(factsLabel(undefined)).toBe('Los datos que confirmaste y su visibilidad');
  });

  it('notices a new LinkedIn credential and reads the OAuth return', () => {
    const off = { connected: false, connected_at: undefined, expires_at: null } as never;
    const on = { connected: true, connected_at: '2026-11-07T10:00:00Z', expires_at: '2027-01-06T10:00:00Z' } as never;
    expect(linkedinReconnected(off, on)).toBe(true);
    expect(linkedinReconnected(on, on)).toBe(false);
    expect(linkedinReturnMessage('error', 'raro')?.text).toBe('No se pudo completar la conexión (motivo: raro). Vuelve a intentarlo.');
    expect(linkedinReturnMessage(undefined, undefined)).toBeNull();
  });
});

describe('Galería', () => {
  it('PATCHes only what changed', () => {
    const photo = { note: 'Recórtala', ai_edit: 'auto' as const };
    expect(photoPatch(photo, ' Recórtala ', 'auto')).toEqual({});
    expect(photoPatch(photo, 'Otra', 'auto')).toEqual({ note: 'Otra' });
    expect(photoPatch(photo, 'Recórtala', 'no')).toEqual({ ai_edit: 'no' });
  });

  it('warns where a removed photo is used, and words the upload', () => {
    expect(inUseWarning({ display_state: 'elegida', used_in: { piece_id: 'p', date: 'd', text: 'Elegida para el post del jueves 12' } })).toBe('Ojo: elegida para el post del jueves 12.');
    expect(inUseWarning({ display_state: 'publicada', used_in: { piece_id: 'p', date: 'd', text: 'Publicada' } })).toBeNull();
    expect(uploadedMessage(1)).toBe('Foto subida. El equipo la verá en su próxima ronda.');
    expect(rejectedMessage([])).toBeNull();
    expect(isFiltro('elegidas')).toBe(true);
    expect(isFiltro(undefined)).toBe(false);
  });
});
