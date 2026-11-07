import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { getAccounts, getActivity, getContact, getFeed, getOverview, getRedSummary, listContacts, asList } from './endpoints';
import { keys } from './queryClient';
import type { ContactStage } from './types';

export function useOverview() {
  return useQuery({ queryKey: keys.overview, queryFn: getOverview, refetchInterval: 30_000 });
}

export function useActivity() {
  return useQuery({ queryKey: keys.activity, queryFn: getActivity, refetchInterval: 15_000 });
}

export function useFeed() {
  return useQuery({ queryKey: keys.feed, queryFn: () => getFeed(50), refetchInterval: 30_000 });
}

export function useAccounts() {
  return useQuery({ queryKey: keys.accounts, queryFn: async () => asList(await getAccounts()) });
}

// ---------------------------------------------------------------- network (Red)

export function useRedSummary() {
  return useQuery({ queryKey: keys.redSummary, queryFn: getRedSummary, refetchInterval: 60_000 });
}

/** Keeps the raw page (`{count,next,previous,results}` or a plain array) so the page can paginate. */
export function useContacts(stage: ContactStage | '', page: number) {
  return useQuery({
    queryKey: keys.contacts(stage, page),
    queryFn: () => listContacts({ stage, page }),
    placeholderData: keepPreviousData,
    refetchInterval: 60_000,
  });
}

export function useContact(contactId: string) {
  return useQuery({ queryKey: keys.contact(contactId), queryFn: () => getContact(contactId), enabled: Boolean(contactId) });
}
