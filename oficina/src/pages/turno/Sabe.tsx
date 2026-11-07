import { useId, useMemo, useState, type FormEvent } from 'react';
import { useAddHecho, useCorrectHecho, useHechos, useRetireHecho } from '../../api/hooks';
import type { MemoryFact } from '../../api/types';
import { IconPlus, IconSearch } from '../../components/icons';
import { Badge, Button, ConfirmModal, EmptyState, ErrorRetry, Modal, Skeleton, useToast } from '../../components/ui';
import { factOrigin, normalize, shortDate } from './model';
import { VisibilityField } from './VisibilityField';

/** The search shows up from this many facts on. */
export const SEARCH_FROM = 21;

function byNewest(a: MemoryFact, b: MemoryFact): number {
  return (b.updated_at ?? '').localeCompare(a.updated_at ?? '');
}

function FactCard({ fact, onEdit, onRetire }: { fact: MemoryFact; onEdit: () => void; onRetire: () => void }) {
  const meta = [factOrigin(fact), shortDate(fact.updated_at), fact.edits > 1 ? `v${fact.edits}` : ''].filter(Boolean).join(' · ');
  const topic = fact.topic || fact.key;
  return (
    <li className="card turno-fact">
      <div className="turno-head">
        <h3 className="turno-label">{topic}</h3>
        <Badge tone={fact.public_use ? 'ok' : 'muted'}>{fact.public_use ? 'Público' : 'Privado'}</Badge>
      </div>
      <p className="turno-body">{fact.text}</p>
      <p className="turno-meta">{meta}</p>
      <div className="turno-fact-actions">
        <Button size="small" onClick={onEdit} aria-label={`Editar: ${topic}`}>
          Editar
        </Button>
        <Button size="small" variant="danger" onClick={onRetire} aria-label={`Retirar: ${topic}`}>
          Retirar
        </Button>
      </div>
    </li>
  );
}

/** «Añadir algo que quieras que sepan» (new) and «Editar» (a new version of an existing fact). */
function FactModal({ fact, onClose }: { fact: MemoryFact | null; onClose: () => void }) {
  const toast = useToast();
  const add = useAddHecho();
  const correct = useCorrectHecho();
  const mutation = fact ? correct : add;
  const [text, setText] = useState(fact?.text ?? '');
  const [topic, setTopic] = useState('');
  const [publicUse, setPublicUse] = useState(fact?.public_use ?? false);
  const id = useId();

  const submit = async (event: FormEvent) => {
    event.preventDefault();
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
      // Shown inside the modal.
    }
  };

  return (
    <Modal title={fact ? 'Editar lo que sabe el equipo' : 'Añadir algo que quieras que sepan'} onClose={onClose} busy={mutation.isPending}>
      <form className="confirm" onSubmit={submit} noValidate>
        {fact ? <p className="turno-meta">{fact.topic || fact.key}</p> : null}
        <div className="field">
          <label htmlFor={`${id}-text`}>{fact ? 'Texto' : 'Qué quieres que sepan'}</label>
          <textarea id={`${id}-text`} rows={4} maxLength={4000} required value={text} onChange={(event) => setText(event.target.value)} />
        </div>
        {fact ? null : (
          <div className="field">
            <label htmlFor={`${id}-topic`}>
              Tema<span className="field-flag"> · opcional</span>
            </label>
            <input id={`${id}-topic`} maxLength={200} placeholder="Por ejemplo: Límites" value={topic} onChange={(event) => setTopic(event.target.value)} />
          </div>
        )}
        <VisibilityField value={publicUse} onChange={setPublicUse} disabled={mutation.isPending} />
        <p className="turno-meta">{fact ? 'Se guarda como una versión nueva; la anterior queda en el historial.' : 'Se confirma al guardar: lo escribes tú.'}</p>
        <ErrorRetry error={mutation.error} />
        <div className="confirm-actions">
          <Button onClick={onClose} disabled={mutation.isPending}>
            Cancelar
          </Button>
          <Button type="submit" variant="primary" disabled={!text.trim()} loading={mutation.isPending} loadingLabel="Guardando…">
            Guardar
          </Button>
        </div>
      </form>
    </Modal>
  );
}

function RetireModal({ fact, onClose }: { fact: MemoryFact; onClose: () => void }) {
  const toast = useToast();
  const retire = useRetireHecho();
  return (
    <ConfirmModal
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
          // Shown inside the modal.
        }
      }}
      onClose={onClose}
    >
      <p>
        El equipo deja de usar «{fact.topic || fact.key}» desde ahora. Si vuelve a hacer falta, te lo preguntará.
      </p>
    </ConfirmModal>
  );
}

/** «Lo que el equipo sabe de ti»: the confirmed facts, with Editar, Retirar, Añadir and a search past 20. */
export function Sabe() {
  const hechos = useHechos();
  const [adding, setAdding] = useState(false);
  const [editing, setEditing] = useState<MemoryFact | null>(null);
  const [retiring, setRetiring] = useState<MemoryFact | null>(null);
  const [search, setSearch] = useState('');
  const searchId = useId();

  const facts = useMemo(() => [...(hechos.data ?? [])].sort(byNewest), [hechos.data]);
  const searchable = facts.length >= SEARCH_FROM;
  const needle = searchable ? normalize(search.trim()) : '';
  const shown = needle ? facts.filter((fact) => normalize(`${fact.topic} ${fact.text}`).includes(needle)) : facts;

  return (
    <div className="turno-sabe">
      <p className="turno-intro">Esto es lo único que el equipo puede contar de ti. Nadie inventará tus experiencias, clientes ni servicios.</p>
      <Button block icon={<IconPlus size={20} />} onClick={() => setAdding(true)}>
        Añadir algo que quieras que sepan
      </Button>
      {hechos.isPending ? <Skeleton variant="row" count={3} label="Cargando lo que sabe el equipo…" /> : null}
      {hechos.isError && !hechos.data ? <ErrorRetry error={hechos.error} onRetry={() => void hechos.refetch()} /> : null}
      {hechos.data && !facts.length ? (
        <EmptyState title="Aún no hay nada confirmado">
          <p>Nadie inventará tus experiencias, clientes ni servicios: responde las preguntas del equipo para que puedan usarlas.</p>
        </EmptyState>
      ) : null}
      {searchable ? (
        <div className="field turno-search">
          <label htmlFor={searchId} className="vh">
            Buscar en lo que sabe el equipo
          </label>
          <span className="turno-search-icon" aria-hidden="true">
            <IconSearch size={20} />
          </span>
          <input id={searchId} type="search" placeholder="Buscar" value={search} onChange={(event) => setSearch(event.target.value)} />
          <p className="turno-meta" role="status">
            {needle ? `${shown.length} de ${facts.length}` : `${facts.length} datos`}
          </p>
        </div>
      ) : null}
      {facts.length ? (
        shown.length ? (
          <ul className="turno-facts">
            {shown.map((fact) => (
              <FactCard key={fact.key} fact={fact} onEdit={() => setEditing(fact)} onRetire={() => setRetiring(fact)} />
            ))}
          </ul>
        ) : (
          <p className="turno-meta">Nada coincide con «{search.trim()}».</p>
        )
      ) : null}
      {adding ? <FactModal fact={null} onClose={() => setAdding(false)} /> : null}
      {editing ? <FactModal fact={editing} onClose={() => setEditing(null)} /> : null}
      {retiring ? <RetireModal fact={retiring} onClose={() => setRetiring(null)} /> : null}
    </div>
  );
}
