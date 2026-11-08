// The capture sheet of Captura.dc.html: audio, photos, a note and «Para qué es», sent to the team in
// one multipart POST /api/v1/capturas, with a 5 s «Deshacer». Mounted once by the app layout.
//
// It moves as in MovCaptura:
// - opened by the capture button, the button turns into the sheet's audio element (the recording ball,
//   the «Grabar un audio» icon or the play button) on SOFT while the sheet rises on FIRM;
// - the recording ball beats with the voice inside a ring, and its icons turn between mic and pause;
// - «Descartar» throws the ball into a bin that pops in, closes and shakes («AVISO»);
// - photos pop in;
// - «Guardar»: once the team has it, the content fades, the audio drops into an envelope that seals
//   («ÉXITO»), the sheet goes down, the envelope flies off and the button pulses under the toast.
import {
  CAPTURE_LIMITS,
  captureKeys,
  undoCaptura,
  useCapturas,
  useCreateCaptura,
  type CaptureOutput,
  type CapturePurpose,
} from '@compartido/api/capturas';
import { asList, listPreguntas } from '@compartido/api/endpoints';
import { audioFilename, mmss } from '@compartido/logic/audio';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useAudioPlayer, useAudioPlayerStatus } from 'expo-audio';
import { useEffect, useRef, useState } from 'react';
import { Image, Linking, Pressable, StyleSheet, View, type LayoutChangeEvent } from 'react-native';
import Animated, {
  cancelAnimation,
  useAnimatedReaction,
  useAnimatedStyle,
  useDerivedValue,
  useSharedValue,
  withDelay,
  withRepeat,
  withSequence,
  withSpring,
  withTiming,
  type SharedValue,
} from 'react-native-reanimated';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { localPart, reportError, type LocalPart } from '@/api/errorReport';
import { keys } from '@/api/queryClient';
import { Icon } from '@/components/icons';
import { Button, ConfirmSheet, FilterChip, Note, Options, Sheet, T, errorMessage, useToast } from '@/components/ui';
import { Field } from '@/components/ui/Field';
import { useSheetFrame, type SheetFrame, type SheetHandle } from '@/components/ui/Sheet';
import { captureMotion, captureTimeline, curves, durations, haptic, microLayout, springWith, timelineWith, timingWith, useMotion } from '@/theme/motion';
import { colors, radius, shell, space } from '@/theme/tokens';
import { lerp, qbez, seg, useVoiceLevel } from './choreo';
import { BIN, BinGlyph, ENVELOPE, EnvelopeGlyph } from './glyphs';
import { CaptureHistory } from './History';
import { checkPhotos, pickFromGallery, takePhoto } from './photos';
import { useRecorder, useRecorderLive } from './recorder';
import { DRAFT_KEPT, describeSendError } from './sendError';
import { closeCaptureSheet, notifyCaptureSent, openCaptureSheet, useCaptureSheet } from './store';
import type { CaptureDraft, CaptureOrigin, CaptureSeed, CaptureTarget, MicNoteKind, PickedPhoto, RecordedAudio } from './types';
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

// ---------------------------------------------------------------- the stage of the choreography

/** The recording ball (112 px) and the sheet's other audio elements the button can turn into. */
const BALL = 112;
const RECORD_ICON = 36;
type AudioKind = 'rec' | 'none' | 'done';
const ELEMENT: Record<AudioKind, { size: number; icon: number }> = {
  rec: { size: BALL, icon: 40 },
  none: { size: RECORD_ICON, icon: 20 },
  done: { size: shell.touch, icon: 20 },
};

interface Point {
  x: number;
  y: number;
}

/**
 * Where the sheet's audio element is: its wrapper's place in the sheet's content and its own centre in
 * the wrapper (from layout), and whether it shows yet (hidden while the button's ball flies to it).
 */
interface Stage {
  wrapper: SharedValue<Point>;
  element: SharedValue<Point & { known: boolean }>;
  docked: SharedValue<boolean>;
}

