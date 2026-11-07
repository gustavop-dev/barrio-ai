import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { getLinkedInStatus, LINKEDIN_OAUTH_START, logout, sendTestPush } from '../api/endpoints';
import { keys } from '../api/queryClient';
import type { LinkedInStatus } from '../api/types';
import { SIGNED_OUT, useSession } from '../auth/session';
import { Badge, ErrorNote, Loading, PageHeader, type Tone } from '../components/ui';
import { formatDateTime } from '../lib/format';
import { currentSubscription, detectPush, disablePush, enablePush } from '../push/push';

// ---------------------------------------------------------------- official LinkedIn

/** `motivo` values of `/ajustes?linkedin=error&motivo=…` (linkedin_views.oauth_callback). */
export const LINKEDIN_REASONS: Record<string, string> = {
  sesion:
    'La sesión de la oficina no llegó de vuelta desde LinkedIn o había caducado. Entra de nuevo si hace falta y vuelve a pulsar «Conectar LinkedIn».',
  permiso: 'Tu usuario no tiene el permiso «approve_actions», necesario para conectar la cuenta de LinkedIn.',
  state:
    'La respuesta de LinkedIn no corresponde a esta solicitud: el enlace caduca a los 10 minutos y solo vale una vez. Vuelve a intentarlo desde aquí.',
  denegado: 'Cancelaste o denegaste la autorización en LinkedIn. No se ha conectado nada.',
  code: 'LinkedIn no devolvió un código de autorización válido. Vuelve a intentarlo.',
  scope:
    'LinkedIn no concedió el permiso para publicar (w_member_social). Acepta todos los permisos y comprueba que la app tenga el producto «Share on LinkedIn».',
  canje:
    'No se pudo canjear la autorización con LinkedIn ni leer tu perfil. Vuelve a intentarlo en unos minutos; si se repite, revisa LINKEDIN_CLIENT_ID, LINKEDIN_CLIENT_SECRET y LINKEDIN_REDIRECT_URI en el servidor.',
};

export interface LinkedInNotice {
  ok: boolean;
  title: string;
  text: string;
}

/** The message for the return from the OAuth flow, or null when the URL carries none. */
export function linkedinReturnMessage(result: string | null, reason: string | null): LinkedInNotice | null {
  if (result === 'ok') {
    return { ok: true, title: 'LinkedIn conectado', text: 'La publicación diaria ya puede usar la API oficial con tu cuenta.' };
  }
  if (result === 'error') {
    const text = (reason && LINKEDIN_REASONS[reason]) || `No se pudo completar la conexión${reason ? ` (motivo: ${reason})` : ''}. Vuelve a intentarlo.`;
    return { ok: false, title: 'No se pudo conectar LinkedIn', text };
  }
  return null;
}

/** Reads `?linkedin=…&motivo=…` once and removes it, so a reload does not repeat the message. */
function useLinkedInReturn() {
  const [params, setParams] = useSearchParams();
  const [notice, setNotice] = useState(() => linkedinReturnMessage(params.get('linkedin'), params.get('motivo')));
  useEffect(() => {
    if (!params.has('linkedin') && !params.has('motivo')) return;
    const next = new URLSearchParams(params);
    next.delete('linkedin');
    next.delete('motivo');
    setParams(next, { replace: true });
  }, [params, setParams]);
  return [notice, () => setNotice(null)] as const;
}

const days = (n: number) => `${n} ${n === 1 ? 'día' : 'días'}`;

function linkedinBadge(status: LinkedInStatus): { label: string; tone: Tone } {
  if (status.expired) return { label: 'Caducado', tone: 'bad' };
  if (status.connected && status.expiring_soon) return { label: 'Caduca pronto', tone: 'warn' };
  if (status.connected) return { label: 'Conectado', tone: 'ok' };
  return { label: 'Sin conectar', tone: 'muted' };
}

