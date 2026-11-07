import { useEffect, useRef, useState, type ReactNode } from 'react';
import { Link, useLocation } from 'react-router-dom';
import type { TuTurno, TurnoCard, TurnoRecent } from '../../api/types';
import { IconChevronDown } from '../../components/icons';
import { Badge, EmptyState, ErrorRetry, Section, Skeleton } from '../../components/ui';
import { activeCards, agoText, dayAndTime, doneTodaySentence, groupByPriority, longDate, PRIORITY_LABEL, splitLater, toAgent, type PriorityGroup } from './model';
import { TurnoCardView } from './TurnoCardView';
import { useSeenCards } from './useSeenCards';

/** The derived parts of GET /tu-turno that the view and its header share. */
export function pendingView(data: TuTurno | undefined) {
  const cards = data ? activeCards(data) : [];
  const groups = groupByPriority(cards);
  const { postponed, expired } = splitLater(data?.later);
  return { cards, groups, postponed, expired, recent: data?.recent ?? [] };
}

function Fold({ summary, children }: { summary: string; children: ReactNode }) {
  return (
    <details className="fold">
      <summary>
        {summary}
        <IconChevronDown size={20} />
      </summary>
      <div className="fold-body">{children}</div>
    </details>
  );
}

function FoldRow({ title, sub, badge }: { title: string; sub: string; badge: string }) {
  return (
    <li className="turno-row">
      <span className="turno-row-text">
        <span>{title}</span>
        {sub ? <span className="turno-meta">{sub}</span> : null}
      </span>
      <Badge tone="muted">{badge}</Badge>
    </li>
  );
}

function postponedTitle(card: TurnoCard): string {
  if (card.question) return `Responde ${toAgent(card.agent_label)}: ${card.question.question}`;
  return card.title;
}

function postponedSub(card: TurnoCard): string {
  const back = longDate(card.question?.postponed_until);
  return back ? `Vuelve el ${back} · no cuenta en el contador` : 'No cuenta en el contador';
}

function recentSorted(recent: readonly TurnoRecent[]): TurnoRecent[] {
  return [...recent].sort((a, b) => (b.at ?? '').localeCompare(a.at ?? ''));
}

/** Pospuestas, Hecho recientemente and «Cómo se ordena», folded, at the end. */
function Folds({ postponed, recent }: { postponed: TurnoCard[]; recent: TurnoRecent[] }) {
  return (
    <div className="turno-folds">
      {postponed.length ? (
        <Fold summary={`Pospuestas · ${postponed.length}`}>
          <ul className="turno-rows">
            {postponed.map((card) => (
              <FoldRow key={card.id} title={postponedTitle(card)} sub={postponedSub(card)} badge="Pospuesta" />
            ))}
          </ul>
        </Fold>
      ) : null}
      {recent.length ? (
        <Fold summary={`Hecho recientemente · ${recent.length}`}>
          <ul className="turno-rows">
            {recentSorted(recent).map((item) => (
              <FoldRow key={`${item.kind}:${item.id}:${item.at}`} title={item.title} sub={agoText(item.at)} badge={item.how} />
            ))}
          </ul>
        </Fold>
      ) : null}
      <Fold summary="Cómo se ordena lo que depende de ti">
        <p className="turno-explain">Urgente: algo se rompe o se queda bloqueado si no actúas. Pone el contador en rojo.</p>
        <p className="turno-explain">Importante: tiene plazo en menos de 48 h, alguien espera tu respuesta o algo caduca en unos días.</p>
        <p className="turno-explain">Cuando puedas: preguntas y tareas sin prisa. Si su plazo se acerca, suben solas a Importante.</p>
        <p className="turno-meta">Lo pospuesto sale del contador hasta su fecha. Lo informativo no entra aquí: va a Notificaciones.</p>
      </Fold>
    </div>
  );
}

/** Scrolls to /tu-turno#turno-<id> once the cards are there (the shell tries before they load). */
function useScrollToCard(ready: boolean) {
  const { hash } = useLocation();
  const done = useRef('');
  useEffect(() => {
    if (!ready || !hash || done.current === hash) return;
    const element = document.getElementById(decodeURIComponent(hash.slice(1)));
    if (!element) return;
    done.current = hash;
    element.scrollIntoView?.({ block: 'start' });
  }, [ready, hash]);
}

/**
 * Cards that were Nueva when they first showed keep «NUEVA» for the whole visit, although the
 * POST /vistos and the next refresh turn them into Vista.
 */
function useFreshIds(cards: readonly TurnoCard[]): ReadonlySet<string> {
  const [fresh, setFresh] = useState<ReadonlySet<string>>(() => new Set());
  const added = cards.filter((card) => card.state === 'nueva' && !fresh.has(card.id)).map((card) => card.id);
  if (added.length) setFresh((current) => new Set([...current, ...added]));
  return fresh;
}

function NothingPending({ data }: { data: TuTurno }) {
  const sentence = doneTodaySentence(data.summary?.done_today);
  const next = data.summary?.next_piece;
  return (
    <EmptyState title="Nada depende de ti hoy" action={<Link to="/calendario">Ver el Calendario</Link>}>
      {sentence ? <p>{sentence}</p> : null}
      {next ? <p>La próxima pieza sale {dayAndTime(next.scheduled_for)}.</p> : null}
    </EmptyState>
  );
}

function Groups({ groups, fresh }: { groups: PriorityGroup[]; fresh: ReadonlySet<string> }) {
  const observe = useSeenCards();
  return (
    <>
      {groups.map((group) => (
        <Section
          key={group.priority}
          id={`turno-${group.priority}`}
          label={`${PRIORITY_LABEL[group.priority]} · ${group.cards.length}`}
          intro={
            group.priority === 'cuando_puedas' && group.cards.some((card) => card.question)
              ? 'Lo que respondas pasa a la memoria confirmada: así el equipo puede contar experiencias reales.'
              : undefined
          }
        >
          {group.cards.map((card) => (
            <TurnoCardView key={card.id} card={card} priority={group.priority} isNew={card.state === 'nueva' || fresh.has(card.id)} observe={observe} />
          ))}
        </Section>
      ))}
    </>
  );
}

/** Pendiente: cards by priority, the expired ones in a neutral tone, then the folds. */
export function Pendiente({ query }: { query: { data: TuTurno | undefined; isPending: boolean; error: unknown; refetch: () => unknown } }) {
  const view = pendingView(query.data);
  const fresh = useFreshIds(view.cards);
  useScrollToCard(Boolean(query.data));

  if (query.isPending) return <Skeleton variant="card" count={3} label="Cargando lo que depende de ti…" />;
  if (!query.data) return <ErrorRetry error={query.error} onRetry={() => void query.refetch()} />;

  const nothing = view.groups.length === 0;
  const quiet = nothing && !view.postponed.length && !view.recent.length;
  return (
    <div className="turno-groups">
      {query.error ? <ErrorRetry error={query.error} onRetry={() => void query.refetch()} title="No se pudo actualizar" /> : null}
      {nothing ? <NothingPending data={query.data} /> : <Groups groups={view.groups} fresh={fresh} />}
      {view.expired.length ? (
        <Section id="turno-caducadas" label={`Ya no es urgente · ${view.expired.length}`}>
          {view.expired.map((card) => (
            <TurnoCardView key={card.id} card={card} priority={null} isNew={false} />
          ))}
        </Section>
      ) : null}
      {quiet ? null : <Folds postponed={view.postponed} recent={view.recent} />}
    </div>
  );
}
