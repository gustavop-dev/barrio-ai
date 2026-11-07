import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState, type FormEvent } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { approveAction, asList, listActions, rejectAction, resolveAction } from '../api/endpoints';
import { keys } from '../api/queryClient';
import { ACTION_STATES, type Action, type Capability, type Paginated } from '../api/types';
import { Badge, Empty, ErrorNote, ExternalLink, Loading, Modal, PageHeader, type Tone } from '../components/ui';
import { actionStateLabel, capabilityLabel, formatDateTime, timeAgo } from '../lib/format';

const STATE_TONE: Record<string, Tone> = {
  proposed: 'info',
  approved: 'info',
  executing: 'warn',
  sent: 'warn',
  confirmed: 'ok',
  uncertain: 'bad',
  failed: 'bad',
  rejected: 'muted',
  superseded: 'muted',
  discarded: 'muted',
  expired: 'muted',
};

/** Filter by capability, with readable values in the URL (`?capacidad=publicaciones`). */
export const CAPABILITY_FILTERS: readonly { value: string; code: Capability; label: string }[] = [
  { value: 'comentarios', code: 'INT-03', label: 'Comentarios' },
  { value: 'reacciones', code: 'INT-02', label: 'Reacciones' },
  { value: 'publicaciones', code: 'CONT-09', label: 'Publicaciones propias' },
];

export const isOwnPublication = (action: Action) => action.capability === 'CONT-09';

export const canVeto = (action: Action) => action.state === 'proposed' || action.state === 'approved';
export const canApprove = (action: Action) => action.state === 'proposed';
export const canResolve = (action: Action) => action.state === 'uncertain';

type Decision = 'veto' | 'approve' | 'resolve';

function DecisionModal({ action, kind, onClose }: { action: Action; kind: Decision; onClose: () => void }) {
  const queryClient = useQueryClient();
  const [note, setNote] = useState('');
  const [outcome, setOutcome] = useState<'confirmed' | 'failed' | ''>('');
  const mutation = useMutation({
    mutationFn: async () => {
      if (kind === 'veto') return rejectAction(action.id, note.trim());
      if (kind === 'approve') return approveAction(action.id, action.payload_hash, note.trim());
      if (!outcome) throw new Error('Elige el resultado');
      return resolveAction(action.id, outcome, note.trim());
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: keys.actionsAll });
      void queryClient.invalidateQueries({ queryKey: keys.editorialAll });
      void queryClient.invalidateQueries({ queryKey: keys.overview });
      void queryClient.invalidateQueries({ queryKey: keys.feed });
      onClose();
    },
  });
  const noteRequired = kind !== 'approve';
  const valid = (!noteRequired || note.trim()) && (kind !== 'resolve' || outcome);
  const own = isOwnPublication(action);
  const title =
    kind === 'veto' ? (own ? 'Vetar la publicación' : 'Vetar la acción') : kind === 'approve' ? 'Aprobar esta versión' : 'Resolver la incertidumbre';
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (valid && !mutation.isPending) mutation.mutate();
  };
  return (
    <Modal title={title} onClose={onClose}>
      <form onSubmit={submit}>
        {kind === 'veto' ? (
          <p>
            {own ? 'La pieza no se publicará y ese día quedará sin publicación.' : 'La acción no se ejecutará.'} Queda registrada con tu
            nota.
          </p>
        ) : null}
        {kind === 'approve' ? <p>Apruebas exactamente esta versión del texto (hash {action.payload_hash.slice(0, 10)}…). Si cambia, habrá que volver a aprobar.</p> : null}
        {kind === 'resolve' ? (
          <fieldset className="radios">
            <legend>¿Qué pasó en LinkedIn?</legend>
            <label className="radio">
              <input type="radio" name="outcome" value="confirmed" checked={outcome === 'confirmed'} onChange={() => setOutcome('confirmed')} />
              Se publicó: confirmar
            </label>
            <label className="radio">
              <input type="radio" name="outcome" value="failed" checked={outcome === 'failed'} onChange={() => setOutcome('failed')} />
              No se aplicó: marcar como fallida
            </label>
          </fieldset>
        ) : null}
        <label htmlFor="decision-note">{noteRequired ? 'Nota' : 'Nota (opcional)'}</label>
        <textarea
          id="decision-note"
          value={note}
          maxLength={2000}
          required={noteRequired}
          onChange={(event) => setNote(event.target.value)}
          placeholder={kind === 'veto' ? 'Por qué no debe publicarse' : kind === 'resolve' ? 'Qué comprobaste' : ''}
        />
        <ErrorNote error={mutation.error} />
        <div className="buttonrow">
          <button type="button" className="secondary" onClick={onClose}>
            Cancelar
          </button>
          <button type="submit" className={kind === 'veto' ? 'danger' : 'primary'} disabled={!valid || mutation.isPending}>
            {mutation.isPending ? 'Enviando…' : kind === 'veto' ? 'Vetar' : kind === 'approve' ? 'Aprobar' : 'Resolver'}
          </button>
        </div>
      </form>
    </Modal>
  );
}

