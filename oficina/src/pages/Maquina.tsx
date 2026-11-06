import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { setAccountPaused, setControl } from '../api/endpoints';
import { useFeed, useOverview } from '../api/hooks';
import { keys } from '../api/queryClient';
import type { Account, Control, Overview } from '../api/types';
import { Badge, Empty, ErrorNote, Loading, Meter, Modal, PageHeader } from '../components/ui';
import { actionStateLabel, capabilityLabel, formatDateTime, money, timeAgo } from '../lib/format';

const ACCOUNT_STATUS: Record<string, string> = { running: 'Conectada', unknown: 'Sin comprobar' };

const SOURCE_LABEL: Record<string, string> = {
  db: 'desde la app',
  env: 'desde el entorno del servidor (OPERATOR_PAUSED)',
  none: '—',
};

function ControlPanel({ control }: { control: Control }) {
  const queryClient = useQueryClient();
  const [asking, setAsking] = useState(false);
  const [reason, setReason] = useState('');
  const mutation = useMutation({
    mutationFn: (input: { paused: boolean; reason: string }) => setControl(input.paused, input.reason),
    onSuccess: (next) => {
      queryClient.setQueryData<Overview>(keys.overview, (old) => (old ? { ...old, control: next } : old));
      void queryClient.invalidateQueries({ queryKey: keys.overview });
      void queryClient.invalidateQueries({ queryKey: keys.feed });
      setAsking(false);
      setReason('');
    },
  });
  const fromEnv = control.paused && control.source === 'env';

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (control.paused) mutation.mutate({ paused: false, reason: reason.trim() });
    else if (reason.trim()) mutation.mutate({ paused: true, reason: reason.trim() });
  };
  const open = () => {
    mutation.reset();
    setReason('');
    setAsking(true);
  };

  return (
    <section className={control.paused ? 'card control paused' : 'card control running'} aria-labelledby="control-title">
      <h2 id="control-title">{control.paused ? 'La máquina está detenida' : 'La máquina está en marcha'}</h2>
      {control.paused ? (
        <dl className="facts">
          <dt>Motivo</dt>
          <dd>{control.reason || 'Sin motivo indicado'}</dd>
          <dt>Origen</dt>
          <dd>{SOURCE_LABEL[control.source] ?? control.source}</dd>
          {control.updated_by ? (
            <>
              <dt>Por</dt>
              <dd>{control.updated_by}</dd>
            </>
          ) : null}
          {control.updated_at ? (
            <>
              <dt>Cuándo</dt>
              <dd>{formatDateTime(control.updated_at)}</dd>
            </>
          ) : null}
        </dl>
      ) : (
        <p className="muted">Observa, redacta, aprueba por política y ejecuta dentro de los topes. Una parada total lo detiene todo.</p>
      )}
      {fromEnv ? (
        <p className="note warn" role="note">
          Esta parada viene del entorno del servidor (<code>OPERATOR_PAUSED=true</code>). No se puede levantar desde la app: hay que cambiar la
          configuración del servidor.
        </p>
      ) : null}
      <button
        type="button"
        className={control.paused ? 'bigbutton resume' : 'bigbutton stop'}
        onClick={open}
        disabled={fromEnv || mutation.isPending}
      >
        {control.paused ? 'REANUDAR' : 'PARADA TOTAL'}
      </button>
      {!asking ? <ErrorNote error={mutation.error} /> : null}
      {asking ? (
        <Modal title={control.paused ? '¿Reanudar la máquina?' : 'Parada total'} onClose={() => setAsking(false)}>
          <form onSubmit={submit}>
            {control.paused ? (
              <p>La máquina volverá a observar, redactar y ejecutar según la política, la ventana horaria y los topes.</p>
            ) : (
              <p>Se detiene todo el ciclo autónomo y ninguna acción se ejecuta hasta que la reanudes.</p>
            )}
            <label htmlFor="control-reason">{control.paused ? 'Nota (opcional)' : 'Motivo de la parada'}</label>
            <textarea
              id="control-reason"
              required={!control.paused}
              maxLength={500}
              value={reason}
              onChange={(event) => setReason(event.target.value)}
              placeholder={control.paused ? '' : 'Por ejemplo: reviso los comentarios de esta semana'}
            />
            <ErrorNote error={mutation.error} />
            <div className="buttonrow">
              <button type="button" className="secondary" onClick={() => setAsking(false)}>
                Cancelar
              </button>
              <button
                type="submit"
                className={control.paused ? 'primary' : 'danger'}
                disabled={mutation.isPending || (!control.paused && !reason.trim())}
              >
                {mutation.isPending ? 'Enviando…' : control.paused ? 'Reanudar' : 'Detener la máquina'}
              </button>
            </div>
          </form>
        </Modal>
      ) : null}
    </section>
  );
}

