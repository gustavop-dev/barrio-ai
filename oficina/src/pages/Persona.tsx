import { useId, useState, type FormEvent } from 'react';
import { Link, useLocation, useParams } from 'react-router-dom';
import { ApiError } from '../api/client';
import { useAddContactNote, useContact, useDiscardContact, useOportunidades } from '../api/hooks';
import type { Contact, ContactHistoryEntry, ContactNote, Opportunity } from '../api/types';
import { useSession } from '../auth/session';
import { useCapture } from '../capture/CaptureContext';
import { useTopBarBack } from '../components/Layout';
import { IconChevronLeft, IconExternal, IconMicrofono, IconPlus } from '../components/icons';
import {
  Avatar,
  Badge,
  Button,
  ButtonLink,
  Card,
  ConfirmModal,
  EmptyState,
  ErrorRetry,
  EXTERNAL_HINT_ID,
  ExternalLink,
  isHttps,
  LabelChip,
  Section,
  Skeleton,
  StageTrack,
  useToast,
} from '../components/ui';
import {
  actionStateLabel,
  capabilityLabel,
  CONTACT_AFFINITY_LABEL,
  CONTACT_EVENT_LABEL,
  CONTACT_MODALITY_LABEL,
  CONTACT_ROLE_LABEL,
  contactSourceLabel,
  excerpt,
  formatTime,
  labelOf,
  networkDistanceLabel,
} from '../lib/format';
import { journey } from './personas/journey';
import {
  ATTRIBUTION_LABEL,
  CHANNEL_LABEL,
  daysInStage,
  DISCARDABLE,
  labelFrom,
  longDate,
  personStage,
  relativeDay,
  shortDate,
} from './personas/labels';
import { OportunidadForm } from './personas/OportunidadForm';
import './personas/personas.css';

function displayName(contact: Contact): string {
  return contact.display_name || contact.public_identifier || 'Sin nombre';
}

/** «hoy 10:12», «ayer 18:03» or «6 nov». */
function when(iso: string): string {
  const day = relativeDay(iso);
  return day === 'hoy' || day === 'ayer' ? `${day} ${formatTime(iso)}` : day;
}

function NextStep({ contact }: { contact: Contact }) {
  const step = contact.next_step;
  if (!step) return null;
  const mine = step.owner === 'gustavo' || contact.your_turn;
  const owner = mine ? 'Te toca' : step.owner === 'equipo' ? 'Equipo' : null;
  const at = step.at ? (mine ? `Para el ${shortDate(step.at)}` : `A partir del ${shortDate(step.at)}`) : null;
  return (
    <Card as="section" tone={mine ? 'warn' : 'default'} className="persona-next" aria-label="Siguiente paso">
      <p className="persona-label">
        Siguiente paso{owner ? ` · ${owner}` : ''}
      </p>
      <p className="persona-text">{step.text}</p>
      {at ? <p className="persona-meta">{at}</p> : null}
      {step.action ? (
        <p className="persona-meta">
          {capabilityLabel(step.action.capability)} · {actionStateLabel(step.action.state)} · <Link to="/calendario">Ver en el Calendario</Link>
        </p>
      ) : null}
      {contact.your_turn ? (
        <ButtonLink to="/tu-turno" block>
          Ir a Tu turno
        </ButtonLink>
      ) : null}
    </Card>
  );
}

