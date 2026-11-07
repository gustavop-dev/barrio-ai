// Ajustes › Lo que el equipo sabe de ti (link) and Sesión y Acerca de (logout, version, art credit).
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Link, useNavigate } from 'react-router-dom';
import { ART_CREDIT, ART_CREDIT_URL, factsLabel } from '../../../../compartido/src/logic/ajustes';
import { logout } from '../../api/endpoints';
import { useAjustes } from '../../api/hooks';
import { keys } from '../../api/queryClient';
import { SIGNED_OUT, useSession } from '../../auth/session';
import { IconChevronRight } from '../../components/icons';
import { Button, Card, ErrorRetry, ExternalLink, Section } from '../../components/ui';
import { Row } from './shared';

/** Same as package.json. */
export const APP_VERSION = '0.1.0';

export function SabeLink() {
  const ajustes = useAjustes();
  const count = ajustes.data?.facts_count;
  return (
    <section id="sabe" aria-label="Lo que el equipo sabe de ti">
      <Link to="/tu-turno/sabe" className="card aj-linkcard">
        <span className="aj-linkcard-text">
          <span className="t-cuerpo">Lo que el equipo sabe de ti</span>
          <span className="t-detalle text-suave">
            {factsLabel(count)}
          </span>
        </span>
        <IconChevronRight size={22} />
      </Link>
    </section>
  );
}

export function SesionSection() {
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
    <Section label="Sesión y Acerca de" id="sesion">
      <Card className="aj-card">
        <p className="t-cuerpo">{user ? `Has entrado como ${user.username}.` : 'Sin sesión.'}</p>
        <Button variant="secondary" block loading={signOut.isPending} loadingLabel="Cerrando…" onClick={() => signOut.mutate()}>
          Cerrar sesión
        </Button>
        <p className="t-detalle text-suave">Cerrar sesión no desactiva las notificaciones de este dispositivo.</p>
        <ErrorRetry error={signOut.error} />
      </Card>
      <Card className="aj-card aj-card-tight">
        <Row label="Versión">oficina {APP_VERSION}</Row>
        <div className="aj-credit">
          <p className="t-detalle text-suave">{ART_CREDIT}</p>
          <ExternalLink href={ART_CREDIT_URL} className="aj-credit-link">
            <span className="vh">LimeZu en itch.io</span>
          </ExternalLink>
        </div>
      </Card>
    </Section>
  );
}
