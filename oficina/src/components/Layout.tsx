import { createContext, useContext, useEffect, useMemo, useState, useSyncExternalStore, type ReactNode } from 'react';
import { Link, NavLink, Outlet, matchPath, useLocation } from 'react-router-dom';
import { useOverview, useTuTurno } from '../api/hooks';
import { CaptureButton } from '../capture/CaptureButton';
import { useCapture } from '../capture/CaptureContext';
import { CaptureSheetHost } from '../capture/CaptureSheet';
import {
  IconAjustes,
  IconCalendario,
  IconChevronLeft,
  IconChevronRight,
  IconGaleria,
  IconMicrofono,
  IconNotificaciones,
  IconOficina,
  IconPausa,
  IconPersonas,
  IconResultados,
  IconTuTurno,
} from './icons';
import { EXTERNAL_HINT_ID } from './ui/ExternalLink';
import { turnoAnchor } from '../../../compartido/src/logic/turno';

type IconComponent = typeof IconOficina;

interface NavItem {
  to: string;
  label: string;
  icon: IconComponent;
  end?: boolean;
}

const OFICINA: NavItem = { to: '/', label: 'Oficina', icon: IconOficina, end: true };
const TU_TURNO: NavItem = { to: '/tu-turno', label: 'Tu turno', icon: IconTuTurno };
const NOTIFICACIONES: NavItem = { to: '/notificaciones', label: 'Notificaciones', icon: IconNotificaciones };
const CALENDARIO: NavItem = { to: '/calendario', label: 'Calendario', icon: IconCalendario };
const RESULTADOS: NavItem = { to: '/resultados', label: 'Resultados', icon: IconResultados };
const PERSONAS: NavItem = { to: '/personas', label: 'Personas', icon: IconPersonas };
const GALERIA: NavItem = { to: '/galeria', label: 'Galería', icon: IconGaleria };
const AJUSTES: NavItem = { to: '/ajustes', label: 'Ajustes', icon: IconAjustes };

/** Desktop sidebar: the eight views. */
export const SIDEBAR_NAV: readonly NavItem[] = [OFICINA, TU_TURNO, NOTIFICACIONES, CALENDARIO, RESULTADOS, PERSONAS, GALERIA, AJUSTES];
/** Mobile bottom bar, around the capture button in the centre. */
export const BOTTOM_NAV_LEFT: readonly NavItem[] = [OFICINA, RESULTADOS];
export const BOTTOM_NAV_RIGHT: readonly NavItem[] = [PERSONAS, GALERIA];
/** Mobile top bar, right side. */
export const TOP_NAV: readonly NavItem[] = [TU_TURNO, NOTIFICACIONES, CALENDARIO, AJUSTES];

const ART_CREDIT_URL = 'https://limezu.itch.io/moderninteriors';

// ---------------------------------------------------------------- shell helpers

/** Anchor id of a Tu turno card (shared with the native app: compartido/src/logic/turno.ts). */
export { turnoAnchor };

function subscribeOnline(callback: () => void) {
  window.addEventListener('online', callback);
  window.addEventListener('offline', callback);
  return () => {
    window.removeEventListener('online', callback);
    window.removeEventListener('offline', callback);
  };
}

/** navigator.onLine, kept up to date. */
export function useOnline(): boolean {
  return useSyncExternalStore(
    subscribeOnline,
    () => navigator.onLine,
    () => true,
  );
}

export interface TopBarBack {
  to: string;
  label: string;
}

interface ShellState {
  back: TopBarBack | null;
  setBack: (back: TopBarBack | null) => void;
}

const ShellContext = createContext<ShellState>({ back: null, setBack: () => {} });

/**
 * On mobile, detail views replace the logo with «← {label}». /calendario/pieza/:id and
 * /personas/:id get one by default; call this to point it somewhere else (e.g. the piece's day).
 */
export function useTopBarBack(back: TopBarBack | null) {
  const { setBack } = useContext(ShellContext);
  const to = back?.to;
  const label = back?.label;
  useEffect(() => {
    setBack(to && label ? { to, label } : null);
    return () => setBack(null);
  }, [setBack, to, label]);
}

function defaultBack(pathname: string): TopBarBack | null {
  if (matchPath('/calendario/pieza/:pieceId', pathname)) return { to: '/calendario', label: 'Calendario' };
  if (matchPath('/personas/:contactId', pathname)) return { to: '/personas', label: 'Personas' };
  return null;
}

