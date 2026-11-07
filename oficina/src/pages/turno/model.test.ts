import { describe, expect, it } from 'vitest';
import { cardFixture, dayAt, factFixture, hoursFromNow, notificacionesFixture, questionCard, turnoFixture } from '../../test/fixtures/turno';
import { groupNotifications, timeLabel } from '../notificaciones/model';
import { buildAnswer } from './QuestionForm';
import {
  activeCards,
  createdText,
  deadlineInfo,
  doneTodaySentence,
  factOrigin,
  groupByPriority,
  normalize,
  priorityOf,
  prioritySummary,
  splitLater,
  toAgent,
} from './model';

const NOW = new Date(2026, 10, 7, 10, 0).getTime();

describe('Tu turno · prioridades', () => {
  it('uses the priority the backend sends', () => {
    expect(priorityOf(cardFixture({ priority: 'cuando_puedas', critical: true }), NOW)).toBe('cuando_puedas');
  });

  it('derives it when missing: critical is urgente, under 48 h or warn is importante, the rest cuando puedas', () => {
    expect(priorityOf(cardFixture({ critical: true }), NOW)).toBe('urgente');
    expect(priorityOf(cardFixture({ tone: 'warn' }), NOW)).toBe('importante');
    expect(priorityOf(cardFixture({ tone: 'info', deadline: hoursFromNow(47, NOW) }), NOW)).toBe('importante');
    expect(priorityOf(cardFixture({ tone: 'info', deadline: hoursFromNow(49, NOW) }), NOW)).toBe('cuando_puedas');
    expect(priorityOf(cardFixture({ tone: 'info' }), NOW)).toBe('cuando_puedas');
  });

  it('orders the old payload by priority, then nearest deadline, then most recent', () => {
    const recentNoDeadline = questionCard({ id: 'a' }, { priority: undefined, created_at: hoursFromNow(-1, NOW) });
    const olderNoDeadline = questionCard({ id: 'b' }, { priority: undefined, created_at: hoursFromNow(-5, NOW) });
    const farDeadline = questionCard({ id: 'c' }, { priority: undefined, deadline: hoursFromNow(100, NOW) });
    const urgent = cardFixture({ id: 'u', critical: true });
    const data = turnoFixture({ alerts: [urgent], questions: [olderNoDeadline, recentNoDeadline, farDeadline] });
    expect(activeCards(data, NOW).map((card) => card.id)).toEqual(['u', 'question:c', 'question:a', 'question:b']);
    // `items` wins when present, in its order.
    expect(activeCards({ ...data, items: [farDeadline] }, NOW).map((card) => card.id)).toEqual(['question:c']);
  });

  it('groups and summarises «1 urgente · 2 importantes · 1 cuando puedas»', () => {
    const groups = groupByPriority(
      [
        cardFixture({ id: '1', priority: 'importante' }),
        cardFixture({ id: '2', priority: 'urgente' }),
        cardFixture({ id: '3', priority: 'importante' }),
        cardFixture({ id: '4', priority: 'cuando_puedas' }),
      ],
      NOW,
    );
    expect(groups.map((g) => [g.priority, g.cards.map((c) => c.id)])).toEqual([
      ['urgente', ['2']],
      ['importante', ['1', '3']],
      ['cuando_puedas', ['4']],
    ]);
    expect(prioritySummary(groups)).toBe('1 urgente · 2 importantes · 1 cuando puedas');
  });

  it('splits `later` into postponed and expired', () => {
    const { postponed, expired } = splitLater([
      questionCard({ id: 'p' }, { state: 'pospuesta' }),
      questionCard({ id: 'e' }, { state: 'caducada' }),
      questionCard({ id: 'legacy', expired: true }, { state: undefined }),
    ]);
    expect(postponed.map((c) => c.id)).toEqual(['question:p']);
    expect(expired.map((c) => c.id)).toEqual(['question:e', 'question:legacy']);
  });
});

