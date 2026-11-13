// Personas › Conexiones: the role chips with their counts, the role of a row, «Aceptó el …» and the sections by when
// the person accepted, in Bogotá days.
import { contactFixture, redSummaryFixture } from '../fixtures/personas';
import { acceptedLabel, connectionPeriod, connectionSections, NO_ROLE, roleChips, roleLabel, rolePlural } from './conexiones';

const connected = (id: string, connected_at: string | null, updated_at = '2026-01-01T15:00:00Z') =>
  contactFixture(id, { stage: 'connected', display_stage: 'connected', connected_at, updated_at });

// Thursday 12 November 2026, 15:00 in Bogotá: the week started on Monday the 9th.
const NOW = new Date('2026-11-12T20:00:00Z');

describe('Conexiones · role chips', () => {
  it('counts every connection, then one chip per role present, in the barrio order and «Sin etiqueta» last', () => {
    const summary = redSummaryFixture({ connections: { total: 7, roles: { [NO_ROLE]: 2, par: 1, mentor: 1, comprador: 3, lider: 0 } } });
    expect(roleChips(summary)).toEqual({
      all: 'Todas · 7',
      chips: [
        { value: 'comprador', label: 'Compradores · 3' },
        { value: 'par', label: 'Pares · 1' },
        { value: 'mentor', label: 'mentor · 1' },
        { value: NO_ROLE, label: 'Sin etiqueta · 2' },
      ],
    });
  });

  it('shows «Todas» alone until the summary answers, or when an older backend sends no counts', () => {
    expect(roleChips(undefined)).toEqual({ all: 'Todas', chips: [] });
    expect(roleChips(redSummaryFixture({ connections: undefined }))).toEqual({ all: 'Todas', chips: [] });
  });

  it('names the roles in plural for the chips and in singular for a row', () => {
    expect(['comprador', 'par', 'recomendador', 'divulgador', 'lider', 'aliado', NO_ROLE].map(rolePlural)).toEqual([
      'Compradores',
      'Pares',
      'Recomendadores',
      'Divulgadores',
      'Líderes',
      'Aliados',
      'Sin etiqueta',
    ]);
    expect(roleLabel(contactFixture('c-1', { classification: { role: 'lider' } }))).toBe('Líder');
    expect(roleLabel(contactFixture('c-1', { classification: {} }))).toBe('Sin etiqueta');
    expect(roleLabel(contactFixture('c-1', { classification: { role: '' } }))).toBe('Sin etiqueta');
  });
});

describe('Conexiones · when they accepted', () => {
  it('writes the Bogotá day, with the year only when it is not this one', () => {
    expect(acceptedLabel(connected('c-1', '2026-11-12T03:00:00Z'), NOW)).toBe('Aceptó el 11/11');
    expect(acceptedLabel(connected('c-1', '2026-03-05T15:00:00Z'), NOW)).toBe('Aceptó el 05/03');
    expect(acceptedLabel(connected('c-1', '2025-12-24T15:00:00Z'), NOW)).toBe('Aceptó el 24/12/2025');
    expect(acceptedLabel(connected('c-1', null), NOW)).toBe('');
  });

  it.each([
    ['2026-11-12T15:00:00Z', NOW, 'semana'],
    ['2026-11-09T05:00:00Z', NOW, 'semana'], // Monday 00:00 in Bogotá
    ['2026-11-09T04:59:00Z', NOW, 'mes'], // still Sunday the 8th in Bogotá
    ['2026-11-01T12:00:00Z', NOW, 'mes'],
    ['2026-11-01T03:00:00Z', NOW, 'antes'], // 31 October, 22:00 in Bogotá
    ['2025-11-10T15:00:00Z', NOW, 'antes'],
    // On Monday 2 November the week has just started: Sunday the 1st is «Este mes», 31 October «Antes».
    ['2026-11-01T15:00:00Z', new Date('2026-11-02T15:00:00Z'), 'mes'],
    // A week across two months: on Tuesday 1 December, Monday 30 November is this week and Sunday the 29th is before.
    ['2026-11-30T15:00:00Z', new Date('2026-12-01T15:00:00Z'), 'semana'],
    ['2026-11-29T15:00:00Z', new Date('2026-12-01T15:00:00Z'), 'antes'],
  ])('a connection on %s, seen on %s, goes under %s', (at, now, period) => {
    expect(connectionPeriod(connected('c-1', at), now)).toBe(period);
  });

  it('falls back on the last update when the connection has no date', () => {
    expect(connectionPeriod(connected('c-1', null, '2026-11-10T15:00:00Z'), NOW)).toBe('semana');
    expect(connectionPeriod(connected('c-1', null, '2026-10-10T15:00:00Z'), NOW)).toBe('antes');
  });

  it('groups the list under «Esta semana», «Este mes» and «Antes», keeping the order and leaving out empty sections', () => {
    const list = [
      connected('a', '2026-11-11T15:00:00Z'),
      connected('b', '2026-10-02T15:00:00Z'),
      connected('c', '2026-11-10T15:00:00Z'),
      connected('d', null, '2026-09-01T15:00:00Z'),
    ];
    expect(connectionSections(list, NOW).map((section) => [section.title, section.data.map((contact) => contact.id)])).toEqual([
      ['Esta semana', ['a', 'c']],
      ['Antes', ['b', 'd']],
    ]);
    expect(connectionSections([], NOW)).toEqual([]);
  });
});
