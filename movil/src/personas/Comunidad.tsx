import { useState, type ReactNode } from 'react';
import { ScrollView, StyleSheet, View } from 'react-native';
import { useAccounts } from '@compartido/api/hooks';
import { communityCopy as copy, findingBasis, useCommunity, useRefreshCommunity, useWithdrawCommunity } from '@compartido/api/comunidad';
import { useContentInsets } from '@/components/shell/useContentInsets';
import { Button, ErrorRetry, Skeleton, T, pageContent } from '@/components/ui';
import { ExternalLink } from '@/components/ui/ExternalLink';
import { Select } from '@/components/ui/Select';
import { space } from '@/theme/tokens';

export function Comunidad({ header }: { header: ReactNode }) {
  const accounts = useAccounts();
  const [chosen, setChosen] = useState('');
  const account = chosen || accounts.data?.[0]?.id || '';
  const report = useCommunity(account);
  const refresh = useRefreshCommunity();
  const withdraw = useWithdrawCommunity();
  const [sources, setSources] = useState(false);
  const { bottom } = useContentInsets();
  const data = report.data;
  const study = data?.study;
  return <ScrollView testID="community-study" contentContainerStyle={[pageContent, { paddingBottom: bottom }, styles.content]}>
    {header}<T variant="subtitulo" accessibilityRole="header">{copy.title}</T>
    <ErrorRetry error={accounts.error || report.error} onRetry={() => { void accounts.refetch(); void report.refetch(); }} />
    {accounts.isPending || (account && report.isPending) ? <Skeleton variant="card" count={2} /> : null}
    {!accounts.isPending && !accounts.isError && !accounts.data?.length ? <T>No hay ninguna cuenta de LinkedIn.</T> : null}
    {(accounts.data?.length ?? 0) > 1 ? <Select label="Cuenta" value={account} options={accounts.data!.map((a) => ({ value: a.id, label: a.label }))}
      onChange={(value) => { setChosen(value); setSources(false); }} testID="community-account" /> : null}
    <T>{copy.privacy}</T><T testID="community-status">{data?.status}</T>
    {data?.pending ? <T>{copy.pending}</T> : null}
    {study ? <View style={styles.content}>
      <T>Periodo {study.period} · Versión {study.version} · {study.coverage.sample_size ?? 0} personas</T>
      <T>Ventana: {study.window_start.slice(0, 10)} — {study.window_end.slice(0, 10)}. Cobertura desde {study.coverage.since?.slice(0, 10) ?? 'sin dato'}.</T>
      <T>Público potencial separado: {study.coverage.potential ?? 0} personas.</T>
      {study.summary.unknown_follow_reason !== undefined ? <T>Motivo de seguimiento desconocido: {study.summary.unknown_follow_reason} personas.</T> : null}
      {study.state === 'insufficient' ? <T>{copy.insufficient}</T> : null}
      {study.state === 'partial_error' ? <T>Estudio parcial: el análisis no pudo completarse.</T> : null}
      {study.summary.findings?.map((f) => <View key={f.id} style={styles.content}>
        <T variant="subtitulo">{f.pattern}</T><T>{findingBasis(f.basis)} · {f.people} personas · {f.id}</T>
        <T>{f.interpretation}</T><T>{f.uncertainty}</T><T>Contraejemplos: {f.counterexamples ?? 'Evidencia insuficiente'}</T>
        {f.examples?.map((example) => <T key={example.id}>{example.paraphrase} · {example.id}</T>)}
        {f.counterexample_note ? <T>{f.counterexample_note}</T> : null}
      </View>)}
      {study.coverage.limitations?.map((text) => <T key={text}>{text}</T>)}
      <T>Unidades: {study.summary.units?.join(', ') || 'Sin unidades aplicadas'}</T>
    </View> : null}
    <T>{copy.retention}</T>
    {account ? <Button onPress={() => refresh.mutate(account)} disabled={data?.pending} loading={refresh.isPending} testID="community-refresh">Actualizar estudio</Button> : null}
    <ErrorRetry error={refresh.error || withdraw.error} />
    {data?.sources.length ? <Button onPress={() => setSources(!sources)} testID="community-sources">Fuentes públicas</Button> : null}
    {sources && data ? <View style={styles.content}>
      <T>{copy.withdrawal}</T>
      {data.sources.map((s, i) => <View key={s.id} style={styles.content}>
        <T variant="subtitulo">Fuente {i + 1} · {s.kind === 'public_comment' ? 'Comentario' : 'Perfil'}</T>
        <T>{s.text}</T><T>{s.event_at?.slice(0, 10) ?? 'Fecha de publicación desconocida'} · Leído {s.observed_at.slice(0, 10)}</T>
        {s.url ? <ExternalLink href={s.url}>Abrir fuente pública</ExternalLink> : null}
        {s.analysis.follow_quote ? <T>Motivo declarado: {s.analysis.follow_quote}</T> : null}
        <Button disabled={withdraw.isPending} onPress={() => withdraw.mutate({ source: s.id })} testID={`community-withdraw-${i}`}>{`Retirar fuente ${i + 1}`}</Button>
        <Button disabled={withdraw.isPending} onPress={() => withdraw.mutate({ source: s.id, wholePerson: true })}>{`Excluir persona de fuente ${i + 1}`}</Button>
        <Button disabled={withdraw.isPending} onPress={() => withdraw.mutate({ source: s.id, reason: 'incorrect' })}>{`Marcar fuente ${i + 1} incorrecta`}</Button>
      </View>)}
    </View> : null}
  </ScrollView>;
}

const styles = StyleSheet.create({ content: { gap: space[4] } });