/** Scroll to the top on a new view, or to the #anchor when there is one. */
function useScrollOnNavigate() {
  const { pathname, hash } = useLocation();
  useEffect(() => {
    if (hash) {
      document.getElementById(decodeURIComponent(hash.slice(1)))?.scrollIntoView?.({ block: 'start' });
      return;
    }
    window.scrollTo?.(0, 0);
  }, [pathname, hash]);
}

// ---------------------------------------------------------------- banners

/**
 * Global pause banner, under the top bar on every view, from `overview.control`. When the machine runs
 * but a LinkedIn account is paused, it says so and links to that notice in Tu turno.
 */
export function PauseBanner() {
  const overview = useOverview();
  const control = overview.data?.control;
  if (control?.paused) {
    const detail = [control.reason, control.source === 'env' ? 'fijada en el entorno' : ''].filter(Boolean);
    return (
      <div role="status" aria-live="polite">
        <Link to="/ajustes#maquina" className="pausebanner">
          <span className="pauseicon" aria-hidden="true">
            <IconPausa size={20} />
          </span>
          <span className="pausetext">
            <span className="pausetitle">Máquina en pausa</span>
            {detail.map((part) => (
              <span key={part}> · {part}</span>
            ))}
          </span>
          <IconChevronRight size={20} />
        </Link>
      </div>
    );
  }
  const account = overview.data?.accounts?.find((a) => a.paused);
  if (account) {
    return (
      <div role="status" aria-live="polite">
        <Link to={`/tu-turno#${turnoAnchor(`account_paused:${account.id}`)}`} className="pausebanner">
          <span className="pauseicon" aria-hidden="true">
            <IconPausa size={20} />
          </span>
          <span className="pausetext">
            <span className="pausetitle">La cuenta de LinkedIn está en pausa</span>
            {account.paused_reason ? <span> · {account.paused_reason}</span> : null}
          </span>
          <IconChevronRight size={20} />
        </Link>
      </div>
    );
  }
  return null;
}

export function OfflineStrip() {
  const online = useOnline();
  if (online) return null;
  return (
    <p className="offlinestrip" role="status">
      Sin conexión. Mostrando lo último que cargó.
    </p>
  );
}

// ---------------------------------------------------------------- navigation pieces

interface TurnCount {
  count: number;
  critical: boolean;
  /** Urgent items (critical cards), for the accessible label. */
  urgent: number;
  /** Unread notifications: only drives the bell dot, never a number. */
  unread: number;
}

/**
 * Badges from GET /api/v1/tu-turno: the Tu turno number (hidden at 0, alerta when `critical`) and
 * `notifications_unread` for the bell dot.
 */
function useTurnCount(): TurnCount {
  const turno = useTuTurno();
  const data = turno.data;
  const cards = data ? [...(data.alerts ?? []), ...(data.questions ?? []), ...(data.tasks?.perfil ?? []), ...(data.tasks?.conversaciones ?? [])] : [];
  return {
    count: data?.count ?? 0,
    critical: Boolean(data?.critical),
    urgent: data?.urgent_count ?? cards.filter((card) => card.critical).length,
    unread: data?.notifications_unread ?? 0,
  };
}

/** «Tu turno, 6 pendientes, 1 urgente». */
export function turnLabel({ count, critical, urgent }: Pick<TurnCount, 'count' | 'critical' | 'urgent'>): string {
  if (count <= 0) return 'Tu turno';
  const pending = `${count} ${count === 1 ? 'pendiente' : 'pendientes'}`;
  const urgentText = critical ? (urgent > 0 ? `, ${urgent} ${urgent === 1 ? 'urgente' : 'urgentes'}` : ', con algo urgente') : '';
  return `Tu turno, ${pending}${urgentText}`;
}

function notificationsLabel(unread: number): string {
  return unread > 0 ? 'Notificaciones, hay novedades' : 'Notificaciones';
}

function Counter({ count, critical }: Pick<TurnCount, 'count' | 'critical'>) {
  if (count <= 0) return null;
  return (
    <span className="navcount" data-tone={critical ? 'critical' : 'neutral'} aria-hidden="true">
      {count > 99 ? '99+' : count}
    </span>
  );
}

function UnreadDot({ unread }: { unread: number }) {
  if (unread <= 0) return null;
  return <span className="navdot" aria-hidden="true" />;
}

function navLabel(item: NavItem, turn: TurnCount): string | undefined {
  if (item.to === TU_TURNO.to) return turnLabel(turn);
  if (item.to === NOTIFICACIONES.to) return notificationsLabel(turn.unread);
  return undefined;
}

