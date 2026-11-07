// The calendar's state lives in the route params, as in the PWA's URL:
// /calendario?vista=mes|semana|lista&fecha=AAAA-MM-DD&capas=tuyo,publicaciones (plus tipo and no_salio in Lista).
// Defaults are left out (no `fecha` is today, no `vista` is Semana). A link that arrives while the tab is
// mounted (a push, a Tu turno card) replaces the state; changes made here go back to the route.
import type { ActividadTipo } from '@compartido/api/types';
import { isIsoDay } from '@compartido/logic/dates';
import { DEFAULT_VISTA, isLayer, isTipo, isVista, type Vista } from '@compartido/logic/events';
import { router, useLocalSearchParams } from 'expo-router';
import { useCallback, useEffect, useState } from 'react';

export type CalendarParamKey = 'vista' | 'fecha' | 'capas' | 'tipo' | 'no_salio';
export type CalendarRouteParams = Partial<Record<CalendarParamKey, string | string[]>>;

export interface CalendarParams {
  vista: Vista;
  /** null: today. */
  fecha: string | null;
  /** null: every available layer. */
  capas: ReadonlySet<string> | null;
  tipo: ActividadTipo;
  noSalio: boolean;
}

const KEYS: readonly CalendarParamKey[] = ['vista', 'fecha', 'capas', 'tipo', 'no_salio'];

function first(value: string | string[] | undefined): string | null {
  const one = Array.isArray(value) ? value[0] : value;
  return one === undefined || one === '' ? null : one;
}

/** Reads the params like the PWA reads its URL; anything invalid falls back to the default. */
export function readCalendarParams(raw: CalendarRouteParams): CalendarParams {
  const vista = first(raw.vista);
  const fecha = first(raw.fecha);
  const capas = first(raw.capas);
  const tipo = first(raw.tipo);
  return {
    vista: isVista(vista) ? vista : DEFAULT_VISTA,
    fecha: isIsoDay(fecha) ? fecha : null,
    capas: capas === null ? null : new Set(capas.split(',').filter(isLayer)),
    tipo: isTipo(tipo) ? tipo : 'todo',
    noSalio: first(raw.no_salio) === '1',
  };
}

function pick(raw: CalendarRouteParams): Partial<Record<CalendarParamKey, string>> {
  const values: Partial<Record<CalendarParamKey, string>> = {};
  for (const key of KEYS) {
    const value = first(raw[key]);
    if (value !== null) values[key] = value;
  }
  return values;
}

export function useCalendarParams() {
  const route = useLocalSearchParams<CalendarRouteParams>();
  const routeKey = JSON.stringify(pick(route));
  // `routeKey` is the route as last seen: when it changes (a link while the tab was mounted, or the
  // route catching up with our own setParams), the route wins. `dirty`: our change still has to reach it.
  const [state, setState] = useState(() => ({ routeKey, values: pick(route), dirty: false }));
  let values = state.values;
  if (state.routeKey !== routeKey) {
    values = pick(route);
    setState({ routeKey, values, dirty: false });
  }

  useEffect(() => {
    if (!state.dirty) return;
    const routeParams: Record<string, string | undefined> = {};
    for (const key of KEYS) routeParams[key] = state.values[key];
    router.setParams(routeParams);
  }, [state]);

  const update = useCallback((changes: Partial<Record<CalendarParamKey, string | null>>) => {
    setState((current) => {
      const next: CalendarRouteParams = { ...current.values };
      for (const [key, value] of Object.entries(changes) as [CalendarParamKey, string | null][]) {
        if (value === null) delete next[key];
        else next[key] = value;
      }
      return { routeKey: current.routeKey, values: pick(next), dirty: true };
    });
  }, []);

  return { ...readCalendarParams(values), update };
}
