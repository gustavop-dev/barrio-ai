import { QueryClient } from '@tanstack/react-query';
import { ApiError } from './client';

export const keys = {
  session: ['session'] as const,
  overview: ['overview'] as const,
  feed: ['feed'] as const,
  activity: ['activity'] as const,
  accounts: ['accounts'] as const,
  actions: (state: string, page: number, capability = '') => ['actions', state, page, capability] as const,
  actionsAll: ['actions'] as const,
  referents: (account: string) => ['referents', account] as const,
  unit: (id: string) => ['unit', id] as const,
  source: (key: string) => ['source', key] as const,
  memory: ['memory'] as const,
  editorialAll: ['editorial'] as const,
  calendar: (desde: string) => ['editorial', 'calendar', desde] as const,
  piece: (id: string) => ['editorial', 'piece', id] as const,
  linkedin: ['linkedin-status'] as const,
};

/** Client errors (4xx) are answers, not glitches: never retry them. */
export function shouldRetry(failureCount: number, error: unknown): boolean {
  if (error instanceof ApiError && error.status < 500) return false;
  return failureCount < 2;
}

export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: shouldRetry,
        staleTime: 10_000,
        refetchOnWindowFocus: true,
      },
      mutations: { retry: false },
    },
  });
}
