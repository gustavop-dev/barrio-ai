// Ajustes › Máquina: total stop and resume (overview.control) and the Unipile account pause.
import { useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { useOverview, useSetAccountPaused, useSetControl } from '../../api/hooks';
import { keys } from '../../api/queryClient';
import type { Account, Control, Overview } from '../../api/types';
import { whenLabel } from '../../capture/parts';
import { Badge, Button, Card, ConfirmModal, ErrorRetry, Note, Section, Skeleton, useToast, type Tone } from '../../components/ui';
import { timeAgo } from '../../lib/format';
import { Row } from './shared';

const ACCOUNT_STATUS: Record<string, { label: string; tone: Tone }> = {
  running: { label: 'Conectada', tone: 'ok' },
  unknown: { label: 'Sin comprobar', tone: 'muted' },
  token_expired: { label: 'Token caducado', tone: 'bad' },
};

const PROVIDER_LABEL: Record<string, string> = { unipile: 'Unipile', fake: 'simulada' };

/** The accounts the machine acts with through Unipile; the official LinkedIn one lives in its own section. */
export function unipileAccounts(accounts: Account[] | undefined): Account[] {
  return (accounts ?? []).filter((account) => !account.provider.startsWith('linkedin'));
}

function ControlCard({ control }: { control: Control }) {
  const client = useQueryClient();
  const toast = useToast();
  const mutation = useSetControl();
  const [asking, setAsking] = useState(false);
  const fromEnv = control.paused && control.source === 'env';

  const submit = (note: string) =>
    mutation.mutate(
      { paused: !control.paused, reason: note },
      {
        onSuccess: (next) => {
          client.setQueryData<Overview>(keys.overview, (old) => (old ? { ...old, control: next } : old));
          setAsking(false);
          toast.show(next.paused ? 'Máquina detenida.' : 'Máquina en marcha.');
        },
      },
    );

  const open = () => {
    mutation.reset();
    setAsking(true);
  };

  if (!control.paused) {
    return (
      <Card className="aj-card">
        <div>
          <Badge tone="ok">En marcha</Badge>
        </div>
        <p className="t-cuerpo">La máquina está en marcha. Observa, redacta y actúa dentro de los topes.</p>
        <Button variant="stop" onClick={open}>
          Parada total
        </Button>
        <p className="t-detalle text-suave">Pide un motivo: se detiene todo el ciclo y ninguna acción se ejecuta hasta que la reanudes.</p>
        {asking ? (
          <ConfirmModal
            title="Parada total"
            tone="stop"
            note="required"
            noteLabel="Motivo"
            notePlaceholder="Por ejemplo: reviso los topes de la semana"
            confirmLabel="Detener la máquina"
            busy={mutation.isPending}
            error={mutation.error}
            onConfirm={submit}
            onClose={() => setAsking(false)}
          >
            Se detiene todo el ciclo y ninguna acción se ejecuta hasta que la reanudes.
          </ConfirmModal>
        ) : null}
      </Card>
    );
  }

  return (
    <Card tone="bad" className="aj-card">
      <div>
        <Badge tone="bad" solid>
          Detenida
        </Badge>
      </div>
      <p className="t-cuerpo">Motivo: {control.reason ? control.reason.replace(/\.$/, '') : 'sin motivo indicado'}.</p>
      <div className="aj-rows">
        <Row label="Origen">{fromEnv ? 'Desde el servidor' : 'Desde la app'}</Row>
        {control.updated_by ? <Row label="Quién">{control.updated_by}</Row> : null}
        {control.updated_at ? <Row label="Cuándo">{whenLabel(control.updated_at)}</Row> : null}
      </div>
      <Button variant="resume" disabled={fromEnv} onClick={open}>
        Reanudar
      </Button>
      {fromEnv ? (
        <p className="t-detalle text-suave">
          La parada viene del servidor (<code>OPERATOR_PAUSED=true</code>). No se puede levantar desde la app.
        </p>
      ) : null}
      {!asking ? <ErrorRetry error={mutation.error} /> : null}
      {asking ? (
        <ConfirmModal
          title="¿Reanudar la máquina?"
          note="optional"
          noteLabel="Nota"
          confirmLabel="Reanudar"
          busy={mutation.isPending}
          error={mutation.error}
          onConfirm={submit}
          onClose={() => setAsking(false)}
        >
          La máquina vuelve a observar, redactar y actuar según la política, la ventana horaria y los topes.
        </ConfirmModal>
      ) : null}
    </Card>
  );
}

function AccountCard({ account }: { account: Account }) {
  const toast = useToast();
  const mutation = useSetAccountPaused();
  const [asking, setAsking] = useState(false);
  const status = ACCOUNT_STATUS[account.status] ?? { label: account.status, tone: 'warn' as Tone };
  const provider = PROVIDER_LABEL[account.provider] ?? account.provider;

  const setPaused = (paused: boolean, reason = '') =>
    mutation.mutate(
      { accountId: account.id, paused, reason },
      {
        onSuccess: () => {
          setAsking(false);
          toast.show(paused ? 'Cuenta en pausa.' : 'Cuenta reanudada.');
        },
      },
    );

  return (
    <Card className="aj-card">
      <div className="aj-cardhead">
        <p className="t-cuerpo">
          {account.label} ({provider})
        </p>
        <span className="aj-badges">
          <Badge tone={status.tone}>{status.label}</Badge>
          {account.paused ? <Badge tone="bad">En pausa</Badge> : null}
          {account.is_locked ? <Badge tone="warn">Bloqueada</Badge> : null}
        </span>
      </div>
      <p className="t-detalle text-suave">{account.last_checked_at ? `Comprobada ${timeAgo(account.last_checked_at)}` : 'Todavía sin comprobar'}</p>
      {account.paused && account.paused_reason ? (
        <Note tone="warn" role={null}>
          {account.paused_reason}
        </Note>
      ) : null}
      {account.paused ? (
        <Button variant="primary" block loading={mutation.isPending} loadingLabel="Reanudando…" onClick={() => setPaused(false)}>
          Reanudar la cuenta
        </Button>
      ) : (
        <Button
          variant="secondary"
          block
          onClick={() => {
            mutation.reset();
            setAsking(true);
          }}
        >
          Pausar solo esta cuenta
        </Button>
      )}
      {!asking ? <ErrorRetry error={mutation.error} /> : null}
      {asking ? (
        <ConfirmModal
          title="¿Pausar solo esta cuenta?"
          tone="danger"
          note="required"
          noteLabel="Motivo"
          confirmLabel="Pausar la cuenta"
          busy={mutation.isPending}
          error={mutation.error}
          onConfirm={(reason) => setPaused(true, reason)}
          onClose={() => setAsking(false)}
        >
          El equipo deja de actuar con esta cuenta hasta que la reanudes. El resto de la máquina sigue en marcha.
        </ConfirmModal>
      ) : null}
    </Card>
  );
}

export function MaquinaSection() {
  const overview = useOverview();
  const accounts = unipileAccounts(overview.data?.accounts);
  return (
    <Section label="Máquina" id="maquina">
      {overview.isPending ? <Skeleton variant="card" count={2} label="Cargando la máquina…" /> : null}
      <ErrorRetry error={overview.error} onRetry={() => void overview.refetch()} />
      {overview.data ? <ControlCard control={overview.data.control} /> : null}
      {accounts.map((account) => (
        <AccountCard key={account.id} account={account} />
      ))}
      {overview.data && !accounts.length ? <p className="t-detalle text-suave">No hay ninguna cuenta de Unipile configurada.</p> : null}
    </Section>
  );
}
