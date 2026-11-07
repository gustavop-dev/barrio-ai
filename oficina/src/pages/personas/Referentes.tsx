import { useId, useState, type FormEvent } from 'react';
import { useAccounts, useDeleteReferent, useReferents, useUpdateReferent } from '../../api/hooks';
import type { Referent } from '../../api/types';
import { IconPlus } from '../../components/icons';
import { Badge, Button, ConfirmModal, EmptyState, ErrorRetry, ExternalLink, Modal, Note, Skeleton, useToast } from '../../components/ui';
import { observedAgo, referentName } from '../../../../compartido/src/logic/barrio';
import { normalizeProfileUrl, useAddReferent, useObserveNow } from './api';

function AddReferentModal({ account, onClose }: { account: string; onClose: () => void }) {
  const add = useAddReferent();
  const toast = useToast();
  const urlId = useId();
  const reasonId = useId();
  const [url, setUrl] = useState('');
  const [reason, setReason] = useState('');
  const [touched, setTouched] = useState(false);
  const normalized = normalizeProfileUrl(url);
  const urlError = touched && !normalized ? 'Pega la URL de un perfil: https://www.linkedin.com/in/…' : null;
  const reasonError = touched && !reason.trim() ? 'El motivo es obligatorio.' : null;

  const submit = (event: FormEvent) => {
    event.preventDefault();
    setTouched(true);
    if (!normalized || !reason.trim() || add.isPending) return;
    add.mutate(
      { account, identifier: normalized, reason: reason.trim() },
      {
        onSuccess: () => {
          toast.show('Referente añadido');
          onClose();
        },
      },
    );
  };

  return (
    <Modal title="Añadir referente" onClose={onClose} busy={add.isPending}>
      <form className="confirm" onSubmit={submit} noValidate>
        <p className="confirm-text">Una voz cuya conversación importa para tu barrio. El equipo lee sus posts y descubre a quien comenta.</p>
        <div className="field">
          <label htmlFor={urlId}>URL del perfil en LinkedIn</label>
          <input
            id={urlId}
            type="url"
            inputMode="url"
            autoCapitalize="none"
            spellCheck={false}
            placeholder="https://www.linkedin.com/in/…"
            value={url}
            onChange={(event) => setUrl(event.target.value)}
            aria-invalid={Boolean(urlError)}
            aria-describedby={urlError ? `${urlId}-error` : undefined}
          />
          {urlError ? (
            <p id={`${urlId}-error`} className="field-error">
              {urlError}
            </p>
          ) : null}
        </div>
        <div className="field">
          <label htmlFor={reasonId}>
            Motivo <span className="field-flag">· obligatorio</span>
          </label>
          <textarea
            id={reasonId}
            rows={3}
            maxLength={1000}
            placeholder="Por qué su conversación importa para tu barrio"
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            aria-invalid={Boolean(reasonError)}
            aria-describedby={reasonError ? `${reasonId}-error` : undefined}
          />
          {reasonError ? (
            <p id={`${reasonId}-error`} className="field-error">
              {reasonError}
            </p>
          ) : null}
        </div>
        <ErrorRetry error={add.error} />
        <div className="confirm-actions">
          <Button onClick={onClose} disabled={add.isPending}>
            Cancelar
          </Button>
          <Button type="submit" variant="primary" loading={add.isPending} loadingLabel="Guardando…">
            Añadir referente
          </Button>
        </div>
      </form>
    </Modal>
  );
}

