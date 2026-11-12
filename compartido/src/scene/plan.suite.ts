import type { TestAPI } from './testAPI';
import {
  CORRIDOR_X, CROSS_Y, LIGHT_AREAS, PLACES, PLAN_HEIGHT, PLAN_WIDTH, REST_IDS, REST_SPOTS, lightZoneAt, planRoute, routeLength, sceneScale,
  visitPlaceFor, zoneAt,
} from './plan';
import { CHARACTERS, LIBRARIAN, ROLE_BY_ID, TEAMS, type Point } from './roles';

const axisAligned = (route: readonly Point[]) => route.every((p, i) => i === 0 || p[0] === route[i - 1]![0] || p[1] === route[i - 1]![1]);
const onCorridor = (p: Point) => p[0] === CORRIDOR_X;
const onRoute = (p: Point) => onCorridor(p) || (CROSS_Y as readonly number[]).includes(p[1]);
/** Whether a route ever goes back over the segment it just walked. */
const turnsBack = (route: readonly Point[]) => route.some((b, i) => {
  if (i === 0 || i === route.length - 1) return false;
  const a = route[i - 1]!, c = route[i + 1]!;
  return a[1] === b[1] && b[1] === c[1] && (b[0] - a[0]) * (c[0] - b[0]) < 0
    || a[0] === b[0] && b[0] === c[0] && (b[1] - a[1]) * (c[1] - b[1]) < 0;
});

export function suite({ describe, it, expect }: TestAPI) {
describe('the vertical plan', () => {
  it('starts every seat and visit route on the central corridor and ends a seat route at home', () => {
    for (const role of CHARACTERS) {
      expect(onCorridor(role.via[0]!), role.id).toBe(true);
      expect(role.via[role.via.length - 1], role.id).toEqual(role.home);
      expect(axisAligned(role.via), role.id).toBe(true);
    }
    for (const [id, place] of Object.entries(PLACES)) {
      expect(onCorridor(place.via[0]!), id).toBe(true);
      expect(axisAligned(place.via), id).toBe(true);
    }
  });

  it('keeps everyone inside the plan, the game room included', () => {
    for (const via of [...CHARACTERS.map((role) => role.via), ...REST_IDS.map((id) => REST_SPOTS[id].via)]) {
      for (const [x, y] of via) {
        expect(x).toBeGreaterThan(0);
        expect(x).toBeLessThan(PLAN_WIDTH);
        expect(y).toBeGreaterThan(0);
        expect(y).toBeLessThan(PLAN_HEIGHT);
      }
    }
  });

  it('routes from a seat to the library through the corridors', () => {
    const route = planRoute(ROLE_BY_ID.copywriter_a.via, PLACES.biblioteca1.via);
    expect(route).toEqual([
      [58, 208],
      [58, 178],
      [96, 178],
      [96, 110],
      [32, 110],
      [32, 112],
    ]);
    expect(axisAligned(route)).toBe(true);
    expect(routeLength(route)).toBe(30 + 38 + 68 + 64 + 2);
  });

  it('routes back home from a visit, and joins places on the same cross corridor without detours', () => {
    expect(planRoute(PLACES.barrio.via, ROLE_BY_ID.lector_par.via)).toEqual([
      [128, 290],
      [128, 254],
      [96, 254],
      [140, 254],
      [140, 322],
    ]);
    // Operación stands on the corridor: the door is straight up.
    expect(planRoute(ROLE_BY_ID.operador_cuenta.via, PLACES.puerta.via)).toEqual([
      [96, 58],
      [96, 34],
    ]);
  });

  it('only walks along corridors between the seat and the visit spot', () => {
    for (const role of CHARACTERS) {
      if (role === LIBRARIAN) continue;
      for (const place of Object.values(PLACES)) {
        const route = planRoute(role.via, place.via);
        expect(axisAligned(route)).toBe(true);
        // Every turning point between leaving the seat route and entering the place route is on a corridor.
        const middle = route.slice(role.via.length - 1, route.length - place.via.length + 1);
        expect(middle.every(onRoute), `${role.id} → ${JSON.stringify(place.via)}`).toBe(true);
      }
    }
  });

  it('walks to and from every rest spot along the corridors, never turning back', () => {
    for (const id of REST_IDS) {
      const spot = REST_SPOTS[id];
      expect(onCorridor(spot.via[0]!), id).toBe(true);
      expect(axisAligned(spot.via), id).toBe(true);
      for (const role of CHARACTERS) {
        if (role.service) continue;
        for (const route of [planRoute(role.via, spot.via), planRoute(spot.via, role.via)]) {
          expect(axisAligned(route), `${role.id} ⇄ ${id}`).toBe(true);
          expect(turnsBack(route), `${role.id} ⇄ ${id}: ${JSON.stringify(route)}`).toBe(false);
        }
      }
      for (const other of REST_IDS) expect(turnsBack(planRoute(spot.via, REST_SPOTS[other].via)), `${id} → ${other}`).toBe(false);
    }
  });

  it('lights every seat with its own zone and every rest spot with the game room, the kitchen or the library', () => {
    for (const role of CHARACTERS) expect(lightZoneAt(role.home[0], role.home[1]), role.id).toBe(role.team);
    for (const id of REST_IDS) {
      const [x, y] = REST_SPOTS[id].via[REST_SPOTS[id].via.length - 1]!;
      expect(['juegos', 'relaciones', 'biblioteca'], id).toContain(lightZoneAt(x, y));
    }
    // The light areas cut the plan without gaps or overlaps.
    let covered = 0;
    for (const { box } of LIGHT_AREAS) covered += box[2] * box[3];
    expect(covered).toBe(PLAN_WIDTH * PLAN_HEIGHT);
    expect(lightZoneAt(96, 178)).toBe('pasillo');
    expect(lightZoneAt(96, 400)).toBe('juegos');
  });

  it('hands deliveries over at the receiving team', () => {
    for (const team of TEAMS) expect(PLACES[visitPlaceFor(team.id)]).toBeDefined();
  });

  it('finds the zone under a point: the library or a team', () => {
    expect(zoneAt(40, 60)).toBe('biblioteca');
    expect(zoneAt(96, 50)).toBe('operacion');
    expect(zoneAt(150, 60)).toBe('relaciones');
    expect(zoneAt(40, 150)).toBe('observatorio');
    expect(zoneAt(150, 150)).toBe('estrategia');
    expect(zoneAt(40, 220)).toBe('editorial');
    expect(zoneAt(150, 220)).toBe('revision');
    expect(zoneAt(96, 300)).toBe('barrio');
    expect(zoneAt(96, 178)).toBeNull();
  });

  it('always draws at an integer scale, 2× on phones', () => {
    expect(sceneScale(390, 724)).toBe(2);
    expect(sceneScale(375, 600)).toBe(2);
    expect(sceneScale(360, 600)).toBe(2);
    expect(sceneScale(300, 600)).toBe(1);
    // Wide screens are limited by the height, but never below 2×.
    expect(sceneScale(1200, 780)).toBe(2);
    expect(sceneScale(1200, 1400)).toBe(3);
    expect(sceneScale(4000, 4000)).toBe(4);
  });
});

}
