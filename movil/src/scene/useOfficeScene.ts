import { useEffect, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { runOnJS, runOnUI, useAnimatedReaction, useFrameCallback, useSharedValue } from 'react-native-reanimated';
import type { StatusMap } from '@compartido/scene/activity';
import type { OficinaEventos } from '@compartido/api/oficina';
import { createScene, ingestScene, pumpScene, receiveSceneCapture, sceneSnapshot, setSceneStill } from '@compartido/scene/runtime';
import { officeFrames, officeMotion } from '@/theme/motion';
import { advanceFrame } from './frame';
import { subscribeCaptureReceipts } from './captureReceipts';

function reportFrames(frames: number, meanDelta: number, maxDelta: number, slow: number, meanWork: number) {
  console.info('[Oficina/UI]', { frames, meanDeltaMs: meanDelta, maxDeltaMs: maxDelta, overBudget: slow, meanSimulationMs: meanWork });
}
export function useOfficeScene({ active, live, paused, reduced, statuses, page, covered = false }: {
  active: boolean; live: boolean; paused: boolean; reduced: boolean; statuses: StatusMap; page?: OficinaEventos;
  /** Something covers the whole scene (the capture sheet, a panel at full height): its clock stops, nothing redraws. */
  covered?: boolean;
}) {
  const client = useQueryClient();
  const [initial] = useState(() => createScene({ frozen: true, still: reduced }, officeMotion));
  const scene = useSharedValue(initial);
  const enabled = useSharedValue(false);
  const clock = useSharedValue({ remainder: 0 });
  const stats = useSharedValue({ count: 0, sum: 0, max: 0, slow: 0, work: 0 });
  const [snapshot, setSnapshot] = useState(() => sceneSnapshot(initial));
  useAnimatedReaction(() => scene.value.version, (version, previous) => {
    if (version !== previous) runOnJS(setSnapshot)(sceneSnapshot(scene.value));
  });
  useEffect(() => {
    runOnUI(() => {
      enabled.value = active;
      clock.value.remainder = 0;
      scene.modify((s) => {
        s.statuses = statuses; s.paused = paused; s.frozen = !live || !active; s.wallTime = Date.now();
        setSceneStill(s, reduced); pumpScene(s); s.version++;
        return s;
      });
    })();
  }, [active, live, paused, reduced, statuses, scene, enabled, clock]);
  useEffect(() => {
    if (!page) return;
    runOnUI(() => {
      scene.modify((s) => { s.wallTime = Date.now(); ingestScene(s, page.events, page.now); return s; });
    })();
  }, [page, scene]);
  useEffect(() => subscribeCaptureReceipts(client, () => {
    runOnUI(() => {
      scene.modify((s) => { s.wallTime = Date.now(); receiveSceneCapture(s); return s; });
    })();
  }), [client, scene]);
  const frame = useFrameCallback(({ timeSincePreviousFrame: delta }) => {
    const started = __DEV__ ? performance.now() : 0;
    scene.modify((s) => {
      s.wallTime = Date.now();
      advanceFrame(s, clock.value, delta, enabled.value);
      return s;
    });
    if (__DEV__ && delta !== null) {
      const p = stats.value;
      p.count++; p.sum += delta; p.max = Math.max(p.max, delta); p.work += performance.now() - started;
      if (delta > officeFrames.slowFrameMs) p.slow++;
      if (p.count >= officeFrames.reportFrames) {
        runOnJS(reportFrames)(p.count, p.sum / p.count, p.max, p.slow, p.work / p.count);
        p.count = 0; p.sum = 0; p.max = 0; p.slow = 0; p.work = 0;
      }
    }
  }, false);
  // While covered the frame callback stops: the Skia scene stops redrawing (battery on the phone, and the software GPU
  // of the QA emulator) and its clock waits; events still queue and play once it shows again.
  useEffect(() => {
    frame.setActive(active && live && !paused && !reduced && !covered);
    return () => frame.setActive(false);
  }, [frame, active, live, paused, reduced, covered]);
  return { scene, snapshot };
}
