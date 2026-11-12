import { useEffect, useId, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { lastActivity, stageCount, totalCount } from '../../../../compartido/src/logic/barrio';
import { agree, isFeminineName } from '../../../../compartido/src/logic/genero';
import { asList } from '../../api/endpoints';
import { useRedSummary } from '../../api/hooks';
import type { Contact, ContactStage, RedSummary } from '../../api/types';
import { IconFilter, IconSearch } from '../../components/icons';
import { Avatar, Badge, Button, ChipStrip, EmptyState, ErrorRetry, FilterChip, LabelChip, Note, Skeleton } from '../../components/ui';
import { CONTACT_MODALITY_LABEL, CONTACT_ROLE_LABEL, contactSourceLabel, labelOf } from '../../lib/format';
import { useContactPages } from './api';
import { FUNNEL_ASIDE, FUNNEL_MAIN, MODALITY_SHORT, personStage, SOURCE_FILTER, type PersonStage } from './labels';

// Shared with the native app (compartido/src/logic/barrio.ts).
export { lastActivity };

/** Warnings on top: the network off and invitations paused (red/summary). */
export function NetworkWarnings({ summary }: { summary: RedSummary | undefined }) {
  if (!summary) return null;
  return (
    <>
      {summary.enabled === false ? (
        <Note tone="warn" title="La red está apagada en el servidor">
          El equipo no descubre ni propone a nadie nuevo. Lo guardado sigue aquí.
        </Note>
      ) : null}
      {summary.invites_blocked?.blocked ? (
        <Note tone="warn" title="Invitaciones en pausa: LinkedIn las limitó">
          {summary.invites_blocked.reason ? <p>{summary.invites_blocked.reason}</p> : null}
          <p>El equipo sigue observando y siguiendo.</p>
        </Note>
      ) : null}
    </>
  );
}

function PersonRow({ contact, search, selected }: { contact: Contact; search: string; selected: boolean }) {
  const stage = personStage(contact.display_stage ?? contact.stage);
  const classification = contact.classification ?? {};
  const classified = Object.keys(classification).length > 0;
  return (
    <li>
      <Link to={{ pathname: `/personas/${encodeURIComponent(contact.id)}`, search }} className="person-row" aria-current={selected ? 'page' : undefined}>
        <Avatar name={contact.display_name} />
        <span className="person-row-body">
          <span className="person-row-top">
            <span className="person-row-name">{contact.display_name || contact.public_identifier || 'Sin nombre'}</span>
            <Badge tone={stage.tone}>{agree(stage.label, isFeminineName(contact.display_name))}</Badge>
          </span>
          {contact.headline ? <span className="person-row-headline">{contact.headline}</span> : null}
          <span className="person-row-chips">
            {classified && classification.role ? <LabelChip tone="info">{labelOf(CONTACT_ROLE_LABEL, classification.role)}</LabelChip> : null}
            {classified && classification.modality ? <LabelChip tone="muted">{MODALITY_SHORT[classification.modality] ?? classification.modality}</LabelChip> : null}
            {!classified ? <span className="person-row-meta">Sin clasificar todavía</span> : null}
          </span>
          <span className="person-row-meta">
            {contactSourceLabel(contact.source, contact.evidence)} · {lastActivity(contact)}
          </span>
          {contact.your_turn ? (
            <span className="person-row-turn">
              <Badge tone="warn">Te toca</Badge>
            </span>
          ) : null}
        </span>
      </Link>
    </li>
  );
}

function FilterSelect({ label, value, options, onChange }: { label: string; value: string; options: Record<string, string>; onChange: (value: string) => void }) {
  const id = useId();
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      <select id={id} value={value} onChange={(event) => onChange(event.target.value)}>
        <option value="">Todos</option>
        {Object.entries(options).map(([key, text]) => (
          <option key={key} value={key}>
            {text}
          </option>
        ))}
      </select>
    </div>
  );
}

