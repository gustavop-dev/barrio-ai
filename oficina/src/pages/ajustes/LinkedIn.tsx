// Ajustes › LinkedIn oficial (publicación): status, expiry, scopes, notices, the OAuth return
// message and Conectar/Reconectar (a full navigation, never fetch).
import { LINKEDIN_OAUTH_START } from '../../api/endpoints';
import { useLinkedInStatus } from '../../api/hooks';
import { useSession } from '../../auth/session';
import { Badge, Button, ButtonLink, Card, ErrorRetry, Note, Section, Skeleton } from '../../components/ui';
import { canConnectLinkedIn, days, linkedinBadge, linkedinLongDate as longDate, linkedinScopesText, linkedinShortDate as shortDate, useLinkedInReturn } from './linkedin';
import { Row } from './shared';

export function LinkedInSection() {
  const session = useSession();
  const status = useLinkedInStatus();
  const [notice, dismiss] = useLinkedInReturn();
  const user = session.data?.user;
  const canConnect = canConnectLinkedIn(user);
  const data = status.data;
  const badge = data ? linkedinBadge(data) : null;
  const known = Boolean(data?.member_urn);

  return (
    <Section label="LinkedIn oficial · publicación" id="linkedin">
      {notice ? (
        <Note
          tone={notice.ok ? 'ok' : 'error'}
          title={notice.title}
          role={notice.ok ? 'status' : 'alert'}
          actions={
            <Button variant="secondary" size="small" onClick={dismiss}>
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
        <Card className="aj-card">
          <div className="aj-cardhead">
            <p className="t-cuerpo">Publicación en LinkedIn</p>
            <Badge tone={badge.tone}>{badge.label}</Badge>
          </div>
          {data.connected && data.expiring_soon && data.days_left !== null && data.expires_at ? (
            <Note tone="warn" role="status">
              El permiso caduca el {longDate(data.expires_at)} (quedan {days(data.days_left)}). LinkedIn no deja renovarlo solo: reconecta antes para que la
              publicación diaria no se pause.
            </Note>
          ) : null}
          {data.expired ? (
            <Note tone="error" role="status">
              El permiso caducó y la publicación diaria está en pausa. Reconecta LinkedIn para reanudarla.
            </Note>
          ) : null}
          {data.account?.paused && !data.expired ? (
            <Note tone="warn" role="status">
              La cuenta oficial está en pausa{data.account.paused_reason ? `: ${data.account.paused_reason}` : '.'}
            </Note>
          ) : null}
          {!data.live ? (
            <Note tone="info" role="status">
              La publicación real está desactivada en el servidor (<code>LIVE_LINKEDIN_OFFICIAL=false</code>): no sale nada a LinkedIn aunque la cuenta esté
              conectada.
            </Note>
          ) : null}
          <div className="aj-rows">
            {known ? (
              <Row label="Miembro">
                {data.member_name || 'Sin nombre'} · <span className="aj-urn">{data.member_urn}</span>
              </Row>
            ) : null}
            {data.expires_at ? (
              <Row label="Caduca">
                {shortDate(data.expires_at)}
                {data.days_left !== null && !data.expired ? ` · quedan ${days(data.days_left)}` : ''}
              </Row>
            ) : null}
            {data.scopes.length ? <Row label="Permisos">{data.scopes.join(', ')}</Row> : null}
            <Row label="Versión de la API">{data.api_version || 'sin configurar'}</Row>
          </div>
          {!data.configured ? (
            <Note tone="warn" role="status">
              Falta configurar la app de LinkedIn en el servidor (<code>LINKEDIN_CLIENT_ID</code>, <code>LINKEDIN_CLIENT_SECRET</code> y{' '}
              <code>LINKEDIN_REDIRECT_URI</code>). Hasta entonces no se puede conectar.
            </Note>
          ) : !canConnect ? (
            <Note tone="warn" role="status">
              Tu usuario no tiene el permiso «approve_actions», necesario para conectar LinkedIn.
            </Note>
          ) : (
            <>
              {/* A full navigation, never fetch: Django keeps the OAuth state in the session and redirects to LinkedIn. */}
              <ButtonLink href={LINKEDIN_OAUTH_START} variant={data.expired || data.expiring_soon || !known ? 'primary' : 'secondary'} block>
                {known ? 'Reconectar LinkedIn' : 'Conectar LinkedIn'}
              </ButtonLink>
              <p className="t-detalle text-suave">
                Te lleva a LinkedIn para autorizar la publicación ({linkedinScopesText(data)}) y
                vuelve aquí. El token se guarda cifrado en tu servidor; esta app nunca lo ve.
              </p>
            </>
          )}
        </Card>
      ) : null}
    </Section>
  );
}
