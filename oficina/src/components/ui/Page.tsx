import { useEffect, type ReactNode } from 'react';

export const APP_NAME = '0ff1ce';

/** Sets the tab title to «{title} · 0ff1ce» while the view is mounted. */
export function usePageTitle(title: string | null | undefined) {
  useEffect(() => {
    if (!title) return;
    const previous = document.title;
    document.title = `${title} · ${APP_NAME}`;
    return () => {
      document.title = previous;
    };
  }, [title]);
}

export interface PageProps {
  /** h1 of the view (32/40) and the tab title. */
  title: string;
  /** Line under the title, tinta-suave («2 avisos · 3 preguntas · 1 tarea»). */
  subtitle?: ReactNode;
  /** Controls on the right of the title (Hoy, ←, →). */
  actions?: ReactNode;
  /** narrow: ~760px column (Bandeja de entrada, Ajustes); default: 1280px; full: no max width. */
  width?: 'narrow' | 'default' | 'full';
  /** Hides the visual h1 (keeps it for screen readers) when the design has no title. */
  hideTitle?: boolean;
  children?: ReactNode;
}

/** Standard view wrapper: padding 20/16 on mobile, 32/40 on desktop, 24px between blocks. */
export function Page({ title, subtitle, actions, width = 'default', hideTitle = false, children }: PageProps) {
  usePageTitle(title);
  return (
    <div className={['page', width !== 'default' ? width : ''].filter(Boolean).join(' ')}>
      <header className={hideTitle ? 'page-head vh' : 'page-head'}>
        <div className="page-headrow">
          <h1 className="page-title">{title}</h1>
          {actions ? <div className="page-actions">{actions}</div> : null}
        </div>
        {subtitle ? <p className="page-subtitle">{subtitle}</p> : null}
      </header>
      {children}
    </div>
  );
}

export interface SectionProps {
  /** UPPERCASE label («AVISOS», «1 · ¿GENERA NEGOCIO?»). */
  label: ReactNode;
  id?: string;
  /** Text under the label, tinta-suave. */
  intro?: ReactNode;
  children?: ReactNode;
  className?: string;
}

/** A block of a view: etiqueta label, optional intro and content with 12px gaps. */
export function Section({ label, id, intro, children, className }: SectionProps) {
  const headingId = id ? `${id}-titulo` : undefined;
  return (
    <section className={['section', className ?? ''].filter(Boolean).join(' ')} id={id} aria-labelledby={headingId}>
      <h2 className="section-label" id={headingId}>
        {label}
      </h2>
      {intro ? <p className="t-detalle text-suave">{intro}</p> : null}
      {children}
    </section>
  );
}

export interface SegmentedOption<T extends string> {
  value: T;
  label: string;
}

export interface SegmentedProps<T extends string> {
  label: string;
  options: readonly SegmentedOption<T>[];
  value: T;
  onChange: (value: T) => void;
}

/** Segmented control (7 · 28 · 90 días; Mes · Semana · Lista): one pressed button in a linea tray. */
export function Segmented<T extends string>({ label, options, value, onChange }: SegmentedProps<T>) {
  return (
    <div role="group" aria-label={label} className="segmented">
      {options.map((option) => (
        <button key={option.value} type="button" aria-pressed={option.value === value} onClick={() => onChange(option.value)}>
          {option.label}
        </button>
      ))}
    </div>
  );
}

export interface TabItem<T extends string> {
  value: T;
  label: string;
}

export interface TabBarProps<T extends string> {
  label: string;
  tabs: readonly TabItem<T>[];
  value: T;
  onChange: (value: T) => void;
  /** id prefix: each tab is `${idPrefix}-${value}` and controls `${idPrefix}-${value}-panel`. */
  idPrefix: string;
}

/** Underlined tabs (Pendiente · Lo que el equipo sabe de ti). Arrow keys move between tabs. */
export function TabBar<T extends string>({ label, tabs, value, onChange, idPrefix }: TabBarProps<T>) {
  return (
    <div
      role="tablist"
      aria-label={label}
      className="tabbar"
      onKeyDown={(event) => {
        if (event.key !== 'ArrowRight' && event.key !== 'ArrowLeft') return;
        const index = tabs.findIndex((t) => t.value === value);
        const next = tabs[(index + (event.key === 'ArrowRight' ? 1 : tabs.length - 1)) % tabs.length];
        if (next) {
          onChange(next.value);
          document.getElementById(`${idPrefix}-${next.value}`)?.focus();
        }
      }}
    >
      {tabs.map((tab) => (
        <button
          key={tab.value}
          id={`${idPrefix}-${tab.value}`}
          type="button"
          role="tab"
          aria-selected={tab.value === value}
          aria-controls={`${idPrefix}-${tab.value}-panel`}
          tabIndex={tab.value === value ? 0 : -1}
          onClick={() => onChange(tab.value)}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}