function NavBadge({ item, turn }: { item: NavItem; turn: TurnCount }) {
  if (item.to === TU_TURNO.to) return <Counter count={turn.count} critical={turn.critical} />;
  if (item.to === NOTIFICACIONES.to) return <UnreadDot unread={turn.unread} />;
  return null;
}

function Sidebar({ turn }: { turn: TurnCount }) {
  const { openCapture } = useCapture();
  return (
    <aside className="sidebar">
      <Link to="/" className="sidebar-brand" aria-label="0ff1ce, ir a la Oficina">
        <img src="/brand/firma-horizontal.svg" alt="0ff1ce" width={105} height={32} />
      </Link>
      <button type="button" className="btn primary block capture-side" onClick={() => openCapture()}>
        <IconMicrofono size={22} />
        Capturar
      </button>
      <nav aria-label="Secciones">
        <ul>
          {SIDEBAR_NAV.map((item) => {
            const Icon = item.icon;
            return (
              <li key={item.to}>
                <NavLink to={item.to} end={item.end} aria-label={navLabel(item, turn)}>
                  <Icon />
                  <span>{item.label}</span>
                  <NavBadge item={item} turn={turn} />
                </NavLink>
              </li>
            );
          })}
        </ul>
      </nav>
      <p className="credit">
        Arte:{' '}
        <a href={ART_CREDIT_URL} target="_blank" rel="noopener noreferrer">
          LimeZu · Modern Interiors
        </a>
      </p>
    </aside>
  );
}

function TopBar({ turn, back }: { turn: TurnCount; back: TopBarBack | null }) {
  return (
    <header className="topbar">
      {back ? (
        <Link to={back.to} className="topbar-back">
          <IconChevronLeft size={20} />
          {back.label}
        </Link>
      ) : (
        <Link to="/" className="topbar-brand" aria-label="0ff1ce, ir a la Oficina">
          <img src="/brand/firma-horizontal.svg" alt="0ff1ce" width={92} height={28} />
        </Link>
      )}
      <nav className="topbar-nav" aria-label="Accesos">
        {TOP_NAV.map((item) => {
          const Icon = item.icon;
          return (
            <NavLink key={item.to} to={item.to} className="topbar-icon" aria-label={navLabel(item, turn) ?? item.label}>
              <Icon />
              <NavBadge item={item} turn={turn} />
            </NavLink>
          );
        })}
      </nav>
    </header>
  );
}

function BottomLink({ item }: { item: NavItem }) {
  const Icon = item.icon;
  return (
    <NavLink to={item.to} end={item.end}>
      <span className="navpill" aria-hidden="true">
        <Icon />
      </span>
      <span className="navlabel">{item.label}</span>
    </NavLink>
  );
}

function BottomNav() {
  return (
    <nav className="bottomnav" aria-label="Secciones">
      {BOTTOM_NAV_LEFT.map((item) => (
        <BottomLink key={item.to} item={item} />
      ))}
      <CaptureButton />
      {BOTTOM_NAV_RIGHT.map((item) => (
        <BottomLink key={item.to} item={item} />
      ))}
    </nav>
  );
}

// ---------------------------------------------------------------- layout

export function ShellProvider({ children }: { children: ReactNode }) {
  const [back, setBack] = useState<TopBarBack | null>(null);
  const value = useMemo(() => ({ back, setBack }), [back]);
  return <ShellContext.Provider value={value}>{children}</ShellContext.Provider>;
}

function Shell() {
  const location = useLocation();
  const { back } = useContext(ShellContext);
  const turn = useTurnCount();
  useScrollOnNavigate();
  const topBack = back ?? defaultBack(location.pathname);

  return (
    <div className="shell">
      <a className="skiplink" href="#contenido">
        Saltar al contenido
      </a>
      <Sidebar turn={turn} />
      <div className="shell-main">
        <div className="shell-head">
          <TopBar turn={turn} back={topBack} />
          <PauseBanner />
          <OfflineStrip />
        </div>
        <main id="contenido" className="shell-content" tabIndex={-1}>
          <Outlet />
        </main>
      </div>
      <BottomNav />
      <CaptureSheetHost />
      <span id={EXTERNAL_HINT_ID} hidden>
        Se abre en otra pestaña
      </span>
    </div>
  );
}

/** App shell: sidebar (desktop), top bar + bottom bar with the capture button (mobile), banners. */
export function Layout() {
  return (
    <ShellProvider>
      <Shell />
    </ShellProvider>
  );
}
