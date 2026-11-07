import { useId, useState, type MouseEvent, type ReactNode } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  dataUntil,
  NOT_SPLIT_BY_MODALITY,
  periodNote,
  readDias,
  readModalidad,
  RESULTADOS_MODALITIES as MODALITIES,
  RESULTADOS_PERIODS as PERIODS,
  RESULTADOS_SECTIONS as SECTIONS,
} from '../../../compartido/src/logic/resultados';
import { useResultados } from '../api/hooks';
import type { Resultados as ResultadosData } from '../api/types';
import { ErrorRetry, Page, Section, Skeleton } from '../components/ui';
import { OportunidadForm } from './personas/OportunidadForm';
import { ResumenSemanal } from './resultados/ResumenSemanal';
import { Contenido, Equipo, Gente, Negocio, SectionBoundary } from './resultados/sections';
import './resultados/resultados.css';

// Shared with the native app (compartido/src/logic/resultados.ts).
export { dataUntil };

function jump(id: string) {
  return (event: MouseEvent<HTMLAnchorElement>) => {
    event.preventDefault();
    const reduce = typeof window.matchMedia === 'function' && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    document.getElementById(id)?.scrollIntoView?.({ behavior: reduce ? 'auto' : 'smooth', block: 'start' });
    const heading = document.getElementById(`${id}-titulo`);
    if (heading) {
      heading.setAttribute('tabindex', '-1');
      heading.focus({ preventScroll: true });
    }
  };
}

function Compact<T extends string | number>({ label, value, options, onChange }: { label: string; value: T; options: readonly { value: T; label: string }[]; onChange: (value: string) => void }) {
  const id = useId();
  return (
    <div className="res-select">
      <label htmlFor={id}>{label}</label>
      <select id={id} value={String(value)} onChange={(event) => onChange(event.target.value)}>
        {options.map((option) => (
          <option key={option.value} value={String(option.value)}>
            {option.label}
          </option>
        ))}
      </select>
    </div>
  );
}

/** /resultados: the weekly summary, then «¿vamos bien?» in the order business → audience → content → team. */
export function Resultados() {
  const [params, setParams] = useSearchParams();
  const dias = readDias(params.get('dias'));
  const modalidad = readModalidad(params.get('modalidad'));
  const query = useResultados(dias, modalidad);
  const [registering, setRegistering] = useState(false);
  const data = query.data;
  const retry = () => void query.refetch();

  const set = (key: 'dias' | 'modalidad', value: string, fallback: string) => {
    setParams(
      (current) => {
        const next = new URLSearchParams(current);
        if (value === fallback) next.delete(key);
        else next.set(key, value);
        return next;
      },
      { replace: true },
    );
  };

  const block = (render: (data: ResultadosData) => ReactNode, skeleton = 4) => {
    if (data) return <SectionBoundary onRetry={retry}>{render(data)}</SectionBoundary>;
    if (query.isPending) return <Skeleton variant="kpi" count={skeleton} label="Cargando…" />;
    return <p className="res-muted">No se pudo cargar esta sección.</p>;
  };

  const notSplit = modalidad !== 'todo' ? NOT_SPLIT_BY_MODALITY : undefined;

  return (
    <Page title="Resultados">
      <ResumenSemanal />

      <div className="res-controls">
        <div className="res-selects">
          <Compact label="Periodo" value={dias} options={PERIODS} onChange={(value) => set('dias', value, '28')} />
          <Compact label="Modalidad" value={modalidad} options={MODALITIES} onChange={(value) => set('modalidad', value, 'todo')} />
        </div>
        <p className="res-muted" aria-live="polite">
          {periodNote(data, query.isPending, dias)}
        </p>
        <nav aria-label="Secciones de Resultados" className="res-jump">
          {SECTIONS.map((section) => (
            <a key={section.id} href={`#${section.id}`} onClick={jump(section.id)}>
              {section.chip}
            </a>
          ))}
        </nav>
      </div>

      {query.isError ? <ErrorRetry title={data ? 'No se pudo actualizar' : 'No se pudieron cargar los resultados'} error={query.error} onRetry={retry} /> : null}

      <div className={query.isPlaceholderData ? 'res-body stale' : 'res-body'} aria-busy={query.isPlaceholderData || undefined}>
        <Section id={SECTIONS[0].id} label={SECTIONS[0].label} className="res-section">
          {block((d) => <Negocio data={d.negocio} onRegister={() => setRegistering(true)} />, 6)}
        </Section>
        <Section id={SECTIONS[1].id} label={SECTIONS[1].label} className="res-section">
          {block((d) => <Gente data={d.audiencia} />, 6)}
        </Section>
        <Section id={SECTIONS[2].id} label={SECTIONS[2].label} intro={notSplit} className="res-section">
          {block((d) => <Contenido data={d.contenido} />)}
        </Section>
        <Section id={SECTIONS[3].id} label={SECTIONS[3].label} intro={notSplit} className="res-section">
          {block((d) => <Equipo data={d.equipo} />)}
        </Section>
      </div>

      {registering ? <OportunidadForm onClose={() => setRegistering(false)} /> : null}
    </Page>
  );
}