export function ActionCard({ action }: { action: Action }) {
  const [decision, setDecision] = useState<Decision | null>(null);
  const post = action.post;
  const own = isOwnPublication(action);
  const execution = action.execution;
  return (
    <article className="card action" aria-labelledby={`action-${action.id}`}>
      <div className="cardhead">
        <h3 id={`action-${action.id}`}>
          {capabilityLabel(action.capability)} <span className="muted small">v{action.version}</span>
        </h3>
        <span className="badges">
          <Badge tone={STATE_TONE[action.state] ?? 'muted'}>{actionStateLabel(action.state)}</Badge>
          <Badge tone="muted">{action.source === 'human' ? 'Tuya' : 'Agente'}</Badge>
        </span>
      </div>
      <p className="muted small">Creada {timeAgo(action.created_at)}</p>

      {own ? (
        <div className="origin">
          <p className="small">
            <span className="muted">Día programado: </span>
            <strong>{action.scheduled_for ? formatDateTime(action.scheduled_for) : 'sin fecha'}</strong>
          </p>
          {action.state === 'approved' ? (
            <p className="note info">Sale sola a esa hora por la política autónoma, salvo que la vetes antes.</p>
          ) : action.state === 'proposed' ? (
            <p className="note info">Pendiente de la política autónoma (o de tu aprobación en modo «approval»). Aprobada, saldrá sola a esa hora salvo veto.</p>
          ) : null}
          {action.piece_id ? (
            <p className="small">
              <Link to={`/contenido/${encodeURIComponent(action.piece_id)}`}>Ver la pieza: brief, variantes y verificación</Link>
            </p>
          ) : null}
        </div>
      ) : post ? (
        <div className="origin">
          <p className="sectionlabel">POST DE ORIGEN · {post.author_name || 'Autor desconocido'}</p>
          <blockquote className="posttext">{post.text}</blockquote>
          <p className="small">
            {post.posted_at ? <span className="muted">{formatDateTime(post.posted_at)} · </span> : null}
            <ExternalLink href={post.share_url}>Ver el post en LinkedIn</ExternalLink>
          </p>
        </div>
      ) : null}

      <p className="sectionlabel">{own ? 'TEXTO FINAL' : action.payload.reaction ? 'REACCIÓN PROPUESTA' : 'TEXTO PROPUESTO'}</p>
      {action.payload.text ? (
        <p className="proposed" lang={own ? 'en' : undefined}>
          {action.payload.text}
        </p>
      ) : null}
      {action.payload.reaction ? <p className="proposed">{action.payload.reaction}</p> : null}

      {action.rationale ? (
        <>
          <p className="sectionlabel">JUSTIFICACIÓN</p>
          <p>{action.rationale}</p>
        </>
      ) : null}
      {action.citations?.length ? (
        <>
          <p className="sectionlabel">CITAS DEL CURSO</p>
          <ul className="chips">
            {action.citations.map((unit) => (
              <li key={unit}>
                <Link className="chip" to={`/conocimiento?unidad=${encodeURIComponent(unit)}`}>
                  {unit}
                </Link>
              </li>
            ))}
          </ul>
        </>
      ) : null}
      {action.risks?.length ? (
        <>
          <p className="sectionlabel">RIESGOS</p>
          <ul className="risks">
            {action.risks.map((risk, index) => (
              <li key={index}>{risk}</li>
            ))}
          </ul>
        </>
      ) : null}
      {action.decision_note ? (
        <p className="small">
          <span className="muted">Decisión{action.decided_at ? ` (${formatDateTime(action.decided_at)})` : ''}: </span>
          {action.decision_note}
        </p>
      ) : null}

      {execution ? (
        <div className="execution">
          <p className="sectionlabel">EJECUCIÓN</p>
          <p className="small">
            <Badge tone={STATE_TONE[execution.state] ?? 'muted'}>{actionStateLabel(execution.state)}</Badge>{' '}
            {execution.http_status ? <span className="muted">HTTP {execution.http_status} · </span> : null}
            {execution.finished_at ? <span className="muted">{formatDateTime(execution.finished_at)}</span> : execution.started_at ? <span className="muted">desde {formatDateTime(execution.started_at)}</span> : null}
          </p>
          {execution.note ? <p className="small">{execution.note}</p> : null}
          <ExternalLink href={execution.external_url}>{own ? 'Ver el post publicado en LinkedIn' : 'Ver en LinkedIn'}</ExternalLink>
        </div>
      ) : null}

      {canVeto(action) || canResolve(action) ? (
        <div className="buttonrow">
          {canApprove(action) ? (
            <button type="button" className="primary" onClick={() => setDecision('approve')}>
              Aprobar
            </button>
          ) : null}
          {canVeto(action) ? (
            <button type="button" className="danger" onClick={() => setDecision('veto')}>
              Vetar
            </button>
          ) : null}
          {canResolve(action) ? (
            <button type="button" className="primary" onClick={() => setDecision('resolve')}>
              Resolver
            </button>
          ) : null}
        </div>
      ) : null}
      {decision ? <DecisionModal action={action} kind={decision} onClose={() => setDecision(null)} /> : null}
    </article>
  );
}

