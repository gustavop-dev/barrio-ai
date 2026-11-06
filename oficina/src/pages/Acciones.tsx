import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState, type FormEvent } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { approveAction, asList, listActions, rejectAction, resolveAction } from '../api/endpoints';
import { keys } from '../api/queryClient';
import { ACTION_STATES, type Action, type Paginated } from '../api/types';
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
      void queryClient.invalidateQueries({ queryKey: keys.overview });
      void queryClient.invalidateQueries({ queryKey: keys.feed });
      onClose();
    },
  });
  const noteRequired = kind !== 'approve';
  const valid = (!noteRequired || note.trim()) && (kind !== 'resolve' || outcome);
  const title = kind === 'veto' ? 'Vetar la acción' : kind === 'approve' ? 'Aprobar esta versión' : 'Resolver la incertidumbre';
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (valid && !mutation.isPending) mutation.mutate();
  };
  return (
    <Modal title={title} onClose={onClose}>
      <form onSubmit={submit}>
        {kind === 'veto' ? <p>La acción no se ejecutará. Queda registrada con tu nota.</p> : null}
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

      {post ? (
        <div className="origin">
          <p className="sectionlabel">POST DE ORIGEN · {post.author_name || 'Autor desconocido'}</p>
          <blockquote className="posttext">{post.text}</blockquote>
          <p className="small">
            {post.posted_at ? <span className="muted">{formatDateTime(post.posted_at)} · </span> : null}
            <ExternalLink href={post.share_url}>Ver el post en LinkedIn</ExternalLink>
          </p>
        </div>
      ) : null}

      <p className="sectionlabel">{action.payload.reaction ? 'REACCIÓN PROPUESTA' : 'TEXTO PROPUESTO'}</p>
      {action.payload.text ? <p className="proposed">{action.payload.text}</p> : null}
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
          <ExternalLink href={execution.external_url}>Ver en LinkedIn</ExternalLink>
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
  const page = Math.max(1, Number(params.get('page') ?? '1') || 1);
  const query = useQuery({
    queryKey: keys.actions(state, page),
    queryFn: () => listActions(state, page),
    placeholderData: keepPreviousData,
    refetchInterval: 30_000,
  });
  const paginated = query.data && !Array.isArray(query.data) ? (query.data as Paginated<Action>) : null;
  const actions = asList(query.data);

  const update = (nextState: string, nextPage = 1) => {
    const next = new URLSearchParams();
    if (nextState) next.set('state', nextState);
    if (nextPage > 1) next.set('page', String(nextPage));
    setParams(next, { replace: true });
  };

  return (
    <div className="stack">
      <PageHeader eyebrow="LO QUE HACE LA MÁQUINA" title="Acciones">
        Propuestas, aprobaciones y ejecuciones en LinkedIn. Puedes vetar lo pendiente y resolver lo incierto.
      </PageHeader>
      <div className="filters">
        <label htmlFor="state-filter">Estado</label>
        <select id="state-filter" value={state} onChange={(event) => update(event.target.value)}>
          <option value="">Todas</option>
          {ACTION_STATES.map((s) => (
            <option key={s} value={s}>
              {actionStateLabel(s)}
            </option>
          ))}
        </select>
        {paginated ? <span className="muted small">{paginated.count} en total</span> : null}
      </div>
      {query.isPending ? <Loading label="Cargando acciones…" /> : null}
      {query.isError ? <ErrorNote error={query.error} onRetry={() => void query.refetch()} /> : null}
      {query.isSuccess && !actions.length ? <Empty>No hay acciones {state ? `en estado «${actionStateLabel(state)}»` : 'todavía'}.</Empty> : null}
      {actions.map((action) => (
        <ActionCard key={action.id} action={action} />
      ))}
      {paginated && (paginated.next || paginated.previous) ? (
        <div className="buttonrow pager">
          <button type="button" className="secondary" disabled={!paginated.previous} onClick={() => update(state, page - 1)}>
            ← Anteriores
          </button>
          <span className="muted small">Página {page}</span>
          <button type="button" className="secondary" disabled={!paginated.next} onClick={() => update(state, page + 1)}>
            Siguientes →
          </button>
        </div>
      ) : null}
    </div>
  );
}