/** Personas → Barrio: the funnel as filter chips, search and filters, and the list of people. */
export function Barrio({ selectedId }: { selectedId: string }) {
  const [params, setParams] = useSearchParams();
  const stage = params.get('etapa') ?? '';
  const q = params.get('q') ?? '';
  const role = params.get('rol') ?? '';
  const modality = params.get('modalidad') ?? '';
  const source = params.get('origen') ?? '';
  const [text, setText] = useState(q);
  const [moreOpen, setMoreOpen] = useState(Boolean(role || modality || source));
  const filtersId = useId();
  const summary = useRedSummary();
  const list = useContactPages({ stage: stage as PersonStage & ContactStage, q, role, modality, source });

  const update = (changes: Record<string, string>) => {
    setParams(
      (current) => {
        const next = new URLSearchParams(current);
        next.delete('pestana');
        for (const [key, value] of Object.entries(changes)) {
          if (value) next.set(key, value);
          else next.delete(key);
        }
        return next;
      },
      { replace: true },
    );
  };

  // The search box writes ?q= after a short pause.
  useEffect(() => {
    if (text.trim() === q) return;
    const timer = window.setTimeout(() => {
      setParams(
        (current) => {
          const next = new URLSearchParams(current);
          if (text.trim()) next.set('q', text.trim());
          else next.delete('q');
          return next;
        },
        { replace: true },
      );
    }, 300);
    return () => window.clearTimeout(timer);
  }, [text, q, setParams]);

  const people = (list.data?.pages ?? []).flatMap((page) => asList(page));
  const extraFilters = [role, modality, source].filter(Boolean).length;
  const anyFilter = Boolean(stage || q || extraFilters);
  const rowSearch = (() => {
    const next = new URLSearchParams(params);
    next.delete('pestana');
    const value = next.toString();
    return value ? `?${value}` : '';
  })();

  const chip = (key: PersonStage) => {
    const count = stageCount(summary.data, key);
    const meta = personStage(key);
    if (key === 'conversation' && summary.data && count === null) {
      return (
        <FilterChip key={key} pressed={false} unavailableLabel="aún no disponible">
          {meta.label}
        </FilterChip>
      );
    }
    return (
      <FilterChip key={key} pressed={stage === key} count={count} onClick={() => update({ etapa: stage === key ? '' : key })}>
        {meta.label}
      </FilterChip>
    );
  };

  return (
    <div className="barrio">
      <NetworkWarnings summary={summary.data} />
      <ChipStrip label="Filtrar por etapa">
        <FilterChip pressed={!stage} count={totalCount(summary.data)} onClick={() => update({ etapa: '' })}>
          Todas
        </FilterChip>
        {FUNNEL_MAIN.map(chip)}
        <span className="chip-gap" aria-hidden="true" />
        {FUNNEL_ASIDE.map(chip)}
      </ChipStrip>

      <div className="barrio-search">
        <label className="barrio-searchbox">
          <IconSearch size={20} />
          <span className="vh">Buscar por nombre</span>
          <input type="search" placeholder="Buscar por nombre" value={text} onChange={(event) => setText(event.target.value)} />
        </label>
        <button
          type="button"
          className="barrio-filterbutton"
          aria-expanded={moreOpen}
          aria-controls={filtersId}
          aria-label={`Más filtros: rol, modalidad y origen${extraFilters ? ` (${extraFilters} ${extraFilters === 1 ? 'activo' : 'activos'})` : ''}`}
          onClick={() => setMoreOpen((open) => !open)}
        >
          <IconFilter size={22} />
          {extraFilters ? (
            <span className="barrio-filtercount" aria-hidden="true">
              {extraFilters}
            </span>
          ) : null}
        </button>
      </div>
      {moreOpen ? (
        <div id={filtersId} className="barrio-filters">
          <FilterSelect label="Rol del barrio" value={role} options={CONTACT_ROLE_LABEL} onChange={(value) => update({ rol: value })} />
          <FilterSelect label="Modalidad" value={modality} options={CONTACT_MODALITY_LABEL} onChange={(value) => update({ modalidad: value })} />
          <FilterSelect label="Origen" value={source} options={SOURCE_FILTER} onChange={(value) => update({ origen: value })} />
        </div>
      ) : null}

      {list.isPending ? <Skeleton variant="row" count={6} label="Cargando personas…" /> : null}
      {list.isError && !list.data ? <ErrorRetry error={list.error} onRetry={() => void list.refetch()} /> : null}
      {list.isError && list.data ? <ErrorRetry title="No se pudo actualizar la lista" error={list.error} onRetry={() => void list.refetch()} /> : null}

      {list.data && !people.length ? (
        anyFilter ? (
          <EmptyState
            title={stage && !q && !extraFilters ? `Nadie en «${personStage(stage).label}» ahora mismo` : 'Nadie coincide con estos filtros'}
            action={
              <Button
                onClick={() => {
                  setText('');
                  update({ etapa: '', q: '', rol: '', modalidad: '', origen: '' });
                }}
              >
                Quitar filtros
              </Button>
            }
          />
        ) : (
          <EmptyState title="Aún no hay personas">El equipo empieza a descubrir cuando lee los comentarios de los referentes.</EmptyState>
        )
      ) : null}

      {people.length ? (
        <ul className="person-list" aria-label="Personas del barrio" aria-busy={list.isFetching && list.isPlaceholderData ? true : undefined}>
          {people.map((contact) => (
            <PersonRow key={contact.id} contact={contact} search={rowSearch} selected={contact.id === selectedId} />
          ))}
        </ul>
      ) : null}
      {list.hasNextPage ? (
        <Button block onClick={() => void list.fetchNextPage()} loading={list.isFetchingNextPage} loadingLabel="Cargando…">
          Cargar más
        </Button>
      ) : null}
    </div>
  );
}
