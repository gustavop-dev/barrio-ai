import { describe, expect, it } from 'vitest';
import { EventQueue, describeEvent, describeSummary, summaryActor, type OfficeEvent } from './events';

const BASE = Date.parse('2026-11-07T15:00:00Z');
const at = (s: number) => new Date(BASE + s * 1000).toISOString();
const NOW = at(60);

function ev(id: number, tipo: OfficeEvent['tipo'], rol: string, s: number, extra: Partial<OfficeEvent> = {}): OfficeEvent {
  return { id, ts: at(s), tipo, rol, destino: '', detalle: '', ...extra };
}

const ids = (queue: EventQueue) => {
  const out: (string | number)[] = [];
  for (let item = queue.shift(); item; item = queue.shift()) out.push(item.kind === 'event' ? item.event.id : `resumen:${item.summary.total}`);
  return out;
};

describe('EventQueue', () => {
  it('plays events oldest first, whatever order they arrive in', () => {
    const queue = new EventQueue();
    queue.ingest([ev(3, 'entrega', 'copywriter_a', 30), ev(1, 'consulta_biblioteca', 'copywriter_a', 10)], NOW);
    queue.ingest([ev(2, 'publicacion', 'operador_cuenta', 20)], NOW);
    expect(ids(queue)).toEqual([1, 2, 3]);
  });

  it('breaks ties on the same timestamp by id', () => {
    const queue = new EventQueue();
    queue.ingest([ev(11, 'entrega', 'perfil', 10), ev(10, 'consulta_biblioteca', 'perfil', 10)], NOW);
    expect(ids(queue)).toEqual([10, 11]);
  });

  it('never plays the same event twice (pages overlap)', () => {
    const queue = new EventQueue();
    expect(queue.ingest([ev(1, 'consulta_biblioteca', 'perfil', 10)], NOW)).toBe(1);
    expect(queue.ingest([ev(1, 'consulta_biblioteca', 'perfil', 10), ev(2, 'entrega', 'perfil', 12)], NOW)).toBe(1);
    expect(ids(queue)).toEqual([1, 2]);
    expect(queue.ingest([ev(2, 'entrega', 'perfil', 12)], NOW)).toBe(0);
    expect(queue.size).toBe(0);
  });

  it('ignores malformed events and unknown kinds', () => {
    const queue = new EventQueue();
    const added = queue.ingest([null, 'x', { id: 1, ts: 'mañana', tipo: 'entrega', rol: 'perfil' }, { id: 2, ts: at(1), tipo: 'baile', rol: 'perfil' }, ev(3, 'entrega', 'perfil', 2)], NOW);
    expect(added).toBe(1);
    expect(ids(queue)).toEqual([3]);
  });

  it('summarizes when many arrive at once and keeps only the newest to play', () => {
    const queue = new EventQueue({ maxPending: 4, keep: 2 });
    queue.ingest(
      [
        ev(1, 'consulta_biblioteca', 'copywriter_a', 1),
        ev(2, 'entrega', 'copywriter_a', 2, { destino: 'lector_comprador' }),
        ev(3, 'consulta_biblioteca', 'lector_comprador', 3),
        ev(4, 'consulta_biblioteca', 'copywriter_b', 4),
        ev(5, 'entrega', 'lector_comprador', 5, { destino: 'director_editorial' }),
        ev(6, 'publicacion', 'operador_cuenta', 6),
      ],
      NOW,
    );
    const first = queue.shift();
    expect(first?.kind).toBe('summary');
    if (first?.kind !== 'summary') return;
    expect(first.summary.reason).toBe('overflow');
    expect(first.summary.counts).toEqual({ consulta_biblioteca: 3, entrega: 1, publicacion: 0 });
    expect(first.summary.events.map((e) => e.id)).toEqual([1, 2, 3, 4]);
    expect(describeSummary(first.summary)).toBe('Mientras tanto: 3 consultas a la biblioteca y 1 entrega.');
    expect(ids(queue)).toEqual([5, 6]);
  });

  it('summarizes events that are already old instead of walking them (the first page brings 10 minutes)', () => {
    const queue = new EventQueue({ staleMs: 120_000 });
    const now = at(600);
    queue.ingest([ev(1, 'consulta_biblioteca', 'perfil', 10), ev(2, 'publicacion', 'operador_cuenta', 20), ev(3, 'entrega', 'perfil', 590)], now);
    const first = queue.shift();
    expect(first?.kind === 'summary' && first.summary.reason).toBe('backlog');
    expect(first?.kind === 'summary' && describeSummary(first.summary)).toBe('Hace un rato: 1 consulta a la biblioteca y 1 publicación.');
    expect(ids(queue)).toEqual([3]);
  });

  it('keeps accumulating while nobody takes from it (machine paused) and folds the excess into one summary', () => {
    const queue = new EventQueue({ maxPending: 4, keep: 2 });
    for (let i = 1; i <= 10; i++) queue.ingest([ev(i, 'entrega', 'perfil', i)], NOW);
    // Every time more than 4 wait, all but the newest 2 fold into the summary.
    expect(queue.size).toBe(5);
    const first = queue.shift();
    expect(first?.kind === 'summary' && first.summary.total).toBe(6);
    expect(ids(queue)).toEqual([7, 8, 9, 10]);
  });

  it('remembers the newest timestamp for the next poll', () => {
    const queue = new EventQueue();
    queue.ingest([ev(2, 'entrega', 'perfil', 20), ev(1, 'entrega', 'perfil', 10)], NOW);
    expect(queue.lastTs).toBe(at(20));
  });
});

