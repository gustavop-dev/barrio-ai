// Ajustes (Ajustes.dc.html, DISENO-VISTAS «6. Ajustes», rev 18): connections, this device and the
// machine controls that are rarely touched. On desktop a sub-index on the left jumps to each section.
import { Link } from 'react-router-dom';
import { AJUSTES_SECTIONS } from '../../../compartido/src/logic/ajustes';
import { Page } from '../components/ui';
import { AutonomiaSection } from './ajustes/Autonomia';
import { CapturaSection } from './ajustes/Captura';
import { GastoSection } from './ajustes/Gasto';
import { LinkedInSection } from './ajustes/LinkedIn';
import { MaquinaSection } from './ajustes/Maquina';
import { NotificacionesSection } from './ajustes/Notificaciones';
import { OrientacionSection } from './ajustes/Orientacion';
import { SabeLink, SesionSection } from './ajustes/Sesion';
import './ajustes/ajustes.css';

// The anchors of the sub-index (the pause banner links to #maquina), shared with the native app.
export { AJUSTES_SECTIONS } from '../../../compartido/src/logic/ajustes';

export function Ajustes() {
  return (
    <Page title="Ajustes">
      <div className="aj-layout">
        <nav className="aj-index desktop-only" aria-label="Secciones de Ajustes">
          <ul>
            {AJUSTES_SECTIONS.map((section) => (
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
          <SabeLink />
          <SesionSection />
        </div>
      </div>
    </Page>
  );
}
