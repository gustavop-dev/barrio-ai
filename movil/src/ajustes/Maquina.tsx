// Ajustes › Máquina: total stop and resume (overview.control) behind a confirmation, a stop from the
// server that cannot be lifted here, and the pause of each Unipile or directo account with a required reason; a
// directo account also shows its last daily LinkedIn canary and, when the server has it on, «Conectar LinkedIn»:
// the remote view of the server's browser opens in the in-app browser (no WebView: a native module), and the
// login's state is asked every 3 s until it ends.
import { ApiError } from '@compartido/api/client';
import { useCancelLinkedInLogin, useLinkedInLogin, useOverview, useReopenLinkedInLogin, useSetAccountPaused, useSetControl, useStartLinkedInLogin } from '@compartido/api/hooks';
import { keys } from '@compartido/api/queryClient';
import type { Account, AccountLogin, Control, Overview } from '@compartido/api/types';
import {
  accountStatus,
  canaryLine,
  connectLabel,
  controlReason,
  LOGIN_PRIVACY,
  loginActive,
  loginLine,
  providerLabel,
  stoppedFromServer,
  unipileAccounts,
} from '@compartido/logic/ajustes';
import { whenLabel } from '@compartido/logic/capturas';
import { timeAgo } from '@compartido/logic/format';
import { useQueryClient } from '@tanstack/react-query';
import * as WebBrowser from 'expo-web-browser';
import { useState } from 'react';
import { Badge, Button, Card, ConfirmSheet, ErrorRetry, KeyValue, Note, Section, Skeleton, T, useToast } from '@/components/ui';
import { haptic } from '@/theme/motion';
import { colors } from '@/theme/tokens';
import { CardHead, MachineButton } from './parts';

function ControlCard({ control }: { control: Control }) {
  const client = useQueryClient();
  const toast = useToast();
  const mutation = useSetControl();
  const [asking, setAsking] = useState(false);
  const fromServer = stoppedFromServer(control);

  const submit = (note: string) =>
    mutation.mutate(
      { paused: !control.paused, reason: note },
      {
        onSuccess: (next) => {
          client.setQueryData<Overview>(keys.overview, (old) => (old ? { ...old, control: next } : old));
          setAsking(false);
          haptic('actionSuccess');
          toast.show(next.paused ? 'Máquina detenida.' : 'Máquina en marcha.');
        },
        onError: () => haptic('actionError'),
      },
    );

  const open = () => {
    mutation.reset();
    setAsking(true);
  };

  if (!control.paused) {
    return (
      <Card>
        <CardHead>
          <Badge tone="ok">En marcha</Badge>
        </CardHead>
        <T>La máquina está en marcha. Observa, redacta y actúa dentro de los topes.</T>
        <MachineButton kind="stop" onPress={open}>
          Parada total
        </MachineButton>
        <T variant="detalle" soft>
          Pide un motivo: se detiene todo el ciclo y ninguna acción se ejecuta hasta que la reanudes.
        </T>
        {asking ? (
          <ConfirmSheet
            title="Parada total"
            tone="danger"
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
          </ConfirmSheet>
        ) : null}
      </Card>
    );
  }

  return (
    <Card tone="bad">
      <CardHead>
        <Badge tone="bad" solid>
          Detenida
        </Badge>
      </CardHead>
      <T>{controlReason(control)}</T>
      <KeyValue label="Origen">{fromServer ? 'Desde el servidor' : 'Desde la app'}</KeyValue>
      {control.updated_by ? <KeyValue label="Quién">{control.updated_by}</KeyValue> : null}
      {control.updated_at ? <KeyValue label="Cuándo">{whenLabel(control.updated_at)}</KeyValue> : null}
      <MachineButton kind="resume" disabled={fromServer} onPress={open}>
        Reanudar
      </MachineButton>
      {fromServer ? (
        <T variant="detalle" soft>
          La parada viene del servidor (OPERATOR_PAUSED=true). No se puede levantar desde la app.
        </T>
      ) : null}
      {!asking ? <ErrorRetry error={mutation.error} /> : null}
      {asking ? (
        <ConfirmSheet
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
        </ConfirmSheet>
      ) : null}
    </Card>
  );
}

/** The last daily LinkedIn canary of a `directo` account: a quiet line when it passed, a note with the reason when not. */
function CanaryLine({ canary }: { canary: NonNullable<ReturnType<typeof canaryLine>> }) {
  if (canary.tone === 'ok' || canary.tone === 'muted') {
    return (
      <T variant="detalle" soft>
        {canary.text}
      </T>
    );
  }
  return (
    <Note tone={canary.tone === 'bad' ? 'error' : 'warn'} title={canary.text}>
      {canary.detail || undefined}
    </Note>
  );
}

/** The server's browser in the in-app browser (Custom Tabs on Android, Safari view on iOS). */
function openRemoteView(url: string) {
  return WebBrowser.openBrowserAsync(url, { showTitle: true, toolbarColor: colors.surface, controlsColor: colors.brandDeep });
}

