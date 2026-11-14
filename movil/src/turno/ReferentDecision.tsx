import { useState } from 'react';
import { View } from 'react-native';
import { router } from 'expo-router';
import { useReferents, useTurnoAction } from '@compartido/api/hooks';
import type { TurnoCard } from '@compartido/api/types';
import { editedProposal, editFields, experimentLines, evidenceSummary, industryLines } from '@compartido/logic/referentes';
import { Button, ErrorRetry, Field, Sheet, T } from '@/components/ui';
import { Select } from '@/components/ui/Select';
import { ExternalLink } from '@/components/ui/ExternalLink';
import { space } from '@/theme/tokens';

/** What a referent decision rests on (Tu turno shows it under «Ver más»): the change, the occupancy, the evidence and
 * its limits, or the experiment's plan. */
export function ReferentDetails({ card }: { card: TurnoCard }) {
  const change = card.referent_change;
  const exp = card.referent_experiment;
  return <View style={{ gap: space[2] }}>
    {change ? <>
      <T>{card.body}</T>
      <T>{change.occupancy.main} main protegidos · {change.occupancy.variables}/10 variables · {change.occupancy.before} → {change.occupancy.after}/15 activos</T>
      {change.outgoing ? <ExternalLink href={change.outgoing.profile_url}>{`Sale: ${change.outgoing.display_name}`}</ExternalLink> : null}
      {change.proposal.incoming ? <>
        <ExternalLink href={change.proposal.incoming.profile_url}>{`Entra: ${change.proposal.incoming.display_name}`}</ExternalLink>
        {industryLines(change.proposal.incoming).map((line, i) => <T key={`industria-${i}`} testID={`industria-${i}`}>{line}</T>)}
        <T>{change.proposal.incoming.top_voice ? 'Top Voice verificado con fuente'
          : `Top Voice: no verificado · ${change.proposal.incoming.industria ? 'referente de industria' : 'voz del nicho'}`}</T>
        <T>Nicho: {change.proposal.incoming.niche}</T><T>Audiencia: {change.proposal.incoming.audience}</T>
        <T>Aporte: {change.proposal.incoming.contribution}</T><T>Hipótesis por medir; el alta no inicia un experimento.</T>
      </> : null}
      <T>{evidenceSummary(change)}</T>
      <T>Muestra y límites: evidencia observacional parcial; no identifica a todos los seguidores ni demuestra causalidad.</T>
      {change.limitations.map((line, i) => <T key={i}>{line}</T>)}
      {change.sources.map(source => <View key={source.id}><ExternalLink href={source.url}>{source.title || source.url}</ExternalLink><T variant="detalle">{source.retrieved_at}</T></View>)}
      {change.conflict ? <T accessibilityRole="alert">{change.conflict}</T> : null}
    </> : null}
    {exp ? experimentLines(exp).map((line, i) => <T key={i}>{line}</T>) : null}
  </View>;
}

/** The decision's own buttons, always visible on its card: «Gestionar protegidos» and «Editar» (with its sheet). */
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
  return <View style={{ gap: space[2] }}>
    <Button onPress={() => router.push('/personas?pestana=referentes')}>Gestionar protegidos</Button>
    {(change?.can_decide || exp?.can_decide) ? <Button onPress={() => { setFields(change ? editFields(change) : null); setPlan(exp?.plan); setStart(exp?.starts_at ?? ''); setError(null); run.reset(); setEditing(true); }} testID={`edit-${card.id}`}>Editar</Button> : null}
    {editing ? <Sheet label={change ? 'Editar propuesta de referentes' : 'Revisar experimento'} suspended={run.isPending} onClose={() => setEditing(false)} testID="referent-edit">
      <T>Guardar bloquea la aplicación por silencio. Un experimento revisado necesita otra aprobación.</T>
      {change && fields ? <>
        {change.proposal.outgoing ? <Select label="Sale" value={fields.outgoing} onChange={outgoing => setFields({ ...fields, outgoing })}
          options={(refs.data ?? []).filter(r => !r.protected && r.active !== false).map(r => ({ value: r.id, label: r.display_name ?? r.id }))} /> : null}
        {(Object.keys(fields) as (keyof typeof fields)[]).filter(k => k !== 'outgoing' && (change.proposal.incoming || k === 'reason')).map(k =>
          <Field key={k} label={FIELD_LABELS[k]} value={fields[k]} onChangeText={value => setFields({ ...fields, [k]: value })} testID={`referent-edit-${k}`} />)}
      </> : null}
      {exp && plan ? <>
        {(['hypothesis', 'audience', 'comparison'] as const).map(k => <Field key={k} label={PLAN_LABELS[k]} value={plan[k]} onChangeText={value => setPlan({ ...plan, [k]: value })} />)}
        <Field label="Inicio de base (ISO con zona)" value={start} onChangeText={setStart} />
        {(['min_classified', 'min_coverage', 'min_fit_week', 'min_exposure'] as const).map(k => <Field key={k} label={PLAN_LABELS[k]} value={String(plan[k])} keyboardType="decimal-pad" onChangeText={value => setPlan({ ...plan, [k]: Number(value) })} />)}
      </> : null}
      <ErrorRetry error={error ?? run.error} />
      <Button loading={run.isPending} onPress={() => void save(false)}>Guardar cambios</Button>
      {change ? <Button variant="primary" loading={run.isPending} onPress={() => void save(true)}>Guardar y aplicar cambios</Button> : null}
    </Sheet> : null}
  </View>;
}
const FIELD_LABELS = { reason: 'Motivo', outgoing: 'Sale', name: 'Nombre del candidato', url: 'Perfil de LinkedIn', niche: 'Nicho', audience: 'Audiencia observada', contribution: 'Aporte de Gustavo', source: 'Fuente pública del cambio' };
const PLAN_LABELS = { hypothesis: 'Hipótesis', audience: 'Público', comparison: 'Comparación', min_classified: 'Muestra mínima clasificada', min_coverage: 'Cobertura mínima (0 a 1)', min_fit_week: 'Personas con encaje por semana', min_exposure: 'Comentarios publicados mínimos' };
