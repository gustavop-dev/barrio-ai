import { describe, expect, it } from 'vitest';
import type { Activity, RoleStatus } from '../api/types';
import { ROLES, ROLE_BY_ID, ROLE_IDS, TEAMS, WALKERS, rolesOfTeam, type RoleId } from './roles';
import { actorsAt, poseFor, statusesFrom, summarize, walkersAt, type StatusMap } from './simulation';

function activity(roles: Partial<Record<RoleId, RoleStatus>>): Activity {
  return {
    updated_at: '2026-11-06T20:00:00Z',
    roles: Object.fromEntries(Object.entries(roles).map(([id, status]) => [id, { status, detail: '', since: null }])),
  };
}

function all(status: RoleStatus): StatusMap {
  return statusesFrom(activity(Object.fromEntries(ROLE_IDS.map((id) => [id, status]))));
}

describe('roles of the office', () => {
  it('places the 16 contract roles, including the three new ones in their teams', () => {
    expect(ROLES.map((r) => r.id).sort()).toEqual([...ROLE_IDS].sort());
    expect(rolesOfTeam('relaciones').map((r) => r.id)).toEqual(['relaciones_comunidad', 'conversaciones_inbox']);
    expect(rolesOfTeam('operacion').map((r) => r.id)).toEqual(['operador_cuenta']);
    expect(ROLE_BY_ID.operador_cuenta.service).toBe(true);
    expect(TEAMS.filter((t) => t.isNew).map((t) => t.id)).toEqual(['relaciones', 'operacion']);
  });

  it('gives every character its own spot on the floor', () => {
    for (const role of ROLES) {
      const [x, y] = role.home;
      expect(x).toBeGreaterThan(24);
      expect(x).toBeLessThan(450);
      expect(y).toBeGreaterThan(56);
      expect(y).toBeLessThan(289);
      for (const other of ROLES) {
        if (other === role) continue;
        expect(Math.hypot(other.home[0] - x, other.home[1] - y)).toBeGreaterThanOrEqual(25);
      }
      const team = TEAMS.find((t) => t.id === role.team)!;
      const [bx, by, bw, bh] = team.box;
      expect(x >= bx && x <= bx + bw && y >= by - 30 && y <= by + bh + 30).toBe(true);
    }
  });
});

describe('real activity drives each character', () => {
  it('marks roles missing from the response as unknown', () => {
    const statuses = statusesFrom(activity({ operador_cuenta: 'trabajando' }));
    expect(statuses.operador_cuenta).toBe('trabajando');
    expect(statuses.posicionamiento).toBe('desconocido');
    expect(statusesFrom(null).perfil).toBe('desconocido');
  });

  it('maps trabajando to the reading (work) animation, en_espera to idle and diseno to a faded still figure', () => {
    const working = poseFor(ROLE_BY_ID.posicionamiento, 'trabajando');
    expect(working).toMatchObject({ action: 'reading', animated: true, dimmed: false, tag: null });

    const waiting = poseFor(ROLE_BY_ID.posicionamiento, 'en_espera');
    expect(waiting).toMatchObject({ action: 'idle_anim', animated: true, dimmed: false, tag: null });

    const design = poseFor(ROLE_BY_ID.relaciones_comunidad, 'diseno');
    expect(design).toMatchObject({ action: 'idle_anim', animated: false, dimmed: true, tag: 'en diseño' });

    // No data: no animation at all, nothing is simulated.
    expect(poseFor(ROLE_BY_ID.perfil, 'desconocido')).toMatchObject({ animated: false, dimmed: false, tag: null });
  });

  it('falls back to idle for the one sheet without a reading animation', () => {
    expect(ROLE_BY_ID.lector_par.sprite).toBe(11);
    expect(poseFor(ROLE_BY_ID.lector_par, 'trabajando')).toMatchObject({ action: 'idle_anim', animated: true });
  });

  it('builds actors from statuses with the right pose', () => {
    const statuses = statusesFrom(
      activity({ operador_cuenta: 'trabajando', conversaciones_inbox: 'en_espera', relaciones_comunidad: 'diseno' }),
    );
    const actors = actorsAt(0, statuses);
    const byRole = Object.fromEntries(actors.map((a) => [a.role, a]));
    expect(byRole.operador_cuenta).toMatchObject({ action: 'reading', animated: true, dimmed: false });
    expect(byRole.conversaciones_inbox).toMatchObject({ action: 'idle_anim', animated: true, dimmed: false });
    expect(byRole.relaciones_comunidad).toMatchObject({ dimmed: true, tag: 'en diseño', animated: false });
    expect(summarize(['relaciones_comunidad', 'conversaciones_inbox', 'operador_cuenta'], statuses)).toEqual({
      trabajando: 1,
      en_espera: 1,
      diseno: 1,
      desconocido: 0,
    });
  });

  it('lets only waiting characters take the ambient strolls', () => {
    const ms = 6000 + 4000; // first cycle, during the outbound trip
    const [first] = walkersAt(ms);
    expect(first).toBe(WALKERS[0]);

    const waiting = actorsAt(ms, all('en_espera')).find((a) => a.role === first)!;
    expect(waiting.away).toBe(true);
    expect(waiting.action).toBe('run');

    for (const status of ['trabajando', 'diseno'] as const) {
      const still = actorsAt(ms, all(status)).find((a) => a.role === first)!;
      expect(still.away).toBe(false);
      expect([still.x, still.y]).toEqual([...ROLE_BY_ID[first!].home]);
    }
    expect(actorsAt(ms, statusesFrom(null)).some((a) => a.away)).toBe(false);
  });

  it('never moves the new roles from their seats', () => {
    for (let ms = 0; ms < 65000 * 16; ms += 5000) {
      for (const actor of actorsAt(ms, all('en_espera'))) {
        if (['relaciones_comunidad', 'conversaciones_inbox', 'operador_cuenta'].includes(actor.role)) expect(actor.away).toBe(false);
      }
    }
  });
});