function AccountCard({ account }: { account: Account }) {
  const queryClient = useQueryClient();
  const [reason, setReason] = useState('');
  const [pausing, setPausing] = useState(false);
  const mutation = useMutation({
    mutationFn: (paused: boolean) => setAccountPaused(account.id, paused, paused ? reason.trim() : ''),
    onSuccess: () => {
      setPausing(false);
      setReason('');
      void queryClient.invalidateQueries({ queryKey: keys.overview });
      void queryClient.invalidateQueries({ queryKey: keys.accounts });
    },
  });
  const capacities = Object.entries(account.capacity ?? {});
  return (
    <article className="card account">
      <div className="cardhead">
        <h3>{account.label}</h3>
        <span className="badges">
          <Badge tone={account.status === 'running' ? 'ok' : 'warn'}>{ACCOUNT_STATUS[account.status] ?? account.status}</Badge>
          {account.paused ? <Badge tone="bad">En pausa</Badge> : null}
          {account.is_locked ? <Badge tone="warn">Bloqueada</Badge> : null}
        </span>
      </div>
      <p className="muted small">
        Conector {account.provider} · comprobada {timeAgo(account.last_checked_at)}
      </p>
      {account.paused && account.paused_reason ? <p className="note warn">{account.paused_reason}</p> : null}
      {capacities.length ? (
        <div className="capacity">
          {capacities.map(([code, cap]) => (
            <div key={code} className="capblock">
              <p className="sectionlabel">
                {capabilityLabel(code)} <span className="muted">({code})</span> · quedan <strong>{cap.left}</strong> hoy
              </p>
              <Meter label={`${capabilityLabel(code)} hoy`} value={cap.daily_used} max={cap.daily} />
              <Meter label={`${capabilityLabel(code)} esta semana`} value={cap.weekly_used} max={cap.weekly} />
            </div>
          ))}
        </div>
      ) : (
        <Empty>Sin topes de capacidad informados.</Empty>
      )}
      {account.paused ? (
        <button type="button" className="primary" disabled={mutation.isPending} onClick={() => mutation.mutate(false)}>
          {mutation.isPending ? 'Reanudando…' : 'Reanudar la cuenta'}
        </button>
      ) : pausing ? (
        <form
          onSubmit={(event) => {
            event.preventDefault();
            if (reason.trim()) mutation.mutate(true);
          }}
        >
          <label htmlFor={`pause-${account.id}`}>Motivo para pausar la cuenta</label>
          <input id={`pause-${account.id}`} value={reason} onChange={(event) => setReason(event.target.value)} maxLength={500} required />
          <div className="buttonrow">
            <button type="button" className="secondary" onClick={() => setPausing(false)}>
              Cancelar
            </button>
            <button type="submit" className="danger" disabled={!reason.trim() || mutation.isPending}>
              Pausar la cuenta
            </button>
          </div>
        </form>
      ) : (
        <button type="button" className="secondary" onClick={() => setPausing(true)}>
          Pausar solo esta cuenta
        </button>
      )}
      <ErrorNote error={mutation.error} />
    </article>
  );
}

