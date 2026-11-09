// Capture and Galería (CONTRATO-API.md «Captura y Galería») plus the Ajustes preferences:
// shapes, calls and hooks. Uploads are multipart (api.postForm: the web transport keeps the CSRF
// header, the native one sends the bearer token). Files are browser Blobs/Files on the web and
// `{uri, name, type}` parts in React Native (NativeFile).
import { useInfiniteQuery, useMutation, useQuery, useQueryClient, type InfiniteData, type QueryClient } from '@tanstack/react-query';
import { api } from './client';
import { asList } from './endpoints';
import { keys } from './queryClient';
import type { Ajustes, Paginated } from './types';
import type { AIEdit, PieceImage } from './imagenes';

// ================================================================ shapes

export type CapturePurpose = 'post' | 'propuesta' | 'dato' | 'respuesta' | 'galeria';
export type CaptureContextKind = 'pregunta' | 'persona' | 'pieza';

export type CaptureState =
  | 'recibida'
  | 'transcribiendo'
  | 'procesando'
  | 'dato_guardado'
  | 'anotado'
  | 'idea'
  | 'usado'
  | 'sin_usar'
  | 'error'
  | 'deshecha';

/** While a capture is in one of these, the PWA polls GET /api/v1/capturas/<id> every 2–3 s. */
export const CAPTURE_PROCESSING: readonly CaptureState[] = ['recibida', 'transcribiendo', 'procesando'];

export function isProcessing(state: string): boolean {
  return (CAPTURE_PROCESSING as readonly string[]).includes(state);
}

export interface CaptureOutput {
  ai_edit?: AIEdit;
  publish_asap?: boolean;
  publish_asap_evidence?: string;
  publish_asap_expected_slot?: string | null;
  publish_asap_reason?: string;
  id: string;
  created_at: string;
  note: string;
  purpose: CapturePurpose | null;
  purpose_label: string | null;
  team_decided: { purpose: CapturePurpose; label: string; reason: string } | null;
  context: { tipo: CaptureContextKind; id: string; label: string } | null;
  has_audio: boolean;
  audio_duration_s: number | null;
  audio_mime: string | null;
  audio_url: string | null;
  transcript: string;
  transcript_language: string | null;
  state: CaptureState | string;
  state_label: string;
  outcome: { kind: string; text: string; link: string | null; reason?: string } | null;
  photos: { id: string; url: string }[];
  error: string | null;
  undo_until: string | null;
  can_undo: boolean;
}

/**
 * A file part as React Native's FormData takes it: a local `uri` (file://, content://) with its name
 * and type. Browsers append a Blob or File instead.
 */
export interface NativeFile {
  uri: string;
  name: string;
  type: string;
}

/** What a photo field accepts: a browser File or a native part. */
export type UploadFile = File | NativeFile;

function isNativeFile(file: Blob | NativeFile): file is NativeFile {
  return typeof (file as NativeFile).uri === 'string' && !(typeof Blob !== 'undefined' && file instanceof Blob);
}

/** The types the contract accepts, by file extension (for a part that comes without a type). */
const TYPE_BY_EXTENSION: Record<string, string> = {
  jpg: 'image/jpeg',
  jpeg: 'image/jpeg',
  png: 'image/png',
  webp: 'image/webp',
  heic: 'image/heic',
  heif: 'image/heif',
  m4a: 'audio/mp4',
  mp4: 'audio/mp4',
  aac: 'audio/aac',
  mp3: 'audio/mpeg',
  ogg: 'audio/ogg',
  webm: 'audio/webm',
  wav: 'audio/wav',
  flac: 'audio/flac',
};

