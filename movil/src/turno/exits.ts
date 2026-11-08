// MovTuTurno: how a card leaves Tu turno and how the list and the counters follow, step by step.
//
//   resolved with its button   check in the button, card in 0ff1ce-claro · hold doneHoldMs
//   «Más tarde» button         the card slides right and down, fading · laterSlide
//   swiped                     it already flew off under the finger (right: hold doneHoldMs on the check underneath)
//   then, for all of them      the card collapses and the list closes the gap · collapse
//   then                       it stops counting: the group counter and the top bar badge roll,
//                              «Pospuestas» counts it; an empty group label collapses labelDelayMs later,
//                              and «Nada depende de ti hoy» fades in emptyDelayMs later.
//
// A card only leaves when the backend has confirmed: from the POST until the end, the list holds the
// rows it showed (the backend has usually dropped the card before the POST even resolves) and plays
// these steps on them; then it follows GET /tu-turno again. With reduced motion every step is instant.
import type { TuTurno, TurnoCard, TurnoPriority } from '@compartido/api/types';
import { activeCards, groupByPriority, PRIORITY_LABEL, splitLater } from '@compartido/logic/turno';
import { useQueryClient } from '@tanstack/react-query';
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { keys } from '@/api/queryClient';
import { turnoMotion, turnoTimings } from '@/theme/motion';
import { setHeldTurno } from './heldCount';

// ---------------------------------------------------------------- rows

/** The derived parts of GET /tu-turno that the list and its header share. */
export function pendingView(data: TuTurno | undefined) {
  const cards = data ? activeCards(data) : [];
  const groups = groupByPriority(cards);
  const { postponed, expired } = splitLater(data?.later);
  return { cards, groups, postponed, expired, recent: data?.recent ?? [] };
}

export type PendingView = ReturnType<typeof pendingView>;

export type Group = TurnoPriority | 'caducadas';

export type Row =
  | { key: string; kind: 'label'; group: Group; name: string; count: number; intro?: string }
  | { key: string; kind: 'card'; group: Group; card: TurnoCard; priority: TurnoPriority | null }
  | { key: 'empty'; kind: 'empty' }
  | { key: 'folds'; kind: 'folds'; postponed: number };

const QUESTION_INTRO = 'Lo que respondas pasa a la memoria confirmada: así el equipo puede contar experiencias reales.';

/** The rows of the list: each group's label and cards, the expired ones, then «Nada depende de ti hoy» and the folds. */
export function buildRows(view: PendingView): Row[] {
  const rows: Row[] = [];
  for (const group of view.groups) {
    rows.push({
      key: `label-${group.priority}`,
      kind: 'label',
      group: group.priority,
      name: PRIORITY_LABEL[group.priority],
      count: group.cards.length,
      intro: group.priority === 'cuando_puedas' && group.cards.some((card) => card.question) ? QUESTION_INTRO : undefined,
    });
    for (const card of group.cards) rows.push({ key: card.id, kind: 'card', group: group.priority, card, priority: group.priority });
  }
  // Nothing that counts (expired cards do not, TUR-01): «Nada depende de ti hoy» first, as the PWA, then the expired ones.
  if (!view.groups.length) rows.push({ key: 'empty', kind: 'empty' });
  if (view.expired.length) {
    rows.push({ key: 'label-caducadas', kind: 'label', group: 'caducadas', name: 'Ya no es urgente', count: view.expired.length });
    for (const card of view.expired) rows.push({ key: `caducada-${card.id}`, kind: 'card', group: 'caducadas', card, priority: null });
  }
  const quiet = view.groups.length === 0 && !view.postponed.length && !view.recent.length;
  if (!quiet) rows.push({ key: 'folds', kind: 'folds', postponed: view.postponed.length });
  return rows;
}

/** «1 urgente · 2 importantes · 3 cuando puedas» from the rows that still count. */
export function summaryOf(rows: readonly Row[]): string | null {
  const counts = new Map<TurnoPriority, number>();
  for (const row of rows) if (row.kind === 'label' && row.group !== 'caducadas' && row.count > 0) counts.set(row.group, row.count);
  const parts: string[] = [];
  const urgent = counts.get('urgente');
  const important = counts.get('importante');
  const whenever = counts.get('cuando_puedas');
  if (urgent) parts.push(`${urgent} ${urgent === 1 ? 'urgente' : 'urgentes'}`);
  if (important) parts.push(`${important} ${important === 1 ? 'importante' : 'importantes'}`);
  if (whenever) parts.push(`${whenever} cuando puedas`);
  return parts.length ? parts.join(' · ') : null;
}

// ---------------------------------------------------------------- exits

export type ExitKind = 'done' | 'later';

/** How the card leaves before the gap closes: `check` (its button), `slide` («Más tarde» button), `flown` (swiped), `plain` (straight to the collapse). */
export type ExitLead = 'check' | 'slide' | 'flown' | 'plain';