/** «Conectar LinkedIn» of a directo account: start or open again, the state while it lasts, cancel. */
function ConnectLinkedIn({ account }: { account: Account }) {
  const start = useStartLinkedInLogin();
  const reopen = useReopenLinkedInLogin();
  const cancel = useCancelLinkedInLogin();
  const [current, setCurrent] = useState<AccountLogin | null>(null);
  const known = current ?? account.connect?.last ?? null;
  const poll = useLinkedInLogin(known?.id ?? null, loginActive(known));
  // The poll's answer is newer than what started it, unless a cancel came after (current is then already ended).
  const login = poll.data && poll.data.login.id === known?.id && loginActive(known) ? poll.data.login : known;
  const failed = start.error ?? reopen.error;

  const open = (answer: { login: AccountLogin; url: string | null }) => {
    setCurrent(answer.login);
    if (answer.url) void openRemoteView(answer.url).then(() => void poll.refetch());
  };
  const connect = () => {
    reopen.reset();
    start.mutate(account.id, { onSuccess: open, onError: () => haptic('actionError') });
  };

  return (
    <>
      {login ? <StateNote line={loginLine(login)} /> : null}
      {failed instanceof ApiError && failed.status === 503 ? (
        <Note tone="warn" title="El navegador del servidor no está disponible ahora.">
          {failed.detail}
        </Note>
      ) : (
        <ErrorRetry error={failed} />
      )}
      {loginActive(login) && login ? (
        <>
          <Button variant="primary" block loading={reopen.isPending} loadingLabel="Abriendo…" onPress={() => reopen.mutate(login.id, { onSuccess: open })}>
            Abrir de nuevo
          </Button>
          <Button block loading={cancel.isPending} loadingLabel="Cancelando…" onPress={() => cancel.mutate(login.id, { onSuccess: (answer) => setCurrent(answer.login) })}>
            Cancelar la conexión
          </Button>
        </>
      ) : (
        <Button variant="primary" block loading={start.isPending} loadingLabel="Abriendo el navegador del servidor…" onPress={connect} accessibilityLabel={`${connectLabel(account, login)}: ${account.label}`}>
          {connectLabel(account, login)}
        </Button>
      )}
      <T variant="detalle" soft>
        {LOGIN_PRIVACY}
      </T>
    </>
  );
}

/** A state line: quiet when fine, a note otherwise. */
function StateNote({ line }: { line: { text: string; tone: string } }) {
  if (line.tone === 'ok' || line.tone === 'muted' || line.tone === 'info') {
    return (
      <T variant="detalle" soft>
        {line.text}
      </T>
    );
  }
  return <Note tone={line.tone === 'bad' ? 'error' : 'warn'}>{line.text}</Note>;
}

function AccountCard({ account }: { account: Account }) {
  const toast = useToast();
  const mutation = useSetAccountPaused();
  const [asking, setAsking] = useState(false);
  const status = accountStatus(account);
  const canary = canaryLine(account);

  const setPaused = (paused: boolean, reason = '') =>
    mutation.mutate(
      { accountId: account.id, paused, reason },
      {
        onSuccess: () => {
          setAsking(false);
          haptic('actionSuccess');
          toast.show(paused ? 'Cuenta en pausa.' : 'Cuenta reanudada.');
        },
        onError: () => haptic('actionError'),
      },
    );

  return (
    <Card>
      <CardHead title={`${account.label} (${providerLabel(account)})`}>
        <Badge tone={status.tone}>{status.label}</Badge>
        {account.paused ? <Badge tone="bad">En pausa</Badge> : null}
        {account.is_locked ? <Badge tone="warn">Bloqueada</Badge> : null}
      </CardHead>
      <T variant="detalle" soft>
        {account.last_checked_at ? `Comprobada ${timeAgo(account.last_checked_at)}` : 'Todavía sin comprobar'}
      </T>
      {canary ? <CanaryLine canary={canary} /> : null}
      {account.paused && account.paused_reason ? <Note tone="warn">{account.paused_reason}</Note> : null}
      {account.provider === 'directo' && account.connect?.enabled ? <ConnectLinkedIn account={account} /> : null}
      {account.paused ? (
        <Button variant="primary" block loading={mutation.isPending} loadingLabel="Reanudando…" onPress={() => setPaused(false)}>
          Reanudar la cuenta
        </Button>
      ) : (
        <Button
          block
          onPress={() => {
            mutation.reset();
            setAsking(true);
          }}
          accessibilityLabel={`Pausar solo esta cuenta: ${account.label}`}
        >
          Pausar solo esta cuenta
        </Button>
      )}
      {!asking ? <ErrorRetry error={mutation.error} /> : null}
      {asking ? (
        <ConfirmSheet
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
        </ConfirmSheet>
      ) : null}
    </Card>
  );
}

export function MaquinaSection() {
  const overview = useOverview();
  const accounts = unipileAccounts(overview.data?.accounts);
  return (
    <Section label="Máquina">
      {overview.isPending ? <Skeleton variant="card" count={2} label="Cargando la máquina…" /> : null}
      <ErrorRetry error={overview.error} onRetry={() => void overview.refetch()} />
      {overview.data ? <ControlCard control={overview.data.control} /> : null}
      {accounts.map((account) => (
        <AccountCard key={account.id} account={account} />
      ))}
      {overview.data && !accounts.length ? (
        <T variant="detalle" soft>
          No hay ninguna cuenta de Unipile configurada.
        </T>
      ) : null}
    </Section>
  );
}
