import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useReferents, useTurnoAction } from '../../api/hooks';
import type { TurnoCard } from '../../api/types';
import { editedProposal, editFields, experimentLines, evidenceSummary } from '../../../../compartido/src/logic/referentes';
import { Button, ErrorRetry, ExternalLink, Modal } from '../../components/ui';

export function ReferentDecision({ card }: { card: TurnoCard }) {
  const change = card.referent_change;
  const exp = card.referent_experiment;
  const [editing, setEditing] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const [fields, setFields] = useState(change ? editFields(change) : null);
  const [plan, setPlan] = useState(exp?.plan);
  const [start, setStart] = useState(exp?.starts_at ?? '');
  const refs = useReferents(change?.account ?? '');
  const run = useTurnoAction();
  const save = async (apply: boolean) => {
    setError(null);
    try {
      if (change && fields) await run.mutateAsync({ action: { label: 'Guardar', endpoint: change.endpoint,
        body: { version: change.version, decision: apply ? 'edit_apply' : 'edit', proposal: editedProposal(change, fields) } } });
      if (exp && plan) await run.mutateAsync({ action: { label: 'Guardar', endpoint: exp.endpoint,
        body: { version: exp.version, decision: 'edit', plan, starts_at: start } } });
      setEditing(false);
    } catch (e) { setError(e instanceof Error ? e : new Error('No se pudo guardar.')); }
  };
  return <div className="turno-block">
    {change ? <>
      <p>{card.body}</p>
      <p>{change.occupancy.main} main protegidos · {change.occupancy.variables}/10 variables · {change.occupancy.before} → {change.occupancy.after}/15 activos</p>
      {change.outgoing ? <ExternalLink href={change.outgoing.profile_url}>Sale: {change.outgoing.display_name}</ExternalLink> : null}
      {change.proposal.incoming ? <>
        <ExternalLink href={change.proposal.incoming.profile_url}>Entra: {change.proposal.incoming.display_name}</ExternalLink>
        <p>{change.proposal.incoming.top_voice ? 'Top Voice verificado con fuente' : 'Top Voice: no verificado · voz del nicho'}</p>
        <p>Nicho: {change.proposal.incoming.niche}</p><p>Audiencia: {change.proposal.incoming.audience}</p>
        <p>Aporte: {change.proposal.incoming.contribution}</p>
        <p>Hipótesis por medir; el alta no inicia un experimento.</p>
      </> : null}
      <p>{evidenceSummary(change)}</p>
      <p>Muestra y límites: evidencia observacional parcial; no identifica a todos los seguidores ni demuestra causalidad.</p>
      {change.limitations.map((line, i) => <p key={i}>{line}</p>)}
      {change.sources.map(source => <p key={source.id}><ExternalLink href={source.url}>{source.title || source.url}</ExternalLink> · {source.retrieved_at}</p>)}
      {change.conflict ? <p role="alert">{change.conflict}</p> : null}
    </> : null}
    {exp ? <>{experimentLines(exp).map((line, i) => <p key={i}>{line}</p>)}</> : null}
    <Link to="/personas?pestana=referentes">Gestionar protegidos</Link>
    {(change?.can_decide || exp?.can_decide) ? <Button onClick={() => { setFields(change ? editFields(change) : null); setPlan(exp?.plan); setStart(exp?.starts_at ?? ''); setError(null); run.reset(); setEditing(true); }}>Editar</Button> : null}
    {editing ? <Modal title={change ? 'Editar propuesta de referentes' : 'Revisar experimento'} busy={run.isPending} onClose={() => setEditing(false)}>
      <p>Guardar bloquea la aplicación por silencio. Un experimento revisado necesita otra aprobación.</p>
      {change && fields ? <>
        {change.proposal.outgoing ? <label className="field">Sale<select aria-label="Sale" value={fields.outgoing} onChange={e => setFields({ ...fields, outgoing: e.target.value })}>
          {refs.data?.filter(r => !r.protected && r.active !== false).map(r => <option key={r.id} value={r.id}>{r.display_name}</option>)}
        </select></label> : null}
        {(Object.keys(fields) as (keyof typeof fields)[]).filter(k => k !== 'outgoing' && (change.proposal.incoming || k === 'reason')).map(k =>
          <label className="field" key={k}>{FIELD_LABELS[k]}<input aria-label={FIELD_LABELS[k]} value={fields[k]} onChange={e => setFields({ ...fields, [k]: e.target.value })} /></label>)}
      </> : null}
      {exp && plan ? <>
        {(['hypothesis', 'audience', 'comparison'] as const).map(k => <label className="field" key={k}>{PLAN_LABELS[k]}<input aria-label={PLAN_LABELS[k]} value={plan[k]} onChange={e => setPlan({ ...plan, [k]: e.target.value })} /></label>)}
        <label className="field">Inicio de base (ISO con zona)<input aria-label="Inicio de base" value={start} onChange={e => setStart(e.target.value)} /></label>
        {(['min_classified', 'min_coverage', 'min_fit_week', 'min_exposure'] as const).map(k => <label className="field" key={k}>{PLAN_LABELS[k]}<input aria-label={PLAN_LABELS[k]} type="number" step="any" value={plan[k]} onChange={e => setPlan({ ...plan, [k]: Number(e.target.value) })} /></label>)}
      </> : null}
      <ErrorRetry error={error ?? run.error} />
      <Button loading={run.isPending} onClick={() => void save(false)}>Guardar cambios</Button>
      {change ? <Button variant="primary" loading={run.isPending} onClick={() => void save(true)}>Guardar y aplicar cambios</Button> : null}
    </Modal> : null}
  </div>;
}
const FIELD_LABELS = { reason: 'Motivo', outgoing: 'Sale', name: 'Nombre del candidato', url: 'Perfil de LinkedIn', niche: 'Nicho', audience: 'Audiencia observada', contribution: 'Aporte de Gustavo', source: 'Fuente pública del cambio' };
const PLAN_LABELS = { hypothesis: 'Hipótesis', audience: 'Público', comparison: 'Comparación', min_classified: 'Muestra mínima clasificada', min_coverage: 'Cobertura mínima (0 a 1)', min_fit_week: 'Personas con encaje por semana', min_exposure: 'Comentarios publicados mínimos' };
