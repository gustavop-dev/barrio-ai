// The native session: a device token (POST /api/v1/auth/token) kept in SecureStore, sent as a bearer
// token by the transport. No cookies, no CSRF. The gate in app/(app)/_layout.tsx reads `status`.
//
// - Start-up: no token → signed out. With one, GET /auth/session decides: `authenticated:false` or a
//   401 (revoked or unknown token) clears it. Anything else keeps it and the app opens inside (ACC-06):
//   no connection (the transport's NetworkError), or the server failing (a 5xx during a deploy). The
//   screens show their own errors, and the session is asked again until the user is back.
// - Any 401 from the API (compartido's onUnauthorized) clears the token and goes back to login.
// - Logout, in this order: DELETE /push/expo (needs the token), POST /auth/token/revocar, clear SecureStore.
// - The Expo push token is registered on every launch with a session (the backend just updates it).
import { ApiError, onUnauthorized } from '@compartido/api/client';
import { getSession, loginWithToken, revokeToken } from '@compartido/api/endpoints';
import type { Session, User } from '@compartido/api/types';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { keys } from '@/api/queryClient';
import { clearToken, currentToken, loadToken, saveToken } from '@/api/token';
import { deviceName, registerForPush, unregisterPush, type PushResult } from '@/push/register';

export const SIGNED_OUT: Session = { authenticated: false, user: null };

export type SessionStatus = 'cargando' | 'fuera' | 'dentro';

/** Inside without knowing the user (offline start, server failing): how often the session is asked again. */
export const SESSION_RETRY_MS = 15_000;

export interface SessionApi {
  status: SessionStatus;
  user: User | null;
  /** The last push registration of this launch (null until it ran). */
  push: PushResult | null;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const SessionContext = createContext<SessionApi | null>(null);

export function useSession(): SessionApi {
  const value = useContext(SessionContext);
  if (!value) throw new Error('useSession() fuera de <SessionProvider>');
  return value;
}

/** Reads the stored token and asks the backend whether it still opens a session. */
export async function restoreSession(): Promise<Session> {
  const token = currentToken() ?? (await loadToken());
  if (!token) return SIGNED_OUT;
  try {
    const session = await getSession();
    if (session?.authenticated) return session;
    await clearToken();
    return SIGNED_OUT;
  } catch (error) {
    // Only the server saying the token is not valid logs out. Offline, or with the server failing, the
    // phone keeps its token: the screens show their own errors and retry.
    if (error instanceof ApiError && error.status === 401) {
      await clearToken();
      return SIGNED_OUT;
    }
    return { authenticated: true, user: null };
  }
}

/** Signed in, but the user is not known yet (the start-up could not reach the server). */
const userMissing = (data: Session | undefined) => Boolean(data?.authenticated && !data.user);

export function SessionProvider({ children, autoRegisterPush = true }: { children: ReactNode; autoRegisterPush?: boolean }) {
  const queryClient = useQueryClient();
  // `always`: the start-up must decide even before the network is known (offline it keeps the token).
  // While the user is missing, the session is stale: it is asked again when the network comes back and
  // every SESSION_RETRY_MS, so «Tu nota» and the LinkedIn permissions come back (ACC-06.6).
  const session = useQuery({
    queryKey: keys.session,
    queryFn: restoreSession,
    networkMode: 'always',
    retry: false,
    staleTime: (query) => (userMissing(query.state.data) ? 0 : Infinity),
    refetchInterval: (query) => (userMissing(query.state.data) ? SESSION_RETRY_MS : false),
  });
  const [push, setPush] = useState<PushResult | null>(null);
  const registered = useRef(false);

  const signOutLocally = useCallback(async () => {
    await clearToken();
    registered.current = false;
    setPush(null);
    queryClient.removeQueries({ predicate: (query) => query.queryKey[0] !== keys.session[0] });
    queryClient.setQueryData(keys.session, SIGNED_OUT);
  }, [queryClient]);

  // When any request finds the token gone, forget cached data and show the login.
  useEffect(() => onUnauthorized(() => void signOutLocally()), [signOutLocally]);

  const status: SessionStatus = session.isPending ? 'cargando' : session.data?.authenticated ? 'dentro' : 'fuera';

  // Register the Expo push token once per launch with a session.
  useEffect(() => {
    if (status !== 'dentro' || !autoRegisterPush || registered.current) return;
    registered.current = true;
    void registerForPush().then(setPush);
  }, [status, autoRegisterPush]);

  const login = useCallback(
    async (username: string, password: string) => {
      const result = await loginWithToken(username.trim(), password, deviceName());
      await saveToken(result.token);
      queryClient.setQueryData<Session>(keys.session, { authenticated: true, user: result.user });
    },
    [queryClient],
  );

  const logout = useCallback(async () => {
    await unregisterPush();
    try {
      await revokeToken();
    } catch {
      // Revoked already or offline: the phone forgets the token anyway; Ajustes in the PWA lists devices.
    }
    await signOutLocally();
  }, [signOutLocally]);

  const value = useMemo<SessionApi>(
    () => ({ status, user: session.data?.user ?? null, push, login, logout }),
    [status, session.data, push, login, logout],
  );
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}
