// A LinkedIn contact of the network block (Red): who it is, how it was found and how it was classified.
import type { ContactBrief, ContactClassification } from '../api/types';
import {
  CONTACT_AFFINITY_LABEL,
  CONTACT_MODALITY_LABEL,
  CONTACT_ROLE_LABEL,
  contactSourceLabel,
  excerpt,
  labelOf,
  networkDistanceLabel,
  percent,
} from '../lib/format';
import { Badge, ExternalLink } from './ui';

export function contactName(contact: Pick<ContactBrief, 'display_name' | 'public_identifier'>): string {
  return contact.display_name || contact.public_identifier || 'Contacto sin nombre';
}

/** The name, linked to the LinkedIn profile in a new tab (only https URLs become links). */
export function ProfileLink({ contact }: { contact: Pick<ContactBrief, 'display_name' | 'public_identifier' | 'profile_url'> }) {
  const name = contactName(contact);
  if (!contact.profile_url || !/^https:\/\//i.test(contact.profile_url)) return <>{name}</>;
  return (
    <a href={contact.profile_url} target="_blank" rel="noopener noreferrer">
      {name} <span aria-hidden="true">↗</span>
    </a>
  );
}

/** «Comentó en un post de …» with an excerpt of the comment, the search query or the invitation message. */
export function ContactEvidence({ contact }: { contact: Pick<ContactBrief, 'source' | 'evidence'> }) {
  const evidence = contact.evidence ?? {};
  const quote =
    contact.source === 'commenter' ? excerpt(evidence.comment) : contact.source === 'incoming' ? excerpt(evidence.invitation_message, 240) : '';
  return (
    <div className="evidence">
      <p className="small">
        <span className="muted">Origen: </span>
        {contactSourceLabel(contact.source, evidence)}
      </p>
      {quote ? <blockquote className="posttext">{quote}</blockquote> : null}
      {contact.source === 'commenter' ? <ExternalLink href={evidence.post_url}>Ver el post</ExternalLink> : null}
    </div>
  );
}

/** The person a RED-* action targets, as shown in /acciones. */
export function ContactPerson({ contact }: { contact: ContactBrief }) {
  const distance = networkDistanceLabel(contact.network_distance);
  return (
    <div className="origin person">
      <p className="sectionlabel">PERSONA</p>
      <p className="personname">
        <strong>
          <ProfileLink contact={contact} />
        </strong>
      </p>
      {contact.headline ? <p className="small">{contact.headline}</p> : null}
      {distance ? <p className="muted small">{distance}</p> : null}
      <ContactEvidence contact={contact} />
    </div>
  );
}

function isClassified(classification: ContactClassification | null | undefined): classification is ContactClassification {
  return Boolean(classification && Object.keys(classification).length);
}

/** Role, modality and reason; `detailed` adds affinity and confidence. `{}` means not classified yet. */
export function ContactClassificationView({ classification, detailed = false }: { classification: ContactClassification | null | undefined; detailed?: boolean }) {
  if (!isClassified(classification)) return <p className="muted small">Sin clasificar todavía.</p>;
  return (
    <div className="classification">
      {classification.fit === false ? (
        <p>
          <Badge tone="bad">No encaja</Badge>
        </p>
      ) : null}
      <dl className="facts">
        <dt>Rol</dt>
        <dd>{labelOf(CONTACT_ROLE_LABEL, classification.role)}</dd>
        <dt>Modalidad</dt>
        <dd>{labelOf(CONTACT_MODALITY_LABEL, classification.modality)}</dd>
        {detailed ? (
          <>
            <dt>Afinidad</dt>
            <dd>{labelOf(CONTACT_AFFINITY_LABEL, classification.affinity)}</dd>
            <dt>Confianza</dt>
            <dd>{percent(classification.confidence)}</dd>
          </>
        ) : null}
      </dl>
      {classification.reason ? <p>{classification.reason}</p> : null}
    </div>
  );
}
