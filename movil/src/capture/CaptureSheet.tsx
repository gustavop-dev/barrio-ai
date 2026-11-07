// The capture sheet of Captura.dc.html: audio, photos, a note and «Para qué es», sent to the team in
// one multipart POST /api/v1/capturas, with a 5 s «Deshacer». Mounted once by the app layout.
import {
  CAPTURE_LIMITS,
  captureKeys,
  undoCaptura,
  useCapturas,
  useCreateCaptura,
  type CaptureOutput,
  type CapturePurpose,
} from '@compartido/api/capturas';
import { ApiError } from '@compartido/api/client';
import { asList, listPreguntas } from '@compartido/api/endpoints';
import { audioFilename, mmss } from '@compartido/logic/audio';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useAudioPlayer, useAudioPlayerStatus } from 'expo-audio';
import { useEffect, useRef, useState } from 'react';
import { Image, Linking, Pressable, StyleSheet, View } from 'react-native';
import { keys } from '@/api/queryClient';
import { Icon } from '@/components/icons';
import { Button, ConfirmSheet, ErrorRetry, FilterChip, Note, Options, Sheet, T, errorMessage, useToast } from '@/components/ui';
import { Field } from '@/components/ui/Field';
import { haptic } from '@/theme/motion';
import { colors, radius, shell, space } from '@/theme/tokens';
import { CaptureHistory } from './History';
import { checkPhotos, pickFromGallery, takePhoto } from './photos';
import { Pulse } from './Pulse';
import { useRecorder, useRecorderLive } from './recorder';
import { closeCaptureSheet, openCaptureSheet, useCaptureSheet } from './store';
import type { CaptureDraft, CaptureSeed, CaptureTarget, MicNoteKind, PickedPhoto, RecordedAudio } from './types';
import { Wave } from './Wave';

