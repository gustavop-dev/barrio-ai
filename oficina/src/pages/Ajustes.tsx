// Ajustes (Ajustes.dc.html, DISENO-VISTAS «6. Ajustes», rev 18): connections, this device and the
// machine controls that are rarely touched. On desktop a sub-index on the left jumps to each section.
// Organizaciones, phase 7: every member also has «Mi perfil» and «Mi voz», the admin «Organización», and a member in
// onboarding (inactive) reads first what is left before the admin activates her.
import { Link } from 'react-router-dom';
import { ajustesSections } from '../../../compartido/src/logic/ajustes';
import { ALTA_NOTICE, inOnboarding } from '../../../compartido/src/logic/miembro';
import { useYo } from '../api/hooks';
import { Note, Page } from '../components/ui';
import { AutonomiaSection } from './ajustes/Autonomia';
import { CapturaSection } from './ajustes/Captura';
import { GastoSection } from './ajustes/Gasto';
import { LinkedInSection } from './ajustes/LinkedIn';
import { MaquinaSection } from './ajustes/Maquina';
import { MiPerfilSection } from './ajustes/MiPerfil';
import { MiVozSection } from './ajustes/MiVoz';
import { NotificacionesSection } from './ajustes/Notificaciones';
import { OrganizacionSection } from './ajustes/Organizacion';
import { OrientacionSection } from './ajustes/Orientacion';
import { SabeLink, SesionSection } from './ajustes/Sesion';
import './ajustes/ajustes.css';

// The anchors of the sub-index (the pause banner links to #maquina), shared with the native app.
export { AJUSTES_SECTIONS } from '../../../compartido/src/logic/ajustes';

export function Ajustes() {
  const yo = useYo();
  const member = yo.data?.member ?? null;
  return (
    <Page title="Ajustes">
      {inOnboarding(yo.data) ? (
        <Note tone="warn" title="Tu cuenta está en alta">
          {ALTA_NOTICE}
        </Note>
      ) : null}
      <Link to="/equipo">Mapa del equipo</Link>
      <div className="aj-layout">
        <nav className="aj-index desktop-only" aria-label="Secciones de Ajustes">
          <ul>
            {ajustesSections(yo.data).map((section) => (
              <li key={section.id}>
                <Link to={{ hash: `#${section.id}` }} replace>
                  {section.label}
                </Link>
              </li>
            ))}
          </ul>
        </nav>
        <div className="aj-sections">
          <MaquinaSection />
          <OrientacionSection />
          <AutonomiaSection />
          <GastoSection />
          <LinkedInSection />
          <CapturaSection />
          <NotificacionesSection />
          {member ? <MiPerfilSection /> : null}
          {member ? <MiVozSection /> : null}
          {member && yo.data?.is_admin ? <OrganizacionSection /> : null}
          <SabeLink />
          <SesionSection />
        </div>
      </div>
    </Page>
  );
}
