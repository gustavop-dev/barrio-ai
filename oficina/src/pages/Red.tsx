import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useState, type FormEvent } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { asList, discardContact } from '../api/endpoints';
import { useContacts, useRedSummary } from '../api/hooks';
import { keys } from '../api/queryClient';
import { CONTACT_STAGES, type Contact, type ContactStage, type Paginated, type RedSummary } from '../api/types';
import { ContactClassificationView, ContactEvidence, contactName, ProfileLink } from '../components/Contact';
import { Badge, Empty, ErrorNote, Loading, Meter, Modal, PageHeader, type Tone } from '../components/ui';
import {
  actionStateLabel,
  AUTONOMY_MODE_LABEL,
  capabilityLabel,
  CONTACT_EVENT_LABEL,
  CONTACT_STAGE,
  contactStageLabel,
  formatDateTime,
  labelOf,
  money,
  NETWORK_READ_LABEL,
  networkDistanceLabel,
  timeAgo,
} from '../lib/format';
import { actionsHref } from './Acciones';

const STAGE_TONE: Record<string, Tone> = {
  candidate: 'muted',
  fit: 'info',
  followed: 'info',
  invited: 'warn',
  connected: 'ok',
  incoming: 'warn',
  closed: 'muted',
  discarded: 'muted',
};

const MODE_TONE: Record<string, Tone> = { auto: 'ok', approval: 'info', off: 'muted' };

const ACTION_TONE: Record<string, Tone> = { proposed: 'info', approved: 'info', executing: 'warn', sent: 'warn', uncertain: 'bad', failed: 'bad' };

/** Discarding is refused (409) once the contact is invited, connected, closed or already discarded. */
const DISCARDABLE: readonly ContactStage[] = ['candidate', 'fit', 'followed', 'incoming'];
export const canDiscard = (contact: Pick<Contact, 'stage'>) => DISCARDABLE.includes(contact.stage);

function isStage(value: string): value is ContactStage {
  return (CONTACT_STAGES as readonly string[]).includes(value);
}

function SummaryPanel({ data }: { data: RedSummary }) {
  const capacities = Object.entries(data.capacity ?? {}).sort(([a], [b]) => a.localeCompare(b));
  const readKeys = [...new Set([...Object.keys(data.read_caps ?? {}), ...Object.keys(data.reads_today ?? {})])] as (keyof RedSummary['read_caps'])[];
  const spent = Number(data.llm?.spent_today ?? 0);
  const budget = Number(data.llm?.daily ?? 0);
  const blocked = data.invites_blocked?.blocked;
  return (
    <>
      {!data.enabled ? (
        <div className="note warn" role="note">
          <strong>El bloque Red está apagado</strong>
          <p>
            Está desactivado en el servidor (<code>NETWORK_ENABLED=false</code>): la máquina no descubre, no clasifica ni propone acciones de
            red. Lo ya guardado sigue visible.
          </p>
        </div>
      ) : null}
      {blocked ? (
        <div className="note error" role="note">
          <strong>Invitaciones en pausa</strong>
          <p>
            LinkedIn rechazó invitaciones por límite en los últimos 7 días. La máquina no enviará invitaciones mientras dure la pausa.
            {data.invites_blocked.reason ? ` Motivo: ${data.invites_blocked.reason}` : ''}
          </p>
        </div>
      ) : null}
      <section className="card" aria-labelledby="red-today">
        <h2 id="red-today">Hoy</h2>
        {capacities.length ? (
          <div className="capacity">
            {capacities.map(([code, cap]) => (
              <div key={code} className="capblock">
                <div className="cardhead">
                  <p className="sectionlabel">
                    {capabilityLabel(code)} <span className="muted">({code})</span>
                  </p>
                  <Badge tone={MODE_TONE[cap.mode] ?? 'muted'}>Modo {labelOf(AUTONOMY_MODE_LABEL, cap.mode)}</Badge>
                </div>
                <Meter label={`${capabilityLabel(code)} hoy`} value={cap.daily_used} max={cap.daily} />
                <p className="muted small">
                  Quedan <strong>{cap.left}</strong> hoy · semana {cap.weekly_used} / {cap.weekly}
                </p>
              </div>
            ))}
          </div>
        ) : (
          <Empty>Sin topes de capacidad informados.</Empty>
        )}
        {capacities.some(([, cap]) => cap.mode === 'approval') ? (
          <p className="small">
            En modo aprobación, cada acción espera tu decisión. <Link to="/acciones?state=proposed">Ver las propuestas pendientes</Link>
          </p>
        ) : null}

        <p className="sectionlabel">LECTURAS EN LINKEDIN</p>
        {readKeys.length ? (
          readKeys.map((key) => (
            <Meter key={key} label={labelOf(NETWORK_READ_LABEL, key)} value={data.reads_today?.[key] ?? 0} max={data.read_caps?.[key] ?? 0} />
          ))
        ) : (
          <Empty>Sin lecturas informadas.</Empty>
        )}

        <p className="sectionlabel">CLASIFICACIÓN CON IA</p>
        <Meter label="Gasto LLM de la red" value={spent} max={budget} display={`${money(spent)} de ${money(budget)}`} />
        {data.llm?.model ? <p className="muted small">Modelo {data.llm.model}</p> : null}
        <p className="muted small">
          Último descubrimiento: {data.last_discovery_at ? timeAgo(data.last_discovery_at) : 'todavía no'} · última sincronización:{' '}
          {data.last_sync_at ? timeAgo(data.last_sync_at) : 'todavía no'}
        </p>
      </section>
    </>
  );
}

