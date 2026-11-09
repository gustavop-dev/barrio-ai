// The capture sheet of Captura.dc.html: audio, photos, a note and «Para qué es», sent to the team in
// one multipart POST. Mounted once by the Layout through CaptureSheetHost.
import { AIEditControl } from '../components/ui/AIEditControl';
import type { AIEdit } from '../../../compartido/src/api/imagenes';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useId, useRef, useState, type ChangeEvent, type DragEvent } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
  CAPTURE_LIMITS,
  captureKeys,
  isAcceptedPhoto,
  undoCaptura,
  useCapturas,
  useCreateCaptura,
  usePreferencias,
  type CaptureOutput,
  type CapturePurpose,
} from '../api/capturas';
import { ApiError } from '../api/client';
import { asList, listPreguntas } from '../api/endpoints';
import { keys } from '../api/queryClient';
import { IconCerrar, IconGaleria, IconMicrofono, IconPausa, IconPlay } from '../components/icons';
import { Button, ChipStrip, ConfirmModal, ErrorRetry, FilterChip, Note, errorMessage, useToast } from '../components/ui';
import type { CaptureDraft, CaptureSeed, CaptureTarget } from './CaptureContext';
import { CaptureHistory } from './History';
import { IconCamara, IconCandado, IconDetener, IconPapelera } from './icons';
import { FileThumb, Wave, useAudioPlayback } from './parts';
import { Sheet } from './Sheet';
import { audioFilename, getMicState, mmss, Recorder, refreshMicState, useRecorder, useRecorderStatus, type MicProblem, type RecordedAudio } from './recorder';
import { closeCaptureSheet, openCaptureSheet, useCaptureSheet } from './store';
import './capture.css';

export const PURPOSES: readonly { value: CapturePurpose; label: string }[] = [
  { value: 'post', label: 'Idea para un post' },
  { value: 'propuesta', label: 'Propuesta de post' },
  { value: 'dato', label: 'Dato sobre mí' },
  { value: 'respuesta', label: 'Responde una pregunta' },
  { value: 'galeria', label: 'Foto para la galería' },
];

const CONTEXT_EYEBROW: Record<CaptureTarget['tipo'], string> = {
  pregunta: 'Responde a una pregunta',
  persona: 'Nota sobre',
  pieza: 'Comentario sobre la pieza',
};

const CONTEXT_FALLBACK: Record<CaptureTarget['tipo'], string> = {
  pregunta: 'Pregunta de Tu turno',
  persona: 'Esta persona',
  pieza: 'Esta pieza',
};

type AudioSlot = { kind: 'none' } | { kind: 'recording'; recorder: Recorder; locked: boolean } | { kind: 'done'; audio: RecordedAudio };

interface Foto {
  id: string;
  file: File;
}

let fotoSeq = 0;
const toFoto = (file: File): Foto => ({ id: `f${++fotoSeq}`, file });

function initialAudio(seed: CaptureSeed): AudioSlot {
  if (seed.recorder) return { kind: 'recording', recorder: seed.recorder, locked: true };
  const audio = seed.audio ?? seed.draft?.audio;
  return audio ? { kind: 'done', audio } : { kind: 'none' };
}

// ---------------------------------------------------------------- audio pieces

function MicNote({ problem, onAllow, onDismiss, onSettings }: { problem: MicProblem | 'explain'; onAllow: () => void; onDismiss: () => void; onSettings: () => void }) {
  if (problem === 'explain') {
    return (
      <Note
        tone="info"
        title="Para grabar, 0ff1ce necesita el micrófono"
        actions={
          <>
            <Button variant="primary" icon={<IconMicrofono size={20} />} onClick={onAllow}>
              Permitir el micrófono
            </Button>
            <Button variant="ghost" onClick={onDismiss}>
              Ahora no
            </Button>
          </>
        }
      >
        Solo se usa mientras mantienes el botón aguamarina o grabas desde esta hoja. El audio se sube cuando lo envías, no mientras grabas.
      </Note>
    );
  }
  if (problem === 'denied') {
    return (
      <Note
        tone="warn"
        title="El micrófono está bloqueado"
        actions={
          <Button variant="secondary" size="small" onClick={onSettings}>
            Ir a Ajustes › Captura y galería
          </Button>
        }
      >
        Puedes enviar fotos o una nota. Para grabar audio, permite el micrófono para 0ff1ce: en Ajustes te explicamos cómo.
      </Note>
    );
  }
  if (problem === 'unsupported') {
    return (
      <Note tone="info" title="Aquí no se puede grabar audio">
        Este navegador o dispositivo no permite grabar. Puedes enviar fotos o una nota.
      </Note>
    );
  }
  return (
    <Note
      tone="error"
      title="No se pudo usar el micrófono"
      actions={
        <Button variant="secondary" size="small" onClick={onAllow}>
          Volver a intentarlo
        </Button>
      }
    >
      Otra app puede estar usándolo. Puedes enviar fotos o una nota.
    </Note>
  );
}