export type ExitPhase = 'acting' | 'leading' | 'collapsing' | 'gone';

export interface CardExit {
  phase: ExitPhase;
  kind: ExitKind;
  lead: ExitLead;
  /** The control that resolved it (`buttonKey`): it turns into the check. */
  by?: string;
}

export interface ExitHow {
  kind: ExitKind;
  lead: ExitLead;
  by?: string;
}

/** The key of the button that resolves a card, for the check: a card action, or a question's «Responder». */
export const buttonKey = {
  action: (label: string) => `action:${label}`,
  answer: 'answer',
} as const;

/** How long each lead lasts before the collapse (ms). A swiped card already left; on the right it holds the check underneath. */
export function leadMs({ kind, lead }: ExitHow): number {
  if (lead === 'check') return turnoMotion.doneHoldMs;
  if (lead === 'slide') return turnoTimings.laterSlide.duration;
  if (lead === 'flown' && kind === 'done') return turnoMotion.doneHoldMs;
  return 0;
}

export interface ExitState {
  /** The rows held while a card is leaving (null: the list follows GET /tu-turno). */
  frozen: Row[] | null;
  exits: Record<string, CardExit>;
  /** Groups whose label has collapsed. */
  labelsGone: Group[];
  /** Cards sent to «Pospuestas» during this hold (the held «Pospuestas» counts them). */
  postponed: number;
  /** Every card sent to «Pospuestas» on this visit: each one flashes the row (never goes back). */
  flash: number;
  /** The empty state comes after the last card left (it fades in late, once the gap has closed). */
  emptyAfterExit: boolean;
}

export const IDLE: ExitState = { frozen: null, exits: {}, labelsGone: [], postponed: 0, flash: 0, emptyAfterExit: false };

const counts = (exit: CardExit | undefined) => exit?.phase !== 'gone';
const shows = (exit: CardExit | undefined) => !exit || exit.phase === 'acting' || exit.phase === 'leading';

/** The held rows with the exits played on them: cards leave at the collapse, counters drop when they are gone, empty labels go. */
export function playExits(state: ExitState): Row[] | null {
  const { frozen, exits, labelsGone } = state;
  if (!frozen) return null;
  const counted = new Map<Group, number>();
  let left = 0;
  for (const row of frozen) {
    if (row.kind !== 'card' || !counts(exits[row.card.id])) continue;
    counted.set(row.group, (counted.get(row.group) ?? 0) + 1);
    left += 1;
  }
  const hadCards = frozen.some((row) => row.kind === 'card');
  const rows: Row[] = [];
  for (const row of frozen) {
    if (row.kind === 'card') {
      if (shows(exits[row.card.id])) rows.push(row);
    } else if (row.kind === 'label') {
      if (!labelsGone.includes(row.group)) rows.push({ ...row, count: counted.get(row.group) ?? 0 });
    } else if (row.kind === 'folds') {
      rows.push({ ...row, postponed: row.postponed + state.postponed });
    } else {
      rows.push(row);
    }
  }
  if (hadCards && left === 0 && !rows.some((row) => row.kind === 'empty')) {
    const folds = rows.findIndex((row) => row.kind === 'folds');
    rows.splice(folds < 0 ? rows.length : folds, 0, { key: 'empty', kind: 'empty' });
  }
  if (state.postponed && !rows.some((row) => row.kind === 'folds')) rows.push({ key: 'folds', kind: 'folds', postponed: state.postponed });
  return rows;
}

/** Groups that still show a label but no longer count any card. */
export function emptyGroups(state: ExitState): Group[] {
  const rows = playExits(state) ?? [];
  return rows.flatMap((row) => (row.kind === 'label' && row.count === 0 ? [row.group] : []));
}

/** Cards the backend no longer lists but the list still counts (the top bar badge keeps them). */
export function heldCards(state: ExitState, data: TuTurno | undefined): { count: number; urgent: number } {
  if (!state.frozen || !data) return { count: 0, urgent: 0 };
  const listed = listedIds(data);
  let count = 0;
  let urgent = 0;
  for (const row of state.frozen) {
    if (row.kind !== 'card' || row.priority === null || !counts(state.exits[row.card.id]) || listed.has(row.card.id)) continue;
    count += 1;
    if (row.priority === 'urgente') urgent += 1;
  }
  return { count, urgent };
}

/** The cards GET /tu-turno lists on the page: active and expired. */
export function listedIds(data: TuTurno): Set<string> {
  return new Set([...activeCards(data), ...splitLater(data.later).expired].map((card) => card.id));
}

// ---------------------------------------------------------------- the hook and its context

export interface TurnoExits {
  /** A card's POST starts: the list holds still until the card has left (or the POST failed). */
  begin: (id: string) => void;
  /** The backend confirmed: the card leaves this way, if GET /tu-turno no longer lists it. */
  resolve: (id: string, how: ExitHow) => void;
  /** The POST failed: the card stays. */
  cancel: (id: string) => void;
}

