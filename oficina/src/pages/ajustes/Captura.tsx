// Ajustes › Captura y galería (rev 18): the microphone permission, with a request button, and the
// default «Edición con IA» (PATCH /api/v1/ajustes/preferencias).
import { AIEditControl } from '../../components/ui/AIEditControl';
import type { AIEdit } from '../../../../compartido/src/api/imagenes';
import { useState } from 'react';
import { usePreferencias, useSavePreferencias } from '../../api/capturas';
import { MicError, requestMic, useMicState, type MicState } from '../../capture/recorder';
import { Badge, Button, Card, ErrorRetry, Note, Section, errorMessage, useToast, type Tone } from '../../components/ui';
import { isUnavailable } from './shared';

const MIC: Record<MicState, { label: string; tone: Tone }> = {
  granted: { label: 'Permitido', tone: 'ok' },
  denied: { label: 'Bloqueado', tone: 'bad' },
  prompt: { label: 'Sin pedir', tone: 'muted' },
  unknown: { label: 'Comprobando…', tone: 'muted' },
  unsupported: { label: 'No disponible', tone: 'muted' },
};

function Microphone() {
  const mic = useMicState();
  const [asking, setAsking] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const badge = MIC[mic];

  const ask = async () => {
    setAsking(true);
    setProblem(null);
    try {
      await requestMic();
    } catch (error) {
      setProblem(error instanceof MicError ? error.message : errorMessage(error));
    } finally {
      setAsking(false);
    }
  };

  return (
    <>
      <div className="aj-cardhead">
        <p className="t-cuerpo">Micrófono</p>
        <Badge tone={badge.tone}>{badge.label}</Badge>
      </div>
      <p className="t-detalle text-suave">Se usa solo mientras mantienes el botón aguamarina o grabas desde la hoja de captura.</p>
      {mic === 'prompt' || mic === 'unknown' ? (
        <Button variant="secondary" block loading={asking} loadingLabel="Esperando al navegador…" onClick={() => void ask()}>
          Permitir el micrófono
        </Button>
      ) : null}
      {mic === 'denied' ? (
        <Note tone="warn" title="Para volver a permitirlo" role={null}>
          Cámbialo en los ajustes del navegador: en el ordenador, el candado junto a la dirección › Micrófono › Permitir; en iPhone, Ajustes › Apps › Safari ›
          Micrófono, o los ajustes de 0ff1ce si la tienes instalada.
        </Note>
      ) : null}
      {mic === 'unsupported' ? <p className="t-detalle text-suave">Este navegador no permite grabar audio. Puedes seguir enviando fotos y notas.</p> : null}
      {problem && mic !== 'denied' ? <p className="field-error">{problem}</p> : null}
    </>
  );
}

function AiEditDefault() {
  const prefs = usePreferencias();
  const save = useSavePreferencias();
  const toast = useToast();
  const [pending, setPending] = useState<AIEdit | null>(null);
  const unavailable = isUnavailable(prefs.error);
  const value = pending ?? prefs.data?.gallery_ai_edit ?? 'auto';

  const change = (next: AIEdit) => {
    if (next === value) return;
    setPending(next);
    save.mutate(
      { gallery_ai_edit: next },
      {
        onSuccess: () => toast.show('Edición con IA guardada para las fotos nuevas.'),
        onError: (error) => toast.show(errorMessage(error), { tone: 'error' }),
        onSettled: () => setPending(null),
      },
    );
  };

  return (
    <>
      <div className="aj-divider" />
      <AIEditControl testID="default-ai" value={value} disabled={!prefs.isSuccess || save.isPending} onChange={change} />
      <p className="t-detalle text-suave">
        {unavailable ? 'Aún no disponible: el servidor todavía no guarda esta preferencia.' : 'Es el valor por defecto de cada foto nueva; puedes cambiarlo foto por foto en la Galería.'}
      </p>
      {!unavailable ? <ErrorRetry error={prefs.error} onRetry={() => void prefs.refetch()} /> : null}
    </>
  );
}

export function CapturaSection() {
  return (
    <Section label="Captura y galería" id="captura">
      <Card className="aj-card aj-card-tight">
        <Microphone />
        <AiEditDefault />
      </Card>
    </Section>
  );
}