function Feed() {
  const feed = useFeed();
  if (feed.isPending) return <Loading label="Leyendo actividad…" />;
  if (feed.isError) return <ErrorNote error={feed.error} onRetry={() => void feed.refetch()} />;
  if (!feed.data.length) return <Empty>Todavía no hay eventos del operador.</Empty>;
  return (
    <ol className="feed">
      {feed.data.map((event) => (
        <li key={event.id}>
          <div className="feedhead">
            <code>{event.action}</code>
            <time dateTime={event.created_at} title={formatDateTime(event.created_at)}>
              {timeAgo(event.created_at)}
            </time>
          </div>
          <p className="small">
            {event.target ? <span>{event.target}</span> : null}
            <span className="muted"> · {event.actor ?? 'máquina'}</span>
          </p>
          {event.metadata && Object.keys(event.metadata).length ? (
            <details>
              <summary>Detalles</summary>
              <pre className="readable">{JSON.stringify(event.metadata, null, 2)}</pre>
            </details>
          ) : null}
        </li>
      ))}
    </ol>
  );
}

export function Maquina() {
  const overview = useOverview();
  if (overview.isPending) return <Loading label="Consultando la máquina…" />;
  if (overview.isError) {
    return (
      <>
        <PageHeader eyebrow="MÁQUINA AUTÓNOMA" title="Máquina" />
        <ErrorNote error={overview.error} onRetry={() => void overview.refetch()} />
      </>
    );
  }
  const data = overview.data;
  const spent = Number(data.today.llm_spent_usd);
  const cap = Number(data.today.llm_daily_cap_usd);
  const proposals = Object.entries(data.today.proposals).filter(([, n]) => n > 0);
  return (
    <div className="stack">
      <PageHeader eyebrow="MÁQUINA AUTÓNOMA" title="Máquina">
        Tú estás sobre el bucle: puedes detenerlo, vetar y resolver en cualquier momento.
      </PageHeader>
      <ControlPanel control={data.control} />

      <div className="grid two">
        <section className="card" aria-labelledby="autopilot-title">
          <h2 id="autopilot-title">Piloto automático</h2>
          <p>
            <Badge tone={data.autopilot.enabled ? 'ok' : 'muted'}>{data.autopilot.enabled ? 'Activado' : 'Desactivado'}</Badge>
          </p>
          <p className="muted small">Política {data.autopilot.policy_version}</p>
        </section>
        <section className="card" aria-labelledby="window-title">
          <h2 id="window-title">Ventana horaria</h2>
          <p>
            <Badge tone={data.window.open_now ? 'ok' : 'muted'}>{data.window.open_now ? 'Abierta ahora' : 'Cerrada ahora'}</Badge>
          </p>
          <p>
            {data.window.start}–{data.window.end} <span className="muted small">({data.window.timezone})</span>
          </p>
          <p className="muted small">Espaciado fijo de {Math.round(data.window.min_spacing_seconds / 60)} min entre acciones.</p>
        </section>
      </div>

      <section className="card" aria-labelledby="today-title">
        <h2 id="today-title">Hoy</h2>
        <Meter label="Gasto LLM del día" value={spent} max={cap} display={`${money(spent)} de ${money(cap)}`} />
        <Meter label="Borradores del día" value={data.today.drafts} max={data.today.drafts_daily_cap} />
        <p className="sectionlabel">PROPUESTAS DE HOY</p>
        {proposals.length ? (
          <ul className="chips">
            {proposals.map(([state, n]) => (
              <li key={state}>
                <Link to={`/acciones?state=${state}`} className="chip">
                  {actionStateLabel(state)} <strong>{n}</strong>
                </Link>
              </li>
            ))}
          </ul>
        ) : (
          <Empty>Ninguna propuesta hoy.</Empty>
        )}
        <p className="small">
          {data.counts.referents} referentes · {data.counts.posts} posts observados ·{' '}
          {data.counts.uncertain ? (
            <Link to="/acciones?state=uncertain">{data.counts.uncertain} inciertas por resolver</Link>
          ) : (
            '0 inciertas'
          )}
        </p>
      </section>

      <section aria-labelledby="accounts-title" className="stack">
        <h2 id="accounts-title">Cuenta de LinkedIn</h2>
        {data.accounts.length ? data.accounts.map((account) => <AccountCard key={account.id} account={account} />) : <Empty>No hay cuentas conectadas.</Empty>}
      </section>

      <section className="card" aria-labelledby="feed-title">
        <h2 id="feed-title">Actividad reciente</h2>
        <Feed />
      </section>
    </div>
  );
}
