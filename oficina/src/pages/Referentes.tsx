import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState, type FormEvent } from 'react';
import { addReferent, asList, listReferents, observeNow } from '../api/endpoints';
import { useAccounts } from '../api/hooks';
import { keys } from '../api/queryClient';
import { Badge, Empty, ErrorNote, ExternalLink, Loading, PageHeader } from '../components/ui';
import { timeAgo } from '../lib/format';

/** Accepts linkedin.com/in/<slug> with or without scheme; returns the https URL or null. */
export function normalizeProfileUrl(raw: string): string | null {
  const value = raw.trim();
  if (!value) return null;
  const withScheme = /^[a-z]+:\/\//i.test(value) ? value : `https://${value}`;
  let url: URL;
  try {
    url = new URL(withScheme);
  } catch {
    return null;
  }
  if (url.protocol !== 'https:') return null;
  if (!/^(www\.|[a-z]{2}\.)?linkedin\.com$/i.test(url.hostname)) return null;
  const match = /^\/in\/([^/]+)\/?$/.exec(url.pathname);
  if (!match) return null;
  return `https://www.linkedin.com/in/${match[1]}/`;
}

function AddReferent({ account }: { account: string }) {
  const queryClient = useQueryClient();
  const [url, setUrl] = useState('');
  const [reason, setReason] = useState('');
  const [touched, setTouched] = useState(false);
  const normalized = normalizeProfileUrl(url);
  const mutation = useMutation({
    mutationFn: () => addReferent(account, normalized ?? '', reason.trim()),
    onSuccess: () => {
      setUrl('');
      setReason('');
      setTouched(false);
      void queryClient.invalidateQueries({ queryKey: keys.referents(account) });
      void queryClient.invalidateQueries({ queryKey: keys.overview });
    },
  });
  const submit = (event: FormEvent) => {
    event.preventDefault();
    setTouched(true);
    if (normalized && reason.trim()) mutation.mutate();
  };
  const urlError = touched && !normalized ? 'Pega la URL de un perfil: https://www.linkedin.com/in/…' : null;
  const reasonError = touched && !reason.trim() ? 'El motivo es obligatorio.' : null;
  return (
    <form className="card" onSubmit={submit} noValidate>
      <h2>Añadir referente</h2>
      <label htmlFor="ref-url">URL del perfil en LinkedIn</label>
      <input
        id="ref-url"
        type="url"
        inputMode="url"
        autoCapitalize="none"
        spellCheck={false}
        placeholder="https://www.linkedin.com/in/…"
        value={url}
        onChange={(event) => setUrl(event.target.value)}
        aria-invalid={Boolean(urlError)}
        aria-describedby={urlError ? 'ref-url-error' : undefined}
      />
      {urlError ? (
        <p id="ref-url-error" className="fielderror">
          {urlError}
        </p>
      ) : null}
      <label htmlFor="ref-reason">Motivo</label>
      <textarea
        id="ref-reason"
        maxLength={1000}
        placeholder="Por qué su conversación importa para tu barrio"
        value={reason}
        onChange={(event) => setReason(event.target.value)}
        aria-invalid={Boolean(reasonError)}
        aria-describedby={reasonError ? 'ref-reason-error' : undefined}
      />
      {reasonError ? (
        <p id="ref-reason-error" className="fielderror">
          {reasonError}
        </p>
      ) : null}
      <ErrorNote error={mutation.error} />
      {mutation.isSuccess ? (
        <p className="note ok" role="status">
          Referente guardado.
        </p>
      ) : null}
      <button type="submit" className="primary" disabled={mutation.isPending}>
        {mutation.isPending ? 'Guardando…' : 'Añadir referente'}
      </button>
    </form>
  );
}

export function Referentes() {
  const accounts = useAccounts();
  const [chosen, setChosen] = useState('');
  const account = chosen || accounts.data?.[0]?.id || '';
  const referents = useQuery({
    queryKey: keys.referents(account),
    queryFn: async () => asList(await listReferents(account)),
    enabled: Boolean(account),
  });
  const observe = useMutation({ mutationFn: () => observeNow(account) });

  if (accounts.isPending) return <Loading label="Cargando cuentas…" />;
  if (accounts.isError) return <ErrorNote error={accounts.error} onRetry={() => void accounts.refetch()} />;

  return (
    <div className="stack">
      <PageHeader eyebrow="OBSERVATORIO" title="Referentes">
        Las voces que la máquina lee para encontrar conversaciones donde aportar.
      </PageHeader>
      {!accounts.data.length ? (
        <Empty>No hay ninguna cuenta de LinkedIn configurada. Conéctala primero en el servidor.</Empty>
      ) : (
        <>
          {accounts.data.length > 1 ? (
            <div className="filters">
              <label htmlFor="account">Cuenta</label>
              <select id="account" value={account} onChange={(event) => setChosen(event.target.value)}>
                {accounts.data.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.label}
                  </option>
                ))}
              </select>
            </div>
          ) : null}
          <section className="card">
            <h2>Observar ahora</h2>
            <p className="muted">Pide al operador que lea ya los posts recientes de los referentes, sin esperar al próximo ciclo.</p>
            <button type="button" className="primary" disabled={observe.isPending} onClick={() => observe.mutate()}>
              {observe.isPending ? 'Encolando…' : 'Observar ahora'}
            </button>
            {observe.isSuccess ? (
              <p className="note ok" role="status">
                Observación encolada. Los posts nuevos aparecerán en unos minutos.
              </p>
            ) : null}
            <ErrorNote error={observe.error} />
          </section>
          <AddReferent account={account} />
          <section className="stack" aria-labelledby="ref-list">
            <h2 id="ref-list">Lista {referents.data ? <span className="muted small">({referents.data.length})</span> : null}</h2>
            {referents.isPending ? <Loading label="Cargando referentes…" /> : null}
            {referents.isError ? <ErrorNote error={referents.error} onRetry={() => void referents.refetch()} /> : null}
            {referents.isSuccess && !referents.data.length ? <Empty>Aún no hay referentes.</Empty> : null}
            <ul className="list">
              {referents.data?.map((ref) => (
                <li key={ref.id} className="card referent">
                  <div className="cardhead">
                    <h3>{ref.display_name || ref.public_identifier || ref.profile_url || 'Referente'}</h3>
                    {ref.active === false ? <Badge tone="muted">Inactivo</Badge> : <Badge tone="ok">Activo</Badge>}
                  </div>
                  <p>{ref.reason}</p>
                  <p className="small muted">
                    {ref.last_observed_at ? `Observado ${timeAgo(ref.last_observed_at)}` : 'Aún sin observar'}
                    {ref.profile_url ? ' · ' : ''}
                    <ExternalLink href={ref.profile_url}>Perfil</ExternalLink>
                  </p>
                </li>
              ))}
            </ul>
          </section>
        </>
      )}
    </div>
  );
}