const NOOP: TurnoExits = { begin: () => undefined, resolve: () => undefined, cancel: () => undefined };

export const TurnoExitsContext = createContext<TurnoExits>(NOOP);

export function useTurnoExitsApi(): TurnoExits {
  return useContext(TurnoExitsContext);
}

/** Runs the exits of Tu turno over `rows` (built from GET /tu-turno): returns the rows to show and the API for the cards. */
export function useTurnoExits(rows: Row[], reduced: boolean) {
  const client = useQueryClient();
  const [state, setState] = useState<ExitState>(IDLE);
  const current = useRef<ExitState>(IDLE);
  const live = useRef(rows);
  const timers = useRef(new Set<ReturnType<typeof setTimeout>>());
  const pendingLabels = useRef(0);
  const motion = useRef(reduced);

  useEffect(() => {
    live.current = rows;
    motion.current = reduced;
  });

  const update = useCallback((change: (state: ExitState) => ExitState) => {
    current.current = change(current.current);
    setState(current.current);
  }, []);

  const after = useCallback((ms: number, run: () => void) => {
    if (ms <= 0) {
      run();
      return;
    }
    const timer = setTimeout(() => {
      timers.current.delete(timer);
      run();
    }, ms);
    timers.current.add(timer);
  }, []);

  /** Everything has left and the labels have collapsed: follow GET /tu-turno again. */
  const settle = useCallback(() => {
    const { exits } = current.current;
    if (pendingLabels.current > 0 || Object.values(exits).some((exit) => exit.phase !== 'gone')) return;
    update((state) => ({ ...IDLE, flash: state.flash, emptyAfterExit: state.emptyAfterExit }));
  }, [update]);

  const setPhase = useCallback(
    (id: string, phase: ExitPhase) => update((state) => (state.exits[id] ? { ...state, exits: { ...state.exits, [id]: { ...state.exits[id]!, phase } } } : state)),
    [update],
  );

  const gone = useCallback(
    (id: string) => {
      const exit = current.current.exits[id];
      if (!exit) return;
      update((state) => {
        const later = exit.kind === 'later' ? 1 : 0;
        const next = { ...state, exits: { ...state.exits, [id]: { ...exit, phase: 'gone' as const } }, postponed: state.postponed + later, flash: state.flash + later };
        const rows = playExits(next) ?? [];
        return { ...next, emptyAfterExit: next.emptyAfterExit || rows.some((row) => row.kind === 'empty') };
      });
      const labels = emptyGroups(current.current).filter((group) => !current.current.labelsGone.includes(group));
      if (labels.length) {
        pendingLabels.current += 1;
        after(motion.current ? 0 : turnoMotion.labelDelayMs, () => {
          pendingLabels.current -= 1;
          update((state) => ({ ...state, labelsGone: [...state.labelsGone, ...labels.filter((group) => !state.labelsGone.includes(group))] }));
          settle();
        });
      }
      settle();
    },
    [after, settle, update],
  );

  const begin = useCallback(
    (id: string) =>
      update((state) => ({
        ...state,
        frozen: state.frozen ?? live.current,
        emptyAfterExit: state.frozen ? state.emptyAfterExit : false,
        exits: { ...state.exits, [id]: { phase: 'acting', kind: 'done', lead: 'plain' } },
      })),
    [update],
  );

  const cancel = useCallback(
    (id: string) => {
      update((state) => {
        const exits = { ...state.exits };
        delete exits[id];
        return { ...state, exits };
      });
      settle();
    },
    [settle, update],
  );

  const resolve = useCallback(
    (id: string, how: ExitHow) => {
      const data = client.getQueryData<TuTurno>(keys.tuTurno);
      if (!current.current.exits[id] || (data && listedIds(data).has(id))) {
        cancel(id);
        return;
      }
      update((state) => ({ ...state, exits: { ...state.exits, [id]: { ...how, phase: 'acting' } } }));
      if (motion.current) {
        gone(id);
        return;
      }
      const lead = leadMs(how);
      if (lead > 0) setPhase(id, 'leading');
      after(lead, () => {
        setPhase(id, 'collapsing');
        after(turnoTimings.collapse.duration, () => gone(id));
      });
    },
    [after, cancel, client, gone, setPhase, update],
  );

  useEffect(() => {
    const pending = timers.current;
    return () => {
      for (const timer of pending) clearTimeout(timer);
      pending.clear();
      setHeldTurno({ count: 0, urgent: 0 });
    };
  }, []);

  const api = useMemo<TurnoExits>(() => ({ begin, resolve, cancel }), [begin, resolve, cancel]);
  return { state, rows: playExits(state) ?? rows, api };
}

/** Publishes the cards the list still counts but GET /tu-turno no longer lists, for the top bar badge. */
export function usePublishHeld(state: ExitState, data: TuTurno | undefined): void {
  const { count, urgent } = heldCards(state, data);
  useEffect(() => {
    setHeldTurno({ count, urgent });
  }, [count, urgent]);
}

