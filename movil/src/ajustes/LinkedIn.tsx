// Ajustes › LinkedIn oficial (publicación): status, expiry, scopes and notices as in the PWA, plus
// Conectar/Reconectar. The OAuth needs the office's cookie session (the callback checks the `state`
// it keeps there, CONTRATO-API «LinkedIn oficial», app-movil-backend «Límites conocidos»), which a
// bearer token cannot open: the button opens the PWA's LinkedIn section in an in-app browser, and the
// status refreshes when Gustavo comes back. A return link (`/ajustes?linkedin=…&motivo=…`) shows the
// same message as the PWA for each of the 7 reasons.
import { useLinkedInStatus } from '@compartido/api/hooks';
import type { LinkedInStatus } from '@compartido/api/types';
import {
  canConnectLinkedIn,
  days,
  linkedinBadge,
  linkedinLongDate,
  linkedinReconnected,
  linkedinReturnMessage,
  linkedinScopesText,
  linkedinShortDate,
  type LinkedInNotice,
} from '@compartido/logic/linkedin';
import * as WebBrowser from 'expo-web-browser';
import { useCallback, useEffect, useRef, useState } from 'react';
import { AppState } from 'react-native';
import { apiUrl } from '@/api/config';
import { useSession } from '@/auth/session';
import { Icon } from '@/components/icons';
import { Badge, Button, Card, ErrorRetry, KeyValue, Note, Section, Skeleton, T } from '@/components/ui';
import { PWA_LINKEDIN } from '@/navigation';
import { colors } from '@/theme/tokens';
import { CardHead } from './parts';

/** Opens the PWA's LinkedIn section in the in-app browser (Custom Tabs on Android, Safari view on iOS). */
export function openLinkedInConnect(): Promise<WebBrowser.WebBrowserResult> {
  return WebBrowser.openBrowserAsync(apiUrl(PWA_LINKEDIN), {
    showTitle: true,
    toolbarColor: colors.surface,
    controlsColor: colors.brandDeep,
    enableBarCollapsing: true,
  });
}

/**
 * Conectar/Reconectar and the refresh on return. iOS resolves the browser promise when it closes;
 * Android resolves it at once («opened»), so the app waits to come back to the foreground.
 */
function useConnectFlow(data: LinkedInStatus | undefined, refetch: () => Promise<{ data?: LinkedInStatus }>, onConnected: () => void) {
  const [waiting, setWaiting] = useState(false);
  const [problem, setProblem] = useState<unknown>(null);
  const before = useRef<LinkedInStatus | undefined>(undefined);

  const refreshAfterReturn = useCallback(async () => {
    setWaiting(false);
    const fresh = await refetch();
    if (linkedinReconnected(before.current, fresh.data)) onConnected();
  }, [refetch, onConnected]);

  useEffect(() => {
    if (!waiting) return;
    const subscription = AppState.addEventListener('change', (state) => {
      if (state === 'active') void refreshAfterReturn();
    });
    return () => subscription.remove();
  }, [waiting, refreshAfterReturn]);

  const connect = useCallback(async () => {
    before.current = data;
    setProblem(null);
    setWaiting(true);
    try {
      const result = await openLinkedInConnect();
      if (result.type !== 'opened') await refreshAfterReturn();
    } catch (error) {
      setWaiting(false);
      setProblem(error);
    }
  }, [data, refreshAfterReturn]);

  return { connect, waiting, problem };
}