/** The type a file name or URI implies by its extension (`IMG_1.HEIC` → `image/heic`), or null. */
export function typeFromName(name: string): string | null {
  const path = name.split(/[?#]/)[0] ?? '';
  const ext = /\.([a-z0-9]+)$/i.exec(path)?.[1]?.toLowerCase();
  return (ext && TYPE_BY_EXTENSION[ext]) || null;
}

/**
 * A URI that Android's networking can open. It reads a part with ContentResolver.openInputStream,
 * which needs a scheme: a bare path (`/data/…/a.m4a`) fails with «Could not retrieve file for uri», so
 * it becomes `file:///data/…/a.m4a`. `file://`, `content://` and any other scheme stay as they are.
 */
export function nativeUri(uri: string): string {
  const value = uri.trim();
  if (/^[a-z][a-z0-9+.-]*:/i.test(value)) return value;
  if (value.startsWith('/')) return `file://${value}`;
  return value;
}

/**
 * A React Native file part that the phone can send: a URI with a scheme, a file name, and always a
 * type (Android refuses a binary part without one: «Binary FormData part needs a content-type
 * header»). The type is the declared one, else the one its name or URI implies.
 */
export function nativePart(file: NativeFile, filename?: string): NativeFile {
  const uri = nativeUri(String(file.uri || ''));
  const fromUri = uri.split(/[?#]/)[0]?.split('/').pop() ?? '';
  const name = (filename || '').trim() || String(file.name || '').trim() || fromUri || 'archivo';
  const type = String(file.type || '').trim().toLowerCase() || typeFromName(name) || typeFromName(uri) || 'application/octet-stream';
  return { uri, name, type };
}

/** Appends a file part: a Blob with its filename on the web, the `{uri, name, type}` object in React Native. */
function appendFile(form: FormData, field: string, file: Blob | NativeFile, filename: string) {
  if (isNativeFile(file)) {
    // React Native's FormData reads uri/name/type from the object; the DOM typing only knows Blob.
    form.append(field, nativePart(file, filename) as unknown as Blob);
    return;
  }
  form.append(field, file, filename);
}

/** The multipart fields of POST /api/v1/capturas. Everything is optional, but it cannot go empty. */
export interface CaptureInput {
  ai_edit?: AIEdit;
  audio?: { blob: Blob | NativeFile; filename: string; durationS: number } | null;
  fotos?: UploadFile[];
  nota?: string;
  para?: CapturePurpose | null;
  contexto?: { tipo: CaptureContextKind; id: string } | null;
  /** Only for a question: the visibility chosen. Not sent when null (the question's suggestion is used). */
  publicUse?: boolean | null;
}

export type PhotoDisplayState = 'nueva' | 'sin_usar' | 'elegida' | 'editada' | 'publicada';
export type PhotoTone = 'info' | 'muted' | 'ok';

export interface PhotoOutput {
  id: string;
  url: string;
  created_at: string;
  state: 'sin_usar' | 'elegida' | 'editada' | 'publicada' | string;
  display_state: PhotoDisplayState | string;
  label: string;
  tone: PhotoTone | string;
  note: string;
  ai_edit: AIEdit;
  instruction?: string;
  instruction_kind?: '' | 'none' | 'original' | 'edit' | 'unsafe';
  versions?: PieceImage[];
  used_in: { piece_id: string | null; date: string | null; text: string } | null;
  capture_id: string | null;
  mime: string;
  size_bytes: number;
  width: number | null;
  height: number | null;
}

export type GaleriaFiltro = 'todas' | 'sin_usar' | 'elegidas' | 'publicadas';

export interface PhotoPatch {
  note?: string;
  ai_edit?: AIEdit;
}

export interface Preferencias {
  gallery_ai_edit: AIEdit;
  updated_at: string | null;
  /** Kinds whose push is off (PATCH accepts it; GET may not return it). */
  push_disabled?: string[];
  /** Kinds whose push is on although their default is off. */
  push_enabled?: string[];
}

export interface PreferenciasPatch {
  gallery_ai_edit?: AIEdit;
  push_disabled?: string[];
  push_enabled?: string[];
}

/** One push type of GET /api/v1/ajustes `push_types` (Ajustes › Notificaciones, a switch each). */
export interface PushType {
  kind: string;
  label: string;
  goes_to: 'tu_turno' | 'notificaciones' | string;
  default: boolean;
  enabled: boolean;
}

/** GET /api/v1/ajustes with the `push_types` added for the per-type switches. */
export type AjustesConPush = Ajustes & { push_types?: PushType[] };

// ================================================================ limits (contract)

export const CAPTURE_LIMITS = {
  audioBytes: 25 * 1024 * 1024,
  audioSeconds: 1800,
  photoBytes: 10 * 1024 * 1024,
  photosPerCapture: 10,
  noteChars: 4000,
} as const;

export const PHOTO_TYPES = ['image/jpeg', 'image/png', 'image/webp', 'image/heic', 'image/heif'];

/** JPEG, PNG, WebP or HEIC (some phones send HEIC without a type: trust the extension then). */
export function isAcceptedPhoto(file: { type: string; name: string }): boolean {
  if (file.type) return PHOTO_TYPES.includes(file.type.toLowerCase());
  return /\.(jpe?g|png|webp|heic|heif)$/i.test(file.name);
}

// ================================================================ calls

const CAP = '/api/v1/capturas';
const GAL = '/api/v1/galeria';
const PREFS = '/api/v1/ajustes/preferencias';
const id = (value: string) => encodeURIComponent(value);

/** The FormData of a capture, exactly as the contract names the parts. */
export function captureForm(input: CaptureInput): FormData {
  const form = new FormData();
  if (input.audio) {
    appendFile(form, 'audio', input.audio.blob, input.audio.filename);
    form.append('audio_duration_s', String(Math.min(CAPTURE_LIMITS.audioSeconds, Math.round(input.audio.durationS * 10) / 10)));
  }
  for (const foto of input.fotos ?? []) appendFile(form, 'fotos', foto, foto.name);
  const nota = (input.nota ?? '').trim();
  if (nota) form.append('nota', nota);
  if (input.para) form.append('para', input.para);
  if (input.ai_edit) form.append('ai_edit', input.ai_edit);
  if (input.contexto) {
    form.append('contexto_tipo', input.contexto.tipo);
    form.append('contexto_id', input.contexto.id);
    if (input.contexto.tipo === 'pregunta' && typeof input.publicUse === 'boolean') form.append('public_use', input.publicUse ? 'true' : 'false');
  }
  return form;
}

/** 201 with the capture in `recibida`; 400 empty or invalid, 409 question no longer open, 413 too big. */
export const createCaptura = (input: CaptureInput) => api.postForm<CaptureOutput>(CAP, captureForm(input));
/** «Lo que enviaste»: newest first, without the undone ones. */
export const listCapturas = (page = 1) => api.get<Paginated<CaptureOutput> | CaptureOutput[]>(`${CAP}${page > 1 ? `?page=${page}` : ''}`);
export const getCaptura = (captureId: string) => api.get<CaptureOutput>(`${CAP}/${id(captureId)}`);
/** «Deshacer»: only within `undo_until` (2 minutes); 409 afterwards. */
export const undoCaptura = (captureId: string) => api.delete<CaptureOutput>(`${CAP}/${id(captureId)}`);

export const listGaleria = (filtro: GaleriaFiltro = 'todas', page = 1) =>
  api.get<Paginated<PhotoOutput> | PhotoOutput[]>(`${GAL}?filtro=${filtro}${page > 1 ? `&page=${page}` : ''}`);
export function uploadFotos(files: UploadFile[]) {
  const form = new FormData();
  for (const file of files) appendFile(form, 'fotos', file, file.name);
  return api.postForm<PhotoOutput[] | Paginated<PhotoOutput>>(GAL, form);
}
export const getFoto = (photoId: string) => api.get<PhotoOutput>(`${GAL}/${id(photoId)}`);
export const updateFoto = (photoId: string, patch: PhotoPatch) => api.patch<PhotoOutput>(`${GAL}/${id(photoId)}`, patch);
export const deleteFoto = (photoId: string) => api.delete(`${GAL}/${id(photoId)}`);

export const getPreferencias = () => api.get<Preferencias>(PREFS);
export const savePreferencias = (patch: PreferenciasPatch) => api.patch<Preferencias>(PREFS, patch);

/**
 * Images and audio are served to the session (cookie or bearer token) only; never trust an absolute URL
 * from elsewhere. The native app prefixes the API origin and sends its token with the image request.
 */
export function sameOrigin(url: string | null | undefined): string | null {
  return url && url.startsWith('/') && !url.startsWith('//') ? url : null;
}

// ================================================================ hooks

export const captureKeys = {
  all: ['capturas'] as const,
  list: ['capturas', 'list'] as const,
  item: (captureId: string) => ['capturas', 'item', captureId] as const,
  galeriaAll: ['galeria'] as const,
  galeria: (filtro: GaleriaFiltro) => ['galeria', filtro] as const,
  preferencias: ['ajustes', 'preferencias'] as const,
};

function nextPage(data: Paginated<unknown> | unknown[], page: number): number | undefined {
  return !Array.isArray(data) && data.next ? page + 1 : undefined;
}

function totalOf<T>(pages: (Paginated<T> | T[])[] | undefined): number | null {
  const first = pages?.[0];
  if (!first) return null;
  return Array.isArray(first) ? first.length : first.count;
}

/** «Lo que enviaste», page by page. `count` is the total for the counter in the sheet header. */
export function useCapturas(enabled = true) {
  const query = useInfiniteQuery({
    queryKey: captureKeys.list,
    queryFn: ({ pageParam }) => listCapturas(pageParam),
    initialPageParam: 1,
    getNextPageParam: (last, _all, page) => nextPage(last, page),
    enabled,
  });
  const items = (query.data?.pages ?? []).flatMap((page) => asList(page));
  return { ...query, items, count: totalOf(query.data?.pages) };
}

/** One capture of the history, polled every 2.5 s while it is being processed. */
export function useCapturaLive(initial: CaptureOutput) {
  return useQuery({
    queryKey: captureKeys.item(initial.id),
    queryFn: () => getCaptura(initial.id),
    initialData: initial,
    enabled: isProcessing(initial.state),
    refetchInterval: (query) => (query.state.data && isProcessing(query.state.data.state) ? 2500 : false),
  });
}

type Pages<T> = InfiniteData<Paginated<T> | T[], number>;

/**
 * Takes an undone capture out of «Lo que enviaste» at once, and lowers its counter: the list hides undone captures,
 * and on a slow network the row would otherwise stay, with its «Deshacer», until the list comes back.
 */
export function removeCapturaFromHistory(client: QueryClient, captureId: string) {
  client.setQueryData<Pages<CaptureOutput>>(captureKeys.list, (data) => {
    if (!data || !data.pages.some((page) => asList(page).some((capture) => capture.id === captureId))) return data;
    const pages = data.pages.map((page) => {
      if (Array.isArray(page)) return page.filter((capture) => capture.id !== captureId);
      return { ...page, count: Math.max(0, page.count - 1), results: page.results.filter((capture) => capture.id !== captureId) };
    });
    return { ...data, pages };
  });
}

/** Puts a photo the API just returned (after a PATCH) into every cached page of the Galería. */
function replacePhotoInGaleria(client: QueryClient, photo: PhotoOutput) {
  client.setQueriesData<Pages<PhotoOutput>>({ queryKey: captureKeys.galeriaAll }, (data) => {
    if (!data?.pages) return data;
    const swap = (item: PhotoOutput) => (item.id === photo.id ? photo : item);
    const pages = data.pages.map((page) => (Array.isArray(page) ? page.map(swap) : { ...page, results: page.results.map(swap) }));
    return { ...data, pages };
  });
}

/**
 * The lists reload in the background after a write. Returning the promise would make TanStack Query wait for the
 * reload before the caller's onSuccess runs: on a slow network «Enviado al equipo.» or «Foto guardada.» would come
 * seconds late, with the sheet still «Enviando…».
 */
function reloadInBackground(client: QueryClient, ...queryKeys: (readonly unknown[])[]) {
  for (const queryKey of queryKeys) void client.invalidateQueries({ queryKey });
}

export function useCreateCaptura() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: createCaptura,
    // Offline, TanStack would pause the mutation with no error: the sheet stayed «Enviando…» with nothing to tell
    // Gustavo. It is tried, fails with «No hay conexión…», and the draft waits for «Reintentar».
    networkMode: 'always',
    onSettled: () => reloadInBackground(client, captureKeys.all, captureKeys.galeriaAll),
  });
}

export function useUndoCaptura() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: undoCaptura,
    onSettled: () =>
      Promise.all([
        client.invalidateQueries({ queryKey: captureKeys.all }),
        client.invalidateQueries({ queryKey: captureKeys.galeriaAll }),
        client.invalidateQueries({ queryKey: keys.tuTurno }),
        client.invalidateQueries({ queryKey: keys.hechos }),
      ]),
  });
}

