import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { logout, sendTestPush } from '../api/endpoints';
import { keys } from '../api/queryClient';
import { SIGNED_OUT, useSession } from '../auth/session';
import { Badge, ErrorNote, Loading, PageHeader } from '../components/ui';
import { currentSubscription, detectPush, disablePush, enablePush } from '../push/push';

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
      <p className="muted">Recibe en este dispositivo las alertas de la máquina: pausas, acciones inciertas y fallos.</p>
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
      <PageHeader eyebrow="ESTE DISPOSITIVO" title="Ajustes" />
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
