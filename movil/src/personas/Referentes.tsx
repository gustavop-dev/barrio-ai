// Personas › Referentes: who the team reads to discover people. «Añadir referente» (a linkedin.com/in/… URL,
// checked in the field, and a mandatory reason), «Observar ahora», deactivate or reactivate with «Deshacer»,
// and remove after confirming. The account selector only shows with more than one account.
import { useAccounts, useDeleteReferent, useReferents, useUpdateReferent } from '@compartido/api/hooks';
import { normalizeProfileUrl, useAddReferent, useObserveNow } from '@compartido/api/personas';
import type { Referent } from '@compartido/api/types';
import { OBSERVE_QUEUED, REFERENT_URL_ERROR, referentMeta, referentName } from '@compartido/logic/barrio';
import { useState, type ReactNode } from 'react';
import { FlatList, RefreshControl, StyleSheet, View } from 'react-native';
import { Icon } from '@/components/icons';
import { useContentInsets } from '@/components/shell/useContentInsets';
import { Badge, Button, ConfirmSheet, EmptyState, EmptyText, ErrorRetry, Field, Note, Sheet, Skeleton, T, pageContent, useToast } from '@/components/ui';
import { ExternalLink } from '@/components/ui/ExternalLink';
import { Select } from '@/components/ui/Select';
import { haptic } from '@/theme/motion';
import { colors, radius, space } from '@/theme/tokens';

function AddReferentSheet({ account, onClose }: { account: string; onClose: () => void }) {
  const add = useAddReferent();
  const toast = useToast();
  const [url, setUrl] = useState('');
  const [reason, setReason] = useState('');
  const [touched, setTouched] = useState(false);
  const normalized = normalizeProfileUrl(url);
  const urlError = touched && !normalized ? REFERENT_URL_ERROR : null;
  const reasonError = touched && !reason.trim() ? 'El motivo es obligatorio.' : null;

  const submit = () => {
    setTouched(true);
    if (!normalized || !reason.trim() || add.isPending) return;
    add.mutate(
      { account, identifier: normalized, reason: reason.trim() },
      {
        onSuccess: () => {
          haptic('actionSuccess');
          toast.show('Referente añadido');
          onClose();
        },
        onError: () => haptic('actionError'),
      },
    );
  };

  return (
    <Sheet label="Añadir referente" onClose={onClose} suspended={add.isPending} testID="add-referent" header={<T variant="subtitulo" accessibilityRole="header">Añadir referente</T>}>
      <T soft>Una voz cuya conversación importa para tu barrio. El equipo lee sus posts y descubre a quien comenta.</T>
      <Field
        label="URL del perfil en LinkedIn"
        placeholder="https://www.linkedin.com/in/…"
        value={url}
        onChangeText={setUrl}
        keyboardType="url"
        autoCapitalize="none"
        autoCorrect={false}
        error={urlError}
        testID="referent-url"
      />
      <Field
        label="Motivo · obligatorio"
        placeholder="Por qué su conversación importa para tu barrio"
        value={reason}
        onChangeText={setReason}
        multiline
        maxLength={1000}
        error={reasonError}
        testID="referent-reason"
      />
      <ErrorRetry error={add.error} />
      <View style={styles.actions}>
        <Button variant="primary" block loading={add.isPending} loadingLabel="Guardando…" onPress={submit}>
          Añadir referente
        </Button>
        <Button block onPress={onClose} disabled={add.isPending}>
          Cancelar
        </Button>
      </View>
    </Sheet>
  );
}

function ReferentCard({ referent, onRemove }: { referent: Referent; onRemove: (referent: Referent) => void }) {
  const update = useUpdateReferent();
  const toast = useToast();
  const active = referent.active !== false;
  const name = referentName(referent);

  const toggle = () => {
    update.mutate(
      { referentId: referent.id, patch: { active: !active } },
      {
        onSuccess: () => {
          haptic('actionSuccess');
          toast.show(active ? 'Referente desactivado' : 'Referente reactivado', {
            undo: () => update.mutate({ referentId: referent.id, patch: { active } }),
          });
        },
        onError: () => haptic('actionError'),
      },
    );
  };

  return (
    <View style={styles.card} testID={`referent-${referent.id}`}>
      <View style={styles.head}>
        <View style={styles.grow}>
          {referent.profile_url && /^https:\/\//i.test(referent.profile_url) ? (
            <ExternalLink href={referent.profile_url} hint="Abre su perfil en LinkedIn">
              {name}
            </ExternalLink>
          ) : (
            <T>{name}</T>
          )}
        </View>
        {active ? <Badge tone="ok">Activo</Badge> : <Badge tone="muted">Inactivo</Badge>}
      </View>
      {referent.reason ? <T>{referent.reason}</T> : null}
      <T variant="detalle" soft>
        {referentMeta(referent)}
      </T>
      <ErrorRetry error={update.error} />
      <View style={styles.row}>
        <View style={styles.grow}>
          <Button size="small" block onPress={toggle} loading={update.isPending} loadingLabel="Guardando…" accessibilityLabel={`${active ? 'Desactivar' : 'Reactivar'} a ${name}`}>
            {active ? 'Desactivar' : 'Reactivar'}
          </Button>
        </View>
        <View style={styles.grow}>
          <Button size="small" block variant="danger" onPress={() => onRemove(referent)} accessibilityLabel={`Quitar a ${name}`}>
            Quitar
          </Button>
        </View>
      </View>
    </View>
  );
}