/** The gallery for one filter, newest first, with «Cargar más». */
export function useGaleria(filtro: GaleriaFiltro) {
  const query = useInfiniteQuery({
    queryKey: captureKeys.galeria(filtro),
    queryFn: ({ pageParam }) => listGaleria(filtro, pageParam),
    initialPageParam: 1,
    getNextPageParam: (last, _all, page) => nextPage(last, page),
  });
  const items = (query.data?.pages ?? []).flatMap((page) => asList(page));
  return { ...query, items, count: totalOf(query.data?.pages) };
}

/** Where an upload is: `done` photos already in, `sending` in the request on its way, of `total`. */
export interface UploadProgress {
  done: number;
  sending: number;
  total: number;
}

/** `onProgress` hears before each request of up to ten photos and once at the end (the native app draws it). */
export function useUploadFotos({ onProgress }: { onProgress?: (progress: UploadProgress) => void } = {}) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (files: UploadFile[]) => {
      // Ten parts per request at most, as in a capture.
      const created: PhotoOutput[] = [];
      for (let start = 0; start < files.length; start += CAPTURE_LIMITS.photosPerCapture) {
        const batch = files.slice(start, start + CAPTURE_LIMITS.photosPerCapture);
        onProgress?.({ done: start, sending: batch.length, total: files.length });
        created.push(...asList(await uploadFotos(batch)));
      }
      onProgress?.({ done: files.length, sending: 0, total: files.length });
      return created;
    },
    // As a capture: offline it fails and offers «Reintentar» instead of pausing silently.
    networkMode: 'always',
    onSettled: () => reloadInBackground(client, captureKeys.galeriaAll),
  });
}

export function useUpdateFoto() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ photoId, patch }: { photoId: string; patch: PhotoPatch }) => updateFoto(photoId, patch),
    // The saved photo goes into the cached Galería at once: opened again before the list reloads, it shows what was saved.
    onSuccess: (photo) => {
      if (photo && typeof photo === 'object' && typeof photo.id === 'string') replacePhotoInGaleria(client, photo);
    },
    onSettled: () => reloadInBackground(client, captureKeys.galeriaAll),
  });
}

export function useDeleteFoto() {
  const client = useQueryClient();
  return useMutation({ mutationFn: deleteFoto, onSettled: () => client.invalidateQueries({ queryKey: captureKeys.galeriaAll }) });
}

export function usePreferencias() {
  return useQuery({ queryKey: captureKeys.preferencias, queryFn: getPreferencias });
}

export function useSavePreferencias() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: savePreferencias,
    onSuccess: (data) => {
      if (data && typeof data === 'object') client.setQueryData(captureKeys.preferencias, data);
    },
    onSettled: () => Promise.all([client.invalidateQueries({ queryKey: captureKeys.preferencias }), client.invalidateQueries({ queryKey: keys.ajustes })]),
  });
}