function WhyFits({ contact }: { contact: Contact }) {
  const c = contact.classification ?? {};
  if (!Object.keys(c).length) {
    return (
      <Card>
        <p className="persona-meta">Sin clasificar todavía. El equipo la clasificará en el próximo ciclo.</p>
      </Card>
    );
  }
  const confidence = typeof c.confidence === 'number' ? Math.round(Math.min(1, Math.max(0, c.confidence)) * 100) : null;
  return (
    <Card className="persona-block">
      <div className="persona-chips">
        {c.fit === false ? <Badge tone="bad">No encaja</Badge> : null}
        {c.role ? <LabelChip tone="info">{labelOf(CONTACT_ROLE_LABEL, c.role)}</LabelChip> : null}
        {c.modality ? <LabelChip tone="muted">{labelOf(CONTACT_MODALITY_LABEL, c.modality)}</LabelChip> : null}
        {c.affinity ? <LabelChip tone="muted">{labelOf(CONTACT_AFFINITY_LABEL, c.affinity)}</LabelChip> : null}
      </div>
      {c.reason ? <p className="persona-text">{c.reason}</p> : null}
      {confidence !== null ? (
        <>
          <div className="persona-row">
            <p className="persona-meta">Confianza</p>
            <p className="persona-small">{confidence} %</p>
          </div>
          <div className="persona-bar" role="img" aria-label={`Confianza ${confidence} %`}>
            <span style={{ width: `${confidence}%` }} />
          </div>
        </>
      ) : null}
      {c.classified_at ? <p className="persona-meta">Clasificada el {longDate(c.classified_at)}</p> : null}
    </Card>
  );
}

function Origin({ contact }: { contact: Contact }) {
  const evidence = contact.evidence ?? {};
  const quote = contact.source === 'commenter' ? excerpt(evidence.comment, 280) : contact.source === 'incoming' ? excerpt(evidence.invitation_message, 280) : '';
  return (
    <Card className="persona-block tight">
      <p className="persona-text">{contactSourceLabel(contact.source, evidence)}</p>
      {quote ? <blockquote className="persona-quote">“{quote}”</blockquote> : null}
      {contact.source === 'commenter' ? <ExternalLink href={evidence.post_url}>Ver el post</ExternalLink> : null}
    </Card>
  );
}

function OpportunityBlock({ contact, onEdit }: { contact: Contact; onEdit: (opportunity: Opportunity) => void }) {
  const brief = contact.opportunity;
  const list = useOportunidades({ contact: contact.id });
  if (!brief) return null;
  const full = list.data ? (Array.isArray(list.data) ? list.data : list.data.results).find((item) => item.id === brief.id) : undefined;
  const nextText = [full?.next_action ?? brief.next_action, relativeDay(full?.next_action_at ?? brief.next_action_at)].filter(Boolean).join(' · ');
  const fields: [string, string][] = [];
  if (full?.need) fields.push(['Necesidad', full.need]);
  if (full) fields.push(['Canal', labelFrom(CHANNEL_LABEL, full.channel)]);
  if (full) fields.push(['Cómo llegó', labelFrom(ATTRIBUTION_LABEL, full.attribution)]);
  if (full?.budget) fields.push(['Presupuesto', full.budget]);
  if (full?.dedication) fields.push(['Dedicación', full.dedication]);
  if (nextText) fields.push(['Siguiente acción', nextText]);
  return (
    <Section label="Oportunidad">
      <Card className="persona-block">
        <div className="persona-row wrap">
          <Badge tone="ok">{brief.stage_label}</Badge>
          {full ? <p className="persona-meta">{daysInStage(full.days_in_stage)}</p> : null}
        </div>
        {fields.map(([label, value]) => (
          <div key={label} className="persona-field">
            <p className="persona-label">{label}</p>
            <p className="persona-text">{value}</p>
          </div>
        ))}
        <ErrorRetry error={list.error} onRetry={() => void list.refetch()} />
        {full ? (
          <Button block onClick={() => onEdit(full)}>
            Editar oportunidad
          </Button>
        ) : null}
      </Card>
    </Section>
  );
}

