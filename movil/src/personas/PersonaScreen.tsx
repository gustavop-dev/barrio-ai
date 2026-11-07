// The person card (/personas/<id>): header with «Abrir en LinkedIn», the next step and who it depends on, the
// journey with dates, why the person fits and where they came from, the conversation read from the inbox, the
// opportunity, notes (written or by voice, through the capture sheet) and the whole history. Actions:
// «Marcar como oportunidad» and «Descartar» (with a mandatory note, only in the stages the API allows).
import { ApiError } from '@compartido/api/client';
import { useAddContactNote, useContact, useDiscardContact, useOportunidades } from '@compartido/api/hooks';
import type { Contact, ContactNote, Opportunity } from '@compartido/api/types';
import {
  confidencePct,
  displayName,
  eventLabel,
  nextStepView,
  noteAuthor,
  opportunityFields,
  originQuote,
  personMeta,
  sortHistory,
  suggestedModality,
} from '@compartido/logic/barrio';
import { CONTACT_AFFINITY_LABEL, CONTACT_MODALITY_LABEL, CONTACT_ROLE_LABEL, contactSourceLabel, labelOf } from '@compartido/logic/format';
import { journey } from '@compartido/logic/journey';
import { daysInStage, DISCARDABLE, longDate, messageWhen, personStage, shortDate } from '@compartido/logic/personas';
import { router } from 'expo-router';
import { useState } from 'react';
import { Linking, Pressable, RefreshControl, ScrollView, StyleSheet, View } from 'react-native';
import { useSession } from '@/auth/session';
import { openCaptureSheet } from '@/capture/store';
import { Icon } from '@/components/icons';
import { useContentInsets } from '@/components/shell/useContentInsets';
import { Avatar, Badge, Button, Card, ConfirmSheet, EmptyState, EmptyText, ErrorRetry, Field, LabelChip, Section, Skeleton, T, pageContent, useToast } from '@/components/ui';
import { ExternalLink } from '@/components/ui/ExternalLink';
import { isHttps } from '@/navigation';
import { haptic } from '@/theme/motion';
import { colors, radius, space } from '@/theme/tokens';
import { ConversationBlock } from './ConversationBlock';
import { Journey } from './Journey';
import { OportunidadForm } from './OportunidadForm';

function NextStep({ contact }: { contact: Contact }) {
  const step = nextStepView(contact);
  if (!step) return null;
  return (
    <Card tone={step.mine ? 'warn' : null}>
      <View accessible accessibilityLabel={[step.label, step.text, step.at, step.action].filter(Boolean).join('. ')} testID="next-step">
        <T variant="etiqueta" soft>
          {step.label}
        </T>
        <T>{step.text}</T>
        {step.at ? (
          <T variant="detalle" soft>
            {step.at}
          </T>
        ) : null}
        {step.action ? (
          <T variant="detalle" soft>
            {step.action}
          </T>
        ) : null}
      </View>
      {step.action ? (
        <Button variant="ghost" size="small" style={styles.start} onPress={() => router.navigate('/calendario')}>
          Ver en el Calendario
        </Button>
      ) : null}
      {contact.your_turn ? (
        <Button block onPress={() => router.navigate('/tu-turno')}>
          Ir a Tu turno
        </Button>
      ) : null}
    </Card>
  );
}