function wrapperLayout(stage: Stage) {
  return (event: LayoutChangeEvent) => stage.wrapper.set({ x: event.nativeEvent.layout.x, y: event.nativeEvent.layout.y });
}

function elementLayout(stage: Stage) {
  return (event: LayoutChangeEvent) => {
    const { x, y, width, height } = event.nativeEvent.layout;
    stage.element.set({ x: x + width / 2, y: y + height / 2, known: true });
  };
}

/** The audio element's centre in the modal, with the sheet open. */
function restPoint(frame: SheetFrame, stage: Stage): Point {
  'worklet';
  return {
    x: frame.contentX.value + stage.wrapper.value.x + stage.element.value.x,
    y: frame.panelY.value + frame.contentY.value + stage.wrapper.value.y + stage.element.value.y - frame.scroll.value,
  };
}

/** Where the envelope seals: across from the audio element, never above the sheet's content. */
function sealPoint(frame: SheetFrame, stage: Stage): Point {
  'worklet';
  const top = frame.panelY.value + frame.contentY.value + ENVELOPE.height;
  const y = stage.element.value.known ? Math.max(top, restPoint(frame, stage).y) : top;
  return { x: frame.width.value / 2, y };
}

function useDocked(stage: Stage) {
  return useAnimatedStyle(() => ({ opacity: stage.docked.value ? 1 : 0 }));
}

/** The capture button turning into the sheet's audio element (`morph`, SOFT), drawn over the sheet. */
function MorphBall({ frame, stage, origin, kind }: { frame: SheetFrame; stage: Stage; origin: CaptureOrigin; kind: AudioKind }) {
  const insets = useSafeAreaInsets();
  const morph = useSharedValue(0);
  const started = useSharedValue(false);
  const icMic = useSharedValue(1);
  const icPlay = useSharedValue(0);
  const { size, icon } = ELEMENT[kind];
  const flight = springWith(captureMotion.morph);
  const crossfade = timingWith(durations.fast, 'enter');
  const bottomInset = insets.bottom;

  // It starts once the sheet and its audio element have a place.
  useAnimatedReaction(
    () => stage.element.value.known && frame.panelY.value > 0,
    (ready) => {
      if (!ready || started.value) return;
      started.set(true);
      morph.set(withSpring(1, flight));
      if (kind === 'done') {
        icMic.set(withTiming(0, crossfade));
        icPlay.set(withTiming(1, crossfade));
      }
    },
  );
  // It hands over to the element in the sheet once at rest (or as soon as the sheet is dragged or closes).
  useAnimatedReaction(
    () => morph.value,
    (m, previous) => {
      if (stage.docked.value) return;
      const resting = m === 1 || (previous !== null && Math.abs(m - 1) < captureMotion.dockWithin && Math.abs(m - previous) < captureMotion.dockWithin);
      if (resting || frame.moved.value) stage.docked.set(true);
    },
  );

  const ball = useAnimatedStyle(() => {
    const m = morph.value;
    const rest = restPoint(frame, stage);
    const fromX = frame.width.value / 2;
    const fromY = frame.rootHeight.value - bottomInset - shell.tabBarHeight - shell.captureLift + shell.captureButton / 2 + origin.lift;
    const fromScale = (shell.captureButton * origin.scale) / size;
    const x = lerp(fromX, rest.x, m);
    const y = lerp(fromY, rest.y, m);
    return {
      opacity: started.value && !stage.docked.value ? 1 : 0,
      transform: [{ translateX: x - size / 2 }, { translateY: y - size / 2 }, { scale: lerp(fromScale, 1, m) }],
    };
  });
  const mic = useAnimatedStyle(() => ({ opacity: icMic.value, transform: [{ rotate: `${(1 - icMic.value) * captureMotion.iconTurnDeg}deg` }] }));
  const play = useAnimatedStyle(() => ({ opacity: icPlay.value, transform: [{ scale: captureMotion.playFrom + (1 - captureMotion.playFrom) * icPlay.value }] }));
  return (
    <Animated.View style={[styles.flying, { width: size, height: size }, ball]}>
      <Animated.View style={[styles.flyingIcon, mic]}>
        <Icon name="microfono" size={icon} color={colors.onBrand} />
      </Animated.View>
      {kind === 'done' ? (
        <Animated.View style={[styles.flyingIcon, play]}>
          <Icon name="play" size={icon} color={colors.onBrand} />
        </Animated.View>
      ) : null}
    </Animated.View>
  );
}

