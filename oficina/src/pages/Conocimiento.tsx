import { useMutation, useQuery } from '@tanstack/react-query';
import { useState, type FormEvent } from 'react';
import { useSearchParams } from 'react-router-dom';
import { getSource, getUnit, searchKnowledge } from '../api/endpoints';
import { keys } from '../api/queryClient';
import { Empty, ErrorNote, Loading, PageHeader } from '../components/ui';
import { prettyValue } from '../lib/format';

/** Evidence is fetched from GET /sources/<key> only when opened. */
function SourceDetail({ sourceKey }: { sourceKey: string }) {
  const [open, setOpen] = useState(false);
  const source = useQuery({ queryKey: keys.source(sourceKey), queryFn: () => getSource(sourceKey), enabled: open });
  return (
    <details className="source" onToggle={(event) => setOpen((event.currentTarget as HTMLDetailsElement).open)}>
      <summary>{sourceKey}</summary>
      {open && source.isPending ? <Loading label="Abriendo la fuente…" /> : null}
      {source.isError ? <ErrorNote error={source.error} /> : null}
      {source.isSuccess ? <pre className="readable">{prettyValue(source.data)}</pre> : null}
    </details>
  );
}

function UnitDetail({ unitId, onClose }: { unitId: string; onClose: () => void }) {
  const unit = useQuery({ queryKey: keys.unit(unitId), queryFn: () => getUnit(unitId) });
  return (
    <section className="card unit" aria-labelledby="unit-title">
      <div className="cardhead">
        <p className="eyebrow">UNIDAD {unitId}</p>
        <button type="button" className="secondary" onClick={onClose}>
          Cerrar
        </button>
      </div>
      {unit.isPending ? <Loading label="Recuperando la unidad original…" /> : null}
      {unit.isError ? <ErrorNote error={unit.error} onRetry={() => void unit.refetch()} /> : null}
      {unit.data ? (
        <>
          <h2 id="unit-title">{unit.data.title}</h2>
          <p className="muted small">Clase {String(unit.data.session).padStart(2, '0')} · conocimiento original del curso, sin reescribir.</p>
          {unit.data.original && typeof unit.data.original === 'object' && !Array.isArray(unit.data.original) ? (
            Object.entries(unit.data.original as Record<string, unknown>).map(([field, value]) => (
              <details key={field} open={field === 'explanation'}>
                <summary>{field}</summary>
                <pre className="readable">{prettyValue(value)}</pre>
              </details>
            ))
          ) : unit.data.original !== undefined ? (
            <pre className="readable">{prettyValue(unit.data.original)}</pre>
          ) : null}
          <h3>Fuentes</h3>
          {unit.data.sources?.length ? (
            unit.data.sources.map((source) => <SourceDetail key={source.key} sourceKey={source.key} />)
          ) : (
            <Empty>Esta unidad no tiene fuentes enlazadas.</Empty>
          )}
        </>
      ) : null}
    </section>
  );
}

export function Conocimiento() {
  const [params, setParams] = useSearchParams();
  const unitId = params.get('unidad');
  const [query, setQuery] = useState(params.get('q') ?? '');
  const search = useMutation({ mutationFn: (text: string) => searchKnowledge(text, 12) });

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const text = query.trim();
    if (!text) return;
    search.mutate(text);
  };
  const openUnit = (id: string) => {
    const next = new URLSearchParams(params);
    next.set('unidad', id);
    setParams(next);
  };
  const closeUnit = () => {
    const next = new URLSearchParams(params);
    next.delete('unidad');
    setParams(next);
  };

  return (
    <div className="stack">
      <PageHeader eyebrow="BIBLIOTECA · CLASES 01–06" title="Conocimiento">
        Busca en las unidades originales del curso y comprueba sus fuentes. Búsqueda textual, sin coste.
      </PageHeader>
      <form className="card searchform" onSubmit={submit} role="search">
        <label htmlFor="q">¿Qué conocimiento necesitas?</label>
        <div className="inline">
          <input id="q" type="search" maxLength={6000} value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Titular, comprador, barrio…" />
          <button type="submit" className="primary" disabled={!query.trim() || search.isPending}>
            {search.isPending ? 'Buscando…' : 'Buscar'}
          </button>
        </div>
      </form>
      {unitId ? <UnitDetail unitId={unitId} onClose={closeUnit} /> : null}
      <ErrorNote error={search.error} />
      {search.data?.warnings?.length ? (
        <div className="note warn">
          {search.data.warnings.map((warning) => (
            <p key={warning}>{warning}</p>
          ))}
        </div>
      ) : null}
      {search.data ? (
        search.data.results.length ? (
          <ul className="list" aria-label="Resultados">
            {search.data.results.map((result) => (
              <li key={result.id}>
                <button type="button" className="result" onClick={() => openUnit(result.id)}>
                  <strong>{result.title}</strong>
                  <small>
                    {result.id} · Clase {String(result.session).padStart(2, '0')} · relevancia {result.score.toFixed(3)}
                  </small>
                </button>
              </li>
            ))}
          </ul>
        ) : (
          <Empty>No encontramos coincidencias. Prueba con otras palabras.</Empty>
        )
      ) : null}
    </div>
  );
}
