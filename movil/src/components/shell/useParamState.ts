// Route params as screen state (the PWA's ?query). A link or a push sets them; the screen changes them in
// place with router.setParams (so a deep link and «Atrás» keep them) and keeps its own copy, so it redraws
// at once. A new link with other params wins over the local copy.
//
// The router applies setParams later, in order. While Gustavo types in a search box the screen can ask for
// ?q=S, then ?q=So, and only afterwards see ?q=S arrive: that is its own earlier change coming back, not a
// new link, so the local copy (newer) stays. Without this, «Sof» typed in the Personas search box became «S»
// (14-fichas on the emulator, run 42497299487). Once the router reaches one of those changes, the earlier
// ones are spent: a later link that happens to match one of them is a new link again.
import { router, useLocalSearchParams } from 'expo-router';
import { useState } from 'react';

/** How many of its own pending changes the screen recognises when the router applies them. */
const OWN_CHANGES_KEPT = 20;

function first(value: string | string[] | undefined): string {
  return (Array.isArray(value) ? value[0] : value) ?? '';
}

export function useParamState<K extends string>(names: readonly K[]): [Record<K, string>, (changes: Partial<Record<K, string>>) => void] {
  const params = useLocalSearchParams<Partial<Record<K, string | string[]>>>();
  const linked = Object.fromEntries(names.map((name) => [name, first(params[name])])) as Record<K, string>;
  /** The params as one string, the way `link` reads them once the router has applied them. */
  const key = (values: Record<K, string>) => names.map((name) => values[name] || '').join('\u0000');
  const link = key(linked);
  /** The local copy: the link it started from, its changes the router has not applied yet (`own`) and the values. */
  const [local, setLocal] = useState<{ link: string; own: string[]; values: Record<K, string> } | null>(null);
  const reached = local ? local.own.indexOf(link) : -1;
  // The router reached one of this screen's changes: the copy now starts from that link, and the changes asked for
  // before it are spent.
  if (local && reached >= 0 && (reached > 0 || local.link !== link)) setLocal({ link, own: local.own.slice(reached), values: local.values });
  const current = local && (local.link === link || reached >= 0) ? local : null;
  const values = current ? current.values : linked;

  const set = (changes: Partial<Record<K, string>>) => {
    const next = { ...values, ...changes } as Record<K, string>;
    setLocal({ link, own: [...(current?.own ?? []), key(next)].slice(-OWN_CHANGES_KEPT), values: next });
    // An empty value removes the param, as the PWA deletes it from the query.
    router.setParams(Object.fromEntries(names.map((name) => [name, next[name] || undefined])));
  };

  return [values, set];
}