function ReferentCard({ referent, onRemove }: { referent: Referent; onRemove: (referent: Referent) => void }) {
  const update = useUpdateReferent();
  const toast = useToast();
  const active = referent.active !== false;
  const name = referentName(referent);
  const count = referent.contacts_count;
  const observed = referent.last_observed_at ? `Observado ${observedAgo(referent.last_observed_at)}` : 'Aún sin observar';
  const people = typeof count === 'number' ? ` · ${count} ${count === 1 ? 'persona del barrio salió' : 'personas del barrio salieron'} de sus posts` : '';

  const toggle = () => {
    update.mutate(
      { referentId: referent.id, patch: { active: !active } },
      {
        onSuccess: () =>
          toast.show(active ? 'Referente desactivado' : 'Referente reactivado', {
            undo: () => update.mutate({ referentId: referent.id, patch: { active } }),
          }),
      },
    );
  };

  return (
    <li className="ref-card">
      <div className="ref-head">
        {referent.profile_url && /^https:\/\//i.test(referent.profile_url) ? (
          <ExternalLink href={referent.profile_url} className="ref-name">
            {name}
          </ExternalLink>
        ) : (
          <span className="ref-name">{name}</span>
        )}
        {active ? <Badge tone="ok">Activo</Badge> : <Badge tone="muted">Inactivo</Badge>}
      </div>
      {referent.reason ? <p className="ref-reason">{referent.reason}</p> : null}
      <p className="ref-meta">
        {observed}
        {people}
      </p>
      <ErrorRetry error={update.error} />
      <div className="ref-actions">
        <Button size="small" onClick={toggle} loading={update.isPending} loadingLabel="Guardando…">
          {active ? 'Desactivar' : 'Reactivar'} <span className="vh">a {name}</span>
        </Button>
        <Button size="small" variant="danger" onClick={() => onRemove(referent)}>
          Quitar <span className="vh">a {name}</span>
        </Button>
      </div>
    </li>
  );
}

/** Personas → Referentes: who the team reads to discover people, «Observar ahora», deactivate and remove. */
export function Referentes() {
  const accounts = useAccounts();
  const [chosen, setChosen] = useState('');
  const account = chosen || accounts.data?.[0]?.id || '';
  const referents = useReferents(account);
  const observe = useObserveNow();
  const remove = useDeleteReferent();
  const toast = useToast();
  const accountId = useId();
  const [adding, setAdding] = useState(false);
  const [removing, setRemoving] = useState<Referent | null>(null);

  if (accounts.isPending) return <Skeleton variant="card" count={2} label="Cargando referentes…" />;
  if (accounts.isError) return <ErrorRetry error={accounts.error} onRetry={() => void accounts.refetch()} />;
  if (!accounts.data.length) {
    return (
      <Note tone="info" title="No hay ninguna cuenta de LinkedIn">
        Conecta la cuenta en el servidor para elegir referentes.
      </Note>
    );
  }

  const list = referents.data ?? [];
  return (
    <div className="referentes">
      {accounts.data.length > 1 ? (
        <div className="field">
          <label htmlFor={accountId}>Cuenta</label>
          <select id={accountId} value={account} onChange={(event) => setChosen(event.target.value)}>
            {accounts.data.map((item) => (
              <option key={item.id} value={item.id}>
                {item.label}
              </option>
            ))}
          </select>
        </div>
      ) : null}
      <div className="ref-buttons">
        <Button variant="primary" block icon={<IconPlus size={20} />} onClick={() => setAdding(true)}>
          Añadir referente
        </Button>
        <Button
          block
          loading={observe.isPending}
          loadingLabel="Encolando…"
          onClick={() => observe.mutate(account, { onSuccess: () => toast.show('Observación encolada. Los posts nuevos aparecerán en unos minutos') })}
        >
          Observar ahora
        </Button>
      </div>
      <ErrorRetry error={observe.error} />
      {referents.isPending ? <Skeleton variant="card" count={2} label="Cargando referentes…" /> : null}
      <ErrorRetry error={referents.error} onRetry={() => void referents.refetch()} />
      {referents.isSuccess && !list.length ? (
        <EmptyState title="Aún no hay referentes">Añade a alguien cuya conversación importe para tu barrio: el equipo empieza a descubrir personas en sus posts.</EmptyState>
      ) : null}
      {list.length ? (
        <ul className="ref-list" aria-label="Referentes">
          {list.map((referent) => (
            <ReferentCard key={referent.id} referent={referent} onRemove={setRemoving} />
          ))}
        </ul>
      ) : null}

      {adding ? <AddReferentModal account={account} onClose={() => setAdding(false)} /> : null}
      {removing ? (
        <ConfirmModal
          title={`Quitar a ${referentName(removing)}`}
          confirmLabel="Quitar"
          busyLabel="Quitando…"
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
                toast.show('Referente quitado');
                setRemoving(null);
              },
            })
          }
        >
          El equipo deja de leer sus posts. Las personas que ya salieron de ellos siguen en el barrio. Si solo quieres una pausa, desactívalo.
        </ConfirmModal>
      ) : null}
    </div>
  );
}