function WhyFits({ contact }: { contact: Contact }) {
  const c = contact.classification ?? {};
  if (!Object.keys(c).length) {
    return (
      <Card>
        <T variant="detalle" soft>
          Sin clasificar todavía. El equipo la clasificará en el próximo ciclo.
        </T>
      </Card>
    );
  }
  const confidence = confidencePct(c.confidence);
  return (
    <Card>
      <View style={styles.chips}>
        {c.fit === false ? <Badge tone="bad">No encaja</Badge> : null}
        {c.role ? <LabelChip tone="info">{labelOf(CONTACT_ROLE_LABEL, c.role)}</LabelChip> : null}
        {c.modality ? <LabelChip tone="muted">{labelOf(CONTACT_MODALITY_LABEL, c.modality)}</LabelChip> : null}
        {c.affinity ? <LabelChip tone="muted">{labelOf(CONTACT_AFFINITY_LABEL, c.affinity)}</LabelChip> : null}
      </View>
      {c.reason ? <T>{c.reason}</T> : null}
      {confidence !== null ? (
        <View accessible accessibilityRole="image" accessibilityLabel={`Confianza ${confidence} %`} style={styles.field}>
          <View style={styles.row}>
            <T variant="detalle" soft style={styles.grow}>
              Confianza
            </T>
            <T variant="detalle">{confidence} %</T>
          </View>
          <View style={styles.track}>
            <View style={[styles.bar, { width: `${confidence}%` }]} />
          </View>
        </View>
      ) : null}
      {c.classified_at ? (
        <T variant="detalle" soft>
          Clasificada el {longDate(c.classified_at)}
        </T>
      ) : null}
    </Card>
  );
}

function Origin({ contact }: { contact: Contact }) {
  const quote = originQuote(contact);
  return (
    <Card>
      <T>{contactSourceLabel(contact.source, contact.evidence)}</T>
      {quote ? (
        <View style={styles.quote}>
          <T>“{quote}”</T>
        </View>
      ) : null}
      {contact.source === 'commenter' ? (
        <ExternalLink href={contact.evidence?.post_url} hint="Abre el post en LinkedIn">
          Ver el post
        </ExternalLink>
      ) : null}
    </Card>
  );
}

function OpportunityBlock({ contact, onEdit }: { contact: Contact; onEdit: (opportunity: Opportunity) => void }) {
  const brief = contact.opportunity;
  const list = useOportunidades({ contact: contact.id });
  if (!brief) return null;
  const full = list.data ? (Array.isArray(list.data) ? list.data : list.data.results).find((item) => item.id === brief.id) : undefined;
  const fields = opportunityFields(brief, full);
  return (
    <Section label="Oportunidad">
      <Card>
        <View style={[styles.row, styles.wrap]}>
          <Badge tone="ok">{brief.stage_label}</Badge>
          {full ? (
            <T variant="detalle" soft>
              {daysInStage(full.days_in_stage)}
            </T>
          ) : null}
        </View>
        {fields.map(([label, value]) => (
          <View key={label} style={styles.field}>
            <T variant="etiqueta" soft>
              {label}
            </T>
            <T>{value}</T>
          </View>
        ))}
        <ErrorRetry error={list.error} onRetry={() => void list.refetch()} />
        {full ? (
          <Button block onPress={() => onEdit(full)}>
            Editar oportunidad
          </Button>
        ) : null}
      </Card>
    </Section>
  );
}

function Notes({ contact, name }: { contact: Contact; name: string }) {
  const session = useSession();
  const add = useAddContactNote();
  const toast = useToast();
  const [writing, setWriting] = useState(false);
  const [text, setText] = useState('');
  const me = session.user?.username;
  const notes: ContactNote[] = [...(contact.notes ?? [])].reverse();

  const save = () => {
    if (!text.trim() || add.isPending) return;
    add.mutate(
      { contactId: contact.id, text: text.trim() },
      {
        onSuccess: () => {
          haptic('actionSuccess');
          setText('');
          setWriting(false);
          toast.show('Nota guardada');
        },
        onError: () => haptic('actionError'),
      },
    );
  };

  return (
    <Section label="Notas">
      <Card>
        {notes.length ? (
          notes.map((note) => (
            <View key={note.id} style={styles.note}>
              <T>{note.text}</T>
              <T variant="detalle" soft>
                {noteAuthor(note, me)} · {shortDate(note.at)}
              </T>
            </View>
          ))
        ) : (
          <T variant="detalle" soft>
            Aún no hay notas sobre esta persona.
          </T>
        )}
        {writing ? (
          <View style={styles.field}>
            <Field label="Nota" value={text} onChangeText={setText} multiline autoFocus editable={!add.isPending} testID="note-text" />
            <ErrorRetry error={add.error} />
            <View style={styles.actions}>
              <Button variant="primary" block disabled={!text.trim()} loading={add.isPending} loadingLabel="Guardando…" onPress={save}>
                Guardar nota
              </Button>
              <Button
                block
                disabled={add.isPending}
                onPress={() => {
                  setWriting(false);
                  setText('');
                  add.reset();
                }}
              >
                Cancelar
              </Button>
            </View>
          </View>
        ) : (
          <View style={styles.actions}>
            <Button block icon={<Icon name="plus" size={20} />} onPress={() => setWriting(true)}>
              Añadir nota
            </Button>
            <Button block icon={<Icon name="microfono" size={20} />} onPress={() => openCaptureSheet({ tipo: 'persona', id: contact.id, label: name })}>
              Nota de voz
            </Button>
          </View>
        )}
      </Card>
    </Section>
  );
}

