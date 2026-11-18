// Ajustes › Mi voz (GET /api/v1/yo/voz, organizaciones phase 7): which voice the team writes with in her name, how
// many of her own texts it has learned from, and the proposal of her voice, which only she confirms or discards.
import { useState } from 'react';
import {
  PROPOSE_COST,
  proposeBlocked,
  signalRows,
  VERSION_STATE_LABEL,
  VERSION_STATE_TONE,
  VOICE_TONE,
  voiceProgress,
  voiceSentence,
} from '../../../../compartido/src/logic/miembro';
import { formatDateTime } from '../../../../compartido/src/logic/format';
import { useDecideMiVoz, useMiVoz, useProposeMiVoz } from '../../api/hooks';
import { IconChevronDown } from '../../components/icons';
import { Badge, Button, Card, ConfirmModal, ErrorRetry, Meter, Note, Section, Skeleton, useToast } from '../../components/ui';
import { isUnavailable, Row, Unavailable } from './shared';

type Asking = { kind: 'confirmar' | 'descartar'; number: number } | { kind: 'proponer' } | null;

export function MiVozSection() {
  const voz = useMiVoz();
  const decide = useDecideMiVoz();
  const propose = useProposeMiVoz();
  const toast = useToast();
  const [asking, setAsking] = useState<Asking>(null);
  const [reading, setReading] = useState(false);
  const data = voz.data;
  const proposal = data?.proposal ?? null;

  const close = () => {
    setAsking(null);
    decide.reset();
    propose.reset();
  };

  return (
    <Section
      label="Mi voz"
      id="voz"
      intro="El equipo aprende tu estilo de lo que apruebas, corriges, respondes y grabas. Tu voz solo cambia cuando tú confirmas una propuesta."
    >
      {voz.isPending ? <Skeleton variant="card" label="Cargando tu voz…" /> : null}
      {isUnavailable(voz.error) ? <Unavailable>El servidor todavía no muestra tu voz.</Unavailable> : <ErrorRetry error={voz.error} onRetry={() => void voz.refetch()} />}
      {data ? (
        <Card className="aj-card">
          <div className="aj-cardhead">
            <p className="t-cuerpo">Voz del equipo en tu nombre</p>
            <span className="aj-badges">
              <Badge tone={VOICE_TONE[data.state] ?? 'muted'} dot>
                <span data-testid="voz-estado">{data.label}</span>
              </Badge>
            </span>
          </div>
          <p className="t-detalle">{voiceSentence(data)}</p>
          <Meter label="Muestra para una propuesta" value={data.signals.texts} max={data.signals.minimum} display={voiceProgress(data.signals)} />
          <div className="aj-rows" aria-label="Señales por tipo">
            {signalRows(data.signals).map((row) => (
              <Row key={row.kind} label={row.label}>
                {row.count}
              </Row>
            ))}
          </div>

          {proposal ? (
            <Note
              tone="info"
              title={`Propuesta de tu voz (versión ${proposal.number}) lista`}
              actions={
                <>
                  <Button variant="secondary" aria-expanded={reading} onClick={() => setReading((value) => !value)}>
                    {reading ? 'Ocultar la propuesta' : 'Ver la propuesta'}
                  </Button>
                  <Button variant="primary" onClick={() => setAsking({ kind: 'confirmar', number: proposal.number })}>
                    Confirmar
                  </Button>
                  <Button variant="ghost" onClick={() => setAsking({ kind: 'descartar', number: proposal.number })}>
                    Descartar
                  </Button>
                </>
              }
            >
              <p>
                Preparada {formatDateTime(proposal.created_at)}. No se usa hasta que la confirmes.
                {proposal.note ? ` ${proposal.note}` : ''}
              </p>
              {reading ? (
                <pre className="t-detalle" style={{ whiteSpace: 'pre-wrap' }} aria-label={`Texto de la propuesta ${proposal.number}`}>
                  {proposal.text}
                </pre>
              ) : null}
            </Note>
          ) : null}

          {data.can_propose ? (
            <div className="aj-actions">
              <Button variant="secondary" onClick={() => setAsking({ kind: 'proponer' })}>
                Pedir propuesta de mi voz
              </Button>
            </div>
          ) : (
            <p className="t-detalle text-suave">{proposeBlocked(data)}</p>
          )}

          {data.versions.length ? (
            <details className="fold">
              <summary>
                <span className="t-cuerpo">Versiones ({data.versions.length})</span>
                <IconChevronDown size={22} />
              </summary>
              <div className="fold-body">
                <ul className="aj-steps" aria-label="Versiones de tu voz">
                  {data.versions.map((version) => (
                    <li key={version.number} className="t-detalle">
                      #{version.number} · <Badge tone={VERSION_STATE_TONE[version.state] ?? 'muted'}>{VERSION_STATE_LABEL[version.state] ?? version.state}</Badge> ·{' '}
                      {version.source} · {formatDateTime(version.decided_at ?? version.created_at)}
                    </li>
                  ))}
                </ul>
              </div>
            </details>
          ) : null}
        </Card>
      ) : null}

      {asking?.kind === 'confirmar' ? (
        <ConfirmModal
          title={`Confirmar la versión ${asking.number} de tu voz`}
          confirmLabel="Confirmar mi voz"
          busyLabel="Confirmando…"
          busy={decide.isPending}
          error={decide.error}
          onClose={close}
          onConfirm={() =>
            decide.mutate(
              { number: asking.number, decision: 'confirmar' },
              {
                onSuccess: () => {
                  close();
                  toast.show(`Voz ${asking.number} confirmada: desde ahora el equipo escribe con ella.`);
                },
              },
            )
          }
        >
          <p>
            Desde ahora el equipo escribe con esta voz y tus borradores dejan de marcarse «Voz provisional». Lo que necesita tu
            aprobación no cambia: eso lo decide el administrador.
          </p>
        </ConfirmModal>
      ) : null}
      {asking?.kind === 'descartar' ? (
        <ConfirmModal
          title={`Descartar la propuesta ${asking.number}`}
          confirmLabel="Descartar la propuesta"
          busyLabel="Descartando…"
          tone="danger"
          note="optional"
          noteLabel="Por qué no te representa"
          busy={decide.isPending}
          error={decide.error}
          onClose={close}
          onConfirm={(note) =>
            decide.mutate(
              { number: asking.number, decision: 'descartar', ...(note ? { note } : {}) },
              {
                onSuccess: () => {
                  close();
                  toast.show(`Propuesta ${asking.number} descartada. Sigue la voz que tenías.`);
                },
              },
            )
          }
        >
          <p>Sigue la voz que tienes. Tus señales se quedan y sirven para una propuesta nueva.</p>
        </ConfirmModal>
      ) : null}
      {asking?.kind === 'proponer' ? (
        <ConfirmModal
          title="Pedir una propuesta de tu voz"
          confirmLabel="Pedir propuesta"
          busyLabel="Preparando…"
          busy={propose.isPending}
          error={propose.error}
          onClose={close}
          onConfirm={() =>
            propose.mutate(undefined, {
              onSuccess: () => {
                close();
                toast.show('Propuesta lista: revísala y decide si te representa.');
              },
            })
          }
        >
          <p>{PROPOSE_COST}</p>
        </ConfirmModal>
      ) : null}
    </Section>
  );
}
