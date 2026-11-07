// «Nueva oportunidad» / «Editar oportunidad» as a full-height sheet with every field of the PWA form
// (DISENO-VISTAS, Personas → Oportunidades), and «Eliminar» behind a confirmation in the same sheet.
import { useQuery } from '@tanstack/react-query';
import { asList, listContacts } from '@compartido/api/endpoints';
import { useCreateOportunidad, useDeleteOportunidad, useUpdateOportunidad } from '@compartido/api/hooks';
import { keys } from '@compartido/api/queryClient';
import { OPPORTUNITY_STAGES, type Opportunity, type OpportunityAttribution, type OpportunityChannel, type OpportunityModality, type OpportunityStage } from '@compartido/api/types';
import { initialModality, opportunityErrors, opportunityInput, type OpportunityDraft, type OpportunityPerson, type PersonMode } from '@compartido/logic/barrio';
import { ATTRIBUTION_LABEL, CHANNEL_LABEL, fromDateInput, OPPORTUNITY_MODALITY_LABEL, OPPORTUNITY_STAGE_LABEL, toDateInput } from '@compartido/logic/personas';
import { useEffect, useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import { Avatar, Button, ErrorRetry, Field, Options, Sheet, T, useToast } from '@/components/ui';
import { Select } from '@/components/ui/Select';
import { haptic } from '@/theme/motion';
import { colors, radius, space } from '@/theme/tokens';

export type { OpportunityPerson };

export interface OportunidadFormProps {
  /** Edit mode when given. */
  opportunity?: Opportunity | null;
  person?: OpportunityPerson | null;
  onClose: () => void;
  onSaved?: (opportunity: Opportunity) => void;
}

/** The pause before the person search asks the API (the PWA's 250 ms). */
const SEARCH_PAUSE_MS = 250;

const MODALITIES = (Object.keys(OPPORTUNITY_MODALITY_LABEL) as OpportunityModality[]).map((value) => ({ value, label: OPPORTUNITY_MODALITY_LABEL[value] }));
const CHANNELS = (Object.keys(CHANNEL_LABEL) as OpportunityChannel[]).map((value) => ({ value, label: CHANNEL_LABEL[value] }));
const STAGES = OPPORTUNITY_STAGES.map((value) => ({ value, label: OPPORTUNITY_STAGE_LABEL[value] }));
const ATTRIBUTIONS = (Object.keys(ATTRIBUTION_LABEL) as OpportunityAttribution[]).map((value) => ({ value, label: ATTRIBUTION_LABEL[value] }));
const PERSON_MODES = [
  { value: 'red' as const, label: 'De Personas' },
  { value: 'fuera' as const, label: 'Alguien fuera de la red' },
];

/** Buscador de Personas: name or headline, two letters at least. */
function PersonSearch({ onPick, error }: { onPick: (person: OpportunityPerson) => void; error: string | null }) {
  const [text, setText] = useState('');
  const [query, setQuery] = useState('');
  useEffect(() => {
    const timer = setTimeout(() => setQuery(text.trim()), SEARCH_PAUSE_MS);
    return () => clearTimeout(timer);
  }, [text]);
  const results = useQuery({
    queryKey: [...keys.redAll, 'picker', query],
    queryFn: async () => asList(await listContacts({ q: query })),
    enabled: query.length >= 2,
  });
  return (
    <View style={styles.block}>
      <Field label="Buscar en Personas" placeholder="Nombre o titular" value={text} onChangeText={setText} autoCorrect={false} autoCapitalize="words" error={error} testID="opp-person-search" />
      {query.length >= 2 ? (
        <View style={styles.block} accessibilityLiveRegion="polite">
          {results.isPending ? (
            <T variant="detalle" soft>
              Buscando…
            </T>
          ) : null}
          <ErrorRetry error={results.error} onRetry={() => void results.refetch()} />
          {results.isSuccess && !results.data.length ? (
            <T variant="detalle" soft>
              Nadie coincide con «{query}».
            </T>
          ) : null}
          {results.data?.slice(0, 8).map((contact) => (
            <Pressable
              key={contact.id}
              accessibilityRole="button"
              onPress={() => onPick({ id: contact.id, display_name: contact.display_name, headline: contact.headline, modality: contact.classification?.modality })}
              style={({ pressed }) => [styles.result, pressed ? styles.pressed : null]}
            >
              <Avatar name={contact.display_name} size={32} />
              <View style={styles.grow}>
                <T>{contact.display_name}</T>
                {contact.headline ? (
                  <T variant="detalle" soft numberOfLines={1}>
                    {contact.headline}
                  </T>
                ) : null}
              </View>
            </Pressable>
          ))}
        </View>
      ) : null}
    </View>
  );
}

export function OportunidadForm({ opportunity, person, onClose, onSaved }: OportunidadFormProps) {
  const editing = Boolean(opportunity);
  const toast = useToast();
  const create = useCreateOportunidad();
  const update = useUpdateOportunidad();
  const remove = useDeleteOportunidad();

  const startPerson: OpportunityPerson | null = opportunity?.contact
    ? { id: opportunity.contact.id, display_name: opportunity.contact.display_name, headline: opportunity.contact.headline }
    : (person ?? null);
  const [draft, setDraft] = useState<OpportunityDraft>(() => ({
    mode: opportunity && !opportunity.contact ? 'fuera' : 'red',
    picked: startPerson,
    personName: opportunity?.person_name ?? '',
    company: opportunity?.company ?? '',
    modality: initialModality(opportunity, person),
    channel: opportunity?.channel ?? 'linkedin',
    stage: opportunity?.stage ?? 'conversacion',
    attribution: opportunity?.attribution ?? '',
    need: opportunity?.need ?? '',
    budget: opportunity?.budget ?? '',
    dedication: opportunity?.dedication ?? '',
    nextAction: opportunity?.next_action ?? '',
    nextAt: toDateInput(opportunity?.next_action_at),
    notes: opportunity?.notes ?? '',
  }));
  const [touched, setTouched] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const set = <K extends keyof OpportunityDraft>(key: K, value: OpportunityDraft[K]) => setDraft((current) => ({ ...current, [key]: value }));

  const errors = opportunityErrors(draft);
  const dateError = draft.nextAt.trim() && !fromDateInput(draft.nextAt.trim()) ? 'Escribe la fecha como AAAA-MM-DD.' : null;
  const invalid = Boolean(errors.person || errors.modality || errors.attribution || dateError);
  const saving = create.isPending || update.isPending;
  const show = (error: string | null) => (touched ? error : null);

  const submit = () => {
    setTouched(true);
    if (invalid || saving) return;
    const input = opportunityInput({ ...draft, nextAt: draft.nextAt.trim() });
    const done = (saved: Opportunity) => {
      haptic('actionSuccess');
      toast.show(editing ? 'Cambios guardados' : 'Oportunidad registrada');
      onSaved?.(saved);
      onClose();
    };
    const failed = () => haptic('actionError');
    if (opportunity) update.mutate({ opportunityId: opportunity.id, patch: input }, { onSuccess: done, onError: failed });
    else create.mutate(input, { onSuccess: done, onError: failed });
  };

  const title = confirmDelete ? 'Eliminar la oportunidad' : editing ? 'Editar oportunidad' : 'Nueva oportunidad';
  const busy = saving || remove.isPending;

  return (
    <Sheet
      label={title}
      onClose={onClose}
      suspended={busy}
      testID="opportunity-form"
      header={
        <T variant="subtitulo" accessibilityRole="header">
          {title}
        </T>
      }
    >
      {opportunity && confirmDelete ? (
        <>
          <T>{`Se borra la oportunidad con ${opportunity.person || 'esta persona'} y su historial. Deja de contar en Resultados. No se puede deshacer.`}</T>
          <ErrorRetry error={remove.error} />
          <View style={styles.actions}>
            <Button
              variant="danger"
              block
              loading={remove.isPending}
              loadingLabel="Eliminando…"
              onPress={() =>
                remove.mutate(opportunity.id, {
                  onSuccess: () => {
                    haptic('actionSuccess');
                    toast.show('Oportunidad eliminada');
                    onClose();
                  },
                  onError: () => haptic('actionError'),
                })
              }
            >
              Eliminar
            </Button>
            <Button block onPress={() => setConfirmDelete(false)} disabled={remove.isPending}>
              Volver
            </Button>
          </View>
        </>
      ) : (
        <>
          <View style={styles.block}>
            <T variant="detalle">
              Persona<T variant="detalle" soft>{' · obligatoria'}</T>
            </T>
            <Options<PersonMode> legend="Quién es" options={PERSON_MODES} value={draft.mode} onChange={(mode) => set('mode', mode)} />
            {draft.mode === 'red' ? (
              draft.picked ? (
                <View style={styles.picked} testID="opp-picked">
                  <Avatar name={draft.picked.display_name} size={32} />
                  <View style={styles.grow}>
                    <T>{draft.picked.display_name}</T>
                    {draft.picked.headline ? (
                      <T variant="detalle" soft numberOfLines={2}>
                        {draft.picked.headline}
                      </T>
                    ) : null}
                  </View>
                  <Button variant="ghost" size="small" onPress={() => set('picked', null)} accessibilityLabel="Cambiar la persona">
                    Cambiar
                  </Button>
                </View>
              ) : (
                <PersonSearch
                  error={show(errors.person)}
                  onPick={(chosen) =>
                    setDraft((current) => ({
                      ...current,
                      picked: chosen,
                      modality: !current.modality && (chosen.modality === 'personal_startups' || chosen.modality === 'projectapp') ? chosen.modality : current.modality,
                    }))
                  }
                />
              )
            ) : (
              <Field label="Nombre" value={draft.personName} maxLength={200} onChangeText={(value) => set('personName', value)} error={show(errors.person)} testID="opp-name" />
            )}
            <Field label="Empresa" optional value={draft.company} maxLength={200} onChangeText={(value) => set('company', value)} testID="opp-company" />
          </View>

          <Select label="Modalidad" value={draft.modality} options={MODALITIES} onChange={(value) => set('modality', value)} error={show(errors.modality)} testID="opp-modality" />
          <Select label="Canal" value={draft.channel} options={CHANNELS} onChange={(value: OpportunityChannel) => set('channel', value)} testID="opp-channel" />
          <Select label="Etapa" value={draft.stage} options={STAGES} onChange={(value: OpportunityStage) => set('stage', value)} testID="opp-stage" />
          <Select label="Cómo llegó" value={draft.attribution} options={ATTRIBUTIONS} onChange={(value) => set('attribution', value)} error={show(errors.attribution)} testID="opp-attribution" />

          <Field label="Necesidad" optional value={draft.need} onChangeText={(value) => set('need', value)} testID="opp-need" />
          <Field label="Presupuesto o compensación" optional value={draft.budget} maxLength={200} placeholder="Texto o rango" onChangeText={(value) => set('budget', value)} testID="opp-budget" />
          <Field label="Dedicación" optional value={draft.dedication} maxLength={200} onChangeText={(value) => set('dedication', value)} testID="opp-dedication" />
          <Field label="Siguiente acción" optional value={draft.nextAction} maxLength={300} onChangeText={(value) => set('nextAction', value)} testID="opp-next" />
          <Field
            label="Fecha"
            optional
            value={draft.nextAt}
            placeholder="AAAA-MM-DD"
            keyboardType="numbers-and-punctuation"
            maxLength={10}
            onChangeText={(value) => set('nextAt', value)}
            error={show(dateError)}
            testID="opp-date"
          />
          <Field label="Notas" optional value={draft.notes} multiline onChangeText={(value) => set('notes', value)} testID="opp-notes" />

          {touched && invalid ? (
            <T variant="detalle" color={colors.alert} accessibilityRole="alert">
              Falta algo obligatorio: revisa los campos marcados.
            </T>
          ) : null}
          <ErrorRetry error={create.error ?? update.error} />
          <View style={styles.actions}>
            <Button variant="primary" block loading={saving} loadingLabel="Guardando…" onPress={submit}>
              {editing ? 'Guardar cambios' : 'Registrar oportunidad'}
            </Button>
            <Button block onPress={onClose} disabled={saving}>
              Cancelar
            </Button>
            {opportunity ? (
              <Button variant="danger" block onPress={() => setConfirmDelete(true)} disabled={saving}>
                Eliminar
              </Button>
            ) : null}
          </View>
        </>
      )}
    </Sheet>
  );
}

const styles = StyleSheet.create({
  block: { gap: space[2] },
  grow: { flex: 1, gap: 2 },
  picked: { flexDirection: 'row', alignItems: 'center', gap: space[3], padding: space[2], borderWidth: 1, borderColor: colors.line, borderRadius: radius.sm },
  result: { minHeight: 48, flexDirection: 'row', alignItems: 'center', gap: space[3], paddingVertical: space[1], borderRadius: radius.sm },
  pressed: { backgroundColor: colors.paper },
  actions: { gap: space[2] },
});