export function Acciones() {
  const [params, setParams] = useSearchParams();
  const state = params.get('state') ?? '';
  const filter = CAPABILITY_FILTERS.find((f) => f.value === params.get('capacidad')) ?? null;
  const capability = filter?.code ?? '';
  const page = Math.max(1, Number(params.get('page') ?? '1') || 1);
  const query = useQuery({
    queryKey: keys.actions(state, page, capability),
    queryFn: () => listActions(state, page, capability),
    placeholderData: keepPreviousData,
    refetchInterval: 30_000,
  });
  const paginated = query.data && !Array.isArray(query.data) ? (query.data as Paginated<Action>) : null;
  // The backend may ignore `capability`: filter what arrives as well.
  const actions = asList(query.data).filter((action) => !capability || action.capability === capability);

  const update = (next: { state?: string; capacidad?: string; page?: number }) => {
    const nextState = next.state ?? state;
    const nextCapacity = next.capacidad ?? filter?.value ?? '';
    const nextPage = next.page ?? 1;
    const search = new URLSearchParams();
    if (nextState) search.set('state', nextState);
    if (nextCapacity) search.set('capacidad', nextCapacity);
    if (nextPage > 1) search.set('page', String(nextPage));
    setParams(search, { replace: true });
  };
  const emptyText = [
    filter ? filter.label.toLowerCase() : 'acciones',
    state ? `en estado «${actionStateLabel(state)}»` : 'todavía',
  ].join(' ');

  return (
    <div className="stack">
      <PageHeader eyebrow="LO QUE HACE LA MÁQUINA" title="Acciones">
        Comentarios, reacciones y publicaciones propias: propuestas, aprobaciones y ejecuciones en LinkedIn. Puedes vetar lo pendiente y
        resolver lo incierto.
      </PageHeader>
      <div className="filters">
        <div className="filter">
          <label htmlFor="capability-filter">Capacidad</label>
          <select id="capability-filter" value={filter?.value ?? ''} onChange={(event) => update({ capacidad: event.target.value })}>
            <option value="">Todas</option>
            {CAPABILITY_FILTERS.map((f) => (
              <option key={f.value} value={f.value}>
                {f.label}
              </option>
            ))}
          </select>
        </div>
        <div className="filter">
          <label htmlFor="state-filter">Estado</label>
          <select id="state-filter" value={state} onChange={(event) => update({ state: event.target.value })}>
            <option value="">Todas</option>
            {ACTION_STATES.map((s) => (
              <option key={s} value={s}>
                {actionStateLabel(s)}
              </option>
            ))}
          </select>
        </div>
        {paginated && !capability ? <span className="muted small">{paginated.count} en total</span> : null}
      </div>
      {query.isPending ? <Loading label="Cargando acciones…" /> : null}
      {query.isError ? <ErrorNote error={query.error} onRetry={() => void query.refetch()} /> : null}
      {query.isSuccess && !actions.length ? <Empty>No hay {emptyText}.</Empty> : null}
      {actions.map((action) => (
        <ActionCard key={action.id} action={action} />
      ))}
      {paginated && (paginated.next || paginated.previous) ? (
        <div className="buttonrow pager">
          <button type="button" className="secondary" disabled={!paginated.previous} onClick={() => update({ page: page - 1 })}>
            ← Anteriores
          </button>
          <span className="muted small">Página {page}</span>
          <button type="button" className="secondary" disabled={!paginated.next} onClick={() => update({ page: page + 1 })}>
            Siguientes →
          </button>
        </div>
      ) : null}
    </div>
  );
}
