import { QueryClientProvider } from '@tanstack/react-query';
import { render } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { vi } from 'vitest';
import { AppRoutes } from '../App';
import { SessionBridge } from '../auth/session';
import { CaptureProvider } from '../capture/CaptureContext';
import { ToastProvider } from '../components/ui/Toast';
import type { Overview, TuTurno } from '../api/types';
import { LocationProbe, testQueryClient } from './render';

/** The whole app (routes, shell, providers) at `path`, with a spy for the capture button. */
export function renderApp(path: string) {
  const client = testQueryClient();
  const onCapture = vi.fn();
  const utils = render(
    <QueryClientProvider client={client}>
      <ToastProvider>
        <CaptureProvider onCapture={onCapture}>
          <MemoryRouter initialEntries={[path]}>
            <SessionBridge>
              <AppRoutes />
              <LocationProbe />
            </SessionBridge>
          </MemoryRouter>
        </CaptureProvider>
      </ToastProvider>
    </QueryClientProvider>,
  );
  return { ...utils, client, onCapture };
}

export function overviewFixture(overrides: Partial<Overview> = {}): Overview {
  return {
    autopilot: { enabled: true, policy_version: 'autonomia-v1' },
    control: { paused: false, reason: '', source: 'none', updated_at: null, updated_by: null },
    window: { start: '07:00', end: '21:00', timezone: 'America/Bogota', open_now: true, min_spacing_seconds: 1200 },
    accounts: [],
    today: { proposals: {}, llm_spent_usd: '0.10', llm_daily_cap_usd: '1', drafts: 0, drafts_daily_cap: 6 },
    counts: { referents: 0, posts: 0, uncertain: 0 },
    ...overrides,
  };
}

export function tuTurnoFixture(overrides: Partial<TuTurno> = {}): TuTurno {
  return {
    count: 0,
    critical: false,
    counts: { avisos: 0, preguntas: 0, tareas: 0 },
    top: null,
    alerts: [],
    questions: [],
    later: [],
    tasks: { perfil: [], conversaciones: [] },
    recent: [],
    summary: { done_today: { posts: 0, comments: 0, reactions: 0, follows: 0, invites: 0, accepts: 0 }, next_piece: null },
    ...overrides,
  };
}
