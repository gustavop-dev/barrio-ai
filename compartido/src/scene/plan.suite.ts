import type { TestAPI } from './testAPI';
import { CORRIDOR_X, CROSS_Y, PLACES, PLAN_HEIGHT, PLAN_WIDTH, planRoute, routeLength, sceneScale, visitPlaceFor, zoneAt } from './plan';
import { CHARACTERS, LIBRARIAN, ROLE_BY_ID, TEAMS, type Point } from './roles';

const axisAligned = (route: readonly Point[]) => route.every((p, i) => i === 0 || p[0] === route[i - 1]![0] || p[1] === route[i - 1]![1]);
const onCorridor = (p: Point) => p[0] === CORRIDOR_X;
const onRoute = (p: Point) => onCorridor(p) || (CROSS_Y as readonly number[]).includes(p[1]);

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

  it('keeps everyone inside the 192×336 plan', () => {
    for (const role of CHARACTERS) {
      for (const [x, y] of role.via) {
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
    expect(sceneScale(1200, 1100)).toBe(3);
    expect(sceneScale(4000, 4000)).toBe(4);
  });
});

}
