// «Lo que el equipo sabe de ti»: the confirmed facts, with Editar, Retirar, Añadir and a search past 20.
import { useAddHecho, useCorrectHecho, useHechos, useRetireHecho } from '@compartido/api/hooks';
import type { MemoryFact } from '@compartido/api/types';
import { factOrigin, normalize, shortDate } from '@compartido/logic/turno';
import { useMemo, useState } from 'react';
import { StyleSheet, View } from 'react-native';
import { Icon } from '@/components/icons';
import { Badge, Button, Card, ConfirmSheet, EmptyState, EmptyText, ErrorRetry, Field, Sheet, Skeleton, T, useToast } from '@/components/ui';
import { space } from '@/theme/tokens';
import { VisibilityField } from './QuestionForm';

/** The search shows up from this many facts on. */
export const SEARCH_FROM = 21;

function byNewest(a: MemoryFact, b: MemoryFact): number {
  return (b.updated_at ?? '').localeCompare(a.updated_at ?? '');
}

function FactCard({ fact, onEdit, onRetire }: { fact: MemoryFact; onEdit: () => void; onRetire: () => void }) {
  const meta = [factOrigin(fact), shortDate(fact.updated_at), fact.edits > 1 ? `v${fact.edits}` : ''].filter(Boolean).join(' · ');
  const topic = fact.topic || fact.key;
  return (
    <Card>
      <View style={styles.head}>
        <T variant="etiqueta" soft style={styles.topic}>
          {topic}
        </T>
        <Badge tone={fact.public_use ? 'ok' : 'muted'}>{fact.public_use ? 'Público' : 'Privado'}</Badge>
      </View>
      <T>{fact.text}</T>
      <T variant="detalle" soft>
        {meta}
      </T>
      <View style={styles.row}>
        <Button size="small" onPress={onEdit} accessibilityLabel={`Editar: ${topic}`}>
          Editar
        </Button>
        <Button size="small" variant="danger" onPress={onRetire} accessibilityLabel={`Retirar: ${topic}`}>
          Retirar
        </Button>
      </View>
    </Card>
  );
}

/** «Añadir algo que quieras que sepan» (new) and «Editar» (a new version of an existing fact). */
function FactSheet({ fact, onClose }: { fact: MemoryFact | null; onClose: () => void }) {
  const toast = useToast();
  const add = useAddHecho();
  const correct = useCorrectHecho();
  const mutation = fact ? correct : add;
  const [text, setText] = useState(fact?.text ?? '');
  const [topic, setTopic] = useState('');
  const [publicUse, setPublicUse] = useState(fact?.public_use ?? false);

  const submit = async () => {
    const clean = text.trim();
    if (!clean || mutation.isPending) return;
    try {
      if (fact) {
        await correct.mutateAsync({ key: fact.key, text: clean, publicUse });
        toast.show(`Guardado como v${fact.edits + 1}`);
      } else {
        await add.mutateAsync({ text: clean, public_use: publicUse, ...(topic.trim() ? { topic: topic.trim() } : {}) });
        toast.show('Guardado. El equipo ya puede usarlo');
      }
      onClose();
    } catch {
      // Shown inside the sheet.
    }
  };

  const title = fact ? 'Editar lo que sabe el equipo' : 'Añadir algo que quieras que sepan';
  return (
    <Sheet label={title} onClose={onClose} suspended={mutation.isPending}>
      <T variant="subtitulo" accessibilityRole="header">
        {title}
      </T>
      {fact ? (
        <T variant="detalle" soft>
          {fact.topic || fact.key}
        </T>
      ) : null}
      <Field label={fact ? 'Texto' : 'Qué quieres que sepan'} value={text} onChangeText={setText} multiline maxLength={4000} />
      {fact ? null : <Field label="Tema" optional placeholder="Por ejemplo: Límites" value={topic} onChangeText={setTopic} maxLength={200} />}
      <VisibilityField value={publicUse} onChange={setPublicUse} disabled={mutation.isPending} />
      <T variant="detalle" soft>
        {fact ? 'Se guarda como una versión nueva; la anterior queda en el historial.' : 'Se confirma al guardar: lo escribes tú.'}
      </T>
      <ErrorRetry error={mutation.error} />
      <View style={styles.actions}>
        <Button variant="primary" block disabled={!text.trim()} loading={mutation.isPending} loadingLabel="Guardando…" onPress={() => void submit()}>
          Guardar
        </Button>
        <Button block onPress={onClose} disabled={mutation.isPending}>
          Cancelar
        </Button>
      </View>
    </Sheet>
  );
}

