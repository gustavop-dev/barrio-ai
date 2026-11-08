// Where the capture sheet lives between calls: the capture button, a Tu turno question («Responder
// con audio») or a push link call openCaptureSheet(); CaptureSheetHost (in the app layout) renders it.
import * as SecureStore from 'expo-secure-store';
import { useSyncExternalStore } from 'react';
import type { CaptureSeed, CaptureTarget } from './types';

export interface CaptureSheetState {
  open: boolean;
  /** Changes on every opening, so the sheet starts clean each time. */
  nonce: number;
  context: CaptureTarget | null;
  seed: CaptureSeed;
}

let state: CaptureSheetState = { open: false, nonce: 0, context: null, seed: {} };
const listeners = new Set<() => void>();

function set(next: CaptureSheetState) {
  state = next;
  listeners.forEach((listener) => listener());
}

export function openCaptureSheet(context?: CaptureTarget, seed: CaptureSeed = {}) {
  markCaptureUsed();
  set({ open: true, nonce: state.nonce + 1, context: context ?? null, seed });
}

export function closeCaptureSheet() {
  if (!state.open) return;
  set({ ...state, open: false, seed: {} });
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

export function useCaptureSheet(): CaptureSheetState {
  return useSyncExternalStore(subscribe, () => state, () => state);
}

// ---------------------------------------------------------------- sent (MovCaptura: the button pulses)

let sentCount = 0;
const sentListeners = new Set<() => void>();

/** A capture reached the team: the capture button pulses once. */
export function notifyCaptureSent() {
  sentCount += 1;
  sentListeners.forEach((listener) => listener());
}

function subscribeSent(listener: () => void) {
  sentListeners.add(listener);
  return () => {
    sentListeners.delete(listener);
  };
}

/** How many captures were sent since the app started (changes on each one). */
export function useCaptureSentCount(): number {
  return useSyncExternalStore(subscribeSent, () => sentCount, () => sentCount);
}

// ---------------------------------------------------------------- first use

const USED_KEY = 'oficina.captura-usada';
let used: boolean | null = null;
const usedListeners = new Set<() => void>();

/** Reads the first-use flag once (the hint shows until it loads only if it was never used). */
export async function loadCaptureUsed(): Promise<void> {
  if (used !== null) return;
  try {
    used = (await SecureStore.getItemAsync(USED_KEY)) === '1';
  } catch {
    used = false;
  }
  usedListeners.forEach((listener) => listener());
}

/** The first-use hint («Mantén oprimido para grabar…») goes away for good after the first use. */
export function markCaptureUsed() {
  if (used === true) return;
  used = true;
  SecureStore.setItemAsync(USED_KEY, '1').catch(() => undefined);
  usedListeners.forEach((listener) => listener());
}

function subscribeUsed(listener: () => void) {
  usedListeners.add(listener);
  return () => {
    usedListeners.delete(listener);
  };
}

/** True while unknown, so the hint never flashes before the flag loads. */
export function useCaptureUsed(): boolean {
  return useSyncExternalStore(subscribeUsed, () => used ?? true, () => true);
}

/** For tests: a closed sheet and a first-time user. */
export function resetCaptureStoreForTests(firstTime = true) {
  state = { open: false, nonce: 0, context: null, seed: {} };
  used = firstTime ? false : true;
}
