// Ajustes › Mi perfil (GET/PATCH /api/v1/yo/perfil, organizaciones phase 7): who the team writes as. Only she edits it
// (also while her member is in onboarding); each save is a revision with who, when and what changed.
// The app is drawn edge to edge, so the screen does not shrink for the keyboard: focusing a field tells Ajustes how far
// that field (its label) is from the section's top, and Ajustes brings the field itself under the top bar. Bringing the
// section's top there left «Cómo te presentas» and the fields after it under the keyboard of a 390×844 phone
// (QA 44402904432, 20-ajustes-perfil-voz).
import { useMiPerfil, useSaveMiPerfil } from '@compartido/api/hooks';
import type { MemberProfile, MemberProfileField } from '@compartido/api/types';
import { isUnavailable } from '@compartido/logic/ajustes';
import { fieldCounter, hasChanges, PROFILE_FIELDS, profileIssues, profileOrigin, profilePatch, revisionLine, savedMessage } from '@compartido/logic/miembro';
import { useCallback, useEffect, useRef, useState, type ComponentRef } from 'react';
import { Keyboard, StyleSheet, View } from 'react-native';
import { Button, Card, ErrorRetry, Field, Fold, Note, Section, Skeleton, SwitchRow, T } from '@/components/ui';
import { haptic } from '@/theme/motion';
import { space } from '@/theme/tokens';
import { Unavailable } from './parts';

type Box = ComponentRef<typeof View>;

/** `onFieldFocus(offset)`: a field got the focus; `offset` is how far its label is from the top of the section. */
export function MiPerfilSection({ onFieldFocus }: { onFieldFocus?: (offset: number) => void }) {
  const perfil = useMiPerfil();
  const save = useSaveMiPerfil();
  const root = useRef<Box>(null);
  const boxes = useRef<Partial<Record<MemberProfileField, Box | null>>>({});
  /** null while the form shows the saved profile. */
  const [draft, setDraft] = useState<MemberProfile | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const saved = perfil.data?.profile;
  const values = draft ?? saved;
  const issues = values ? profileIssues(values) : {};
  const invalid = Object.keys(issues).length > 0;
  const patch = saved && values ? profilePatch(saved, values) : {};
  const changed = hasChanges(patch);

  const edit = (key: MemberProfileField, value: string | boolean) => {
    if (!values) return;
    setStatus(null);
    setDraft({ ...values, [key]: value });
  };

  /** The field she is typing in, while it has the focus. */
  const focused = useRef<MemberProfileField | null>(null);
  const reveal = useCallback(
    (key: MemberProfileField) => {
      const box = boxes.current[key];
      if (!onFieldFocus || !box || !root.current) return;
      box.measureLayout(root.current, (_x, y) => onFieldFocus(y));
    },
    [onFieldFocus],
  );
  // Android's back hides the keyboard and leaves the field focused: tapping it again only brings the keyboard back (no
  // new focus), so the field is lifted again then too.
  useEffect(() => {
    const shown = Keyboard.addListener('keyboardDidShow', () => {
      if (focused.current) reveal(focused.current);
    });
    return () => shown.remove();
  }, [reveal]);

  const submit = () => {
    if (!changed || invalid || save.isPending) return;
    save.mutate(patch, {
      onSuccess: (answer) => {
        setDraft(null);
        setStatus(savedMessage(answer.saved));
        haptic('actionSuccess');
      },
      onError: () => haptic('actionError'),
    });
  };

  return (
    <View ref={root} testID="ajustes-mi-perfil" collapsable={false}>
      <Section label="Mi perfil" intro="Quién eres para el equipo: cómo te nombra, cómo te presenta y lo que nunca escribe en tu nombre. Solo tú lo cambias.">
        {perfil.isPending ? <Skeleton variant="card" label="Cargando tu perfil…" /> : null}
        {isUnavailable(perfil.error) ? <Unavailable>El servidor todavía no guarda tu perfil.</Unavailable> : <ErrorRetry error={perfil.error} onRetry={() => void perfil.refetch()} />}
        {perfil.isSuccess && values ? (
          <Card>
            {profileOrigin(perfil.data) ? (
              <T variant="detalle" soft>
                {profileOrigin(perfil.data)}
              </T>
            ) : null}
            {PROFILE_FIELDS.map((field) =>
              field.key === 'personal_startups' ? (
                <SwitchRow
                  key={field.key}
                  label={field.label}
                  hint={perfil.data.help.personal_startups ?? field.hint}
                  value={values.personal_startups}
                  disabled={save.isPending}
                  onChange={(value) => edit('personal_startups', value)}
                  testID="perfil-personal_startups"
                />
              ) : (
                <View
                  key={field.key}
                  ref={(node) => {
                    boxes.current[field.key] = node;
                  }}
                  collapsable={false}
                  testID={`perfil-campo-${field.key}`}
                >
                  <Field
                    label={field.label}
                    required={field.required}
                    value={String(values[field.key] ?? '')}
                    onChangeText={(value) => edit(field.key, value)}
                    multiline={field.multiline}
                    hint={`${perfil.data.help[field.key] ?? field.hint} · ${fieldCounter(String(values[field.key] ?? ''), field.max)}`}
                    error={issues[field.key] ?? null}
                    editable={!save.isPending}
                    onFocus={() => {
                      focused.current = field.key;
                      reveal(field.key);
                    }}
                    onBlur={() => {
                      if (focused.current === field.key) focused.current = null;
                    }}
                    testID={`perfil-${field.key}`}
                  />
                </View>
              ),
            )}
            <ErrorRetry error={save.error} />
            <View style={styles.actions}>
              <Button variant="primary" disabled={!changed || invalid} loading={save.isPending} loadingLabel="Guardando…" onPress={submit} testID="perfil-guardar">
                Guardar perfil
              </Button>
              {draft !== null ? (
                <Button
                  variant="ghost"
                  disabled={save.isPending}
                  onPress={() => {
                    setDraft(null);
                    save.reset();
                  }}
                >
                  Descartar cambios
                </Button>
              ) : null}
            </View>
            {status ? (
              <T variant="detalle" accessibilityLiveRegion="polite" testID="perfil-estado">
                {status}
              </T>
            ) : null}
            <Fold summary={`Historial (${perfil.data.history.length})`}>
              {perfil.data.history.length ? (
                perfil.data.history.map((revision) => (
                  <T key={revision.number} variant="detalle" testID={`perfil-revision-${revision.number}`}>
                    {revisionLine(revision)}
                  </T>
                ))
              ) : (
                <T variant="detalle" soft>
                  Sin cambios todavía.
                </T>
              )}
            </Fold>
          </Card>
        ) : null}
        {perfil.isSuccess && !perfil.data.member.active ? (
          <Note tone="info">Mientras tu cuenta está en alta, tu perfil se guarda pero el equipo todavía no escribe en tu nombre.</Note>
        ) : null}
      </Section>
    </View>
  );
}

const styles = StyleSheet.create({ actions: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', gap: space[2] } });