function StageFilter({ stage, counts, onChange }: { stage: ContactStage | ''; counts: RedSummary['stages'] | undefined; onChange: (stage: ContactStage | '') => void }) {
  const total = counts ? Object.values(counts).reduce((sum, n) => sum + (n ?? 0), 0) : null;
  return (
    <div className="chips" role="group" aria-label="Filtrar por etapa">
      <button type="button" className="chip" aria-pressed={!stage} onClick={() => onChange('')}>
        Todos {total !== null ? <strong>{total}</strong> : null}
      </button>
      {CONTACT_STAGES.map((value) => (
        <button key={value} type="button" className="chip" aria-pressed={stage === value} onClick={() => onChange(value)}>
          {contactStageLabel(value)} {counts ? <strong>{counts[value] ?? 0}</strong> : null}
        </button>
      ))}
    </div>
  );
}

function DiscardModal({ contact, onClose }: { contact: Contact; onClose: () => void }) {
  const queryClient = useQueryClient();
  const [note, setNote] = useState('');
  const mutation = useMutation({
    mutationFn: () => discardContact(contact.id, note.trim()),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: keys.redAll });
      // Its open action, if any, is rejected along with it.
      void queryClient.invalidateQueries({ queryKey: keys.actionsAll });
      void queryClient.invalidateQueries({ queryKey: keys.overview });
      void queryClient.invalidateQueries({ queryKey: keys.feed });
      onClose();
    },
  });
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (note.trim() && !mutation.isPending) mutation.mutate();
  };
  return (
    <Modal title="Descartar el contacto" onClose={onClose}>
      <form onSubmit={submit}>
        <p>
          {contactName(contact)} pasa a «Descartado» y la máquina no volverá a proponerlo.
          {contact.open_action ? ' Su acción abierta se veta.' : ''} Queda registrado con tu nota.
        </p>
        <label htmlFor="discard-note">Nota</label>
        <textarea
          id="discard-note"
          value={note}
          maxLength={2000}
          required
          onChange={(event) => setNote(event.target.value)}
          placeholder="Por qué no encaja"
        />
        <ErrorNote error={mutation.error} />
        <div className="buttonrow">
          <button type="button" className="secondary" onClick={onClose}>
            Cancelar
          </button>
          <button type="submit" className="danger" disabled={!note.trim() || mutation.isPending}>
            {mutation.isPending ? 'Enviando…' : 'Descartar'}
          </button>
        </div>
      </form>
    </Modal>
  );
}

function byNewest(a: { at: string }, b: { at: string }): number {
  return (new Date(b.at).getTime() || 0) - (new Date(a.at).getTime() || 0);
}

