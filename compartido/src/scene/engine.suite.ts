import type { TestAPI } from './testAPI';
import type { SceneStatus, StatusMap } from './activity';
import { AMBIENT_EVERY, OfficeEngine } from './engine';
import type { OfficeEvent } from './events';
import { ROLES, ROLE_IDS, type CharacterId, type RoleId } from './roles';

const BASE = Date.parse('2026-11-07T15:00:00Z');
const at = (s: number) => new Date(BASE + s * 1000).toISOString();
const NOW = at(30);

function ev(id: number, tipo: OfficeEvent['tipo'], rol: string, extra: Partial<OfficeEvent> = {}): OfficeEvent {
  return { id, ts: at(id), tipo, rol, destino: '', detalle: '', ...extra };
}

function all(status: SceneStatus, overrides: StatusMap = {}): StatusMap {
  return { ...Object.fromEntries(ROLE_IDS.map((id) => [id, status])), ...overrides };
}

function engine(statuses: StatusMap = all('trabajando')) {
  const e = new OfficeEngine({ wallClock: () => 0 });
  e.setStatuses(statuses);
  return e;
}

const atHome = (e: OfficeEngine, id: CharacterId) => {
  const a = e.byId[id];
  return a.x === a.role.home[0] && a.y === a.role.home[1] && !a.away && a.path === null;
};

/** Advances in 100 ms steps until `done` holds (or `limit` ms pass). Returns the elapsed ms. */
function until(e: OfficeEngine, done: () => boolean, limit = 60_000): number {
  let t = 0;
  while (!done() && t < limit) {
    e.advance(100);
    t += 100;
  }
  if (!done()) throw new Error(`no ocurrió en ${limit} ms`);
  return t;
}

function narrations(e: OfficeEngine): string[] {
  const seen: string[] = [];
  let last: number | null = null;
  e.subscribe(() => {
    const now = e.getSnapshot().now;
    if (now && now.key !== last) {
      last = now.key;
      seen.push(now.text);
    }
  });
  return seen;
}