describe('narration', () => {
  it('says who goes where, quoting the detail', () => {
    expect(describeEvent(ev(1, 'consulta_biblioteca', 'copywriter_a', 0, { detalle: 'clase 03' }))).toBe('Copywriter A va a la biblioteca: “clase 03”');
    expect(describeEvent(ev(1, 'consulta_biblioteca', 'analista_barrio_resultados', 0))).toBe('Analista del barrio va a la biblioteca');
    expect(describeEvent(ev(2, 'entrega', 'editor_verificador', 0, { destino: 'operador_cuenta', detalle: 'Etapa verificador terminada' }))).toBe(
      'Editor verificador entrega a Operación: “Etapa verificador terminada”',
    );
    expect(describeEvent(ev(3, 'entrega', 'perfil', 0, { destino: '' }))).toBe('Perfil entrega su trabajo');
    expect(describeEvent(ev(4, 'publicacion', 'operador_cuenta', 0, { detalle: 'Publicación propia' }))).toBe('Operación publica en LinkedIn: “Publicación propia”');
    expect(describeEvent(ev(5, 'consulta_biblioteca', 'quien_sabe', 0))).toBe('El equipo va a la biblioteca');
  });

  it('pluralizes the summary and picks the busiest role for its portrait', () => {
    expect(describeSummary({ reason: 'overflow', counts: { consulta_biblioteca: 1, entrega: 2, publicacion: 3 } })).toBe(
      'Mientras tanto: 1 consulta a la biblioteca, 2 entregas y 3 publicaciones.',
    );
    expect(describeSummary({ reason: 'backlog', counts: { consulta_biblioteca: 0, entrega: 0, publicacion: 1 } })).toBe('Hace un rato: 1 publicación.');
    expect(
      summaryActor({
        reason: 'overflow',
        counts: { consulta_biblioteca: 2, entrega: 1, publicacion: 0 },
        total: 3,
        events: [ev(1, 'consulta_biblioteca', 'perfil', 1), ev(2, 'consulta_biblioteca', 'copywriter_a', 2), ev(3, 'entrega', 'copywriter_a', 3)],
      }),
    ).toBe('copywriter_a');
  });
});
