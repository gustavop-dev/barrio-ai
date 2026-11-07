import { Link, NavLink, Outlet } from 'react-router-dom';
import { useOverview } from '../api/hooks';

export const NAV = [
  { to: '/', label: 'Oficina', short: 'Oficina', icon: '⌂' },
  { to: '/maquina', label: 'Máquina', short: 'Máquina', icon: '◉' },
  { to: '/acciones', label: 'Acciones', short: 'Acciones', icon: '✓' },
  { to: '/contenido', label: 'Contenido', short: 'Piezas', icon: '✎' },
  { to: '/referentes', label: 'Referentes', short: 'Referentes', icon: '☆' },
  { to: '/conocimiento', label: 'Conocimiento', short: 'Fuentes', icon: '▤' },
  { to: '/memoria', label: 'Memoria', short: 'Memoria', icon: '◈' },
  { to: '/ajustes', label: 'Ajustes', short: 'Ajustes', icon: '⚙' },
] as const;

/** Always-visible warning while the whole machine is stopped. */
export function PauseBanner() {
  const overview = useOverview();
  const control = overview.data?.control;
  if (!control?.paused) return null;
  return (
    <Link to="/maquina" className="pausebanner" role="status" aria-live="polite">
      <span className="pauseicon" aria-hidden="true">
        ❚❚
      </span>
      <span>
        <strong>Máquina en pausa</strong>
        {control.reason ? <span className="pausereason"> · {control.reason}</span> : null}
        {control.source === 'env' ? <span className="pausereason"> · fijada en el entorno</span> : null}
      </span>
    </Link>
  );
}

export function Layout() {
  return (
    <div className="shell">
      <a className="skiplink" href="#contenido">
        Saltar al contenido
      </a>
      <nav className="sidenav" aria-label="Secciones">
        <Link to="/" className="brand" aria-label="Barrio AI, inicio">
          <img src="/icons/icon-192.png" alt="" width="40" height="40" />
          <span>
            Barrio <b>AI</b>
          </span>
        </Link>
        <ul>
          {NAV.map((item) => (
            <li key={item.to}>
              <NavLink to={item.to} end={item.to === '/'}>
                <span className="navicon" aria-hidden="true">
                  {item.icon}
                </span>
                {item.label}
              </NavLink>
            </li>
          ))}
        </ul>
        <p className="credit">
          Arte:{' '}
          <a href="https://limezu.itch.io/moderninteriors" target="_blank" rel="noopener noreferrer">
            LimeZu · Modern Interiors
          </a>
        </p>
      </nav>
      <div className="main">
        <header className="topbar">
          <Link to="/" className="brand small" aria-label="Barrio AI, inicio">
            <img src="/icons/icon-192.png" alt="" width="32" height="32" />
            <span>
              Barrio <b>AI</b>
            </span>
          </Link>
        </header>
        <PauseBanner />
        <main id="contenido" tabIndex={-1}>
          <Outlet />
        </main>
      </div>
      <nav className="bottomnav" aria-label="Secciones">
        {NAV.map((item) => (
          <NavLink key={item.to} to={item.to} end={item.to === '/'} aria-label={item.label}>
            <span className="navicon" aria-hidden="true">
              {item.icon}
            </span>
            <span className="navlabel">{item.short}</span>
          </NavLink>
        ))}
      </nav>
    </div>
  );
}
