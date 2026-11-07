import { useQuery } from '@tanstack/react-query';
import { getAccounts, getActivity, getFeed, getOverview, asList } from './endpoints';
import { keys } from './queryClient';

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
