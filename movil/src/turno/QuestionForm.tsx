// A team question: the answer field for its type, Público/Privado with the suggestion preselected,
// Responder, Responder con audio, Más tarde and No quiero compartir esto (the PWA's QuestionForm).
// MovTuTurno: once saved, «Responder» turns into a check before the card leaves; «Más tarde» slides
// the card toward «Pospuestas» (exits.ts plays the steps).
import { undoPregunta } from '@compartido/api/endpoints';
import { useAnswerPregunta, useDeclinePregunta, usePostponePregunta } from '@compartido/api/hooks';
import type { Question, QuestionAnswer } from '@compartido/api/types';
import { longDate } from '@compartido/logic/turno';
import { useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { StyleSheet, View } from 'react-native';
import { keys } from '@/api/queryClient';
import { openCaptureSheet } from '@/capture/store';
import { Icon } from '@/components/icons';
import { Button, ConfirmSheet, ErrorRetry, Field, Options, T, errorMessage, isConflict, useToast } from '@/components/ui';
import { haptic } from '@/theme/motion';
import { colors, radius, space } from '@/theme/tokens';
import { DoneButton } from './DoneButton';
import { buttonKey, useTurnoExitsApi } from './exits';

const DETAIL_PLACEHOLDER = 'Cuéntalo como se lo contarías a un colega: qué había, qué hiciste y qué salió.';

const VISIBILITY = [
  { value: true, label: 'Público', hint: 'El equipo puede mencionarlo en posts y comentarios.' },
  { value: false, label: 'Privado', hint: 'Solo orienta decisiones; nunca aparece en un texto público.' },
] as const;

function proposedText(question: Question): string {
  const value = question.proposed_value as { texto?: unknown } | null;
  return typeof value?.texto === 'string' ? value.texto : '';
}

function initialPublic(question: Question): boolean {
  const value = question.proposed_value as { uso_publico?: unknown } | null;
  if (question.kind === 'confirm' && typeof value?.uso_publico === 'boolean') return value.uso_publico;
  return Boolean(question.suggested_public);
}

/** The body of POST /preguntas/<id>/responder for what was typed, or null while it is not valid yet. */
export function buildAnswer(question: Question, value: string, text: string, publicUse: boolean): QuestionAnswer | null {
  const detail = text.trim();
  if (question.kind === 'confirm') return detail ? { text: detail, public_use: publicUse } : { accept: true, public_use: publicUse };
  switch (question.answer_type) {
    case 'yes_no':
      if (value !== 'si' && value !== 'no') return null;
      return detail ? { value, text: detail, public_use: publicUse } : { value, public_use: publicUse };
    case 'choice':
      return value ? { value, public_use: publicUse } : null;
    case 'number':
      return value.trim() !== '' && Number.isFinite(Number(value.replace(',', '.'))) ? { value: value.trim().replace(',', '.'), public_use: publicUse } : null;
    case 'date':
      return /^\d{4}-\d{2}-\d{2}$/.test(value) ? { value, public_use: publicUse } : null;
    default:
      return detail ? { text: detail, public_use: publicUse } : null;
  }
}

/** «Quién puede verlo»: Público or Privado. */
export function VisibilityField({ value, onChange, disabled, legend = 'Quién puede verlo' }: { value: boolean; onChange: (value: boolean) => void; disabled?: boolean; legend?: string }) {
  return <Options legend={legend} options={VISIBILITY} value={value} onChange={onChange} disabled={disabled} />;
}

function AnswerField({ question, value, text, onValue, onText }: { question: Question; value: string; text: string; onValue: (v: string) => void; onText: (t: string) => void }) {
  if (question.kind === 'confirm') {
    return (
      <>
        <View style={styles.block}>
          <T variant="etiqueta" soft>
            Lo que el equipo cree
          </T>
          <View style={styles.proposed}>
            <T>{proposedText(question) || 'Sin texto propuesto.'}</T>
          </View>
        </View>
        <Field label="Corrígelo si no es así" optional value={text} onChangeText={onText} multiline testID={`answer-fix-${question.id}`} />
      </>
    );
  }
  switch (question.answer_type) {
    case 'yes_no':
      return (
        <>
          <Options
            legend="Tu respuesta"
            horizontal
            value={value === 'si' || value === 'no' ? value : null}
            onChange={onValue}
            options={[
              { value: 'si', label: 'Sí' },
              { value: 'no', label: 'No' },
            ]}
          />
          <Field label="Detalle (opcional)" placeholder={DETAIL_PLACEHOLDER} value={text} onChangeText={onText} multiline />
        </>
      );
    case 'choice':
      return <Options legend="Elige una opción" value={value || null} onChange={onValue} options={question.options.map((option) => ({ value: option, label: option }))} />;
    case 'number':
      return <Field label="Tu respuesta" keyboardType="decimal-pad" value={value} onChangeText={onValue} testID={`answer-${question.id}`} />;
    case 'date':
      return (
        <Field
          label="Tu respuesta"
          placeholder="AAAA-MM-DD"
          keyboardType="numbers-and-punctuation"
          maxLength={10}
          value={value}
          onChangeText={onValue}
          hint="Año, mes y día: 2026-11-30."
          testID={`answer-${question.id}`}
        />
      );
    default:
      return <Field label="Tu respuesta" placeholder={DETAIL_PLACEHOLDER} value={text} onChangeText={onText} multiline testID={`answer-${question.id}`} />;
  }
}

/** `cardId`: its Tu turno card, which leaves once answered or postponed. `resolved`: the answer was saved (the button shows the check). */
export function QuestionForm({ question, cardId, resolved = false }: { question: Question; cardId: string; resolved?: boolean }) {
  const client = useQueryClient();
  const toast = useToast();
  const exits = useTurnoExitsApi();
  const answer = useAnswerPregunta();
  const postpone = usePostponePregunta();
  const decline = useDeclinePregunta();
  const [value, setValue] = useState('');
  const [text, setText] = useState('');
  const [publicUse, setPublicUse] = useState(() => initialPublic(question));
  const [declining, setDeclining] = useState(false);

  const body = buildAnswer(question, value, text, publicUse);
  const busy = answer.isPending || postpone.isPending || decline.isPending;

  // Toasts and the undo outlive the card (it leaves the list once answered), so they use the client
  // and the toast API directly instead of this component's mutation callbacks.
  const undo = async () => {
    try {
      await undoPregunta(question.id);
      toast.show('Respuesta deshecha. La pregunta vuelve a estar abierta');
    } catch (error) {
      toast.show(isConflict(error) ? 'Ya no se puede deshacer: pasaron más de 15 minutos' : errorMessage(error), { tone: 'error' });
    } finally {
      void Promise.all([keys.tuTurno, keys.preguntasAll, keys.hechos].map((queryKey) => client.invalidateQueries({ queryKey })));
    }
  };

  const submit = async () => {
    if (!body || busy) return;
    exits.begin(cardId);
    try {
      await answer.mutateAsync({ questionId: question.id, answer: body });
      haptic('actionSuccess');
      toast.show('Guardado. El equipo ya puede usarlo', { undo: () => void undo() });
      exits.resolve(cardId, { kind: 'done', lead: 'check', by: buttonKey.answer });
    } catch {
      haptic('actionError');
      exits.cancel(cardId);
    }
  };

  const later = async () => {
    exits.begin(cardId);
    try {
      const result = await postpone.mutateAsync(question.id);
      const back = longDate(result?.postponed_until);
      haptic('turnoLater');
      toast.show(back ? `Pospuesta. Vuelve el ${back}` : 'Pospuesta 3 días');
      exits.resolve(cardId, { kind: 'later', lead: 'slide' });
    } catch {
      // Shown under the form through postpone.error.
      exits.cancel(cardId);
    }
  };

  const confirmDecline = async () => {
    exits.begin(cardId);
    try {
      await decline.mutateAsync(question.id);
      setDeclining(false);
      toast.show('Hecho. El equipo no volverá a preguntarlo');
      exits.resolve(cardId, { kind: 'done', lead: 'plain' });
    } catch {
      // Shown inside the sheet.
      exits.cancel(cardId);
    }
  };

  const submitLabel = question.kind === 'confirm' ? (text.trim() ? 'Guardar corrección' : 'Sí, es correcto') : 'Responder';

  return (
    <View style={styles.form}>
      <AnswerField question={question} value={value} text={text} onValue={setValue} onText={setText} />
      <VisibilityField value={publicUse} onChange={setPublicUse} disabled={busy} />
      <ErrorRetry error={answer.error ?? postpone.error} />
      <View style={styles.actions}>
        {resolved ? (
          <DoneButton label={submitLabel} block testID={`answer-done-${question.id}`} />
        ) : (
          <Button variant="primary" block disabled={!body || busy} loading={answer.isPending} loadingLabel="Guardando…" onPress={() => void submit()} testID={`answer-submit-${question.id}`}>
            {submitLabel}
          </Button>
        )}
        <Button block icon={<Icon name="microfono" size={20} />} onPress={() => openCaptureSheet({ tipo: 'pregunta', id: question.id, label: question.question })}>
          Responder con audio
        </Button>
        <View style={styles.ghosts}>
          <Button variant="ghost" onPress={() => void later()} disabled={busy} loading={postpone.isPending} loadingLabel="Posponiendo…">
            Más tarde
          </Button>
          <Button variant="ghost" quiet onPress={() => setDeclining(true)} disabled={busy}>
            No quiero compartir esto
          </Button>
        </View>
      </View>
      {declining ? (
        <ConfirmSheet
          title="No compartir esto"
          tone="danger"
          confirmLabel="No quiero compartirlo"
          busy={decline.isPending}
          error={decline.error}
          onConfirm={() => void confirmDecline()}
          onClose={() => {
            decline.reset();
            setDeclining(false);
          }}
        >
          La pregunta se cierra y el equipo no volverá a hacerla. Tampoco podrá contar esto en público.
        </ConfirmSheet>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  form: { gap: space[4] },
  block: { gap: space[2] },
  proposed: { padding: space[3], borderRadius: radius.sm, backgroundColor: colors.brandLight },
  actions: { gap: space[2] },
  ghosts: { flexDirection: 'row', flexWrap: 'wrap', justifyContent: 'center', gap: space[2] },
});
