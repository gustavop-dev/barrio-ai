import { describe, expect, it } from 'vitest';
import { day, event, item } from '../../test/fixtures/calendario';
import {
  addMonths,
  dayOf,
  deviceDiffers,
  isIsoDay,
  longDayTitle,
  monthGrid,
  relativeDay,
  startOfWeek,
  timeLeft,
  weekRangeLabel,
  zoneOffsetMinutes,
} from './dates';
import { chronological, dayDots, eventLink, eventSentence, itemSentence, pieceIdFromLink, summaryParts } from './events';
import { firstLines, pieceWhen, preparationStages } from './piece';

describe('dates', () => {
  it('computes days in Bogotá, not in UTC', () => {
    expect(dayOf('2026-11-08T03:00:00Z')).toBe('2026-11-07');
    expect(dayOf('2026-11-08T05:00:00Z')).toBe('2026-11-08');
    expect(dayOf(null)).toBeNull();
    expect(zoneOffsetMinutes('America/Bogota', new Date('2026-11-07T15:00:00Z'))).toBe(-300);
    expect(zoneOffsetMinutes('UTC')).toBe(0);
  });

  it('knows when the device shows other hours than Bogotá', () => {
    const at = new Date('2026-11-07T15:00:00Z');
    expect(deviceDiffers('America/Bogota', at)).toBe(-at.getTimezoneOffset() !== -300);
  });

  it('builds Monday-first weeks and 5 or 6 row months', () => {
    expect(startOfWeek('2026-11-08')).toBe('2026-11-02');
    expect(startOfWeek('2026-11-02')).toBe('2026-11-02');
    const november = monthGrid('2026-11-15');
    expect(november[0]).toBe('2026-10-26');
    expect(november).toHaveLength(42);
    expect(monthGrid('2027-02-10')).toHaveLength(28);
    expect(monthGrid('2026-12-01')).toHaveLength(35);
  });

  it('moves by months clamping the day', () => {
    expect(addMonths('2026-01-31', 1)).toBe('2026-02-28');
    expect(addMonths('2026-11-07', -1)).toBe('2026-10-07');
    expect(addMonths('2026-12-15', 1)).toBe('2027-01-15');
  });

  it('labels ranges and days like the design', () => {
    expect(weekRangeLabel('2026-11-05')).toBe('2–8 nov 2026');
    expect(weekRangeLabel('2026-12-01')).toBe('30 nov – 6 dic 2026');
    expect(weekRangeLabel('2026-12-31')).toBe('28 dic 2026 – 3 ene 2027');
    expect(longDayTitle('2026-11-07')).toBe('Sábado 7 de noviembre');
    expect(relativeDay('2026-11-08', '2026-11-07')).toBe('Mañana');
    expect(relativeDay('2026-11-06', '2026-11-07')).toBe('Ayer');
    expect(relativeDay('2026-11-05', '2026-11-07')).toBe('Jueves 5 de noviembre');
    expect(isIsoDay('2026-02-30')).toBe(false);
    expect(isIsoDay('2026-11-07')).toBe(true);
  });

  it('counts down like «sale en 5 h 20 min»', () => {
    expect(timeLeft(5 * 3_600_000 + 20 * 60_000)).toBe('5 h 20 min');
    expect(timeLeft(18 * 3_600_000 + 5 * 60_000)).toBe('18 h');
    expect(timeLeft(12 * 60_000)).toBe('12 min');
    expect(timeLeft(50 * 3_600_000)).toBe('2 días');
  });
});

describe('events', () => {
  const busy = day(
    '2026-11-07',
    [
      event({ layer: 'red', kind: 'connection_fit', title: '2 conexiones nuevas' }),
      event({ layer: 'publicaciones', kind: 'piece_published', at: '2026-11-07T14:00:00Z', title: 'Thesis', link: '/calendario/pieza/p1' }),
      event({ layer: 'tuyo', kind: 'deadline', at: '2026-11-07T22:00:00Z', title: 'Responde: ¿algo?' }),
      event({ layer: 'red', kind: 'invite_expected', title: '2 invitaciones previstas', important: false }),
    ],
    { comments: 1, reactions: 2, accepts: 1 },
  );

  it('puts one dot per visible layer with important events, by priority', () => {
    expect(dayDots(busy, new Set(['tuyo', 'publicaciones', 'red', 'conversaciones', 'sistema']))).toEqual(['tuyo', 'publicaciones', 'red']);
    expect(dayDots(busy, new Set(['red']))).toEqual(['red']);
  });

  it('orders the day chronologically with all-day events first', () => {
    expect(chronological(busy.events).map((e) => e.kind)).toEqual(['connection_fit', 'invite_expected', 'piece_published', 'deadline']);
  });

  it('summarises the day', () => {
    expect(summaryParts(busy).map((p) => p.text)).toEqual(['1 post', '1 comentario', '2 reacciones', '1 invitación aceptada']);
    expect(summaryParts(busy).map((p) => p.tipo)).toEqual(['publicaciones', 'comentarios', 'reacciones', 'red']);
  });

  it('words events and links an uncertain action to its Tu turno card', () => {
    expect(eventSentence(busy.events[1]!)).toBe('Publicaste: Thesis');
    expect(eventSentence(event({ layer: 'publicaciones', kind: 'piece_skipped', title: 'Publicación del día' }))).toBe('Ese día no hubo publicación');
    expect(eventLink(event({ id: 'action_uncertain:abc-1:2026-11-06', layer: 'sistema', kind: 'action_uncertain', title: 'Comentario incierta', link: '/tu-turno' }))).toBe(
      '/tu-turno#turno-uncertain-abc-1',
    );
    expect(pieceIdFromLink('/calendario/pieza/p%201')).toBe('p 1');
    expect(pieceIdFromLink('/personas/c1')).toBeNull();
  });

  it('words activity items', () => {
    expect(itemSentence(item({ capability: 'INT-02', reaction: 'linkedin_celebrate', target: { kind: 'post', name: 'Ana' } }))).toBe('Reaccionaste Celebro al post de Ana');
    expect(itemSentence(item({ capability: 'RED-02', target: { kind: 'person', name: 'Beto' } }))).toBe('Invitaste a Beto (sin nota)');
    expect(itemSentence(item({ capability: 'RED-04', target: { kind: 'person', name: 'Ciro' } }))).toBe('Aceptaste la invitación de Ciro');
  });
});

describe('piece', () => {
  it('says when a piece goes out', () => {
    const context = { today: '2026-11-07', timeZone: 'America/Bogota', now: new Date('2026-11-07T08:40:00Z').getTime() };
    expect(pieceWhen('scheduled', '2026-11-07T14:00:00Z', context)).toBe('Hoy a las 09:00 · sale en 5 h 20 min');
    expect(pieceWhen('published', '2026-11-07T14:00:00Z', { ...context, published: '2026-11-07T14:02:00Z' })).toBe('Salió a las 09:02');
    expect(pieceWhen('blocked', '2026-11-07T14:00:00Z', context)).toBe('Iba a salir a las 09:00');
  });

  it('marks the preparation steps', () => {
    expect(preparationStages('seleccion').map((s) => s.state)).toEqual(['done', 'done', 'done', 'current', 'pending']);
    expect(preparationStages('').map((s) => s.state)).toEqual(['current', 'pending', 'pending', 'pending', 'pending']);
    expect(preparationStages('reparacion').map((s) => s.state)).toEqual(['done', 'done', 'done', 'done', 'current']);
  });

  it('takes the first three lines of the final text', () => {
    expect(firstLines('One.\n\nTwo.\nThree.\nFour.')).toBe('One. Two. Three.');
  });
});