export function Referentes({ header }: { header: ReactNode }) {
  const accounts = useAccounts();
  const [chosen, setChosen] = useState('');
  const account = chosen || accounts.data?.[0]?.id || '';
  const referents = useReferents(account);
  const observe = useObserveNow();
  const remove = useDeleteReferent();
  const toast = useToast();
  const { bottom } = useContentInsets();
  const [adding, setAdding] = useState(false);
  const [removing, setRemoving] = useState<Referent | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const list = referents.data ?? [];

  const refresh = async () => {
    setRefreshing(true);
    try {
      await Promise.all([accounts.refetch(), account ? referents.refetch() : Promise.resolve()]);
    } finally {
      setRefreshing(false);
    }
  };

  let top: ReactNode;
  if (accounts.isPending) top = <Skeleton variant="card" count={2} label="Cargando referentes…" />;
  else if (accounts.isError) top = <ErrorRetry error={accounts.error} onRetry={() => void accounts.refetch()} />;
  else if (!accounts.data.length) {
    top = (
      <Note tone="info" title="No hay ninguna cuenta de LinkedIn">
        Conecta la cuenta en el servidor para elegir referentes.
      </Note>
    );
  } else {
    top = (
      <>
        {accounts.data.length > 1 ? (
          <Select label="Cuenta" value={account} options={accounts.data.map((item) => ({ value: item.id, label: item.label }))} onChange={setChosen} testID="referent-account" />
        ) : null}
        <View style={styles.buttons}>
          <Button variant="primary" block icon={<Icon name="plus" size={20} color={colors.onBrand} />} onPress={() => setAdding(true)}>
            Añadir referente
          </Button>
          <Button
            block
            loading={observe.isPending}
            loadingLabel="Encolando…"
            onPress={() =>
              observe.mutate(account, {
                onSuccess: () => {
                  haptic('actionSuccess');
                  toast.show(OBSERVE_QUEUED);
                },
                onError: () => haptic('actionError'),
              })
            }
          >
            Observar ahora
          </Button>
        </View>
        <ErrorRetry error={observe.error} />
        {referents.isPending ? <Skeleton variant="card" count={2} label="Cargando referentes…" /> : null}
        <ErrorRetry error={referents.error} onRetry={() => void referents.refetch()} />
        {referents.isSuccess && !list.length ? (
          <EmptyState title="Aún no hay referentes">
            <EmptyText>Añade a alguien cuya conversación importe para tu barrio: el equipo empieza a descubrir personas en sus posts.</EmptyText>
          </EmptyState>
        ) : null}
      </>
    );
  }

  return (
    <>
      <FlatList
        testID="referentes-list"
        style={styles.screen}
        contentContainerStyle={[pageContent, styles.rows, { paddingBottom: bottom }]}
        data={accounts.data?.length ? list : []}
        keyExtractor={(referent) => referent.id}
        accessibilityLabel="Referentes"
        ListHeaderComponent={
          <View style={styles.header}>
            {header}
            {top}
          </View>
        }
        renderItem={({ item }) => <ReferentCard referent={item} onRemove={setRemoving} />}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => void refresh()} tintColor={colors.brandDeep} colors={[colors.brandDeep]} />}
      />
      {adding ? <AddReferentSheet account={account} onClose={() => setAdding(false)} /> : null}
      {removing ? (
        <ConfirmSheet
          title={`Quitar a ${referentName(removing)}`}
          confirmLabel="Quitar"
          tone="danger"
          busy={remove.isPending}
          error={remove.error}
          onClose={() => {
            remove.reset();
            setRemoving(null);
          }}
          onConfirm={() =>
            remove.mutate(removing.id, {
              onSuccess: () => {
                haptic('actionSuccess');
                toast.show('Referente quitado');
                setRemoving(null);
              },
              onError: () => haptic('actionError'),
            })
          }
        >
          El equipo deja de leer sus posts. Las personas que ya salieron de ellos siguen en el barrio. Si solo quieres una pausa, desactívalo.
        </ConfirmSheet>
      ) : null}
    </>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.paper },
  rows: { gap: space[3] },
  header: { gap: space[4], marginBottom: space[1] },
  buttons: { gap: space[2] },
  card: { padding: space[4], gap: space[2], backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.line, borderRadius: radius.md },
  head: { flexDirection: 'row', alignItems: 'center', gap: space[2] },
  grow: { flex: 1 },
  row: { flexDirection: 'row', gap: space[2] },
  actions: { gap: space[2] },
});
