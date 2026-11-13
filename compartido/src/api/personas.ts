// Reads and writes of Personas that the shared hooks do not cover: the contact list and the connections list
// (the app's Conexiones) with «Cargar más», the whole opportunity board in one page, adding referents and
// «Observar ahora». Shared by the PWA
// (oficina/src/pages/personas/api.ts re-exports it) and the native app.
import { keepPreviousData, useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from './client';
import { addReferent, asList, listContacts, observeNow } from './endpoints';
import { REFRESH } from './hooks';
import { keys } from './queryClient';
import type { ContactSearch, Opportunity, Paginated } from './types';

export type ContactFilters = Required<Pick<ContactSearch, 'stage' | 'q' | 'role' | 'modality' | 'source'>>;

/** GET /api/v1/red/contacts with the redesign filters, 25 per page, accumulated with «Cargar más». */
export function useContactPages(filters: ContactFilters) {
  const normalized = { ...filters, q: filters.q.trim() };
  return useInfiniteQuery({
    queryKey: [...keys.redAll, 'pages', normalized],
    queryFn: ({ pageParam }) => listContacts({ ...normalized, page: pageParam }),
    initialPageParam: 1,
    getNextPageParam: (last, _all, page) => (!Array.isArray(last) && last?.next ? page + 1 : undefined),
    placeholderData: keepPreviousData,
    refetchInterval: REFRESH.personas,
  });
}

/** Personas › Conexiones: the connected people (`vista=conexiones`), by role and name, 25 per page with «Cargar más». */
export function useConnectionPages({ q, role }: { q: string; role: string }) {
  const normalized = { q: q.trim(), role };
  return useInfiniteQuery({
    queryKey: [...keys.redAll, 'conexiones', normalized],
    queryFn: ({ pageParam }) => listContacts({ vista: 'conexiones', ...normalized, page: pageParam }),
    initialPageParam: 1,
    getNextPageParam: (last, _all, page) => (!Array.isArray(last) && last?.next ? page + 1 : undefined),
    placeholderData: keepPreviousData,
    refetchInterval: REFRESH.personas,
  });
}

/** Query key of the whole board, for the optimistic stage moves. */
export const OPPORTUNITY_BOARD_KEY = [...keys.oportunidadesAll, 'board'];

/** Every opportunity at once (the board needs all of them; the API caps a page at 100). */
export function useOpportunityBoard() {
  return useQuery({
    queryKey: OPPORTUNITY_BOARD_KEY,
    queryFn: async () => asList(await api.get<Paginated<Opportunity> | Opportunity[]>('/api/v1/oportunidades?page_size=100')),
    refetchInterval: REFRESH.personas,
  });
}

export function useAddReferent() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ account, identifier, reason }: { account: string; identifier: string; reason: string }) => addReferent(account, identifier, reason),
    onSettled: () => Promise.all([client.invalidateQueries({ queryKey: ['referents'] }), client.invalidateQueries({ queryKey: keys.overview })]),
  });
}

export function useObserveNow() {
  return useMutation({ mutationFn: (account: string) => observeNow(account) });
}

/** Accepts linkedin.com/in/<slug> with or without scheme; returns the https URL or null. */
export function normalizeProfileUrl(raw: string): string | null {
  const value = raw.trim();
  if (!value) return null;
  const withScheme = /^[a-z]+:\/\//i.test(value) ? value : `https://${value}`;
  let url: URL;
  try {
    url = new URL(withScheme);
  } catch {
    return null;
  }
  if (url.protocol !== 'https:') return null;
  if (!/^(www\.|[a-z]{2}\.)?linkedin\.com$/i.test(url.hostname)) return null;
  const match = /^\/in\/([^/]+)\/?$/.exec(url.pathname);
  if (!match) return null;
  return `https://www.linkedin.com/in/${match[1]}/`;
}
