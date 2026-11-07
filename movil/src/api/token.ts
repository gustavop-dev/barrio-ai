// The device token of POST /api/v1/auth/token, kept in the OS keystore (expo-secure-store) and
// mirrored in memory so every request can read it synchronously.
import * as SecureStore from 'expo-secure-store';

const KEY = 'oficina.token-dispositivo';

let cached: string | null = null;

/** Reads the stored token once at start-up. A keystore failure counts as signed out. */
export async function loadToken(): Promise<string | null> {
  try {
    cached = await SecureStore.getItemAsync(KEY);
  } catch {
    cached = null;
  }
  return cached;
}

export function currentToken(): string | null {
  return cached;
}

export async function saveToken(token: string): Promise<void> {
  cached = token;
  await SecureStore.setItemAsync(KEY, token);
}

export async function clearToken(): Promise<void> {
  cached = null;
  try {
    await SecureStore.deleteItemAsync(KEY);
  } catch {
    // Already gone, or the keystore is unavailable: the in-memory copy is cleared either way.
  }
}