function RecordingPanel({
  recorder,
  locked,
  onDiscard,
  onFinish,
  onRetry,
  onSettings,
}: {
  recorder: Recorder;
  locked: boolean;
  onDiscard: () => void;
  onFinish: (audio: RecordedAudio | null) => void;
  onRetry: () => void;
  onSettings: () => void;
}) {
  const snapshot = useRecorder(recorder);
  const [finishing, setFinishing] = useState(false);
  if (snapshot.state === 'error') {
    return <MicNote problem={recorder.problem?.problem ?? 'error'} onAllow={onRetry} onDismiss={onDiscard} onSettings={onSettings} />;
  }
  const paused = snapshot.state === 'paused';
  const status = snapshot.state === 'starting' ? 'Abriendo el micrófono…' : paused ? 'En pausa' : locked ? 'Grabando · bloqueado' : 'Grabando';
  return (
    <div className="cap-recording">
      <div className={paused || snapshot.state === 'starting' ? 'cap-ball' : 'cap-ball cap-pulse'} aria-hidden="true">
        <IconMicrofono size={44} />
      </div>
      <p className="cap-bigtime" aria-hidden="true">
        {mmss(snapshot.elapsed)}
      </p>
      <p className="cap-status">
        <IconCandado size={16} />
        <span>{status}</span>
        <span className="vh">, {mmss(snapshot.elapsed)}</span>
      </p>
      <Wave levels={snapshot.levels} />
      <div className="cap-rec-actions">
        <button type="button" className="cap-rec-btn discard" onClick={onDiscard}>
          <IconPapelera size={22} />
          Descartar
        </button>
        <button
          type="button"
          className="cap-rec-btn"
          disabled={!recorder.canPause || snapshot.state === 'starting'}
          onClick={() => (paused ? recorder.resume() : recorder.pause())}
        >
          {paused ? <IconPlay size={22} /> : <IconPausa size={22} />}
          {paused ? 'Seguir' : 'Pausar'}
        </button>
        <button
          type="button"
          className="cap-rec-btn finish"
          disabled={finishing}
          onClick={() => {
            setFinishing(true);
            void recorder.stop().then(onFinish);
          }}
        >
          <IconDetener size={22} />
          Terminar
        </button>
      </div>
    </div>
  );
}

function AudioDone({ audio, onRemove }: { audio: RecordedAudio; onRemove: () => void }) {
  const { playing, toggle } = useAudioPlayback(audio.blob);
  return (
    <div className="cap-audio-done">
      <button type="button" className="cap-play" aria-label={playing ? 'Pausar el audio' : 'Escuchar el audio'} aria-pressed={playing} onClick={toggle}>
        {playing ? <IconPausa size={20} /> : <IconPlay size={20} />}
      </button>
      <Wave levels={audio.levels} />
      <span className="cap-duration">{mmss(audio.duration)}</span>
      <button type="button" className="cap-remove" aria-label="Quitar el audio" onClick={onRemove}>
        <IconPapelera size={20} />
      </button>
    </div>
  );
}

// ---------------------------------------------------------------- the sheet

interface CaptureSheetProps {
  context: CaptureTarget | null;
  seed: CaptureSeed;
  onClose: () => void;
}