/** «Guardar»: the audio drops into the envelope, which seals and flies off. */
function SendStage({ frame, stage, clock, withAudio, reduced }: { frame: SheetFrame; stage: Stage; clock: SharedValue<number>; withAudio: boolean; reduced: boolean }) {
  const S = captureTimeline.send;
  const size = ELEMENT.done.size;
  const point = useDerivedValue(() => sealPoint(frame, stage));
  const ball = useAnimatedStyle(() => {
    const t = clock.value;
    const shrink = reduced ? 1 - seg(t, [0, S.ballOff] as const) : lerp(1, S.ballShrinkTo, curves.enter(seg(t, S.ballShrink))) * (1 - seg(t, S.ballGone));
    return {
      opacity: t < S.ballOff ? 1 : 0,
      transform: [{ translateX: point.value.x - size / 2 }, { translateY: point.value.y - size / 2 }, { scale: shrink }],
    };
  });
  const envelope = useAnimatedStyle(() => {
    const t = clock.value;
    const appear = reduced ? 1 : curves.enter(seg(t, S.envelopeIn));
    const fly = reduced ? 0 : curves.exit(seg(t, S.fly));
    const p = point.value;
    const x = qbez(p.x, p.x + S.flyControlX, p.x + S.flyEndX, fly);
    const y = qbez(p.y, p.y + S.flyControlY, p.y + S.flyEndY, fly);
    return {
      opacity: reduced ? 1 - seg(t, S.envelopeFade) : 1,
      transform: [
        { translateX: x - ENVELOPE.width / 2 },
        { translateY: y - ENVELOPE.height / 2 },
        { rotate: `${S.flyTurnDeg * fly}deg` },
        { scale: appear * lerp(1, S.flyScale, fly) },
      ],
    };
  });
  const flap = useAnimatedStyle(() => {
    const closing = seg(clock.value, S.flapClose);
    return { transform: [{ scaleY: lerp(-1, 1, reduced ? closing : curves.enter(closing)) }] };
  });
  return (
    <>
      {withAudio ? (
        <Animated.View style={[styles.flying, { width: size, height: size }, ball]}>
          <Icon name="play" size={ELEMENT.done.icon} color={colors.onBrand} />
        </Animated.View>
      ) : null}
      <Animated.View style={[styles.envelope, envelope]}>
        <EnvelopeGlyph flap={flap} />
      </Animated.View>
    </>
  );
}