function LinkedInSection() {
  const session = useSession();
  const status = useQuery({ queryKey: keys.linkedin, queryFn: getLinkedInStatus, refetchInterval: 5 * 60_000 });
  const [notice, dismiss] = useLinkedInReturn();
  const user = session.data?.user;
  const canConnect = Boolean(user && (user.is_superuser || user.permissions.includes('approve_actions')));
  const data = status.data;
  const badge = data ? linkedinBadge(data) : null;
  const known = Boolean(data?.member_urn);

  return (
    <section className="card" aria-labelledby="linkedin-title">
      <h2 id="linkedin-title">LinkedIn oficial</h2>
      <p className="muted">La cuenta con la que la máquina publica la pieza diaria a través de la API oficial de LinkedIn.</p>
      {notice ? (
        <div className={notice.ok ? 'note ok' : 'note error'} role={notice.ok ? 'status' : 'alert'}>
          <strong>{notice.title}</strong>
          <p>{notice.text}</p>
          <button type="button" className="secondary" onClick={dismiss}>
            Entendido
          </button>
        </div>
      ) : null}
      {status.isPending ? <Loading label="Consultando LinkedIn…" /> : null}
      <ErrorNote error={status.error} onRetry={() => void status.refetch()} />
      {data && badge ? (
        <>
          <p>
            Estado: <Badge tone={badge.tone}>{badge.label}</Badge>
          </p>
          {known ? (
            <dl className="facts">
              <dt>Miembro</dt>
              <dd>
                {data.member_name || 'Sin nombre'} <span className="muted small">{data.member_urn}</span>
              </dd>
              <dt>Caduca</dt>
              <dd>
                {formatDateTime(data.expires_at)}
                {data.days_left !== null && !data.expired ? <strong> · quedan {days(data.days_left)}</strong> : null}
              </dd>
              {data.scopes.length ? (
                <>
                  <dt>Permisos</dt>
                  <dd>
                    <code>{data.scopes.join(' ')}</code>
                  </dd>
                </>
              ) : null}
            </dl>
          ) : null}
          {data.connected && data.expiring_soon && data.days_left !== null ? (
            <p className="note warn" role="note">
              El acceso caduca en {days(data.days_left)}. LinkedIn no deja renovarlo solo: reconecta antes para que la publicación diaria no
              se pause.
            </p>
          ) : null}
          {data.expired ? (
            <p className="note error" role="note">
              El acceso caducó y la publicación diaria está en pausa. Reconecta LinkedIn para reanudarla.
            </p>
          ) : null}
          {data.account?.paused && !data.expired ? (
            <p className="note warn" role="note">
              La cuenta oficial está en pausa{data.account.paused_reason ? `: ${data.account.paused_reason}` : '.'}
            </p>
          ) : null}
          {!data.live ? (
            <p className="note info" role="note">
              La publicación real está desactivada en el servidor (<code>LIVE_LINKEDIN_OFFICIAL=false</code>): no sale nada a LinkedIn aunque
              la cuenta esté conectada.
            </p>
          ) : null}
          <p className="muted small">
            API de LinkedIn {data.api_version ? `versión ${data.api_version}` : 'sin versión configurada'}.
          </p>
          {!data.configured ? (
            <p className="note warn" role="note">
              Falta configurar la app de LinkedIn en el servidor (<code>LINKEDIN_CLIENT_ID</code>, <code>LINKEDIN_CLIENT_SECRET</code> y{' '}
              <code>LINKEDIN_REDIRECT_URI</code>). Hasta entonces no se puede conectar.
            </p>
          ) : !canConnect ? (
            <p className="note warn" role="note">
              Tu usuario no tiene el permiso «approve_actions», necesario para conectar LinkedIn.
            </p>
          ) : (
            <>
              <p className="small">
                Te lleva a LinkedIn para autorizar la publicación ({(data.scopes_required.length ? data.scopes_required : ['w_member_social']).join(', ')}) y
                vuelve aquí. El token se guarda cifrado en tu servidor; esta app nunca lo ve.
              </p>
              {/* A full navigation, never fetch: Django sets the OAuth state in the session and redirects to LinkedIn. */}
              <a className="primary buttonlink" href={LINKEDIN_OAUTH_START}>
                {known ? 'Reconectar LinkedIn' : 'Conectar LinkedIn'}
              </a>
            </>
          )}
        </>
      ) : null}
    </section>
  );
}

// ---------------------------------------------------------------- push

const PUSH_KEY = ['push-subscription'] as const;

function IphoneSteps({ highlight }: { highlight: boolean }) {
  return (
    <div className={highlight ? 'note warn' : 'note info'}>
      <strong>En iPhone o iPad</strong>
      <p>Las notificaciones solo funcionan con Barrio instalada en la pantalla de inicio (iOS 16.4 o posterior):</p>
      <ol>
        <li>Abre esta página en Safari.</li>
        <li>
          Toca <b>Compartir</b> <span aria-hidden="true">(□↑)</span> y elige <b>Añadir a pantalla de inicio</b>.
        </li>
        <li>Abre Barrio desde el icono nuevo, entra y vuelve a Ajustes.</li>
        <li>
          Toca <b>Activar notificaciones</b> y acepta el permiso.
        </li>
      </ol>
    </div>
  );
}

