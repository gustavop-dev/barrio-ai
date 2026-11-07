// Resultados › «Resumen de la semana»: the weekly summary of the results analyst (GET /api/v1/resultados/resumen-semanal).
// Gustavo reads it, adopts its proposed orientation (undoable for 5 s) or discards it, and can generate a missing one.
import { useEffect, useRef, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { useGenerarResumen, useResumenDecision, useResumenSemanal } from '../../api/hooks';
import type { WeeklySummary, WeeklySummaryGenerate, WeeklySummaryItem, WeeklySummaryState } from '../../api/types';
import { IconChevronDown } from '../../components/icons';
import { AgentPortrait, Badge, Button, Card, ConfirmModal, EmptyState, ErrorNote, errorMessage, Note, Section, Skeleton, useToast, type Tone } from '../../components/ui';
import { formatDateTime, formatTime, formatUsd } from '../../lib/format';

const ROLE = 'analista_barrio_resultados';
const ROLE_NAME = 'Analista del barrio';
/** Character sheet of the analyst in the scene (scene/roles.ts). */
const ANALYST_SPRITE = 3;
const OPERATOR_TZ = 'America/Bogota';

const STATE_BADGE: Record<WeeklySummaryState, { tone: Tone; label: string } | null> = {
  nuevo: { tone: 'ok', label: 'Nuevo' },
  visto: null,
  aplicado: { tone: 'info', label: 'Usado como orientación' },
  descartado: { tone: 'muted', label: 'Descartado' },
};

function newRequestId(): string | undefined {
  try {
    return typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function' ? crypto.randomUUID() : undefined;
  } catch {
    return undefined;
  }
}

/** «la semana del 2 al 8 de noviembre» from the backend's «Semana del …». */
function weekPhrase(label: string): string {
  return `la ${label.charAt(0).toLowerCase()}${label.slice(1)}`;
}

function Items({ title, items, empty }: { title: string; items: WeeklySummaryItem[]; empty: string }) {
  return (
    <div className="res-resumen-list">
      <h4 className="res-resumen-heading">{title}</h4>
      {items.length ? (
        <ul>
          {items.map((item, index) => (
            <li key={index}>
              <span>{item.texto}</span>
              {item.cifra ? <span className="res-resumen-cifra">Dato: {item.cifra}</span> : null}
            </li>
          ))}
        </ul>
      ) : (
        <p className="res-muted">{empty}</p>
      )}
    </div>
  );
}

/** The three lists and the warnings: what the data supports, and when it is too thin to conclude. */
function SummaryBody({ summary }: { summary: WeeklySummary }) {
  const analysis = summary.analysis;
  return (
    <>
      <div className="res-resumen-grid">
        <Items title="Lo que funcionó" items={analysis.lo_que_funciono ?? []} empty="Nada destacable con los datos de la semana." />
        <Items title="Lo que no" items={analysis.lo_que_no ?? []} empty="Nada que señalar con los datos de la semana." />
        <Items title="Recomendaciones" items={analysis.recomendaciones ?? []} empty="Sin recomendaciones: los datos no dan para tanto." />
      </div>
      {analysis.advertencias?.length ? (
        <Note tone="warn" role={null} title="Advertencias">
          <ul className="res-resumen-warnings">
            {analysis.advertencias.map((warning, index) => (
              <li key={index}>{warning}</li>
            ))}
          </ul>
        </Note>
      ) : null}
    </>
  );
}

type Decide = (summary: WeeklySummary, decision: 'aplicar' | 'descartar') => void;

/** «Orientación propuesta»: only Gustavo's decision turns it into the team's orientation. */
function Proposal({ summary, onDecide, busy, error }: { summary: WeeklySummary; onDecide: Decide; busy: boolean; error: unknown }) {
  const text = summary.analysis.orientacion_propuesta;
  if (!text) return null;
  const pending = summary.state === 'nuevo' || summary.state === 'visto';
  return (
    <div className="res-resumen-propuesta">
      <h4 className="res-resumen-heading">Orientación propuesta</h4>
      <blockquote className="quote">{text}</blockquote>
      {pending ? (
        <>
          <p className="res-muted">Si la usas, sustituye la orientación del equipo (Ajustes). Podrás deshacerlo durante 5 segundos.</p>
          <div className="res-resumen-actions">
            <Button variant="primary" disabled={busy} onClick={() => onDecide(summary, 'aplicar')}>
              Usar como orientación
            </Button>
            <Button variant="danger" disabled={busy} onClick={() => onDecide(summary, 'descartar')}>
              Descartar
            </Button>
          </div>
          <ErrorNote error={error} />
        </>
      ) : (
        <p className="res-muted">
          {summary.state === 'aplicado' ? 'La usaste como orientación del equipo' : 'La descartaste'}
          {summary.decided_at ? ` el ${formatDateTime(summary.decided_at)}` : ''}.
        </p>
      )}
    </div>
  );
}

function footer(summary: WeeklySummary): string {
  const cost = summary.cost_usd !== null ? ` · ${formatUsd(summary.cost_usd)}` : '';
  return `Escrito el ${formatDateTime(summary.created_at)}${cost}`;
}

function SummaryCard({ summary, onDecide, busy, error }: { summary: WeeklySummary; onDecide: Decide; busy: boolean; error: unknown }) {
  const badge = STATE_BADGE[summary.state];
  return (
    <Card
      as="article"
      className="res-resumen-card"
      eyebrow={summary.label}
      title={summary.analysis.titular}
      titleAs="h3"
      badges={badge ? <Badge tone={badge.tone}>{badge.label}</Badge> : undefined}
      footer={footer(summary)}
    >
      <AgentPortrait role={ROLE} showName name={ROLE_NAME} />
      <SummaryBody summary={summary} />
      <Proposal summary={summary} onDecide={onDecide} busy={busy} error={error} />
    </Card>
  );
}

/** «Generar ahora» behind the cost confirmation (POST /resultados/resumen-semanal/generar). */
function Generate({ offer }: { offer: WeeklySummaryGenerate }) {
  const generate = useGenerarResumen();
  const [asking, setAsking] = useState(false);
  // One id per intent: a retry after a network error never queues a second summary.
  const [requestId, setRequestId] = useState<string | undefined>(undefined);
  const week = weekPhrase(offer.label);
  if (generate.isSuccess || offer.pending) {
    return <Note tone="info">El analista está escribiendo el resumen de {week}. Tarda uno o dos minutos y aparecerá aquí.</Note>;
  }
  if (!offer.available) return null;
  const open = () => {
    generate.reset();
    setRequestId(newRequestId());
    setAsking(true);
  };
  return (
    <div className="res-resumen-generate">
      {offer.last_error ? (
        <Note tone="warn" role={null} title="El último intento no terminó">
          {offer.last_error}
        </Note>
      ) : null}
      <Button variant="secondary" onClick={open}>
        Generar ahora
      </Button>
      {asking ? (
        <ConfirmModal
          title="Generar el resumen de la semana"
          confirmLabel="Generar"
          busy={generate.isPending}
          error={generate.error}
          onClose={() => setAsking(false)}
          onConfirm={() => generate.mutate(requestId, { onSuccess: () => setAsking(false) })}
        >
          <p>El analista lee las cifras de {week} y escribe qué funcionó, qué no y qué cambiar, con una llamada a Claude.</p>
          <Note tone="warn" role={null}>
            Tiene coste: unos {formatUsd(offer.estimated_usd)} (como mucho {formatUsd(offer.max_usd)}), del presupuesto del resumen semanal.
          </Note>
        </ConfirmModal>
      ) : null}
    </div>
  );
}

function PreviousWeeks({ summaries }: { summaries: WeeklySummary[] }) {
  if (!summaries.length) return null;
  return (
    <details className="fold res-resumen-previous">
      <summary>
        Ver semanas anteriores · {summaries.length}
        <IconChevronDown size={20} />
      </summary>
      <div className="fold-body">
        <ul className="res-resumen-weeks">
          {summaries.map((summary) => {
            const badge = STATE_BADGE[summary.state];
            return (
              <li key={summary.id}>
                <details className="fold">
                  <summary>
                    <span className="res-resumen-week">
                      <span className="res-muted">{summary.label}</span>
                      <span>{summary.analysis.titular}</span>
                    </span>
                    {badge ? <Badge tone={badge.tone}>{badge.label}</Badge> : null}
                    <IconChevronDown size={20} />
                  </summary>
                  <div className="fold-body">
                    <SummaryBody summary={summary} />
                    {summary.analysis.orientacion_propuesta ? (
                      <p className="res-muted">Orientación propuesta: «{summary.analysis.orientacion_propuesta}»</p>
                    ) : null}
                    <p className="res-muted">{footer(summary)}</p>
                  </div>
                </details>
              </li>
            );
          })}
        </ul>
      </div>
    </details>
  );
}

/** Top of /resultados (anchor #resumen, the link of the weekly_summary notification). */
export function ResumenSemanal() {
  const query = useResumenSemanal();
  const decide = useResumenDecision();
  const seen = useResumenDecision();
  const toast = useToast();
  const location = useLocation();
  const data = query.data;
  const latest = data?.latest ?? null;
  const markedSeen = useRef<string | null>(null);
  const scrolled = useRef(false);

  // nuevo → visto once the summary is on screen.
  const latestId = latest?.id;
  const latestState = latest?.state;
  const markSeen = seen.mutate;
  useEffect(() => {
    if (!latestId || latestState !== 'nuevo' || markedSeen.current === latestId) return;
    markedSeen.current = latestId;
    markSeen({ summaryId: latestId, decision: 'visto' });
  }, [latestId, latestState, markSeen]);

  // The notification links to /resultados#resumen: bring the block into view once it has content.
  useEffect(() => {
    if (location.hash !== '#resumen' || !data || scrolled.current) return;
    scrolled.current = true;
    document.getElementById('resumen')?.scrollIntoView?.({ block: 'start' });
  }, [location.hash, data]);

  const undo = (summary: WeeklySummary) => {
    decide
      .mutateAsync({ summaryId: summary.id, decision: 'deshacer' })
      .then(() => toast.show('Deshecho'))
      .catch((error: unknown) => toast.show(errorMessage(error), { tone: 'error' }));
  };

  const onDecide: Decide = (summary, decision) => {
    decide
      .mutateAsync({ summaryId: summary.id, decision })
      .then(() =>
        toast.show(decision === 'aplicar' ? 'Orientación actualizada. El equipo la usa desde su próxima tarea.' : 'Resumen descartado', {
          undo: () => undo(summary),
        }),
      )
      .catch(() => {
        // Shown under the buttons (decide.error).
      });
  };

  let content;
  if (!data) {
    content = query.isError ? (
      <p className="res-muted">No se pudo cargar el resumen de la semana.</p>
    ) : (
      <Skeleton variant="card" label="Cargando el resumen de la semana…" />
    );
  } else {
    const offer = data.generate;
    const missingWeek = offer.available || offer.pending ? offer : null;
    const automatic = offer.automatic && offer.automatic_at ? ` El analista lo escribe cada lunes a las ${formatTime(offer.automatic_at, OPERATOR_TZ)}.` : '';
    content = (
      <>
        {latest ? (
          <>
            {missingWeek && latest.week_start !== offer.week_start ? (
              <Note tone="info" role={null}>
                Aún no hay resumen de {weekPhrase(offer.label)}.{automatic}
              </Note>
            ) : null}
            {missingWeek ? <Generate offer={offer} /> : null}
            <SummaryCard summary={latest} onDecide={onDecide} busy={decide.isPending} error={decide.error} />
          </>
        ) : (
          <Card>
            <EmptyState title="Todavía no hay resúmenes semanales" sprite={ANALYST_SPRITE} align="start" action={missingWeek ? <Generate offer={offer} /> : undefined}>
              <p>
                Cada semana el analista resume qué funcionó, qué no y qué cambiar, con las cifras de la semana.{automatic}
              </p>
            </EmptyState>
          </Card>
        )}
        <PreviousWeeks summaries={data.previous} />
      </>
    );
  }

  return (
    <Section id="resumen" label="Resumen de la semana" className="res-section res-resumen">
      {content}
    </Section>
  );
}