export const PURPOSES: readonly { value: CapturePurpose; label: string }[] = [
  { value: 'post', label: 'Idea para un post' },
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

type AudioSlot = { kind: 'none' } | { kind: 'recording'; locked: boolean } | { kind: 'done'; audio: RecordedAudio };

function initialAudio(seed: CaptureSeed): AudioSlot {
  if (seed.recording) return { kind: 'recording', locked: true };
  const audio = seed.audio ?? seed.draft?.audio;
  return audio ? { kind: 'done', audio } : { kind: 'none' };
}

// ---------------------------------------------------------------- audio pieces

function MicNote({ problem, onAllow, onDismiss }: { problem: MicNoteKind; onAllow: () => void; onDismiss: () => void }) {
  if (problem === 'explain') {
    return (
      <Note
        tone="info"
        title="Para grabar, 0ff1ce necesita el micrófono"
        actions={
          <>
            <Button variant="primary" icon={<Icon name="microfono" size={20} color={colors.onBrand} />} onPress={onAllow}>
              Permitir el micrófono
            </Button>
            <Button variant="ghost" onPress={onDismiss}>
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
          <Button size="small" onPress={() => void Linking.openSettings()}>
            Abrir los ajustes del teléfono
          </Button>
        }
      >
        Puedes enviar fotos o una nota. Para grabar audio, permite el micrófono para 0ff1ce en los ajustes del teléfono.
      </Note>
    );
  }
  return (
    <Note
      tone="error"
      title="No se pudo usar el micrófono"
      actions={
        <Button size="small" onPress={onAllow}>
          Volver a intentarlo
        </Button>
      }
    >
      Otra app puede estar usándolo. Puedes enviar fotos o una nota.
    </Note>
  );
}

function RecordingPanel({ locked, onDiscard, onFinish }: { locked: boolean; onDiscard: () => void; onFinish: (audio: RecordedAudio | null) => void }) {
  const recorder = useRecorder();
  const live = useRecorderLive();
  const [finishing, setFinishing] = useState(false);
  const paused = recorder.phase === 'paused';
  const starting = recorder.phase === 'starting';
  const status = starting ? 'Abriendo el micrófono…' : paused ? 'En pausa' : locked ? 'Grabando · bloqueado' : 'Grabando';
  return (
    <View style={styles.recording} testID="capture-recording">
      <Pulse kind="recordPulse" active={!paused && !starting} style={styles.ball}>
        <Icon name="microfono" size={44} color={colors.onBrand} />
      </Pulse>
      <T variant="titulo" style={styles.tabular} accessibilityElementsHidden>
        {mmss(live.elapsed)}
      </T>
      <View style={styles.status} accessibilityLiveRegion="polite">
        <Icon name="candado" size={16} color={colors.inkSoft} />
        <T variant="detalle" soft>
          {status}
        </T>
      </View>
      <View style={styles.waveRow}>
        <Wave levels={live.levels} />
      </View>
      <View style={styles.recActions}>
        <Pressable accessibilityRole="button" onPress={onDiscard} style={[styles.recButton, styles.recDiscard]}>
          <Icon name="papelera" size={22} color={colors.alert} />
          <T variant="detalle" color={colors.alert}>
            Descartar
          </T>
        </Pressable>
        <Pressable
          accessibilityRole="button"
          disabled={starting}
          onPress={() => (paused ? recorder.resume() : recorder.pause())}
          style={[styles.recButton, starting ? styles.recDisabled : null]}
        >
          <Icon name={paused ? 'play' : 'pausa'} size={22} />
          <T variant="detalle">{paused ? 'Seguir' : 'Pausar'}</T>
        </Pressable>
        <Pressable
          accessibilityRole="button"
          disabled={finishing}
          onPress={() => {
            setFinishing(true);
            void recorder.stop().then(onFinish);
          }}
          style={[styles.recButton, styles.recFinish]}
        >
          <Icon name="detener" size={22} color={colors.onBrand} />
          <T variant="detalle" color={colors.onBrand}>
            Terminar
          </T>
        </Pressable>
      </View>
    </View>
  );
}

function AudioDone({ audio, onRemove }: { audio: RecordedAudio; onRemove: () => void }) {
  const player = useAudioPlayer(audio.uri);
  const status = useAudioPlayerStatus(player);
  const playing = status.playing;
  useEffect(() => {
    if (status.didJustFinish) player.seekTo(0).catch(() => undefined);
  }, [status.didJustFinish, player]);
  return (
    <View style={styles.audioDone} testID="capture-audio">
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={playing ? 'Pausar el audio' : 'Escuchar el audio'}
        accessibilityState={{ selected: playing }}
        onPress={() => (playing ? player.pause() : player.play())}
        style={styles.play}
      >
        <Icon name={playing ? 'pausa' : 'play'} size={20} color={colors.onBrand} />
      </Pressable>
      <Wave levels={audio.levels} />
      <T variant="detalle" style={styles.tabular}>
        {mmss(audio.duration)}
      </T>
      <Pressable accessibilityRole="button" accessibilityLabel="Quitar el audio" onPress={onRemove} style={styles.iconButton}>
        <Icon name="papelera" size={20} color={colors.inkSoft} />
      </Pressable>
    </View>
  );
}

// ---------------------------------------------------------------- the sheet

export function CaptureSheet({ context: initialContext, seed, onClose }: { context: CaptureTarget | null; seed: CaptureSeed; onClose: () => void }) {
  const toast = useToast();
  const client = useQueryClient();
  const recorder = useRecorder();
  const create = useCreateCaptura();
  const history = useCapturas();
  const [view, setView] = useState<'form' | 'history'>(seed.view ?? 'form');
  const [context, setContext] = useState<CaptureTarget | null>(initialContext);
  const [audio, setAudio] = useState<AudioSlot>(() => initialAudio(seed));
  const [mic, setMic] = useState<MicNoteKind | null>(seed.mic ?? null);
  const [fotos, setFotos] = useState<PickedPhoto[]>(() => seed.draft?.fotos ?? []);
  const [fotoProblem, setFotoProblem] = useState<string | null>(null);
  const [nota, setNota] = useState(seed.draft?.nota ?? '');
  const [para, setPara] = useState<CapturePurpose | null>(seed.draft?.para ?? null);
  const [publicChoice, setPublicChoice] = useState<boolean | null>(seed.draft?.publicUse ?? null);
  const [confirmClose, setConfirmClose] = useState(false);
  const [sending, setSending] = useState(false);
  const sent = useRef(false);

  // The question behind «Responder con audio»: who asks and which visibility it suggests.
  const questions = useQuery({
    queryKey: keys.preguntas('open'),
    queryFn: async () => asList(await listPreguntas('open')),
    enabled: context?.tipo === 'pregunta',
  });
  const question = context?.tipo === 'pregunta' ? questions.data?.find((q) => q.id === context.id) : undefined;
  const suggestedPublic = typeof question?.suggested_public === 'boolean' ? question.suggested_public : null;
  const publicUse = publicChoice ?? suggestedPublic;

  // A live recording never outlives the sheet: closing it, sending or leaving stops the microphone.
  const discardOnLeave = recorder.discard;
  useEffect(
    () => () => {
      if (!sent.current) void discardOnLeave();
    },
    [discardOnLeave],
  );

  // A recording that stopped by itself at 30 minutes is the audio.
  const autoStopped = audio.kind === 'recording' ? recorder.autoStopped : null;
  // A locked recording whose microphone never opened (another app holds it, for example).
  const recordingFailed = audio.kind === 'recording' && recorder.phase === 'idle' && recorder.failed;
  const recording = audio.kind === 'recording' && recorder.phase !== 'idle';
  const readyAudio = audio.kind === 'done' ? audio.audio : autoStopped;
  const noteTooLong = nota.length > CAPTURE_LIMITS.noteChars;
  const galleryWithoutPhotos = para === 'galeria' && fotos.length === 0;
  const empty = !recording && !readyAudio && fotos.length === 0 && !nota.trim();
  const cannotSend = empty || noteTooLong || galleryWithoutPhotos;

  /** Closing with something unsent asks first («¿Cerrar sin enviar?»). */
  const canClose = () => {
    if (view === 'form' && !empty && !sending) {
      setConfirmClose(true);
      return false;
    }
    return true;
  };
  const closeNow = () => {
    void recorder.discard();
    onClose();
  };
  const close = () => {
    if (canClose()) closeNow();
  };

  const startRecording = async () => {
    const state = await recorder.micState();
    if (state === 'denied') return setMic('denied');
    if (state !== 'granted') return setMic('explain');
    setMic(null);
    setAudio({ kind: 'recording', locked: false });
    haptic('captureStart');
    if (!(await recorder.start())) {
      setAudio({ kind: 'none' });
      setMic('error');
    }
  };

  const allowMic = async () => {
    const state = await recorder.requestMic();
    if (state === 'denied') return setMic('denied');
    if (state !== 'granted') return setMic('explain');
    setMic(null);
    setAudio({ kind: 'recording', locked: false });
    if (!(await recorder.start())) {
      setAudio({ kind: 'none' });
      setMic('error');
    }
  };

  const addPhotos = async (source: 'camera' | 'gallery') => {
    try {
      const outcome = source === 'camera' ? await takePhoto() : await pickFromGallery(CAPTURE_LIMITS.photosPerCapture - fotos.length);
      if ('denied' in outcome) {
        setFotoProblem('La cámara está bloqueada para 0ff1ce: permítela en los ajustes del teléfono, o elige una foto de la galería.');
        return;
      }
      if ('canceled' in outcome) return;
      const { kept, problem } = checkPhotos(outcome.photos, fotos.length);
      setFotoProblem(problem);
      if (kept.length) setFotos((current) => [...current, ...kept]);
    } catch (error) {
      setFotoProblem(errorMessage(error));
    }
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
    if (audio.kind === 'recording' && recorder.phase !== 'idle') finalAudio = await recorder.stop();
    if (finalAudio) setAudio({ kind: 'done', audio: finalAudio });
    const draft: CaptureDraft = { audio: finalAudio, fotos, nota, para, publicUse: publicChoice };
    const sentContext = context;
    create.mutate(
      {
        audio: finalAudio
          ? { blob: { uri: finalAudio.uri, name: audioFilename(finalAudio.mime), type: finalAudio.mime }, filename: audioFilename(finalAudio.mime), durationS: finalAudio.duration }
          : null,
        fotos: fotos.map(({ uri, name, type }) => ({ uri, name, type })),
        nota,
        para,
        contexto: context ? { tipo: context.tipo, id: context.id } : null,
        publicUse: context?.tipo === 'pregunta' ? publicChoice : null,
      },
      {
        onSuccess: (capture) => {
          sent.current = true;
          haptic('captureSent');
          onClose();
          toast.show('Enviado al equipo.', { undo: () => void undo(capture, draft, sentContext) });
        },
        onError: () => haptic('actionError'),
        onSettled: () => setSending(false),
      },
    );
  };

  const header = (
    <View style={styles.headRow}>
      <T variant="subtitulo" accessibilityRole="header" style={styles.headTitle}>
        Para el equipo
      </T>
      <Pressable accessibilityRole="button" onPress={() => setView('history')} style={styles.histLink}>
        <T variant="detalle" color={colors.brandDeep}>
          Lo que enviaste{history.count !== null ? ` · ${history.count}` : ''}
        </T>
      </Pressable>
      <Pressable accessibilityRole="button" accessibilityLabel="Cerrar sin guardar" onPress={close} style={styles.iconButton}>
        <Icon name="cerrar" size={22} color={colors.inkSoft} />
      </Pressable>
    </View>
  );

  return (
    <>
      <Sheet label="Captura para el equipo" onClose={closeNow} canClose={canClose} suspended={confirmClose} header={header} testID="capture-sheet">
        {view === 'history' ? (
          <CaptureHistory onBack={() => setView('form')} onNavigate={onClose} />
        ) : (
          <>
            {context ? (
              <View style={styles.context} testID="capture-context">
                <View style={styles.contextText}>
                  <T variant="etiqueta" color={colors.brandDeep}>
                    {context.tipo === 'pregunta' && question?.agent_label ? `Responde a ${question.agent_label}` : CONTEXT_EYEBROW[context.tipo]}
                  </T>
                  <T variant="detalle">{context.label || question?.question || CONTEXT_FALLBACK[context.tipo]}</T>
                </View>
                <Pressable accessibilityRole="button" accessibilityLabel="Quitar el contexto" onPress={() => setContext(null)} style={styles.iconButton}>
                  <Icon name="cerrar" size={20} color={colors.brandDeep} />
                </Pressable>
              </View>
            ) : null}

            {audio.kind === 'recording' && !autoStopped && !recordingFailed ? (
              <RecordingPanel
                locked={audio.locked}
                onDiscard={() => {
                  void recorder.discard();
                  setAudio({ kind: 'none' });
                }}
                onFinish={(result) => setAudio(result ? { kind: 'done', audio: result } : { kind: 'none' })}
              />
            ) : readyAudio ? (
              <AudioDone
                audio={readyAudio}
                onRemove={() => {
                  recorder.clearAutoStopped();
                  setAudio({ kind: 'none' });
                }}
              />
            ) : mic || recordingFailed ? (
              <MicNote
                problem={mic ?? 'error'}
                onAllow={() => void allowMic()}
                onDismiss={() => {
                  setMic(null);
                  setAudio({ kind: 'none' });
                }}
              />
            ) : (
              <Pressable accessibilityRole="button" onPress={() => void startRecording()} style={styles.record}>
                <View style={styles.recordIcon}>
                  <Icon name="microfono" size={20} color={colors.onBrand} />
                </View>
                <T>Grabar un audio</T>
              </Pressable>
            )}

            <View style={styles.block}>
              <T variant="etiqueta" soft>
                Añadir una imagen
              </T>
              <View style={styles.photoButtons}>
                <Pressable accessibilityRole="button" onPress={() => void addPhotos('camera')} style={styles.photoPick}>
                  <Icon name="camara" size={22} />
                  <T>Tomar foto</T>
                </Pressable>
                <Pressable accessibilityRole="button" onPress={() => void addPhotos('gallery')} style={styles.photoPick}>
                  <Icon name="galeria" size={22} />
                  <T>Galería</T>
                </Pressable>
              </View>
              {fotos.length ? (
                <View style={styles.thumbs} accessibilityLabel="Fotos adjuntas">
                  {fotos.map((foto, index) => (
                    <View key={foto.id} style={styles.thumb}>
                      <Image source={{ uri: foto.uri }} style={styles.thumbImage} accessibilityLabel={`Foto adjunta ${index + 1}`} />
                      <Pressable
                        accessibilityRole="button"
                        accessibilityLabel={`Quitar la foto ${index + 1}`}
                        onPress={() => setFotos((current) => current.filter((f) => f.id !== foto.id))}
                        style={styles.thumbRemove}
                      >
                        <Icon name="cerrar" size={16} color={colors.paper} />
                      </Pressable>
                    </View>
                  ))}
                </View>
              ) : null}
              {fotoProblem ? (
                <T variant="detalle" color={colors.alert}>
                  {fotoProblem}
                </T>
              ) : null}
            </View>

            <Field
              label="Nota para el equipo (opcional)"
              value={nota}
              onChangeText={setNota}
              multiline
              maxLength={CAPTURE_LIMITS.noteChars + 200}
              error={noteTooLong ? `La nota tiene ${nota.length} caracteres; el máximo es ${CAPTURE_LIMITS.noteChars}.` : null}
              testID="capture-note"
            />

            {context?.tipo === 'pregunta' ? (
              <View style={styles.block}>
                <Options
                  legend="Visibilidad de tu respuesta"
                  value={publicUse}
                  onChange={setPublicChoice}
                  options={[
                    { value: true, label: 'Público', hint: 'El equipo puede mencionarlo en posts y comentarios.' },
                    { value: false, label: 'Privado', hint: 'Solo orienta decisiones; nunca aparece en un texto público.' },
                  ]}
                />
                {suggestedPublic === null && publicChoice === null ? (
                  <T variant="detalle" soft>
                    Si no eliges, se usa la que sugiere la pregunta.
                  </T>
                ) : null}
              </View>
            ) : null}

            <View style={styles.block}>
              <T variant="etiqueta" soft>
                Para qué es (opcional)
              </T>
              <View style={styles.chips} accessibilityLabel="Para qué es">
                {PURPOSES.map((option) => (
                  <FilterChip key={option.value} pressed={para === option.value} onPress={() => setPara(para === option.value ? null : option.value)}>
                    {option.label}
                  </FilterChip>
                ))}
              </View>
              <T variant="detalle" soft>
                Si no eliges, el equipo lo transcribe y decide.
              </T>
              {galleryWithoutPhotos ? (
                <T variant="detalle" color={colors.alert}>
                  Para «Foto para la galería» adjunta al menos una foto.
                </T>
              ) : null}
            </View>

            {create.error instanceof ApiError && create.error.status === 413 ? (
              <Note tone="error" title="El envío es demasiado grande">
                El audio puede pesar hasta 25 MB y cada foto hasta 10 MB. Quita alguna foto o graba un audio más corto.
              </Note>
            ) : (
              <ErrorRetry error={create.error} />
            )}
            <Button variant="primary" block disabled={cannotSend} loading={sending} loadingLabel="Enviando…" onPress={() => void send()} testID="capture-send">
              Guardar y enviar al equipo
            </Button>
            <T variant="detalle" soft center>
              Lo verás en «Lo que enviaste», arriba en esta hoja.
            </T>
          </>
        )}
      </Sheet>

      {confirmClose ? (
        <ConfirmSheet
          title="¿Cerrar sin enviar?"
          confirmLabel="Cerrar sin enviar"
          cancelLabel="Seguir aquí"
          tone="danger"
          onClose={() => setConfirmClose(false)}
          onConfirm={() => {
            setConfirmClose(false);
            void recorder.discard();
            onClose();
          }}
        >
          Se pierden el audio, las fotos y la nota de esta captura.
        </ConfirmSheet>
      ) : null}
    </>
  );
}

/** Renders the sheet whenever the store says so. */
export function CaptureSheetHost() {
  const sheet = useCaptureSheet();
  if (!sheet.open) return null;
  return <CaptureSheet key={sheet.nonce} context={sheet.context} seed={sheet.seed} onClose={closeCaptureSheet} />;
}

const styles = StyleSheet.create({
  headRow: { flexDirection: 'row', alignItems: 'center', gap: space[2] },
  headTitle: { flexShrink: 1 },
  histLink: { marginLeft: 'auto', minHeight: shell.touch, justifyContent: 'center', paddingHorizontal: space[1] },
  iconButton: { width: shell.touch, height: shell.touch, alignItems: 'center', justifyContent: 'center', borderRadius: radius.pill },
  context: { flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: space[2], paddingLeft: space[3], paddingRight: space[1], borderRadius: radius.md, backgroundColor: colors.brandLight },
  contextText: { flex: 1, minWidth: 0 },
  recording: { alignItems: 'center', gap: space[3], paddingTop: space[1], paddingBottom: space[2] },
  ball: { width: 112, height: 112, borderRadius: radius.pill, backgroundColor: colors.brand, alignItems: 'center', justifyContent: 'center' },
  tabular: { fontVariant: ['tabular-nums'] },
  status: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  waveRow: { alignSelf: 'stretch', flexDirection: 'row' },
  recActions: { alignSelf: 'stretch', flexDirection: 'row', gap: space[2] },
  recButton: { flex: 1, minHeight: 56, borderWidth: 1, borderColor: colors.inkSoft, borderRadius: radius.md, backgroundColor: colors.surface, alignItems: 'center', justifyContent: 'center', gap: 2 },
  recDiscard: { borderColor: colors.alert },
  recFinish: { backgroundColor: colors.brand, borderColor: colors.brand },
  recDisabled: { opacity: 0.5 },
  audioDone: { flexDirection: 'row', alignItems: 'center', gap: space[3], paddingVertical: space[2], paddingHorizontal: space[3], borderWidth: 1, borderColor: colors.line, borderRadius: radius.md },
  play: { width: shell.touch, height: shell.touch, borderRadius: radius.pill, backgroundColor: colors.brand, alignItems: 'center', justifyContent: 'center' },
  record: { minHeight: 56, flexDirection: 'row', alignItems: 'center', gap: space[3], paddingHorizontal: space[3], borderWidth: 1, borderColor: colors.inkSoft, borderStyle: 'dashed', borderRadius: radius.md },
  recordIcon: { width: 36, height: 36, borderRadius: radius.pill, backgroundColor: colors.brand, alignItems: 'center', justifyContent: 'center' },
  block: { gap: space[2] },
  photoButtons: { flexDirection: 'row', gap: space[2] },
  photoPick: { flex: 1, minHeight: 56, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: space[2], borderWidth: 1, borderColor: colors.inkSoft, borderRadius: radius.md, backgroundColor: colors.surface },
  thumbs: { flexDirection: 'row', flexWrap: 'wrap', gap: space[2] },
  thumb: { width: 72, height: 72, borderRadius: radius.sm, overflow: 'hidden' },
  thumbImage: { width: '100%', height: '100%' },
  thumbRemove: { position: 'absolute', top: 2, right: 2, width: 28, height: 28, borderRadius: radius.pill, backgroundColor: colors.backdrop, alignItems: 'center', justifyContent: 'center' },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: space[2] },
});
