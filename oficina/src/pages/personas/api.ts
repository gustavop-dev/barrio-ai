// Reads and writes of Personas that the shared hooks do not cover: the contact list with «Cargar más»,
// the whole opportunity board in one page, adding referents and «Observar ahora».
import { keepPreviousData, useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../../api/client';
import { addReferent, asList, listContacts, observeNow } from '../../api/endpoints';
import { REFRESH } from '../../api/hooks';
import { keys } from '../../api/queryClient';
import type { ContactSearch, Opportunity, Paginated } from '../../api/types';

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

/** Every opportunity at once (the board needs all of them; the API caps a page at 100). */
export function useOpportunityBoard() {
  return useQuery({
    queryKey: [...keys.oportunidadesAll, 'board'],
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
