import { useState } from 'react';
import { communityCopy as copy, findingBasis, useCommunity, useRefreshCommunity, useWithdrawCommunity } from '../../../../compartido/src/api/comunidad';
import { useAccounts } from '../../api/hooks';
import { Button, Card, ErrorRetry, Skeleton } from '../../components/ui';

export function Comunidad() {
  const accounts = useAccounts();
  const [chosen, setChosen] = useState('');
  const account = chosen || accounts.data?.[0]?.id || '';
  const report = useCommunity(account);
  const refresh = useRefreshCommunity();
  const withdraw = useWithdrawCommunity();
  const [sources, setSources] = useState(false);
  const data = report.data;
  const study = data?.study;
  if (accounts.isPending || (account && report.isPending)) return <Skeleton variant="card" count={2} />;
  return (
    <section aria-label={copy.title} data-testid="community-study">
      <h2>{copy.title}</h2>
      <ErrorRetry error={accounts.error || report.error} onRetry={() => { void accounts.refetch(); void report.refetch(); }} />
      {accounts.data?.length ? <>
        {accounts.data.length > 1 ? <label>Cuenta <select value={account} onChange={(e) => { setChosen(e.target.value); setSources(false); }}>
          {accounts.data.map((a) => <option key={a.id} value={a.id}>{a.label}</option>)}
        </select></label> : null}
        <p>{copy.privacy}</p>
        <p>{data?.status}</p>
        {data?.pending ? <p role="status">{copy.pending}</p> : null}
        {study ? <>
          <p>Periodo {study.period} · Versión {study.version} · {study.coverage.sample_size ?? 0} personas</p>
          <p>Ventana: {study.window_start.slice(0, 10)} — {study.window_end.slice(0, 10)}. Cobertura desde {study.coverage.since?.slice(0, 10) ?? 'sin dato'}.</p>
          <p>Público potencial separado: {study.coverage.potential ?? 0} personas.</p>
          {study.summary.unknown_follow_reason !== undefined ? <p>Motivo de seguimiento desconocido: {study.summary.unknown_follow_reason} personas.</p> : null}
          {study.state === 'insufficient' ? <p>{copy.insufficient}</p> : null}
          {study.state === 'partial_error' ? <p>Estudio parcial: el análisis no pudo completarse.</p> : null}
          {study.summary.findings?.map((f) => <Card key={f.id}>
            <h3>{f.pattern}</h3><p>{findingBasis(f.basis)} · {f.people} personas · {f.id}</p>
            <p>{f.interpretation}</p><p>{f.uncertainty}</p>
            {f.examples?.map((example) => <p key={example.id}>{example.paraphrase} · {example.id}</p>)}
            <p>Contraejemplos: {f.counterexamples ?? 'Evidencia insuficiente'}</p>
            {f.counterexample_note ? <p>{f.counterexample_note}</p> : null}
          </Card>)}
          {study.coverage.limitations?.map((text) => <p key={text}>{text}</p>)}
          <p>Unidades: {study.summary.units?.join(', ') || 'Sin unidades aplicadas'}</p>
        </> : null}
        <p>{copy.retention}</p>
        <Button onClick={() => refresh.mutate(account)} disabled={data?.pending} loading={refresh.isPending}>Actualizar estudio</Button>
        <ErrorRetry error={refresh.error || withdraw.error} />
        {data?.sources.length ? <>
          <Button onClick={() => setSources(!sources)} aria-expanded={sources}>Fuentes públicas</Button>
          {sources ? <div><p>{copy.withdrawal}</p>{data.sources.map((s, i) => <Card key={s.id}>
            <h3>Fuente {i + 1} · {s.kind === 'public_comment' ? 'Comentario' : 'Perfil'}</h3>
            <p>{s.text}</p><p>{s.event_at?.slice(0, 10) ?? 'Fecha de publicación desconocida'} · Leído {s.observed_at.slice(0, 10)}</p>
            {s.url ? <a href={s.url} target="_blank" rel="noreferrer">Abrir fuente pública</a> : null}
            {s.analysis.follow_quote ? <p>Motivo declarado: {s.analysis.follow_quote}</p> : null}
            <Button disabled={withdraw.isPending} onClick={() => withdraw.mutate({ source: s.id })}>Retirar fuente {i + 1}</Button>
            <Button disabled={withdraw.isPending} onClick={() => withdraw.mutate({ source: s.id, wholePerson: true })}>Excluir persona de fuente {i + 1}</Button>
            <Button disabled={withdraw.isPending} onClick={() => withdraw.mutate({ source: s.id, reason: 'incorrect' })}>Marcar fuente {i + 1} incorrecta</Button>
          </Card>)}</div> : null}
        </> : null}
      </> : !accounts.isError ? <p>No hay ninguna cuenta de LinkedIn.</p> : null}
    </section>
  );
}