function History({ contact }: { contact: Contact }) {
  const entries = sortHistory(contact.history ?? []);
  if (!entries.length)
    return (
      <T variant="detalle" soft>
        Sin eventos todavía.
      </T>
    );
  return (
    <View accessibilityRole="list" accessibilityLabel="Historial completo" testID="history">
      {entries.map((entry, index) => (
        <View key={`${entry.at}-${index}`} style={styles.event} testID={`history-${index}`}>
          <View style={styles.grow}>
            <T>{eventLabel(entry)}</T>
            {entry.detail ? (
              <T variant="detalle" soft>
                {entry.detail}
              </T>
            ) : null}
          </View>
          <T variant="detalle" soft>
            {messageWhen(entry.at)}
          </T>
        </View>
      ))}
    </View>
  );
}

export function PersonaScreen({ contactId }: { contactId: string }) {
  const contact = useContact(contactId);
  const discard = useDiscardContact();
  const toast = useToast();
  const { bottom } = useContentInsets();
  const [form, setForm] = useState<{ opportunity: Opportunity | null } | null>(null);
  const [discarding, setDiscarding] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  const refresh = async () => {
    setRefreshing(true);
    try {
      await contact.refetch();
    } finally {
      setRefreshing(false);
    }
  };

  if (contact.isPending) {
    return (
      <View style={[styles.screen, pageContent]}>
        <Skeleton variant="card" count={2} label="Cargando la ficha…" />
      </View>
    );
  }
  if (contact.isError && !contact.data) {
    const missing = contact.error instanceof ApiError && contact.error.status === 404;
    return (
      <View style={[styles.screen, pageContent]}>
        {missing ? (
          <EmptyState
            title="No encontramos a esta persona"
            action={
              <Button variant="secondary" onPress={() => (router.canGoBack() ? router.back() : router.replace('/personas'))}>
                Volver a Personas
              </Button>
            }
          >
            <EmptyText>Puede que el enlace sea viejo.</EmptyText>
          </EmptyState>
        ) : (
          <ErrorRetry error={contact.error} onRetry={() => void contact.refetch()} />
        )}
      </View>
    );
  }

  const person = contact.data;
  const name = displayName(person);
  const stage = personStage(person.display_stage ?? person.stage);
  const meta = personMeta(person);
  const canDiscard = DISCARDABLE.includes(person.stage);
  const profile = isHttps(person.profile_url) ? person.profile_url : null;

  return (
    <>
      <ScrollView
        style={styles.screen}
        contentContainerStyle={[pageContent, { paddingBottom: bottom }]}
        keyboardShouldPersistTaps="handled"
        testID="persona"
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => void refresh()} tintColor={colors.brandDeep} colors={[colors.brandDeep]} />}
      >
        <View style={styles.head} testID="persona-head">
          <View style={styles.top}>
            <Avatar name={name} size={48} />
            <Badge tone={stage.tone}>{stage.label}</Badge>
          </View>
          {profile ? (
            <Pressable accessibilityRole="link" accessibilityHint="Abre su perfil en LinkedIn" onPress={() => void Linking.openURL(profile)} style={styles.nameLink} testID="persona-name">
              <T variant="titulo" accessibilityRole="header" style={styles.shrink}>
                {name}
              </T>
              <Icon name="external" size={22} color={colors.brandDeep} />
            </Pressable>
          ) : (
            <T variant="titulo" accessibilityRole="header" testID="persona-name">
              {name}
            </T>
          )}
          {person.headline ? <T soft>{person.headline}</T> : null}
          {meta ? (
            <T variant="detalle" soft>
              {meta}
            </T>
          ) : null}
          <View style={styles.actions}>
            {profile ? (
              <Button variant="primary" block icon={<Icon name="external" size={20} color={colors.onBrand} />} accessibilityHint="Se abre en LinkedIn" onPress={() => void Linking.openURL(profile)}>
                Abrir en LinkedIn
              </Button>
            ) : null}
            {!person.opportunity ? (
              <Button block onPress={() => setForm({ opportunity: null })}>
                Marcar como oportunidad
              </Button>
            ) : null}
            {canDiscard ? (
              <Button block variant="danger" onPress={() => setDiscarding(true)}>
                Descartar
              </Button>
            ) : null}
          </View>
        </View>

        {contact.isError ? <ErrorRetry title="No se pudo actualizar la ficha" error={contact.error} onRetry={() => void contact.refetch()} /> : null}

        <NextStep contact={person} />

        <Section label="Recorrido">
          <Journey stages={journey(person)} label={`Recorrido de ${name}`} />
        </Section>

        <Section label="Por qué encaja">
          <WhyFits contact={person} />
        </Section>

        <Section label="De dónde salió">
          <Origin contact={person} />
        </Section>

        <View testID="conversation">
          <Section label="Conversación">
            <ConversationBlock conversation={person.conversation} name={name} profileUrl={person.profile_url} />
          </Section>
        </View>

        <OpportunityBlock contact={person} onEdit={(opportunity) => setForm({ opportunity })} />

        <Notes contact={person} name={name} />

        <Section label="Historial completo">
          <History contact={person} />
        </Section>
      </ScrollView>

      {form ? (
        <OportunidadForm
          opportunity={form.opportunity}
          person={{ id: person.id, display_name: name, headline: person.headline, modality: suggestedModality(person) }}
          onClose={() => setForm(null)}
        />
      ) : null}
      {discarding ? (
        <ConfirmSheet
          title={`Descartar a ${name}`}
          confirmLabel="Descartar"
          tone="danger"
          note="required"
          noteLabel="Por qué la descartas"
          busy={discard.isPending}
          error={discard.error}
          onClose={() => {
            discard.reset();
            setDiscarding(false);
          }}
          onConfirm={(note) =>
            discard.mutate(
              { contactId: person.id, note },
              {
                onSuccess: () => {
                  haptic('actionSuccess');
                  setDiscarding(false);
                  toast.show('Descartada: no volverá a proponerse');
                },
                onError: () => haptic('actionError'),
              },
            )
          }
        >
          No volverá a proponerse: el equipo no la seguirá ni la invitará. Si tiene una acción abierta, se veta.
        </ConfirmSheet>
      ) : null}
    </>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.paper },
  head: { gap: space[2] },
  top: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: space[2] },
  nameLink: { flexDirection: 'row', alignItems: 'center', gap: space[2], minHeight: 48 },
  shrink: { flexShrink: 1, color: colors.brandDeep },
  actions: { gap: space[2], marginTop: space[2] },
  start: { alignSelf: 'flex-start' },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: space[1] },
  field: { gap: space[1] },
  row: { flexDirection: 'row', alignItems: 'center', gap: space[2] },
  wrap: { flexWrap: 'wrap' },
  grow: { flex: 1, gap: 2 },
  track: { height: 8, borderRadius: radius.pill, backgroundColor: colors.line, overflow: 'hidden' },
  bar: { height: 8, borderRadius: radius.pill, backgroundColor: colors.brandDeep },
  quote: { borderLeftWidth: 3, borderLeftColor: colors.line, paddingLeft: space[3] },
  note: { gap: 2, paddingBottom: space[2], borderBottomWidth: 1, borderBottomColor: colors.line },
  event: { flexDirection: 'row', alignItems: 'flex-start', gap: space[3], paddingVertical: space[2], borderBottomWidth: 1, borderBottomColor: colors.line },
});