describe('Tu turno · textos', () => {
  it('writes the deadline line, in alerta under 24 h', () => {
    expect(deadlineInfo(questionCard({}, { deadline: dayAt(0, 15, 0, NOW) }), NOW)).toEqual({ text: 'Útil antes de las 15:00', soon: true });
    expect(deadlineInfo(cardFixture({ deadline: dayAt(1, 9, 0, NOW) }), NOW)).toEqual({ text: 'Plazo: antes de mañana a las 09:00', soon: true });
    expect(deadlineInfo(cardFixture({ id: 'linkedin_expiring', deadline: hoursFromNow(72, NOW), days_left: 3 } as never), NOW)).toEqual({
      text: 'Plazo: caduca en 3 días',
      soon: false,
    });
    expect(deadlineInfo(cardFixture({ deadline: null }), NOW)).toBeNull();
  });

  it('writes «Creada hace X»', () => {
    expect(createdText(hoursFromNow(-14, NOW), NOW)).toBe('Creada hace 14 h');
    expect(createdText(dayAt(-1, 9, 0, NOW), NOW)).toBe('Creada ayer');
    expect(createdText(dayAt(-3, 9, 0, NOW), NOW)).toBe('Creada hace 3 días');
    expect(createdText(null, NOW)).toBeNull();
  });

  it('summarises the day, leaving out what did not happen', () => {
    expect(doneTodaySentence({ posts: 1, comments: 6, follows: 4 })).toBe('Hoy el equipo publicó 1 post, comentó en 6 y siguió a 4 personas.');
    expect(doneTodaySentence({ invites: 1 })).toBe('Hoy el equipo invitó a 1 persona.');
    expect(doneTodaySentence({})).toBe('Hoy el equipo aún no ha publicado ni interactuado.');
    expect(doneTodaySentence(null)).toBeNull();
  });

  it('names who asked and where a fact came from', () => {
    expect(toAgent('Director editorial')).toBe('al Director editorial');
    expect(toAgent('Perfil')).toBe('a Perfil');
    expect(factOrigin(factFixture({ origin: { kind: 'manual' } }))).toBe('Lo añadiste tú');
    expect(factOrigin(factFixture({ origin: { kind: 'question', agent_label: 'Director editorial' } }))).toBe('Respondiste al Director editorial');
    expect(normalize('Ñandú Pagos')).toBe('nandu pagos');
  });
});

describe('Tu turno · respuestas', () => {
  const ask = (answer_type: 'text' | 'yes_no' | 'choice' | 'number' | 'date') => questionCard({ answer_type, options: ['A', 'B'] }).question!;

  it('builds the body for each answer type, or null while incomplete', () => {
    expect(buildAnswer(ask('text'), '', '  ', true)).toBeNull();
    expect(buildAnswer(ask('text'), '', 'Hola', true)).toEqual({ text: 'Hola', public_use: true });
    expect(buildAnswer(ask('yes_no'), '', 'detalle', false)).toBeNull();
    expect(buildAnswer(ask('yes_no'), 'no', '', false)).toEqual({ value: 'no', public_use: false });
    expect(buildAnswer(ask('choice'), 'B', '', false)).toEqual({ value: 'B', public_use: false });
    expect(buildAnswer(ask('number'), 'doce', '', true)).toBeNull();
    expect(buildAnswer(ask('number'), '12', '', true)).toEqual({ value: '12', public_use: true });
    expect(buildAnswer(ask('date'), '2026-11', '', true)).toBeNull();
    expect(buildAnswer(ask('date'), '2026-11-07', '', true)).toEqual({ value: '2026-11-07', public_use: true });
  });

  it('confirms a proposed value or corrects it', () => {
    const confirm = questionCard({ kind: 'confirm', proposed_value: { texto: 'Founder', uso_publico: true } }).question!;
    expect(buildAnswer(confirm, '', '', true)).toEqual({ accept: true, public_use: true });
    expect(buildAnswer(confirm, '', 'Founder y CEO', true)).toEqual({ text: 'Founder y CEO', public_use: true });
  });
});

describe('Notificaciones · grupos', () => {
  it('puts Próximo first, then Hoy, Ayer and older days, newest first', () => {
    const groups = groupNotifications(notificacionesFixture(), 'todas', Date.now());
    expect(groups.map((g) => g.title).slice(0, 3)).toEqual(['Próximo', 'Hoy', 'Ayer']);
    expect(groups[3]!.title).toMatch(/^[A-ZÁÉÍÓÚ][a-záéíóú]+ \d+ de [a-z]+$/);
    expect(groups.find((g) => g.upcoming)?.items).toHaveLength(1);
  });

  it('keeps only the unread ones with «Sin leer»', () => {
    const groups = groupNotifications(notificacionesFixture(), 'sin_leer', Date.now());
    expect(groups.map((g) => g.title)).toEqual(['Hoy']);
  });

  it('labels the time of what is coming', () => {
    const tomorrow = { ...notificacionesFixture().upcoming[0]!, at: dayAt(1, 9, 0, NOW) };
    expect(timeLabel(tomorrow, true, NOW)).toBe('Mañana 09:00');
    expect(timeLabel({ ...tomorrow, kind: 'invite_expected' }, true, NOW)).toBe('Mañana');
    expect(timeLabel({ ...tomorrow, kind: 'machine_paused_env', at: dayAt(-1, 18, 42, NOW) }, true, NOW)).toBe('Desde ayer, 18:42');
    expect(timeLabel({ ...tomorrow, at: dayAt(0, 8, 5, NOW) }, false, NOW)).toBe('08:05');
  });
});
