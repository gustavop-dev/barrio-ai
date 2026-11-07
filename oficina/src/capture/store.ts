// Where the capture sheet lives between calls: App.tsx hands openCaptureSheet to CaptureProvider,
// and CaptureSheetHost (mounted once in the Layout) renders whatever this store says.
import { useSyncExternalStore } from 'react';
import type { CaptureSeed, CaptureTarget } from './CaptureContext';

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

/** Opens the sheet, with an optional context (question, person, piece) and seed (audio, history…). */
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

// ---------------------------------------------------------------- first use

const USED_KEY = 'oficina.captura.usada';
let used: boolean | null = null;
const usedListeners = new Set<() => void>();

function readUsed(): boolean {
  if (used !== null) return used;
  try {
    used = localStorage.getItem(USED_KEY) === '1';
  } catch {
    used = false;
  }
  return used;
}

/** The first-use hint («Mantén oprimido para grabar…») goes away for good after the first use. */
export function markCaptureUsed() {
  if (readUsed()) return;
  used = true;
  try {
    localStorage.setItem(USED_KEY, '1');
  } catch {
    // Without storage the hint comes back on the next visit; it is only a hint.
  }
  usedListeners.forEach((listener) => listener());
}

function subscribeUsed(listener: () => void) {
  usedListeners.add(listener);
  return () => {
    usedListeners.delete(listener);
  };
}

export function useCaptureUsed(): boolean {
  return useSyncExternalStore(subscribeUsed, readUsed, () => true);
}

/** For tests: back to a closed sheet and a first-time visitor. */
export function resetCaptureStoreForTests() {
  state = { open: false, nonce: 0, context: null, seed: {} };
  used = null;
  try {
    localStorage.removeItem(USED_KEY);
  } catch {
    // ignore
  }
}