export function CaptureSheet({ context: initialContext, seed, onClose }: CaptureSheetProps) {
  const toast = useToast();
  const client = useQueryClient();
  const navigate = useNavigate();
  const create = useCreateCaptura();
  const prefs = usePreferencias();
  const [aiChoice, setAiChoice] = useState<AIEdit | null>(seed.draft?.ai_edit ?? null);
  const aiEdit = aiChoice ?? prefs.data?.gallery_ai_edit ?? null;
  const aiEditToSend = aiEdit ?? undefined;
  const [view, setView] = useState<'form' | 'history'>(seed.view ?? 'form');
  const history = useCapturas();
  const [context, setContext] = useState<CaptureTarget | null>(initialContext);
  const [audio, setAudio] = useState<AudioSlot>(() => initialAudio(seed));
  const [mic, setMic] = useState<MicProblem | 'explain' | null>(seed.mic ?? null);
  const [fotos, setFotos] = useState<Foto[]>(() => (seed.draft?.fotos ?? []).map(toFoto));
  const [fotoProblem, setFotoProblem] = useState<string | null>(null);
  const [nota, setNota] = useState(seed.draft?.nota ?? '');
  const [para, setPara] = useState<CapturePurpose | null>(seed.draft?.para ?? null);
  const [publicChoice, setPublicChoice] = useState<boolean | null>(seed.draft?.publicUse ?? null);
  const [confirmClose, setConfirmClose] = useState(false);
  const [sending, setSending] = useState(false);
  const [dragging, setDragging] = useState(false);
  const noteId = useId();
  const visibilityName = useId();
  const recorderRef = useRef<Recorder | null>(null);

  // The question behind a «Responder con audio»: who asks and which visibility it suggests.
  // Same key and shape as usePreguntas('open'), but only fetched for a question.
  const questions = useQuery({
    queryKey: keys.preguntas('open'),
    queryFn: async () => asList(await listPreguntas('open')),
    enabled: context?.tipo === 'pregunta',
  });
  const question = context?.tipo === 'pregunta' ? questions.data?.find((q) => q.id === context.id) : undefined;
  const suggestedPublic = typeof question?.suggested_public === 'boolean' ? question.suggested_public : null;
  const publicUse = publicChoice ?? suggestedPublic;

  // A live recording must never outlive the sheet: closing it, sending or navigating stops the microphone.
  useEffect(() => {
    recorderRef.current = audio.kind === 'recording' ? audio.recorder : null;
  }, [audio]);
  const mounted = useRef(false);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      const recorder = recorderRef.current;
      // Deferred: StrictMode unmounts and remounts once in development, and a locked recording must survive that.
      setTimeout(() => {
        if (!mounted.current) void recorder?.discard();
      }, 0);
    };
  }, []);

  // The sheet re-renders when the recording starts, fails, pauses or stops by itself.
  useRecorderStatus(audio.kind === 'recording' ? audio.recorder : null);
  const recording = audio.kind === 'recording' && audio.recorder.active;
  const autoStopped = audio.kind === 'recording' ? audio.recorder.autoStopped : null;
  const readyAudio = audio.kind === 'done' ? audio.audio : autoStopped;
  const noteTooLong = nota.length > CAPTURE_LIMITS.noteChars;
  const galleryWithoutPhotos = para === 'galeria' && fotos.length === 0;
  const empty = !recording && !readyAudio && fotos.length === 0 && !nota.trim();
  const audioTooBig = Boolean(readyAudio && readyAudio.blob.size > CAPTURE_LIMITS.audioBytes);
  const cannotSend = empty || noteTooLong || galleryWithoutPhotos || audioTooBig;
  const hasContent = !empty;

  const close = () => {
    // While the send is on its way the sheet stays: closed, its result (the toast or the error) would be lost (CAP-14).
    if (sending) return;
    if (view === 'form' && hasContent) {
      setConfirmClose(true);
      return;
    }
    void recorderRef.current?.discard();
    onClose();
  };

  const goTo = (to: string) => {
    void recorderRef.current?.discard();
    onClose();
    navigate(to);
  };

  const startRecording = async () => {
    let state = getMicState();
    if (state === 'unknown') state = await refreshMicState();
    if (state === 'unsupported') return setMic('unsupported');
    if (state === 'denied') return setMic('denied');
    if (state !== 'granted' && mic !== 'explain') return setMic('explain');
    setMic(null);
    setAudio({ kind: 'recording', recorder: Recorder.start(), locked: false });
  };

  const allowMic = () => {
    setMic(null);
    setAudio({ kind: 'recording', recorder: Recorder.start(), locked: false });
  };

  const discardRecording = () => {
    if (audio.kind === 'recording') void audio.recorder.discard();
    setAudio({ kind: 'none' });
  };

  const addFiles = (files: File[]) => {
    if (!files.length) return;
    const accepted: File[] = [];
    const rejected: string[] = [];
    for (const file of files) {
      if (!isAcceptedPhoto(file) || file.size > CAPTURE_LIMITS.photoBytes) rejected.push(file.name || 'una foto');
      else accepted.push(file);
    }
    const room = CAPTURE_LIMITS.photosPerCapture - fotos.length;
    const kept = accepted.slice(0, Math.max(0, room));
    const problems: string[] = [];
    if (rejected.length) problems.push(`No se añadió ${rejected.join(', ')}: solo JPEG, PNG, WebP o HEIC de hasta 10 MB.`);
    if (accepted.length > kept.length) problems.push(`Puedes adjuntar hasta ${CAPTURE_LIMITS.photosPerCapture} fotos por envío.`);
    setFotoProblem(problems.length ? problems.join(' ') : null);
    if (kept.length) setFotos((current) => [...current, ...kept.map(toFoto)]);
  };

  const onPick = (event: ChangeEvent<HTMLInputElement>) => {
    addFiles(Array.from(event.target.files ?? []));
    event.target.value = '';
  };

  const onDrop = (event: DragEvent) => {
    event.preventDefault();
    setDragging(false);
    addFiles(Array.from(event.dataTransfer?.files ?? []).filter((file) => file.type.startsWith('image/') || isAcceptedPhoto(file)));
  };

  const undo = async (capture: CaptureOutput, draft: CaptureDraft, sentContext: CaptureTarget | null) => {
    const until = capture.undo_until ? Date.parse(capture.undo_until) : NaN;
    if (Number.isFinite(until) && until <= Date.now()) {
      toast.show('Ya no se puede deshacer: pasaron los 2 minutos.', { tone: 'error' });
      return;
    }
    try {
      await undoCaptura(capture.id);
      toast.show('Envío deshecho. Lo tienes otra vez en la hoja.');
      openCaptureSheet(sentContext ?? undefined, { draft });
    } catch (error) {
      toast.show(errorMessage(error), { tone: 'error' });
    } finally {
      void client.invalidateQueries({ queryKey: captureKeys.all });
      void client.invalidateQueries({ queryKey: captureKeys.galeriaAll });
      void client.invalidateQueries({ queryKey: keys.tuTurno });
    }
  };

  const send = async () => {
    if (cannotSend || sending) return;
    setSending(true);
    let finalAudio = readyAudio;
    if (audio.kind === 'recording' && audio.recorder.active) finalAudio = await audio.recorder.stop();
    if (finalAudio) setAudio({ kind: 'done', audio: finalAudio });
    const draft: CaptureDraft = { audio: finalAudio, fotos: fotos.map((f) => f.file), nota, para, publicUse: publicChoice, ai_edit: aiEditToSend };
    const sentContext = context;
    create.mutate(
      {
        audio: finalAudio ? { blob: finalAudio.blob, filename: audioFilename(finalAudio.mime), durationS: finalAudio.duration } : null,
        fotos: draft.fotos,
        nota,
        ai_edit: fotos.length ? aiEditToSend : undefined,
        para,
        contexto: context ? { tipo: context.tipo, id: context.id } : null,
        publicUse: context?.tipo === 'pregunta' ? publicChoice : null,
      },
      {
        onSuccess: (capture) => {
          onClose();
          toast.show('Enviado al equipo.', { undo: () => void undo(capture, draft, sentContext) });
        },
        onSettled: () => setSending(false),
      },
    );
  };

  const count = history.count;

  return (
    <>
      <Sheet label="Captura para el equipo" onClose={close} suspended={confirmClose} className="cap-sheet">
      <div className="cap-sheet-head">
        <span className="cap-handle" aria-hidden="true" />
        <div className="cap-headrow">
          <h2 className="t-subtitulo">Para el equipo</h2>
          <button type="button" className="cap-histlink" onClick={() => setView('history')}>
            Lo que enviaste{count !== null ? ` · ${count}` : ''}
          </button>
          <button type="button" className="cap-close" aria-label="Cerrar sin enviar" onClick={close}>
            <IconCerrar size={22} />
          </button>
        </div>
      </div>

      {view === 'history' ? (
        <CaptureHistory onBack={() => setView('form')} onNavigate={() => onClose()} />
      ) : (
        <form
          className="cap-form"
          onSubmit={(event) => {
            event.preventDefault();
            void send();
          }}
          noValidate
        >
          {context ? (
            <div className="cap-context">
              <span className="cap-context-text">
                <span className="cap-context-eyebrow">
                  {context.tipo === 'pregunta' && question?.agent_label ? `Responde a ${question.agent_label}` : CONTEXT_EYEBROW[context.tipo]}
                </span>
                <span className="t-detalle">{context.label || question?.question || CONTEXT_FALLBACK[context.tipo]}</span>
              </span>
              <button type="button" className="cap-context-remove" aria-label="Quitar el contexto" onClick={() => setContext(null)}>
                <IconCerrar size={20} />
              </button>
            </div>
          ) : null}

          {audio.kind === 'recording' && !autoStopped ? (
            <RecordingPanel
              recorder={audio.recorder}
              locked={audio.locked}
              onDiscard={discardRecording}
              onFinish={(result) => setAudio(result ? { kind: 'done', audio: result } : { kind: 'none' })}
              onRetry={allowMic}
              onSettings={() => goTo('/ajustes#captura')}
            />
          ) : readyAudio ? (
            <AudioDone audio={readyAudio} onRemove={() => setAudio({ kind: 'none' })} />
          ) : mic ? (
            <MicNote problem={mic} onAllow={allowMic} onDismiss={() => setMic(null)} onSettings={() => goTo('/ajustes#captura')} />
          ) : (
            <button type="button" className="cap-record" onClick={() => void startRecording()}>
              <span className="cap-record-icon" aria-hidden="true">
                <IconMicrofono size={20} />
              </span>
              Grabar un audio
            </button>
          )}
          {audioTooBig ? <p className="field-error">El audio pasa de 25 MB: grábalo más corto.</p> : null}

          <div
            className={dragging ? 'cap-photos dragging' : 'cap-photos'}
            onDragOver={(event) => {
              event.preventDefault();
              setDragging(true);
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={onDrop}
          >
            <p className="section-label">Añadir una imagen</p>
            <div className="cap-photo-buttons">
              <label className="cap-photo-pick">
                <IconCamara size={22} />
                Tomar foto
                <input type="file" accept="image/*" capture="environment" onChange={onPick} className="cap-file" />
              </label>
              <label className="cap-photo-pick">
                <IconGaleria size={22} />
                Galería
                <input type="file" accept="image/*" multiple onChange={onPick} className="cap-file" />
              </label>
            </div>
            {fotos.length ? (
              <ul className="cap-thumbs" aria-label="Fotos adjuntas">
                {fotos.map((foto, index) => (
                  <li key={foto.id} className="cap-thumb">
                    <FileThumb file={foto.file} alt={`Foto adjunta ${index + 1}`} />
                    <button type="button" aria-label={`Quitar la foto ${index + 1}`} onClick={() => setFotos((current) => current.filter((f) => f.id !== foto.id))}>
                      <IconCerrar size={16} />
                    </button>
                  </li>
                ))}
              </ul>
            ) : null}
            {fotoProblem ? <p className="field-error">{fotoProblem}</p> : null}
          </div>

          {fotos.length ? <div>
            <AIEditControl testID="capture-ai" value={aiEdit} onChange={setAiChoice} disabled={sending} />
            {aiEdit === null ? <p className="t-detalle text-suave">{prefs.isPending ? 'Cargando el valor de Ajustes…' : 'Se usará el valor de Ajustes si no eliges una opción.'}</p> : null}
          </div> : null}

          <div className="cap-note">
            <label htmlFor={noteId} className="section-label">
              Nota para el equipo (opcional)
            </label>
            <textarea
              id={noteId}
              rows={3}
              value={nota}
              maxLength={CAPTURE_LIMITS.noteChars + 200}
              aria-invalid={noteTooLong || undefined}
              onChange={(event) => setNota(event.target.value)}
              onInput={(event) => {
                const node = event.currentTarget;
                node.style.height = 'auto';
                node.style.height = `${Math.min(node.scrollHeight, 280)}px`;
              }}
            />
            {noteTooLong ? (
              <p className="field-error">
                La nota tiene {nota.length} caracteres; el máximo es {CAPTURE_LIMITS.noteChars}.
              </p>
            ) : null}
          </div>

          {context?.tipo === 'pregunta' ? (
            <fieldset className="cap-visibility">
              <legend className="section-label">Visibilidad de tu respuesta</legend>
              {[
                { value: true, label: 'Público', hint: 'El equipo puede mencionarlo en posts y comentarios.' },
                { value: false, label: 'Privado', hint: 'Solo orienta decisiones; nunca aparece en un texto público.' },
              ].map((option) => (
                <label key={option.label} className="cap-radio">
                  <input type="radio" name={visibilityName} checked={publicUse === option.value} onChange={() => setPublicChoice(option.value)} />
                  <span>
                    <span>{option.label}</span>
                    <span className="t-detalle text-suave">{option.hint}</span>
                  </span>
                </label>
              ))}
              {suggestedPublic === null && publicChoice === null ? (
                <p className="t-detalle text-suave">Si no eliges, se usa la que sugiere la pregunta.</p>
              ) : null}
            </fieldset>
          ) : null}

          <div className="cap-purpose">
            <p className="section-label" id={`${noteId}-para`}>
              Para qué es (opcional)
            </p>
            <ChipStrip label="Para qué es" scroll={false}>
              {PURPOSES.map((option) => (
                <FilterChip key={option.value} pressed={para === option.value} onClick={() => setPara(para === option.value ? null : option.value)}>
                  {option.label}
                </FilterChip>
              ))}
            </ChipStrip>
            <p className="t-detalle text-suave">Si no eliges, el equipo lo transcribe y decide.</p>
            {galleryWithoutPhotos ? <p className="field-error">Para «Foto para la galería» adjunta al menos una foto.</p> : null}
          </div>

          {create.error instanceof ApiError && create.error.status === 413 ? (
            <Note tone="error" title="El envío es demasiado grande">
              El audio puede pesar hasta 25 MB y cada foto hasta 10 MB. Quita alguna foto o graba un audio más corto.
            </Note>
          ) : (
            <ErrorRetry error={create.error} />
          )}
          <Button type="submit" variant="primary" block disabled={cannotSend} loading={sending} loadingLabel="Enviando…" className="cap-send">
            Guardar y enviar al equipo
          </Button>
          <p className="t-detalle text-suave cap-foot">Lo verás en «Lo que enviaste», arriba en esta hoja.</p>
        </form>
      )}
      </Sheet>

      {confirmClose ? (
        <ConfirmModal
          title="¿Cerrar sin enviar?"
          confirmLabel="Cerrar sin enviar"
          cancelLabel="Seguir aquí"
          tone="danger"
          onClose={() => setConfirmClose(false)}
          onConfirm={() => {
            setConfirmClose(false);
            void recorderRef.current?.discard();
            onClose();
          }}
        >
          Se pierden el audio, las fotos y la nota de esta captura.
        </ConfirmModal>
      ) : null}
    </>
  );
}

/**
 * Renders the sheet whenever the store says so, and opens «Lo que enviaste» when the URL carries
 * `?enviado=1` (the link of a capture_processed notification), removing it from the URL.
 */
export function CaptureSheetHost() {
  const sheet = useCaptureSheet();
  const [params, setParams] = useSearchParams();
  const wantsHistory = params.get('enviado') === '1';

  useEffect(() => {
    if (!wantsHistory) return;
    openCaptureSheet(undefined, { view: 'history' });
    setParams(
      (current) => {
        const next = new URLSearchParams(current);
        next.delete('enviado');
        return next;
      },
      { replace: true },
    );
  }, [wantsHistory, setParams]);

  if (!sheet.open) return null;
  return <CaptureSheet key={sheet.nonce} context={sheet.context} seed={sheet.seed} onClose={closeCaptureSheet} />;
}
