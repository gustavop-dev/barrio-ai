// Ajustes (Ajustes.dc.html, DISENO-VISTAS «6. Ajustes», rev 18): connections, this device and the
// machine controls that are rarely touched. On desktop a sub-index on the left jumps to each section.
import { Link } from 'react-router-dom';
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

/** The anchors of the sub-index (the pause banner links to #maquina). */
export const AJUSTES_SECTIONS = [
  { id: 'maquina', label: 'Máquina' },
  { id: 'orientacion', label: 'Orientación para el equipo' },
  { id: 'autonomia', label: 'Autonomía y límites' },
  { id: 'gasto', label: 'Gasto de IA' },
  { id: 'linkedin', label: 'LinkedIn oficial' },
  { id: 'captura', label: 'Captura y galería' },
  { id: 'notificaciones', label: 'Notificaciones' },
  { id: 'sabe', label: 'Lo que el equipo sabe de ti' },
  { id: 'sesion', label: 'Sesión y Acerca de' },
] as const;

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