function Notes({ contact }: { contact: Contact }) {
  const session = useSession();
  const { openCapture } = useCapture();
  const add = useAddContactNote();
  const toast = useToast();
  const fieldId = useId();
  const [writing, setWriting] = useState(false);
  const [text, setText] = useState('');
  const me = session.data?.user?.username;
  const notes: ContactNote[] = [...(contact.notes ?? [])].reverse();

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!text.trim() || add.isPending) return;
    add.mutate(
      { contactId: contact.id, text: text.trim() },
      {
        onSuccess: () => {
          setText('');
          setWriting(false);
          toast.show('Nota guardada');
        },
      },
    );
  };

  return (
    <Section label="Notas">
      <Card className="persona-block tight">
        {notes.length ? (
          <ul className="persona-notes">
            {notes.map((note) => (
              <li key={note.id}>
                <p className="persona-text">{note.text}</p>
                <p className="persona-meta">
                  {note.by && note.by !== me ? `Nota de ${note.by}` : 'Tu nota'} · {shortDate(note.at)}
                </p>
              </li>
            ))}
          </ul>
        ) : (
          <p className="persona-meta">Aún no hay notas sobre esta persona.</p>
        )}
        {writing ? (
          <form className="persona-noteform" onSubmit={submit}>
            <div className="field">
              <label htmlFor={fieldId}>Nota</label>
              <textarea id={fieldId} rows={3} value={text} autoFocus onChange={(event) => setText(event.target.value)} />
            </div>
            <ErrorRetry error={add.error} />
            <div className="persona-actions">
              <Button
                onClick={() => {
                  setWriting(false);
                  setText('');
                  add.reset();
                }}
                disabled={add.isPending}
              >
                Cancelar
              </Button>
              <Button type="submit" variant="primary" disabled={!text.trim()} loading={add.isPending} loadingLabel="Guardando…">
                Guardar nota
              </Button>
            </div>
          </form>
        ) : (
          <div className="persona-actions">
            <Button icon={<IconPlus size={20} />} onClick={() => setWriting(true)}>
              Añadir nota
            </Button>
            <Button icon={<IconMicrofono size={20} />} onClick={() => openCapture({ tipo: 'persona', id: contact.id, label: displayName(contact) })}>
              Nota de voz
            </Button>
          </div>
        )}
      </Card>
    </Section>
  );
}

function History({ entries }: { entries: ContactHistoryEntry[] }) {
  const ordered = [...entries].sort((a, b) => (a.at < b.at ? 1 : a.at > b.at ? -1 : 0));
  if (!ordered.length) return <p className="persona-meta">Sin eventos todavía.</p>;
  return (
    <ul className="persona-history">
      {ordered.map((entry, index) => (
        <li key={`${entry.at}-${index}`}>
          <div className="persona-history-body">
            <p className="persona-text">{CONTACT_EVENT_LABEL[entry.event] ?? entry.event}</p>
            {entry.detail ? <p className="persona-meta">{entry.detail}</p> : null}
          </div>
          <p className="persona-meta">
            <time dateTime={entry.at}>{when(entry.at)}</time>
          </p>
        </li>
      ))}
    </ul>
  );
}