function RetireSheet({ fact, onClose }: { fact: MemoryFact; onClose: () => void }) {
  const toast = useToast();
  const retire = useRetireHecho();
  return (
    <ConfirmSheet
      title="Retirar este dato"
      tone="danger"
      confirmLabel="Retirar"
      note="optional"
      noteLabel="Motivo"
      busy={retire.isPending}
      error={retire.error}
      onConfirm={async (reason) => {
        try {
          await retire.mutateAsync({ key: fact.key, reason });
          toast.show('Retirado. El equipo ya no lo usará');
          onClose();
        } catch {
          // Shown inside the sheet.
        }
      }}
      onClose={onClose}
    >
      {`El equipo deja de usar «${fact.topic || fact.key}» desde ahora. Si vuelve a hacer falta, te lo preguntará.`}
    </ConfirmSheet>
  );
}

export function Sabe() {
  const hechos = useHechos();
  const [adding, setAdding] = useState(false);
  const [editing, setEditing] = useState<MemoryFact | null>(null);
  const [retiring, setRetiring] = useState<MemoryFact | null>(null);
  const [search, setSearch] = useState('');

  const facts = useMemo(() => [...(hechos.data ?? [])].sort(byNewest), [hechos.data]);
  const searchable = facts.length >= SEARCH_FROM;
  const needle = searchable ? normalize(search.trim()) : '';
  const shown = needle ? facts.filter((fact) => normalize(`${fact.topic} ${fact.text}`).includes(needle)) : facts;

  return (
    <View style={styles.sabe} testID="turno-sabe">
      <T soft>Esto es lo único que el equipo puede contar de ti. Nadie inventará tus experiencias, clientes ni servicios.</T>
      <Button block icon={<Icon name="plus" size={20} />} onPress={() => setAdding(true)}>
        Añadir algo que quieras que sepan
      </Button>
      {hechos.isPending ? <Skeleton variant="row" count={3} label="Cargando lo que sabe el equipo…" /> : null}
      {hechos.isError && !hechos.data ? <ErrorRetry error={hechos.error} onRetry={() => void hechos.refetch()} /> : null}
      {hechos.data && !facts.length ? (
        <EmptyState title="Aún no hay nada confirmado">
          <EmptyText>Nadie inventará tus experiencias, clientes ni servicios: responde las preguntas del equipo para que puedan usarlas.</EmptyText>
        </EmptyState>
      ) : null}
      {searchable ? (
        <View style={styles.search}>
          <Field label="Buscar en lo que sabe el equipo" placeholder="Buscar" value={search} onChangeText={setSearch} returnKeyType="search" />
          <T variant="detalle" soft accessibilityLiveRegion="polite">
            {needle ? `${shown.length} de ${facts.length}` : `${facts.length} datos`}
          </T>
        </View>
      ) : null}
      {facts.length ? (
        shown.length ? (
          shown.map((fact) => <FactCard key={fact.key} fact={fact} onEdit={() => setEditing(fact)} onRetire={() => setRetiring(fact)} />)
        ) : (
          <T variant="detalle" soft>
            Nada coincide con «{search.trim()}».
          </T>
        )
      ) : null}
      {adding ? <FactSheet fact={null} onClose={() => setAdding(false)} /> : null}
      {editing ? <FactSheet fact={editing} onClose={() => setEditing(null)} /> : null}
      {retiring ? <RetireSheet fact={retiring} onClose={() => setRetiring(null)} /> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  sabe: { gap: space[3] },
  head: { flexDirection: 'row', alignItems: 'flex-start', justifyContent: 'space-between', gap: space[2] },
  topic: { flex: 1 },
  row: { flexDirection: 'row', gap: space[2] },
  actions: { gap: space[2] },
  search: { gap: space[1] },
});
