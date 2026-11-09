import type { TestAPI } from './testAPI';
import type { Activity } from '../api/types';
import { lookFor, statusesFrom, summarize, summaryText } from './activity';
import { ROLE_IDS } from './roles';

export function suite({ describe, it, expect }: TestAPI) {
describe('activity mapping', () => {
  it('maps each role to its real status', () => {
    const activity: Activity = {
      updated_at: '2026-11-07T15:00:00Z',
      roles: {
        operador_cuenta: { status: 'trabajando', detail: 'Ejecutando una acción aprobada', since: '2026-11-07T14:59:00Z' },
        editor_visual: { status: 'trabajando', detail: 'Preparando foto, infografía o carrusel para la pieza', since: '2026-11-07T14:59:00Z' },
        relaciones_comunidad: { status: 'en_espera', detail: '', since: null },
        conversaciones_inbox: { status: 'diseno', detail: 'Contrato diseñado; aún sin implementar', since: null },
      },
    };
    const statuses = statusesFrom(activity);
    expect(statuses.operador_cuenta).toBe('trabajando');
    expect(statuses.editor_visual).toBe('trabajando');
    expect(statusesFrom(undefined).editor_visual).toBe('desconocido');
    expect(statuses.relaciones_comunidad).toBe('en_espera');
    expect(statuses.conversaciones_inbox).toBe('diseno');
    // A role the endpoint does not describe is «sin datos», never «en espera».
    expect(statuses.perfil).toBe('desconocido');
    expect(Object.keys(statuses).sort()).toEqual([...ROLE_IDS].sort());
  });

  it('reads unknown status values, a missing body and loading as «sin datos»', () => {
    const odd = { updated_at: 'x', roles: { perfil: { status: 'dormido', detail: '', since: null } } } as unknown as Activity;
    expect(statusesFrom(odd).perfil).toBe('desconocido');
    expect(new Set(Object.values(statusesFrom(undefined)))).toEqual(new Set(['desconocido']));
    expect(new Set(Object.values(statusesFrom({ updated_at: 'x' } as unknown as Activity)))).toEqual(new Set(['desconocido']));
  });

  it('summarizes a team, mentioning «sin datos» only when there are any', () => {
    const summary = summarize(['relaciones_comunidad', 'conversaciones_inbox'], { relaciones_comunidad: 'en_espera', conversaciones_inbox: 'diseno' });
    expect(summaryText(summary)).toBe('0 trabajando · 1 en espera · 1 en diseño');
    expect(summaryText(summarize(['perfil', 'posicionamiento'], { perfil: 'trabajando' }))).toBe('1 trabajando · 0 en espera · 0 en diseño · 1 sin datos');
  });

  it('only animates real states and only lets «en espera» take idle walks', () => {
    expect(lookFor('trabajando')).toEqual({ animated: true, lit: true, dimmed: false, idleWalks: false });
    expect(lookFor('en_espera')).toEqual({ animated: true, lit: false, dimmed: false, idleWalks: true });
    expect(lookFor('diseno')).toEqual({ animated: false, lit: false, dimmed: true, idleWalks: false });
    expect(lookFor('desconocido')).toEqual({ animated: false, lit: false, dimmed: false, idleWalks: false });
  });
});

}