export function ContactCard({ contact }: { contact: Contact }) {
  const [discarding, setDiscarding] = useState(false);
  const titleId = `contact-${contact.id}`;
  const facts = [networkDistanceLabel(contact.network_distance), contact.location, contact.is_following ? 'Lo sigues' : ''].filter(Boolean);
  const history = [...(contact.history ?? [])].sort(byNewest).slice(0, 3);
  const open = contact.open_action;
  return (
    <article className="card contact" aria-labelledby={titleId}>
      <div className="cardhead">
        <h3 id={titleId}>
          <ProfileLink contact={contact} />
        </h3>
        <Badge tone={STAGE_TONE[contact.stage] ?? 'muted'}>{contactStageLabel(contact.stage)}</Badge>
      </div>
      {contact.headline ? <p>{contact.headline}</p> : null}
      {facts.length ? <p className="muted small">{facts.join(' · ')}</p> : null}
      <ContactEvidence contact={contact} />

      <p className="sectionlabel">CLASIFICACIÓN</p>
      <ContactClassificationView classification={contact.classification} detailed />

      {history.length ? (
        <>
          <p className="sectionlabel">HISTORIAL RECIENTE</p>
          <ol className="history">
            {history.map((entry, index) => (
              <li key={`${entry.at}-${index}`}>
                <strong>{labelOf(CONTACT_EVENT_LABEL, entry.event)}</strong>{' '}
                <time className="muted" dateTime={entry.at} title={formatDateTime(entry.at)}>
                  {timeAgo(entry.at)}
                </time>
                {entry.detail ? <span> · {entry.detail}</span> : null}
              </li>
            ))}
          </ol>
        </>
      ) : null}

      {open ? (
        <>
          <p className="sectionlabel">ACCIÓN ABIERTA</p>
          <p className="small">
            {capabilityLabel(open.capability)} <Badge tone={ACTION_TONE[open.state] ?? 'muted'}>{actionStateLabel(open.state)}</Badge>{' '}
            <Link to={actionsHref(open.capability, open.state)}>Ver en Acciones</Link>
          </p>
        </>
      ) : null}

      {canDiscard(contact) ? (
        <div className="buttonrow">
          <button type="button" className="danger" onClick={() => setDiscarding(true)}>
            Descartar
          </button>
        </div>
      ) : null}
      {discarding ? <DiscardModal contact={contact} onClose={() => setDiscarding(false)} /> : null}
    </article>
  );
}

export function Red() {
  const [params, setParams] = useSearchParams();
  const rawStage = params.get('etapa') ?? '';
  const stage: ContactStage | '' = isStage(rawStage) ? rawStage : '';
  const page = Math.max(1, Number(params.get('page') ?? '1') || 1);
  const summary = useRedSummary();
  const contacts = useContacts(stage, page);
  const paginated = contacts.data && !Array.isArray(contacts.data) ? (contacts.data as Paginated<Contact>) : null;
  // Also filtered here, so a previous page shown while the new filter loads never mixes stages.
  const list = asList(contacts.data).filter((contact) => !stage || contact.stage === stage);
  // Switching stages keeps the previous page as placeholder: show the loader, not a false «no hay contactos».
  const switching = contacts.isPlaceholderData && contacts.isFetching;

  const update = (next: { etapa?: ContactStage | ''; page?: number }) => {
    const nextStage = next.etapa ?? stage;
    const nextPage = next.page ?? 1;
    const search = new URLSearchParams();
    if (nextStage) search.set('etapa', nextStage);
    if (nextPage > 1) search.set('page', String(nextPage));
    setParams(search, { replace: true });
  };

  return (
    <div className="stack">
      <PageHeader eyebrow="CRECER LA RED" title="Red">
        Personas que comentan en los posts de tus referentes o aparecen en búsquedas. La máquina las clasifica y propone seguirlas, invitarlas
        sin nota o aceptar su invitación; cada acción se decide en Acciones.
      </PageHeader>

      {summary.isPending ? <Loading label="Leyendo el resumen de la red…" /> : null}
      {summary.isError ? <ErrorNote error={summary.error} onRetry={() => void summary.refetch()} /> : null}
      {summary.data ? <SummaryPanel data={summary.data} /> : null}

      <section className="stack" aria-labelledby="contacts-title">
        <h2 id="contacts-title">
          Contactos {paginated ? <span className="muted small">({paginated.count})</span> : null}
        </h2>
        <StageFilter stage={stage} counts={summary.data?.stages} onChange={(etapa) => update({ etapa })} />
        {stage ? (
          <p className="muted small">
            {contactStageLabel(stage)}: {CONTACT_STAGE[stage]?.hint}
          </p>
        ) : null}
        {contacts.isPending || (switching && !list.length) ? <Loading label="Cargando contactos…" /> : null}
        {contacts.isError ? <ErrorNote error={contacts.error} onRetry={() => void contacts.refetch()} /> : null}
        {contacts.isSuccess && !switching && !list.length ? (
          <Empty>
            {stage
              ? `No hay contactos en «${contactStageLabel(stage)}».`
              : 'Todavía no hay contactos. Aparecerán cuando la máquina lea los comentarios en los posts de tus referentes o haga búsquedas.'}
          </Empty>
        ) : null}
        {list.map((contact) => (
          <ContactCard key={contact.id} contact={contact} />
        ))}
        {paginated && (paginated.next || paginated.previous) ? (
          <div className="buttonrow pager">
            <button type="button" className="secondary" disabled={!paginated.previous} onClick={() => update({ page: page - 1 })}>
              ← Anteriores
            </button>
            <span className="muted small">Página {page}</span>
            <button type="button" className="secondary" disabled={!paginated.next} onClick={() => update({ page: page + 1 })}>
              Siguientes →
            </button>
          </div>
        ) : null}
      </section>
    </div>
  );
}