export function LinkedInSection({ returnParams, onDismissReturn }: { returnParams: { linkedin?: string; motivo?: string }; onDismissReturn: () => void }) {
  const session = useSession();
  const status = useLinkedInStatus();
  const fromLink = linkedinReturnMessage(returnParams.linkedin, returnParams.motivo);
  const linkKey = fromLink ? `${returnParams.linkedin}|${returnParams.motivo ?? ''}` : '';
  const [dismissed, setDismissed] = useState('');
  const [returned, setReturned] = useState<LinkedInNotice | null>(null);
  const notice = returned ?? (fromLink && dismissed !== linkKey ? fromLink : null);
  const onConnected = useCallback(() => setReturned(linkedinReturnMessage('ok', null)), []);
  const flow = useConnectFlow(status.data, status.refetch, onConnected);
  const canConnect = canConnectLinkedIn(session.user);
  const data = status.data;
  const badge = data ? linkedinBadge(data) : null;
  const known = Boolean(data?.member_urn);

  const dismiss = () => {
    setReturned(null);
    setDismissed(linkKey);
    onDismissReturn();
  };

  return (
    <Section label="LinkedIn oficial · publicación">
      {notice ? (
        <Note
          tone={notice.ok ? 'ok' : 'error'}
          title={notice.title}
          actions={
            <Button size="small" onPress={dismiss}>
              Entendido
            </Button>
          }
        >
          {notice.text}
        </Note>
      ) : null}
      {status.isPending ? <Skeleton variant="card" label="Consultando LinkedIn…" /> : null}
      <ErrorRetry error={status.error} onRetry={() => void status.refetch()} />
      {data && badge ? (
        <Card>
          <CardHead title="Publicación en LinkedIn">
            <Badge tone={badge.tone}>{badge.label}</Badge>
          </CardHead>
          {data.connected && data.expiring_soon && data.days_left !== null && data.expires_at ? (
            <Note tone="warn">
              {`El permiso caduca el ${linkedinLongDate(data.expires_at)} (quedan ${days(data.days_left)}). LinkedIn no deja renovarlo solo: reconecta antes para que la publicación diaria no se pause.`}
            </Note>
          ) : null}
          {data.expired ? <Note tone="error">El permiso caducó y la publicación diaria está en pausa. Reconecta LinkedIn para reanudarla.</Note> : null}
          {data.account?.paused && !data.expired ? (
            <Note tone="warn">{`La cuenta oficial está en pausa${data.account.paused_reason ? `: ${data.account.paused_reason}` : '.'}`}</Note>
          ) : null}
          {!data.live ? (
            <Note tone="info">
              La publicación real está desactivada en el servidor (LIVE_LINKEDIN_OFFICIAL=false): no sale nada a LinkedIn aunque la cuenta esté conectada.
            </Note>
          ) : null}
          {known ? <KeyValue label="Miembro">{`${data.member_name || 'Sin nombre'} · ${data.member_urn}`}</KeyValue> : null}
          {data.expires_at ? (
            <KeyValue label="Caduca">{`${linkedinShortDate(data.expires_at)}${data.days_left !== null && !data.expired ? ` · quedan ${days(data.days_left)}` : ''}`}</KeyValue>
          ) : null}
          {data.scopes.length ? <KeyValue label="Permisos">{data.scopes.join(', ')}</KeyValue> : null}
          <KeyValue label="Versión de la API">{data.api_version || 'sin configurar'}</KeyValue>
          {!data.configured ? (
            <Note tone="warn">
              Falta configurar la app de LinkedIn en el servidor (LINKEDIN_CLIENT_ID, LINKEDIN_CLIENT_SECRET y LINKEDIN_REDIRECT_URI). Hasta entonces no se puede conectar.
            </Note>
          ) : !canConnect ? (
            <Note tone="warn">Tu usuario no tiene el permiso «approve_actions», necesario para conectar LinkedIn.</Note>
          ) : (
            <>
              <Button
                variant={data.expired || data.expiring_soon || !known ? 'primary' : 'secondary'}
                block
                loading={flow.waiting}
                loadingLabel="Esperando a que vuelvas…"
                icon={<Icon name="external" size={18} color={data.expired || data.expiring_soon || !known ? colors.onBrand : colors.inkSoft} />}
                onPress={() => void flow.connect()}
              >
                {known ? 'Reconectar LinkedIn' : 'Conectar LinkedIn'}
              </Button>
              <T variant="detalle" soft>
                {`Se abre la oficina web dentro de la app: entra si te lo pide, toca «${known ? 'Reconectar' : 'Conectar'} LinkedIn» y autoriza la publicación (${linkedinScopesText(data)}). Al volver aquí, el estado se actualiza. El token se guarda cifrado en tu servidor; esta app nunca lo ve.`}
              </T>
              <ErrorRetry error={flow.problem} onRetry={() => void flow.connect()} />
            </>
          )}
        </Card>
      ) : null}
    </Section>
  );
}
