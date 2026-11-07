// Route params as screen state (the PWA's ?query). A link or a push sets them; the screen changes them in
// place with router.setParams (so a deep link and «Atrás» keep them) and keeps its own copy, so it redraws
// at once. A new link with other params wins over the local copy.
import { router, useLocalSearchParams } from 'expo-router';
import { useState } from 'react';

function first(value: string | string[] | undefined): string {
  return (Array.isArray(value) ? value[0] : value) ?? '';
}

export function useParamState<K extends string>(names: readonly K[]): [Record<K, string>, (changes: Partial<Record<K, string>>) => void] {
  const params = useLocalSearchParams<Partial<Record<K, string | string[]>>>();
  const linked = Object.fromEntries(names.map((name) => [name, first(params[name])])) as Record<K, string>;
  const link = names.map((name) => linked[name]).join('\u0000');
  const [local, setLocal] = useState<{ link: string; values: Record<K, string> } | null>(null);
  const values = local && local.link === link ? local.values : linked;

  const set = (changes: Partial<Record<K, string>>) => {
    const next = { ...values, ...changes } as Record<K, string>;
    setLocal({ link, values: next });
    // An empty value removes the param, as the PWA deletes it from the query.
    router.setParams(Object.fromEntries(names.map((name) => [name, next[name] || undefined])));
  };

  return [values, set];
}
