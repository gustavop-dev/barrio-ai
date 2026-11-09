import { useSearchParams } from 'react-router-dom';
import { useTeamGraph, type GraphNode, type TeamGraph } from '../../../compartido/src/api/grafo';
import { graphConnections, graphGroups, graphJobLabel, graphRole } from '../../../compartido/src/logic/grafo';
import { Button, ErrorRetry, Page } from '../components/ui';
import './mapa-equipo.css';

export function MapaEquipo() {
  const query = useTeamGraph();
  const [params, setParams] = useSearchParams();
  const graph = query.data;
  const cycleId = params.get('ciclo') || '';
  const selected = graph?.nodes.find((node) => node.id === params.get('agente'));
  const select = (id?: string) => {
    setParams({ ...(cycleId ? { ciclo: cycleId } : {}), ...(id ? { agente: id } : {}) });
    window.scrollTo?.({ top: 0 });
  };
  return <Page title="Mapa del equipo" width="narrow" subtitle="Qué hace cada agente y cómo se conecta con el equipo.">
    <div className="team-map">
      {query.isPending ? <p role="status">Cargando el mapa…</p> : null}
      <ErrorRetry error={query.error} title="No se pudo cargar el mapa" onRetry={() => void query.refetch()} />
      {graph && !query.isError ? <>
        <label className="team-map-filter">Ver ciclo
          <select value={cycleId} onChange={(event) => setParams(event.target.value ? { ciclo: event.target.value } : {})}>
            <option value="">Todo el equipo</option>
            {graph.cycles.map((cycle) => <option key={cycle.id} value={cycle.id}>{cycle.label}{cycle.status === 'planned' ? ' · En diseño' : ''}</option>)}
          </select>
        </label>
        {!graph.nodes.length ? <p>El mapa todavía no tiene agentes.</p> : selected ? <>
          <Button variant="ghost" onClick={() => select()}>Ver todos los agentes</Button>
          <AgentDetail node={selected} graph={graph} select={select} cycleId={cycleId} />
        </> : <>
          {params.has('agente') ? <p>Este agente ya no está en el mapa.</p> : null}
          {graphGroups(graph, cycleId).map((group) => <details key={group.id} className="team-map-group">
            <summary>{group.label} · {group.nodes.length}</summary>
            <ul>{group.nodes.map((node) => <li key={node.id}>
              <button type="button" onClick={() => select(node.id)} className="team-map-agent">
                <strong>{node.label}</strong><span>{node.status === 'planned' ? 'En diseño' : graphRole[node.role]}</span>
              </button>
            </li>)}</ul>
          </details>)}
        </>}
      </> : null}
    </div>
  </Page>;
}

function AgentDetail({ node, graph, select, cycleId }: { node: GraphNode; graph: TeamGraph; select: (id: string) => void; cycleId: string }) {
  const connections = graphConnections(graph, node.id, cycleId);
  const { jobs, handoffs, records = [] } = node.recent_activity;
  return <article className="team-map-detail" aria-label={node.label}>
    <h2>{node.label}</h2>
    <p>{graph.groups[node.group]} · {node.status === 'planned' ? 'En diseño' : graphRole[node.role]}</p>
    <p>{node.description}</p>
    {node.status === 'planned' ? <p>Este agente aún no ejecuta trabajo.</p> : null}
    <details className="team-map-group">
      <summary>Curso · {node.course_units.length} unidades</summary>
      <p>{node.course_note}</p>
      <ul>{node.course_units.map((id) => <li key={id}>{id}</li>)}</ul>
    </details>
    <h3>Actividad reciente</h3>
    {!jobs.length && !handoffs.length && !records.length ? <p>Sin actividad registrada para este agente.</p> : null}
    <ul>{jobs.map((job) => <li key={job.id}>{graphJobLabel(job.state)} · {new Date(job.at).toLocaleString('es-CO')}</li>)}</ul>
    <ul>{handoffs.map((event) => <li key={event.id}>{event.detail} · {new Date(event.at).toLocaleString('es-CO')}</li>)}</ul>
    <ul>{records.map((record) => <li key={record.id}>{record.label} · {new Date(record.at).toLocaleString('es-CO')}</li>)}</ul>
    <h3>Conexiones</h3>
    <p>Los pasos y entregas los coordina el ciclo. Los especialistas devuelven sus resultados.</p>
    {!connections.length ? <p>Sin conexiones declaradas.</p> : <ul className="team-map-connections">
      {connections.map(({ edge, peer, direction, cycles }) => <li key={edge.id}>
        <button type="button" className="team-map-agent" onClick={() => select(peer.id)}>
          <strong>{direction}: {peer.label}</strong><span>{cycles}{edge.status === 'planned' ? ' · En diseño' : ''}</span>
        </button>
        {edge.call_group ? <p>Comparte una llamada con los demás participantes de esta etapa.</p> : null}
      </li>)}
    </ul>}
  </article>;
}
