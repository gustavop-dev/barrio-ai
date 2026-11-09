import { useTeamGraph, type GraphNode, type TeamGraph } from '@compartido/api/grafo';
import { graphConnections, graphGroups, graphJobLabel, graphRole } from '@compartido/logic/grafo';
import { router, useLocalSearchParams } from 'expo-router';
import { useRef } from 'react';
import { ScrollView, StyleSheet, View, type ScrollViewInstance } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useContentInsets } from '@/components/shell/useContentInsets';
import { Button, ErrorRetry, Fold, PageHeader, Select, T, pageContent } from '@/components/ui';
import { colors, space } from '@/theme/tokens';

export function MapaEquipoScreen() {
  const query = useTeamGraph();
  const { agente, ciclo = '' } = useLocalSearchParams<{ agente?: string; ciclo?: string }>();
  const insets = useContentInsets();
  const safe = useSafeAreaInsets();
  const scroll = useRef<ScrollViewInstance>(null);
  const graph = query.data;
  const selected = graph?.nodes.find((node) => node.id === agente);
  const select = (id?: string) => {
    router.setParams({ agente: id ?? '' });
    scroll.current?.scrollTo({ y: 0, animated: false });
  };
  return <ScrollView ref={scroll} testID="screen-mapa-equipo" style={styles.screen}
    contentContainerStyle={[pageContent, { paddingTop: safe.top + pageContent.paddingTop, paddingBottom: insets.bottom }]}>
    <Button variant="ghost" onPress={() => router.back()}>Volver</Button>
    <PageHeader title="Mapa del equipo" subtitle="Qué hace cada agente y cómo se conecta con el equipo." />
    {query.isPending ? <T accessibilityRole="text">Cargando el mapa…</T> : null}
    <ErrorRetry error={query.error} title="No se pudo cargar el mapa" onRetry={() => void query.refetch()} />
    {graph && !query.isError ? <>
      <Select label="Ver ciclo" value={ciclo} options={[{ value: '', label: 'Todo el equipo' }, ...graph.cycles.map((cycle) => ({ value: cycle.id, label: cycle.label + (cycle.status === 'planned' ? ' · En diseño' : '') }))]}
        onChange={(id) => { router.setParams({ ciclo: id, agente: '' }); scroll.current?.scrollTo({ y: 0, animated: false }); }} />
      {!graph.nodes.length ? <T>El mapa todavía no tiene agentes.</T> : selected ? <>
        <Button variant="ghost" onPress={() => select()}>Ver todos los agentes</Button>
        <AgentDetail node={selected} graph={graph} select={select} cycleId={ciclo} />
      </> : <>
        {agente ? <T>Este agente ya no está en el mapa.</T> : null}
        {graphGroups(graph, ciclo).map((group) => <Fold key={group.id} summary={`${group.label} · ${group.nodes.length}`}>
          {group.nodes.map((node) => <Button key={node.id} testID={`mapa-agente-${node.id}`} variant="ghost" onPress={() => select(node.id)} accessibilityLabel={node.label}>
            <View style={styles.row}><T>{node.label}</T><T variant="detalle" soft>{node.status === 'planned' ? 'En diseño' : graphRole[node.role]}</T></View>
          </Button>)}
        </Fold>)}
      </>}
    </> : null}
  </ScrollView>;
}

function AgentDetail({ node, graph, select, cycleId }: { node: GraphNode; graph: TeamGraph; select: (id: string) => void; cycleId: string }) {
  const connections = graphConnections(graph, node.id, cycleId);
  const { jobs, handoffs, records = [] } = node.recent_activity;
  return <View style={styles.detail} testID="mapa-ficha">
    <T variant="titulo" accessibilityRole="header">{node.label}</T>
    <T soft>{graph.groups[node.group]} · {node.status === 'planned' ? 'En diseño' : graphRole[node.role]}</T>
    <T>{node.description}</T>
    {node.status === 'planned' ? <T>Este agente aún no ejecuta trabajo.</T> : null}
    <Fold key={node.id} summary={`Curso · ${node.course_units.length} unidades`}>
      <T>{node.course_note}</T>
      {node.course_units.map((id) => <T key={id}>{id}</T>)}
    </Fold>
    <T accessibilityRole="header">Actividad reciente</T>
    {!jobs.length && !handoffs.length && !records.length ? <T>Sin actividad registrada para este agente.</T> : null}
    {jobs.map((job) => <T key={job.id}>{graphJobLabel(job.state)} · {new Date(job.at).toLocaleString('es-CO')}</T>)}
    {handoffs.map((event) => <T key={event.id}>{event.detail} · {new Date(event.at).toLocaleString('es-CO')}</T>)}
    {records.map((record) => <T key={record.id}>{record.label} · {new Date(record.at).toLocaleString('es-CO')}</T>)}
    <T accessibilityRole="header">Conexiones</T>
    <T>Los pasos y entregas los coordina el ciclo. Los especialistas devuelven sus resultados.</T>
    {!connections.length ? <T>Sin conexiones declaradas.</T> : connections.map(({ edge, peer, direction, cycles }) => <View key={edge.id} style={styles.row}>
      <Button variant="ghost" onPress={() => select(peer.id)}>{`${direction}: ${peer.label}`}</Button>
      <T variant="detalle" soft>{cycles}{edge.status === 'planned' ? ' · En diseño' : ''}</T>
      {edge.call_group ? <T variant="detalle">Comparte una llamada con los demás participantes de esta etapa.</T> : null}
    </View>)}
  </View>;
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.paper },
  detail: { gap: space[4] },
  row: { gap: space[1], flexShrink: 1 },
});
