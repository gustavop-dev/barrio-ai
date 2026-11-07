import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState, type FormEvent } from 'react';
import { asList, confirmMemory, listMemory, proposeMemory } from '../api/endpoints';
import { keys } from '../api/queryClient';
import type { MemoryItem } from '../api/types';
import { Badge, Empty, ErrorNote, Loading, Modal, PageHeader } from '../components/ui';
import { formatDateTime, prettyValue } from '../lib/format';

const DEFAULT_EVIDENCE = 'Declaración explícita del propietario en la oficina de Barrio AI';

function MemoryCard({ item }: { item: MemoryItem }) {
  const queryClient = useQueryClient();
  const [asking, setAsking] = useState(false);
  const confirm = useMutation({
    mutationFn: () => confirmMemory(item.id, item.version),
    onSuccess: () => {
      setAsking(false);
      void queryClient.invalidateQueries({ queryKey: keys.memory });
    },
  });
  const confirmable = item.status === 'proposed' && item.namespace === 'user';
  return (
    <li className="card memory">
      <div className="cardhead">
        <h3>{item.key}</h3>
        <span className="badges">
          <Badge tone={item.status === 'confirmed' ? 'ok' : 'warn'}>{item.status === 'confirmed' ? 'Confirmado' : 'Propuesto'}</Badge>
          <Badge tone="muted">v{item.version}</Badge>
        </span>
      </div>
      <pre className="readable">{prettyValue(item.value)}</pre>
      <p className="small muted">
        {item.namespace === 'user' ? 'Sobre ti' : 'De trabajo'} · {item.evidence} · {formatDateTime(item.created_at)}
      </p>
      {confirmable ? (
        <button type="button" className="primary" onClick={() => setAsking(true)}>
          Confirmar este dato
        </button>
      ) : null}
      {asking ? (
        <Modal title="Confirmar dato" onClose={() => setAsking(false)}>
          <p>¿Confirmas que «{item.key}» es correcto y que los agentes pueden usarlo como contexto?</p>
          <ErrorNote error={confirm.error} />
          <div className="buttonrow">
            <button type="button" className="secondary" onClick={() => setAsking(false)}>
              Cancelar
            </button>
            <button type="button" className="primary" disabled={confirm.isPending} onClick={() => confirm.mutate()}>
              {confirm.isPending ? 'Confirmando…' : 'Confirmar'}
            </button>
          </div>
        </Modal>
      ) : null}
    </li>
  );
}

export function Memoria() {
  const queryClient = useQueryClient();
  const memory = useQuery({ queryKey: keys.memory, queryFn: async () => asList(await listMemory()) });
  const [key, setKey] = useState('');
  const [value, setValue] = useState('');
  const [evidence, setEvidence] = useState(DEFAULT_EVIDENCE);
  const items = memory.data ?? [];
  const confirmed = items.filter((m) => m.status === 'confirmed');
  const proposed = items.filter((m) => m.status === 'proposed');

  const propose = useMutation({
    mutationFn: () => {
      const current = items.find((m) => m.namespace === 'user' && m.key === key.trim());
      return proposeMemory(key.trim(), value.trim(), evidence.trim() || DEFAULT_EVIDENCE, current?.version ?? 0);
    },
    onSuccess: () => {
      setKey('');
      setValue('');
      setEvidence(DEFAULT_EVIDENCE);
      void queryClient.invalidateQueries({ queryKey: keys.memory });
    },
  });
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (key.trim() && value.trim()) propose.mutate();
  };

  return (
    <div className="stack">
      <PageHeader eyebrow="UNA MEMORIA PARA TODO EL EQUIPO" title="Memoria">
        Los agentes solo usan hechos que tú confirmas. Una propuesta no sustituye al dato confirmado hasta que la apruebes.
      </PageHeader>
      {memory.isPending ? <Loading label="Consultando memoria…" /> : null}
      {memory.isError ? <ErrorNote error={memory.error} onRetry={() => void memory.refetch()} /> : null}
      {memory.isSuccess ? (
        <>
          <section aria-labelledby="mem-proposed">
            <h2 id="mem-proposed">Propuestos ({proposed.length})</h2>
            {proposed.length ? (
              <ul className="list">
                {proposed.map((item) => (
                  <MemoryCard key={item.id} item={item} />
                ))}
              </ul>
            ) : (
              <Empty>Nada pendiente de confirmar.</Empty>
            )}
          </section>
          <section aria-labelledby="mem-confirmed">
            <h2 id="mem-confirmed">Confirmados ({confirmed.length})</h2>
            {confirmed.length ? (
              <ul className="list">
                {confirmed.map((item) => (
                  <MemoryCard key={item.id} item={item} />
                ))}
              </ul>
            ) : (
              <Empty>Aún no hay hechos confirmados. Nadie inventará tu nicho, tus servicios ni tus clientes.</Empty>
            )}
          </section>
        </>
      ) : null}
      <form className="card" onSubmit={submit}>
        <h2>Proponer un dato</h2>
        <label htmlFor="mem-key">Nombre del dato</label>
        <input id="mem-key" maxLength={200} required value={key} onChange={(event) => setKey(event.target.value)} placeholder="Ej.: servicio principal" />
        <label htmlFor="mem-value">Lo que quieres que el equipo recuerde</label>
        <textarea id="mem-value" maxLength={4000} required value={value} onChange={(event) => setValue(event.target.value)} placeholder="Un hecho real sobre ti o tu negocio." />
        <label htmlFor="mem-evidence">Procedencia</label>
        <input id="mem-evidence" maxLength={2000} value={evidence} onChange={(event) => setEvidence(event.target.value)} />
        <ErrorNote error={propose.error} />
        {propose.isSuccess ? (
          <p className="note ok" role="status">
            Propuesta guardada. Confírmala cuando la hayas revisado.
          </p>
        ) : null}
        <button type="submit" className="primary" disabled={!key.trim() || !value.trim() || propose.isPending}>
          {propose.isPending ? 'Guardando…' : 'Proponer dato'}
        </button>
      </form>
    </div>
  );
}