/** /personas/:contactId: the person card (rendered next to the list on desktop). */
export function Persona() {
  const { contactId = '' } = useParams();
  const { search } = useLocation();
  const backTo = `/personas${search}`;
  useTopBarBack({ to: backTo, label: 'Personas' });
  const contact = useContact(contactId);
  const discard = useDiscardContact();
  const toast = useToast();
  const [form, setForm] = useState<{ opportunity: Opportunity | null } | null>(null);
  const [discarding, setDiscarding] = useState(false);

  const back = (
    <Link to={backTo} className="persona-back">
      <IconChevronLeft size={20} />
      Personas
    </Link>
  );

  if (contact.isPending) {
    return (
      <div className="persona">
        {back}
        <Skeleton variant="card" count={2} label="Cargando la ficha…" />
      </div>
    );
  }
  if (contact.isError && !contact.data) {
    const missing = contact.error instanceof ApiError && contact.error.status === 404;
    return (
      <div className="persona">
        {back}
        {missing ? (
          <EmptyState
            title="No encontramos a esta persona"
            action={
              <ButtonLink to={backTo} variant="secondary">
                Volver a Personas
              </ButtonLink>
            }
          >
            Puede que el enlace sea viejo.
          </EmptyState>
        ) : (
          <ErrorRetry error={contact.error} onRetry={() => void contact.refetch()} />
        )}
      </div>
    );
  }

  const person = contact.data;
  const name = displayName(person);
  const stage = personStage(person.display_stage ?? person.stage);
  const meta = [person.location, networkDistanceLabel(person.network_distance), person.is_following ? 'Lo sigues' : ''].filter(Boolean);
  const canDiscard = DISCARDABLE.includes(person.stage);

  return (
    <article className="persona" aria-labelledby="persona-nombre">
      {back}
      <header className="persona-head">
        <div className="persona-top">
          <Avatar name={name} size={48} />
          <Badge tone={stage.tone}>{stage.label}</Badge>
        </div>
        <h2 id="persona-nombre" className="persona-name">
          {isHttps(person.profile_url) ? (
            <a href={person.profile_url} target="_blank" rel="noopener noreferrer" aria-describedby={EXTERNAL_HINT_ID}>
              {name}
              <IconExternal size={22} />
            </a>
          ) : (
            name
          )}
        </h2>
        {person.headline ? <p className="persona-headline">{person.headline}</p> : null}
        {meta.length ? <p className="persona-meta">{meta.join(' · ')}</p> : null}
        <div className="persona-buttons">
          {isHttps(person.profile_url) ? (
            <ButtonLink
              href={person.profile_url}
              target="_blank"
              rel="noopener noreferrer"
              aria-describedby={EXTERNAL_HINT_ID}
              variant="primary"
              block
              icon={<IconExternal size={20} />}
            >
              Abrir en LinkedIn
            </ButtonLink>
          ) : null}
          {!person.opportunity ? (
            <Button block onClick={() => setForm({ opportunity: null })}>
              Marcar como oportunidad
            </Button>
          ) : null}
          {canDiscard ? (
            <Button block variant="danger" onClick={() => setDiscarding(true)}>
              Descartar
            </Button>
          ) : null}
        </div>
      </header>

      {contact.isError ? <ErrorRetry title="No se pudo actualizar la ficha" error={contact.error} onRetry={() => void contact.refetch()} /> : null}

      <NextStep contact={person} />

      <Section label="Recorrido">
        <StageTrack stages={journey(person)} label={`Recorrido de ${name}`} />
      </Section>

      <Section label="Por qué encaja">
        <WhyFits contact={person} />
      </Section>

      <Section label="De dónde salió">
        <Origin contact={person} />
      </Section>

      <Section label="Conversación">
        <Card tone="dashed" className="persona-block tight">
          <p className="persona-text">Aún no disponible</p>
          <p className="persona-meta">Cuando conectemos el inbox de LinkedIn verás aquí el resumen del analista y los últimos mensajes.</p>
          {isHttps(person.profile_url) ? <ExternalLink href={person.profile_url}>Abrir en LinkedIn</ExternalLink> : null}
        </Card>
      </Section>

      <OpportunityBlock contact={person} onEdit={(opportunity) => setForm({ opportunity })} />

      <Notes contact={person} />

      <Section label="Historial completo">
        <History entries={person.history ?? []} />
      </Section>

      {form ? (
        <OportunidadForm
          opportunity={form.opportunity}
          person={{ id: person.id, display_name: name, headline: person.headline, modality: person.classification?.modality }}
          onClose={() => setForm(null)}
        />
      ) : null}
      {discarding ? (
        <ConfirmModal
          title={`Descartar a ${name}`}
          confirmLabel="Descartar"
          busyLabel="Descartando…"
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
                  setDiscarding(false);
                  toast.show('Descartada: no volverá a proponerse');
                },
              },
            )
          }
        >
          No volverá a proponerse: el equipo no la seguirá ni la invitará. Si tiene una acción abierta, se veta.
        </ConfirmModal>
      ) : null}
    </article>
  );
}