export function suite({ describe, it, expect }: TestAPI) {
describe('OfficeEngine · library visits', () => {
  it('walks to the library, the librarian fetches a book from the shelf, and the visitor reads and goes back', () => {
    const e = engine();
    e.ingest([ev(1, 'consulta_biblioteca', 'copywriter_a', { destino: 'biblioteca', detalle: 'clase 03' })], NOW);
    expect(e.now?.text).toBe('Copywriter A va a la biblioteca: “clase 03”');
    expect(e.now?.role).toBe('copywriter_a');
    const visitor = e.byId.copywriter_a;
    const librarian = e.byId.bibliotecario;
    expect(visitor.busy).toBe(true);
    expect(visitor.path).not.toBeNull();
    expect(e.getSnapshot().doing.copywriter_a).toBe('Consultando la biblioteca: “clase 03”');

    until(e, () => visitor.x === 32 && visitor.y === 112 && visitor.path === null);
    expect(visitor.bubble?.icon).toBe('pregunta');
    until(e, () => librarian.y === 66 && librarian.path === null);
    expect(e.statusOf('bibliotecario')).toBe('trabajando');
    until(e, () => visitor.reading);
    expect(atHome(e, 'bibliotecario')).toBe(true);
    until(e, () => !visitor.busy);
    expect(atHome(e, 'copywriter_a')).toBe(true);
    expect(librarian.busy).toBe(false);
    expect(e.statusOf('bibliotecario')).toBe('en_espera');
    const feed = e.getSnapshot().feed;
    expect(feed.find((f) => f.role === 'copywriter_a')?.text).toBe('Copywriter A va a la biblioteca: “clase 03”');
    expect(feed.find((f) => f.role === 'bibliotecario')?.text).toBe('Atiende a Copywriter A: “clase 03”');
  });

  it('lets two visitors use the two counter spots while the librarian serves them in turn', () => {
    const e = engine();
    e.ingest([ev(1, 'consulta_biblioteca', 'copywriter_a'), ev(2, 'consulta_biblioteca', 'copywriter_b')], NOW);
    const a = e.byId.copywriter_a;
    const b = e.byId.copywriter_b;
    until(e, () => b.busy);
    until(e, () => !a.busy && !b.busy, 90_000);
    expect(atHome(e, 'copywriter_a') && atHome(e, 'copywriter_b') && atHome(e, 'bibliotecario')).toBe(true);
  });
});

describe('OfficeEngine · queue', () => {
  it('starts plays in order, two at most, a moment apart', () => {
    const e = engine();
    const said = narrations(e);
    e.ingest(
      [
        ev(1, 'consulta_biblioteca', 'analista_barrio_resultados'),
        ev(2, 'entrega', 'perfil', { destino: 'posicionamiento' }),
        ev(3, 'publicacion', 'operador_cuenta'),
      ],
      NOW,
    );
    expect(said).toEqual(['Analista del barrio va a la biblioteca']);
    until(e, () => said.length === 2);
    expect(said[1]).toBe('Perfil entrega a Posicionamiento');
    // The third waits until one of the two running plays ends.
    e.advance(2_000);
    expect(said).toHaveLength(2);
    until(e, () => said.length === 3);
    expect(said[2]).toBe('Operación publica en LinkedIn');
  });

  it('keeps a role’s events in order: the delivery waits until it is back from the library', () => {
    const e = engine();
    const said = narrations(e);
    const a = e.byId.copywriter_a;
    const where: [number, number][] = [];
    e.subscribe(() => {
      if (where.length < said.length) where.push([a.x, a.y]);
    });
    e.ingest([ev(1, 'consulta_biblioteca', 'copywriter_a'), ev(2, 'entrega', 'copywriter_a', { destino: 'lector_comprador' })], NOW);
    e.advance(5_000);
    expect(said).toEqual(['Copywriter A va a la biblioteca']);
    until(e, () => said.length === 2);
    expect(said[1]).toBe('Copywriter A entrega a Lector comprador');
    // The delivery started from the seat, once the visit had ended.
    expect(where[1]).toEqual([...a.role.home]);
  });

  it('carries the sheet to the receiving team, they talk, and it comes back', () => {
    const e = engine();
    e.ingest([ev(1, 'entrega', 'copywriter_a', { destino: 'lector_comprador', detalle: 'Etapa redactor terminada' })], NOW);
    const a = e.byId.copywriter_a;
    until(e, () => a.x === 128 && a.y === 290 && a.path === null);
    expect(a.bubble?.icon).toBe('hoja');
    until(e, () => e.byId.lector_comprador.bubble?.icon === 'charla');
    until(e, () => !a.busy);
    expect(atHome(e, 'copywriter_a')).toBe(true);
  });

  it('takes Operación out of the door and back for a publication', () => {
    const e = engine();
    e.ingest([ev(1, 'publicacion', 'operador_cuenta', { destino: 'linkedin', detalle: 'Publicación propia' })], NOW);
    const o = e.byId.operador_cuenta;
    until(e, () => o.y === 34);
    until(e, () => o.alpha === 0);
    until(e, () => !o.busy);
    expect(o.alpha).toBe(1);
    expect(atHome(e, 'operador_cuenta')).toBe(true);
  });

  it('summarizes a burst and only walks the newest events', () => {
    const e = engine();
    const said = narrations(e);
    const burst = [1, 2, 3, 4, 5, 6].map((id) => ev(id, 'consulta_biblioteca', ROLES[id]!.id));
    e.ingest(burst, NOW);
    expect(said[0]).toBe('Mientras tanto: 4 consultas a la biblioteca.');
    expect(e.byId[ROLES[1]!.id].busy).toBe(false);
    until(e, () => said.length === 2);
    expect(said[1]).toBe(`${ROLES[5]!.short} va a la biblioteca`);
    // Summarized events still appear in each role's «Lo último que hizo».
    expect(e.getSnapshot().feed.map((f) => f.role)).toContain(ROLES[1]!.id);
  });

  it('only narrates old events and events of unknown roles: nobody walks', () => {
    const e = engine();
    e.ingest([{ ...ev(1, 'consulta_biblioteca', 'perfil'), ts: at(-600) }], NOW);
    expect(e.now?.text).toBe('Hace un rato: 1 consulta a la biblioteca.');
    e.advance(3_000);
    e.ingest([ev(40, 'consulta_biblioteca', 'quien_sabe')], at(45));
    expect(e.now?.text).toBe('El equipo va a la biblioteca');
    e.advance(5_000);
    expect(e.actors.every((a) => !a.busy && !a.away)).toBe(true);
  });
});

describe('OfficeEngine · paused machine and stillness', () => {
  it('freezes everything while the machine is paused; events wait and play when it resumes', () => {
    const e = engine();
    e.setPaused(true);
    e.ingest([ev(1, 'consulta_biblioteca', 'copywriter_a')], NOW);
    expect(e.now).toBeNull();
    e.advance(10_000);
    expect(e.clock).toBe(0);
    expect(atHome(e, 'copywriter_a')).toBe(true);
    expect(e.queue.size).toBe(1);

    e.setPaused(false);
    e.advance(16);
    expect(e.now?.text).toBe('Copywriter A va a la biblioteca');
    expect(e.byId.copywriter_a.busy).toBe(true);
  });

  it('stops a walker where it is when the machine pauses mid-walk', () => {
    const e = engine();
    e.ingest([ev(1, 'consulta_biblioteca', 'lector_par')], NOW);
    const a = e.byId.lector_par;
    e.advance(1_500);
    const frozen = { x: a.x, y: a.y };
    expect(atHome(e, 'lector_par')).toBe(false);
    e.setPaused(true);
    e.advance(5_000);
    expect({ x: a.x, y: a.y }).toEqual(frozen);
    e.setPaused(false);
    e.advance(500);
    expect({ x: a.x, y: a.y }).not.toEqual(frozen);
  });

  it('summarizes what piled up during a long pause', () => {
    const e = engine();
    e.setPaused(true);
    for (let i = 1; i <= 9; i++) e.ingest([ev(i, 'entrega', 'perfil', { destino: 'posicionamiento' })], NOW);
    e.setPaused(false);
    e.advance(16);
    expect(e.now?.text).toBe('Mientras tanto: 6 entregas.');
  });

  it('does not play anything while the activity is unknown (frozen)', () => {
    const e = engine();
    e.setFrozen(true);
    e.ingest([ev(1, 'publicacion', 'operador_cuenta')], NOW);
    e.advance(5_000);
    expect(e.now).toBeNull();
    expect(atHome(e, 'operador_cuenta')).toBe(true);
  });

  it('with reduced motion only narrates: nobody walks, and turning it on sends everyone home', () => {
    const e = engine();
    e.ingest([ev(1, 'consulta_biblioteca', 'copywriter_a')], NOW);
    e.advance(1_000);
    expect(atHome(e, 'copywriter_a')).toBe(false);
    e.setStill(true);
    expect(atHome(e, 'copywriter_a')).toBe(true);
    expect(e.byId.copywriter_a.busy).toBe(false);
    e.ingest([ev(2, 'publicacion', 'operador_cuenta')], NOW);
    expect(e.now?.text).toBe('Operación publica en LinkedIn');
    expect(atHome(e, 'operador_cuenta')).toBe(true);
    expect(e.activeTasks).toBe(0);
  });
});

describe('OfficeEngine · idle behaviour', () => {
  const awayIds = (e: OfficeEngine) => e.actors.filter((a) => a.away || a.bubble).map((a) => a.id);

  it('never moves anyone without an event when nobody is «en espera»', () => {
    for (const statuses of [all('trabajando'), all('diseno'), {}]) {
      const e = engine(statuses);
      for (let t = 0; t < AMBIENT_EVERY * 4; t += 500) {
        e.advance(500);
        expect(awayIds(e)).toEqual([]);
      }
    }
  });

  it('lets only roles «en espera» go for a coffee or chat, never services', () => {
    const waiting: RoleId[] = ['posicionamiento', 'perfil', 'operador_cuenta'];
    const e = engine(all('trabajando', Object.fromEntries(waiting.map((id) => [id, 'en_espera']))));
    const moved = new Set<string>();
    for (let t = 0; t < AMBIENT_EVERY * 5; t += 250) {
      e.advance(250);
      for (const id of awayIds(e)) moved.add(id);
    }
    expect(moved.size).toBeGreaterThan(0);
    for (const id of moved) expect(['posicionamiento', 'perfil']).toContain(id);
  });

  it('keeps idle walks out of the way while events play', () => {
    const e = engine(all('en_espera'));
    for (let i = 0; i < 12; i++) e.ingest([ev(100 + i, 'entrega', 'operador_cuenta', { destino: 'director_editorial', ts: at(100 + i) })], at(100 + i));
    const extra = new Set<string>();
    for (let t = 0; t < 30_000; t += 250) {
      e.advance(250);
      for (const a of e.actors) if (a.away && a.id !== 'operador_cuenta') extra.add(a.id);
    }
    expect([...extra]).toEqual([]);
  });
});

describe('OfficeEngine · reads', () => {
  it('finds the front-most character under a point', () => {
    const e = engine();
    expect(e.hit(58, 200)).toBe('copywriter_a');
    expect(e.hit(42, 70)).toBe('bibliotecario');
    expect(e.hit(2, 2)).toBeNull();
  });

  it('gives the librarian no status until the activity is known', () => {
    const e = new OfficeEngine();
    expect(e.statusOf('bibliotecario')).toBe('desconocido');
    e.setStatuses(all('desconocido'));
    expect(e.statusOf('bibliotecario')).toBe('desconocido');
    e.setStatuses(all('en_espera'));
    expect(e.statusOf('bibliotecario')).toBe('en_espera');
  });
});

}
