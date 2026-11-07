// Where the API lives. Set EXPO_PUBLIC_API_URL (movil/.env or the shell) to point the app at another
// backend, for example the Django of this laptop through a tunnel. Expo inlines it at bundle time.
const DEFAULT_API_URL = 'https://office.projectapp.co';

export const API_URL = (process.env.EXPO_PUBLIC_API_URL || DEFAULT_API_URL).replace(/\/+$/, '');

/** Absolute URL of an API path (`/api/v1/...`) or of a media path the API returned (`/media/...`). */
export function apiUrl(path: string): string {
  return `${API_URL}${path.startsWith('/') ? path : `/${path}`}`;
}
