// Ajustes › Notificaciones en este dispositivo: Web Push (src/push) with activate, test and disable,
// the iPhone steps, and one switch per push type (`push_types`, PATCH /preferencias push_disabled).
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { useSavePreferencias, type AjustesConPush, type PushType } from '../../api/capturas';
import { sendTestPush } from '../../api/endpoints';
import { useAjustes } from '../../api/hooks';
import { IconChevronDown } from '../../components/icons';
import { Badge, Button, Card, ConfirmModal, ErrorRetry, Note, Section, errorMessage, useToast } from '../../components/ui';
import { currentSubscription, detectPush, disablePush, enablePush } from '../../push/push';
import { SwitchRow, Unavailable } from './shared';

const PUSH_KEY = ['push-subscription'] as const;

function IphoneSteps({ highlight }: { highlight: boolean }) {
  return (
    <Note tone={highlight ? 'warn' : 'info'} title="En iPhone o iPad" role={null}>
      <p>Las notificaciones solo funcionan con 0ff1ce instalada en la pantalla de inicio (iOS 16.4 o posterior):</p>
      <ol className="aj-steps">
        <li>Abre esta página en Safari.</li>
        <li>Toca Compartir y elige «Añadir a pantalla de inicio».</li>
        <li>Abre 0ff1ce desde el icono nuevo, entra y vuelve a Ajustes.</li>
        <li>Toca «Activar notificaciones» y acepta el permiso.</li>
      </ol>
    </Note>
  );
}

function Device() {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [support, setSupport] = useState(detectPush);
  const [confirmOff, setConfirmOff] = useState(false);
  const usable = support.supported && !support.needsInstall;
  const subscription = useQuery({ queryKey: PUSH_KEY, queryFn: currentSubscription, enabled: usable, retry: false });
  const refresh = () => {
    setSupport(detectPush());
    void queryClient.invalidateQueries({ queryKey: PUSH_KEY });
  };
  const enable = useMutation({ mutationFn: enablePush, onSuccess: () => toast.show('Notificaciones activadas en este dispositivo.'), onSettled: refresh });
  const disable = useMutation({
    mutationFn: disablePush,
    onSuccess: () => {
      setConfirmOff(false);
      toast.show('Notificaciones desactivadas en este dispositivo.');
    },
    onSettled: refresh,
  });
  const test = useMutation({ mutationFn: sendTestPush, onSuccess: () => toast.show('Notificación de prueba enviada. Debería llegar en unos segundos.') });
  const active = Boolean(subscription.data);
  const blocked = support.permission === 'denied';
  const badge = !usable
    ? { label: support.needsInstall ? 'Instala la app' : 'No disponibles', tone: 'muted' as const }
    : subscription.isPending
      ? { label: 'Comprobando…', tone: 'muted' as const }
      : active
        ? { label: 'Activadas', tone: 'ok' as const }
        : blocked
          ? { label: 'Bloqueadas', tone: 'bad' as const }
          : { label: 'Desactivadas', tone: 'muted' as const };

  return (
    <>
      <div className="aj-cardhead">
        <p className="t-cuerpo">Este dispositivo</p>
        <Badge tone={badge.tone}>{badge.label}</Badge>
      </div>
      <p className="t-detalle text-suave">Te avisan aquí de lo que pide tu acción (Tu turno) y de lo importante que pasa (Notificaciones).</p>
      {support.ios || support.needsInstall ? <IphoneSteps highlight={support.needsInstall} /> : null}
      {!support.supported && !support.needsInstall ? (
        <Note tone="warn" role={null}>
          Este navegador no admite notificaciones push. Prueba con Chrome, Edge, Firefox o la app instalada en iPhone.
        </Note>
      ) : null}
      {usable && blocked ? (
        <Note tone="warn" role={null}>
          Has bloqueado las notificaciones. Permítelas para 0ff1ce en los ajustes del navegador o del sistema.
        </Note>
      ) : null}
      {usable ? (
        active ? (
          <div className="aj-buttons">
            <Button variant="secondary" block loading={test.isPending} onClick={() => test.mutate()}>
              Probar notificación
            </Button>
            <Button
              variant="danger"
              block
              onClick={() => {
                disable.reset();
                setConfirmOff(true);
              }}
            >
              Desactivar
            </Button>
          </div>
        ) : (
          <Button variant="primary" block disabled={subscription.isPending} loading={enable.isPending} loadingLabel="Activando…" onClick={() => enable.mutate()}>
            Activar notificaciones
          </Button>
        )
      ) : null}
      <ErrorRetry error={subscription.error ?? enable.error ?? test.error ?? (confirmOff ? null : disable.error)} />
      {confirmOff ? (
        <ConfirmModal
          title="¿Desactivar las notificaciones aquí?"
          tone="danger"
          confirmLabel="Desactivar"
          busyLabel="Desactivando…"
          busy={disable.isPending}
          error={disable.error}
          onConfirm={() => disable.mutate()}
          onClose={() => setConfirmOff(false)}
        >
          Este dispositivo deja de recibir avisos. Los demás siguen igual y puedes volver a activarlas cuando quieras.
        </ConfirmModal>
      ) : null}
    </>
  );
}

/** One switch per push type; the notice itself still reaches Tu turno or Notificaciones. */
function PerType() {
  const ajustes = useAjustes();
  const save = useSavePreferencias();
  const toast = useToast();
  const [overrides, setOverrides] = useState<Record<string, boolean>>({});
  const types: PushType[] | undefined = (ajustes.data as AjustesConPush | undefined)?.push_types;
  const enabled = (type: PushType) => overrides[type.kind] ?? type.enabled;

  const toggle = (type: PushType, next: boolean) => {
    const previous = overrides;
    const updated = { ...overrides, [type.kind]: next };
    setOverrides(updated);
    const disabled = (types ?? []).filter((t) => !(updated[t.kind] ?? t.enabled)).map((t) => t.kind);
    save.mutate(
      { push_disabled: disabled },
      {
        onSuccess: () => toast.show(next ? `Push activada: ${type.label}.` : `Push apagada: ${type.label}.`),
        onError: (error) => {
          setOverrides(previous);
          toast.show(errorMessage(error), { tone: 'error' });
        },
      },
    );
  };

  return (
    <details className="fold aj-fold-inner">
      <summary>
        Por tipo de notificación
        <IconChevronDown size={22} />
      </summary>
      <div className="fold-body">
        {ajustes.isSuccess && !types ? <Unavailable>El servidor todavía no envía los tipos de notificación.</Unavailable> : null}
        <ErrorRetry error={ajustes.error} onRetry={() => void ajustes.refetch()} />
        {types?.length ? (
          <>
            <p className="t-detalle text-suave">Apagar la push de un tipo no lo borra: el aviso sigue llegando a Tu turno o a Notificaciones.</p>
            <div className="aj-switches">
              {types.map((type) => (
                <SwitchRow
                  key={type.kind}
                  label={type.label}
                  hint={type.goes_to === 'tu_turno' ? 'Va a Tu turno' : type.goes_to === 'notificaciones' ? 'Va a Notificaciones' : undefined}
                  checked={enabled(type)}
                  disabled={save.isPending}
                  onChange={(next) => toggle(type, next)}
                />
              ))}
            </div>
          </>
        ) : null}
      </div>
    </details>
  );
}

export function NotificacionesSection() {
  return (
    <Section label="Notificaciones en este dispositivo" id="notificaciones">
      <Card className="aj-card">
        <Device />
        <PerType />
      </Card>
    </Section>
  );
}