/** What MovCaptura draws over the sheet. */
function CaptureOverlay({ stage, origin, kind, leaving, clock, withAudio, reduced }: { stage: Stage; origin?: CaptureOrigin; kind: AudioKind | null; leaving: boolean; clock: SharedValue<number>; withAudio: boolean; reduced: boolean }) {
  const frame = useSheetFrame();
  if (!frame) return null;
  return (
    <>
      {origin && kind ? <MorphBall frame={frame} stage={stage} origin={origin} kind={kind} /> : null}
      {leaving ? <SendStage frame={frame} stage={stage} clock={clock} withAudio={withAudio} reduced={reduced} /> : null}
    </>
  );
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

function RecordingPanel({
  locked,
  stage,
  onDiscard,
  onFinish,
}: {
  locked: boolean;
  stage: Stage;
  onDiscard: () => void;
  onFinish: (audio: RecordedAudio | null) => void;
}) {
  const recorder = useRecorder();
  const live = useRecorderLive();
  const { reduced } = useMotion();
  const [finishing, setFinishing] = useState(false);
  const [trashing, setTrashing] = useState(false);
  const paused = recorder.phase === 'paused';
  const starting = recorder.phase === 'starting';
  const recording = recorder.phase === 'recording' && !trashing;
  const status = starting ? 'Abriendo el micrófono…' : paused ? 'En pausa' : locked ? 'Grabando · bloqueado' : 'Grabando';
  const level = useVoiceLevel(live.levels[live.levels.length - 1] ?? 0, recording, reduced);
  const beating = recording && !reduced;
  const icMic = useSharedValue(paused ? 0 : 1);
  const icPause = useSharedValue(paused ? 1 : 0);
  const blink = useSharedValue(1);
  const clock = useSharedValue(0);
  const timers = useRef<ReturnType<typeof setTimeout>[]>([]);

  useEffect(() => {
    const pending = timers.current;
    return () => pending.forEach(clearTimeout);
  }, []);

  // Mic and pause turn into each other (fast, EASE_OUT).
  useEffect(() => {
    const crossfade = timingWith(durations.fast, 'enter');
    icMic.set(withTiming(paused ? 0 : 1, crossfade));
    icPause.set(withTiming(paused ? 1 : 0, crossfade));
  }, [paused, icMic, icPause]);

  // Paused, the time blinks every pausedBlinkMs.
  useEffect(() => {
    if (!paused || reduced) {
      cancelAnimation(blink);
      blink.set(1);
      return;
    }
    const half = captureMotion.pausedBlinkMs;
    blink.set(withRepeat(withSequence(withDelay(half, withTiming(captureMotion.pausedBlinkOpacity, { duration: 0 })), withDelay(half, withTiming(1, { duration: 0 }))), -1));
    return () => cancelAnimation(blink);
  }, [paused, reduced, blink]);

  const discard = () => {
    if (trashing) return;
    const D = captureTimeline.discard;
    setTrashing(true);
    void recorder.discard();
    clock.set(withTiming(1, timelineWith(D.ms)));
    timers.current.push(setTimeout(() => haptic('captureDiscard'), D.ms * D.dropAt));
    timers.current.push(setTimeout(onDiscard, D.ms));
  };

  const ballMotion = useAnimatedStyle(() => {
    const t = clock.value;
    const D = captureTimeline.discard;
    const beat = beating ? 1 + captureMotion.ballBeat * level.value : paused ? captureMotion.ballPausedScale : 1;
    if (t <= 0) return { opacity: stage.docked.value ? 1 : 0, transform: [{ translateX: 0 }, { translateY: 0 }, { scale: beat }] };
    const fall = curves.exit(seg(t, D.fly));
    return {
      opacity: t < D.ballOffAt ? 1 : 0,
      transform: [
        { translateX: qbez(0, D.arcX, 0, fall) },
        { translateY: qbez(0, D.arcY, D.binBelow - D.mouth, fall) },
        { scale: (lerp(BALL, D.shrinkTo, fall) / BALL) * beat },
      ],
    };
  });
  const ring = useAnimatedStyle(() => {
    const spread = captureMotion.ringBase + captureMotion.ringLevel * level.value;
    return {
      opacity: beating ? captureMotion.ringOpacity * (1 - level.value * captureMotion.ringFade) : 0,
      transform: [{ scale: (BALL + 2 * spread) / BALL }],
    };
  });
  const mic = useAnimatedStyle(() => ({ opacity: icMic.value, transform: [{ rotate: `${(1 - icMic.value) * captureMotion.iconTurnDeg}deg` }] }));
  const pause = useAnimatedStyle(() => ({
    opacity: icPause.value,
    transform: [{ rotate: `${(icPause.value - 1) * captureMotion.iconTurnDeg}deg` }, { scale: captureMotion.pauseFrom + (1 - captureMotion.pauseFrom) * icPause.value }],
  }));
  const time = useAnimatedStyle(() => ({ opacity: blink.value }));
  const controls = useAnimatedStyle(() => ({ opacity: 1 - seg(clock.value, captureTimeline.discard.fade) }));
  const bin = useAnimatedStyle(() => {
    const t = clock.value;
    const D = captureTimeline.discard;
    if (t <= 0) return { opacity: 0, transform: [{ translateX: 0 }, { scale: 0 }] };
    const pop = seg(t, D.binPop);
    const out = seg(t, D.out);
    const grow = reduced ? 1 : pop < 1 ? curves.enter(pop) * (1 + D.binBump * Math.sin(pop * Math.PI)) : 1;
    const shaking = !reduced && t > D.shake[0] && t < D.shake[1];
    const shake = shaking ? Math.sin(seg(t, D.shake) * Math.PI * D.shakeHalfTurns) * D.shakePx : 0;
    return { opacity: 1 - out, transform: [{ translateX: shake }, { scale: grow * (1 - D.outShrink * out) }] };
  });
  const binLid = useAnimatedStyle(() => {
    const t = clock.value;
    const D = captureTimeline.discard;
    const angle = t < D.dropAt ? D.lidDeg * seg(t, D.lidOpen) : D.lidDeg * (1 - seg(t, D.lidClose));
    return { transform: [{ rotate: `${angle}deg` }] };
  });

  return (
    <View style={styles.recording} testID="capture-recording" onLayout={wrapperLayout(stage)}>
      <Animated.View style={[styles.bin, bin]} pointerEvents="none">
        <BinGlyph lid={binLid} />
      </Animated.View>
      <Animated.View style={[styles.ballSlot, ballMotion]} onLayout={elementLayout(stage)}>
        <Animated.View style={[styles.ring, ring]} />
        <View style={[styles.ball, paused ? styles.ballPaused : null]}>
          <Animated.View style={[styles.flyingIcon, mic]}>
            <Icon name="microfono" size={ELEMENT.rec.icon} color={colors.onBrand} />
          </Animated.View>
          <Animated.View style={[styles.flyingIcon, pause]}>
            <Icon name="pausa" size={ELEMENT.rec.icon} color={colors.brandDeep} />
          </Animated.View>
        </View>
      </Animated.View>
      <Animated.View style={[styles.recordingControls, controls]}>
        <Animated.View style={time}>
          <T variant="titulo" color={paused ? colors.inkSoft : undefined} style={styles.tabular} accessibilityElementsHidden>
            {mmss(live.elapsed)}
          </T>
        </Animated.View>
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
          <Pressable accessibilityRole="button" disabled={trashing} onPress={discard} style={[styles.recButton, styles.recDiscard]}>
            <Icon name="papelera" size={22} color={colors.alert} />
            <T variant="detalle" color={colors.alert}>
              Descartar
            </T>
          </Pressable>
          <Pressable
            accessibilityRole="button"
            disabled={starting || trashing}
            onPress={() => (paused ? recorder.resume() : recorder.pause())}
            style={[styles.recButton, starting ? styles.recDisabled : null]}
          >
            <Icon name={paused ? 'play' : 'pausa'} size={22} />
            <T variant="detalle">{paused ? 'Seguir' : 'Pausar'}</T>
          </Pressable>
          <Pressable
            accessibilityRole="button"
            disabled={finishing || trashing}
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
      </Animated.View>
    </View>
  );
}

function AudioDone({ audio, stage, onRemove }: { audio: RecordedAudio; stage: Stage; onRemove: () => void }) {
  const player = useAudioPlayer(audio.uri);
  const status = useAudioPlayerStatus(player);
  const playing = status.playing;
  const docked = useDocked(stage);
  useEffect(() => {
    if (status.didJustFinish) player.seekTo(0).catch(() => undefined);
  }, [status.didJustFinish, player]);
  return (
    <View style={styles.audioDone} testID="capture-audio" onLayout={wrapperLayout(stage)}>
      <Animated.View style={docked} onLayout={elementLayout(stage)}>
        <Pressable
          accessibilityRole="button"
          accessibilityLabel={playing ? 'Pausar el audio' : 'Escuchar el audio'}
          accessibilityState={{ selected: playing }}
          onPress={() => (playing ? player.pause() : player.play())}
          style={styles.play}
        >
          <Icon name={playing ? 'pausa' : 'play'} size={ELEMENT.done.icon} color={colors.onBrand} />
        </Pressable>
      </Animated.View>
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

function RecordButton({ stage, onPress }: { stage: Stage; onPress: () => void }) {
  const docked = useDocked(stage);
  return (
    <Pressable accessibilityRole="button" onPress={onPress} style={styles.record} onLayout={wrapperLayout(stage)}>
      <Animated.View style={[styles.recordIcon, docked]} onLayout={elementLayout(stage)}>
        <Icon name="microfono" size={ELEMENT.none.icon} color={colors.onBrand} />
      </Animated.View>
      <T>Grabar un audio</T>
    </Pressable>
  );
}

/** A photo of the capture: it pops in, and on «Guardar» flies into the envelope (stagger by `index`). */
function Thumb({
  foto,
  index,
  stage,
  block,
  row,
  clock,
  reduced,
  onRemove,
}: {
  foto: PickedPhoto;
  index: number;
  stage: Stage;
  block: SharedValue<Point>;
  row: SharedValue<Point>;
  clock: SharedValue<number>;
  reduced: boolean;
  onRemove: () => void;
}) {
  const frame = useSheetFrame();
  const centre = useSharedValue<Point>({ x: 0, y: 0 });
  const flight = useAnimatedStyle(() => {
    const t = clock.value;
    if (t <= 0 || !frame) return { opacity: 1, transform: [{ translateX: 0 }, { translateY: 0 }, { scale: 1 }] };
    const S = captureTimeline.send;
    const lag = index * S.thumbStagger;
    const p = reduced ? seg(t, S.thumbsReduced) : curves.exit(seg(t, [S.thumbs[0] + lag, S.thumbs[1] + lag] as const));
    const seal = sealPoint(frame, stage);
    const x = frame.contentX.value + block.value.x + row.value.x + centre.value.x;
    const y = frame.panelY.value + frame.contentY.value + block.value.y + row.value.y + centre.value.y - frame.scroll.value;
    return { opacity: 1 - p, transform: [{ translateX: (seal.x - x) * p }, { translateY: (seal.y - y) * p }, { scale: 1 - S.thumbShrink * p }] };
  });
  return (
    <Animated.View
      entering={microLayout.thumbIn()}
      onLayout={(event) => {
        const { x, y, width, height } = event.nativeEvent.layout;
        centre.set({ x: x + width / 2, y: y + height / 2 });
      }}
    >
      <Animated.View style={[styles.thumb, flight]}>
        <Image source={{ uri: foto.uri }} style={styles.thumbImage} accessibilityLabel={`Foto adjunta ${index + 1}`} />
        <Pressable accessibilityRole="button" accessibilityLabel={`Quitar la foto ${index + 1}`} onPress={onRemove} style={styles.thumbRemove}>
          <Icon name="cerrar" size={16} color={colors.paper} />
        </Pressable>
      </Animated.View>
    </Animated.View>
  );
}

// ---------------------------------------------------------------- a failed send

/**
 * Why «Guardar y enviar al equipo» failed, right above the button (a toast would sit under the sheet's
 * Modal): the reason, that the draft is still here, the technical detail and «Reintentar».
 */
function SendError({ error, onRetry }: { error: unknown; onRetry: () => void }) {
  const problem = describeSendError(error);
  return (
    <View testID="capture-send-error">
      <Note
        tone={problem.tone}
        title={problem.title}
        actions={
          <Button variant="secondary" size="small" onPress={onRetry}>
            Reintentar
          </Button>
        }
      >
        <T variant="detalle">{problem.message}</T>
        <T variant="detalle">{DRAFT_KEPT}</T>
        {problem.technical ? (
          <T variant="detalle" soft selectable>
            Detalle: {problem.technical}
          </T>
        ) : null}
      </Note>
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
  const { reduced } = useMotion();
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
  const [leaving, setLeaving] = useState(false);
  const sent = useRef(false);
  const sheet = useRef<SheetHandle>(null);
  const timers = useRef<ReturnType<typeof setTimeout>[]>([]);

  // The choreography: what the button turns into, where it is, and the «Guardar» clock.
  const [opening] = useState<AudioKind | null>(() => {
    if (seed.mic || seed.view === 'history') return null;
    const first = initialAudio(seed);
    return first.kind === 'recording' ? 'rec' : first.kind === 'done' ? 'done' : 'none';
  });
  const morphing = Boolean(seed.from) && opening !== null;
  const stage: Stage = {
    wrapper: useSharedValue<Point>({ x: 0, y: 0 }),
    element: useSharedValue<Point & { known: boolean }>({ x: 0, y: 0, known: false }),
    docked: useSharedValue(!morphing),
  };
  const photoBlock = useSharedValue<Point>({ x: 0, y: 0 });
  const thumbRow = useSharedValue<Point>({ x: 0, y: 0 });
  const sendClock = useSharedValue(0);
  const contentOpacity = useDerivedValue(() => 1 - seg(sendClock.value, captureTimeline.send.fade));

  useEffect(() => {
    const pending = timers.current;
    return () => pending.forEach(clearTimeout);
  }, []);

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
  const showRecording = audio.kind === 'recording' && !autoStopped && !recordingFailed;
  const element: AudioKind | null = view !== 'form' ? null : showRecording ? 'rec' : readyAudio ? 'done' : mic || recordingFailed ? null : 'none';

  // Another audio element than the one the button flew to shows at once.
  useEffect(() => {
    if (element !== opening) stage.docked.set(true);
  }, [element, opening, stage.docked]);

  const later = (run: () => void, ms: number) => {
    timers.current.push(setTimeout(run, ms));
  };

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
    if (leaving) return;
    if (canClose()) sheet.current?.dismiss();
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

  /** The team has it: the envelope choreography, then the sheet closes, the button pulses and the toast says so. */
  const leave = (then: () => void) => {
    const S = captureTimeline.send;
    setLeaving(true);
    sendClock.set(withTiming(1, timelineWith(S.ms)));
    later(() => haptic('captureSent'), S.ms * S.sealAt);
    later(() => sheet.current?.hide(), S.ms * S.closeAt);
    later(() => {
      onClose();
      notifyCaptureSent();
      then();
    }, S.ms);
  };

  const send = async () => {
    if (cannotSend || sending || leaving) return;
    setSending(true);
    let finalAudio = readyAudio;
    // A live recording (or one whose stop is on its way) is finished first: the file is complete
    // when stop() resolves, and only then does it go up.
    if (audio.kind === 'recording' && !autoStopped) finalAudio = (await recorder.stop()) ?? readyAudio;
    // From here on the audio is part of the draft: a failed send keeps it in the sheet.
    if (finalAudio) setAudio({ kind: 'done', audio: finalAudio });
    const draft: CaptureDraft = { audio: finalAudio, fotos, nota, para, publicUse: publicChoice };
    const sentContext = context;
    const mime = finalAudio?.mime || 'audio/mp4';
    const parts: LocalPart[] = [
      ...(finalAudio ? [localPart('audio', { uri: finalAudio.uri, type: mime })] : []),
      ...fotos.map((foto) => localPart('fotos', foto)),
    ];
    create.mutate(
      {
        // Native parts: a URI with a scheme, a name and always a type (compartido nativePart).
        audio: finalAudio ? { blob: { uri: finalAudio.uri, name: audioFilename(mime), type: mime }, filename: audioFilename(mime), durationS: finalAudio.duration } : null,
        fotos: fotos.map(({ uri, name, type }) => ({ uri, name, type })),
        nota,
        para,
        contexto: context ? { tipo: context.tipo, id: context.id } : null,
        publicUse: context?.tipo === 'pregunta' ? publicChoice : null,
      },
      {
        onSuccess: (capture) => {
          sent.current = true;
          leave(() => toast.show('Enviado al equipo.', { undo: () => void undo(capture, draft, sentContext) }));
        },
        onError: (error) => {
          haptic('actionError');
          // Only metadata: the error, the status and each part's field, type, scheme and size.
          reportError('captura_envio', error, parts);
        },
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
      <Sheet
        ref={sheet}
        label="Captura para el equipo"
        onClose={closeNow}
        canClose={canClose}
        suspended={confirmClose || leaving}
        header={header}
        openHaptic={!morphing}
        contentOpacity={contentOpacity}
        overlay={
          <CaptureOverlay
            stage={stage}
            origin={morphing ? seed.from : undefined}
            kind={opening}
            leaving={leaving}
            clock={sendClock}
            withAudio={Boolean(readyAudio)}
            reduced={reduced}
          />
        }
        testID="capture-sheet"
      >
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

            {showRecording && audio.kind === 'recording' ? (
              <RecordingPanel
                locked={audio.locked}
                stage={stage}
                onDiscard={() => {
                  void recorder.discard();
                  setAudio({ kind: 'none' });
                }}
                onFinish={(result) => setAudio(result ? { kind: 'done', audio: result } : { kind: 'none' })}
              />
            ) : readyAudio ? (
              <AudioDone
                audio={readyAudio}
                stage={stage}
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
              <RecordButton stage={stage} onPress={() => void startRecording()} />
            )}

            <View style={styles.block} onLayout={(event) => photoBlock.set({ x: event.nativeEvent.layout.x, y: event.nativeEvent.layout.y })}>
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
                <View
                  style={styles.thumbs}
                  accessibilityLabel="Fotos adjuntas"
                  onLayout={(event) => thumbRow.set({ x: event.nativeEvent.layout.x, y: event.nativeEvent.layout.y })}
                >
                  {fotos.map((foto, index) => (
                    <Thumb
                      key={foto.id}
                      foto={foto}
                      index={index}
                      stage={stage}
                      block={photoBlock}
                      row={thumbRow}
                      clock={sendClock}
                      reduced={reduced}
                      onRemove={() => setFotos((current) => current.filter((f) => f.id !== foto.id))}
                    />
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

            {create.error && !sending ? <SendError error={create.error} onRetry={() => void send()} /> : null}
            <Button variant="primary" block disabled={cannotSend} loading={sending || leaving} loadingLabel="Enviando…" onPress={() => void send()} testID="capture-send">
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
            sheet.current?.dismiss();
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
  recordingControls: { alignSelf: 'stretch', alignItems: 'center', gap: space[3] },
  ballSlot: { width: BALL, height: BALL, zIndex: 2 },
  ring: { position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, borderRadius: radius.pill, backgroundColor: colors.brand },
  ball: { position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, borderRadius: radius.pill, backgroundColor: colors.brand, alignItems: 'center', justifyContent: 'center' },
  // Paused (MovCaptura): 0ff1ce-claro with a 3 px 0ff1ce-hondo ring inside.
  ballPaused: { backgroundColor: colors.brandLight, borderWidth: 3, borderColor: colors.brandDeep },
  bin: {
    position: 'absolute',
    zIndex: 1,
    left: '50%',
    marginLeft: -BIN.width / 2,
    top: space[1] + BALL / 2 + captureTimeline.discard.binBelow - BIN.height / 2,
  },
  flying: { position: 'absolute', left: 0, top: 0, borderRadius: radius.pill, backgroundColor: colors.brand, alignItems: 'center', justifyContent: 'center' },
  flyingIcon: { position: 'absolute' },
  envelope: { position: 'absolute', left: 0, top: 0 },
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
  recordIcon: { width: RECORD_ICON, height: RECORD_ICON, borderRadius: radius.pill, backgroundColor: colors.brand, alignItems: 'center', justifyContent: 'center' },
  block: { gap: space[2] },
  photoButtons: { flexDirection: 'row', gap: space[2] },
  photoPick: { flex: 1, minHeight: 56, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: space[2], borderWidth: 1, borderColor: colors.inkSoft, borderRadius: radius.md, backgroundColor: colors.surface },
  thumbs: { flexDirection: 'row', flexWrap: 'wrap', gap: space[2] },
  thumb: { width: 72, height: 72, borderRadius: radius.sm, overflow: 'hidden' },
  thumbImage: { width: '100%', height: '100%' },
  thumbRemove: { position: 'absolute', top: 2, right: 2, width: 28, height: 28, borderRadius: radius.pill, backgroundColor: colors.backdrop, alignItems: 'center', justifyContent: 'center' },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: space[2] },
});
