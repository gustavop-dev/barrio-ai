// MovEntrada: from the login into the Oficina, once, right after a successful login (never when the
// app opens with a session already there). The button already says «Entrando…» while the server
// answers; then, from that moment (ms):
//
//   0     the doorway darkens and the door leaf folds to half on its hinge,
//   80    and to an eighth;
//   160   the picture jumps to 2× on the top of the door, and the form and the tagline leave
//         (TOK.fast, EASE_IN, the form dropping 16 points);
//   310   the picture jumps to 3×;
//   460   the login fades into the live Oficina underneath (TOK.base, EASE_OUT).
//
// The zoom and the leaf jump in integer steps, never tween, so the pixels stay crisp. With reduced
// motion the login only crossfades into the Oficina. Every value comes from theme/motion.ts.
import { useCallback, useState } from 'react';
import { runOnJS, useSharedValue, withDelay, withSequence, withTiming } from 'react-native-reanimated';
import { crossfade, entrada, navTiming } from '@/theme/motion';
import type { DoorValues } from './PixelDoor';

export interface Entrada {
  door: DoorValues;
  /** 0 → 1 while the form and the tagline leave. */
  leaving: DoorValues['zoom'];
  /** The login's opacity: 1 → 0 as it fades into the Oficina. */
  shown: DoorValues['zoom'];
  /** Whether the entrance started (the login no longer takes touches). */
  running: boolean;
  start: () => void;
}

/** The entrance's timeline; `onDone` runs when the login has faded out (also if it was cut short). */
export function useEntrada({ reduced, onDone }: { reduced: boolean; onDone: () => void }): Entrada {
  const zoom = useSharedValue(1);
  const leaf = useSharedValue(1);
  const hole = useSharedValue(0);
  const leaving = useSharedValue(0);
  const shown = useSharedValue(1);
  const [running, setRunning] = useState(false);

  const start = useCallback(() => {
    setRunning(true);
    const done = () => {
      'worklet';
      runOnJS(onDone)();
    };
    if (reduced) {
      shown.set(withTiming(0, crossfade('entradaFade'), done));
      return;
    }
    const cut = navTiming('entradaCut');
    hole.set(withTiming(1, cut));
    leaf.set(withSequence(withTiming(entrada.leafHalf, cut), withDelay(entrada.leafStepMs, withTiming(entrada.leafOpen, cut))));
    zoom.set(withSequence(withDelay(entrada.zoom2Ms, withTiming(entrada.zoom2, cut)), withDelay(entrada.zoom3Ms - entrada.zoom2Ms, withTiming(entrada.zoom3, cut))));
    leaving.set(withDelay(entrada.formOutMs, withTiming(1, navTiming('entradaFormOut'))));
    shown.set(withDelay(entrada.fadeMs, withTiming(0, navTiming('entradaFade'), done)));
  }, [reduced, onDone, hole, leaf, zoom, leaving, shown]);

  return { door: { zoom, leaf, hole }, leaving, shown, running, start };
}