function PushSection() {
  const queryClient = useQueryClient();
  const [support, setSupport] = useState(detectPush);
  const subscription = useQuery({ queryKey: PUSH_KEY, queryFn: currentSubscription, enabled: support.supported && !support.needsInstall, retry: false });
  const refresh = () => {
    setSupport(detectPush());
    void queryClient.invalidateQueries({ queryKey: PUSH_KEY });
  };
  const enable = useMutation({ mutationFn: enablePush, onSettled: refresh });
  const disable = useMutation({ mutationFn: disablePush, onSettled: refresh });
  const test = useMutation({ mutationFn: sendTestPush });
  const active = Boolean(subscription.data);
  const busy = enable.isPending || disable.isPending;

  return (
    <section className="card" aria-labelledby="push-title">
      <h2 id="push-title">Notificaciones push</h2>
      <p className="muted">
        Recibe en este dispositivo las alertas de la máquina: piezas listas para salir (con opción de veto), pausas, acciones inciertas,
        caducidad de LinkedIn y fallos.
      </p>
      <IphoneSteps highlight={support.needsInstall} />
      {!support.supported && !support.needsInstall ? (
        <p className="note warn">Este navegador no admite notificaciones push. Prueba con Chrome, Edge, Firefox o la app instalada en iPhone.</p>
      ) : null}
      {support.supported && !support.needsInstall ? (
        <>
          <p>
            Estado en este dispositivo:{' '}
            {subscription.isPending ? (
              <Badge tone="muted">Comprobando…</Badge>
            ) : active ? (
              <Badge tone="ok">Activadas</Badge>
            ) : support.permission === 'denied' ? (
              <Badge tone="bad">Bloqueadas</Badge>
            ) : (
              <Badge tone="muted">Desactivadas</Badge>
            )}
          </p>
          {support.permission === 'denied' ? (
            <p className="note warn">Has bloqueado las notificaciones. Permítelas para Barrio en los ajustes del navegador o del sistema.</p>
          ) : null}
          <ErrorNote error={subscription.error} />
          <div className="buttonrow">
            {!active ? (
              <button type="button" className="primary" disabled={busy || subscription.isPending} onClick={() => enable.mutate()}>
                {enable.isPending ? 'Activando…' : 'Activar notificaciones'}
              </button>
            ) : (
              <>
                <button type="button" className="primary" disabled={test.isPending} onClick={() => test.mutate()}>
                  {test.isPending ? 'Enviando…' : 'Probar notificación'}
                </button>
                <button type="button" className="secondary" disabled={busy} onClick={() => disable.mutate()}>
                  {disable.isPending ? 'Desactivando…' : 'Desactivar'}
                </button>
              </>
            )}
          </div>
          {enable.isSuccess ? (
            <p className="note ok" role="status">
              Notificaciones activadas en este dispositivo.
            </p>
          ) : null}
          {test.isSuccess ? (
            <p className="note ok" role="status">
              Notificación de prueba enviada. Debería llegar en unos segundos.
            </p>
          ) : null}
          {disable.isSuccess ? (
            <p className="note ok" role="status">
              Notificaciones desactivadas en este dispositivo.
            </p>
          ) : null}
          <ErrorNote error={enable.error ?? disable.error ?? test.error} />
        </>
      ) : null}
    </section>
  );
}

export function Ajustes() {
  const session = useSession();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const signOut = useMutation({
    mutationFn: logout,
    onSuccess: () => {
      queryClient.clear();
      queryClient.setQueryData(keys.session, SIGNED_OUT);
      navigate('/login', { replace: true });
    },
  });
  const user = session.data?.user;

  return (
    <div className="stack">
      <PageHeader eyebrow="CONEXIONES Y ESTE DISPOSITIVO" title="Ajustes" />
      <LinkedInSection />
      <PushSection />
      <section className="card" aria-labelledby="session-title">
        <h2 id="session-title">Sesión</h2>
        {session.isPending ? <Loading /> : <p>{user ? <>Has entrado como <b>{user.username}</b>.</> : 'Sin sesión.'}</p>}
        <p className="muted small">Cerrar sesión no desactiva las notificaciones de este dispositivo.</p>
        <ErrorNote error={signOut.error} />
        <button type="button" className="secondary" disabled={signOut.isPending} onClick={() => signOut.mutate()}>
          {signOut.isPending ? 'Cerrando…' : 'Cerrar sesión'}
        </button>
      </section>
      <section className="card" aria-labelledby="about-title">
        <h2 id="about-title">Acerca de</h2>
        <p className="small">
          Barrio AI · oficina v0.1.0. Todo se aloja en tu servidor: la app solo habla con tu backend.
        </p>
        <p className="small">
          Arte:{' '}
          <a href="https://limezu.itch.io/moderninteriors" target="_blank" rel="noopener noreferrer">
            LimeZu · Modern Interiors
          </a>{' '}
          (licencia de uso en este proyecto).
        </p>
      </section>
    </div>
  );
}
