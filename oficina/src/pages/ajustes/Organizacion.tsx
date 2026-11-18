// Ajustes › Organización (GET /api/v1/organizacion, organizaciones phase 7): only its admin. The company's profile, read
// only and compact, and its members with their state: nothing private of anyone (no conversations, drafts or notes).
import { memberAccounts, memberBadges, memberSubtitle } from '../../../../compartido/src/logic/miembro';
import { useOrganizacion } from '../../api/hooks';
import { IconChevronDown } from '../../components/icons';
import { Badge, Card, ErrorRetry, Section, Skeleton } from '../../components/ui';
import { isUnavailable, Row, Unavailable } from './shared';

export function OrganizacionSection() {
  const organizacion = useOrganizacion();
  const data = organizacion.data;
  return (
    <Section label="Organización" id="organizacion" intro="Lo que comparten todos los miembros. Solo lo ves tú, como administrador.">
      {organizacion.isPending ? <Skeleton variant="card" label="Cargando la organización…" /> : null}
      {isUnavailable(organizacion.error) ? (
        <Unavailable>El servidor todavía no muestra la organización.</Unavailable>
      ) : (
        <ErrorRetry error={organizacion.error} onRetry={() => void organizacion.refetch()} />
      )}
      {data ? (
        <>
          <Card className="aj-card" title={data.organization.name} titleAs="h3">
            <div className="aj-rows">
              <Row label="Posicionamiento">{`${data.profile.version} · ${data.profile.date}`}</Row>
              <Row label="Estado">{data.profile.status}</Row>
              <Row label="Idioma y mercado">{data.profile.language}</Row>
              <Row label="Dónde">{data.profile.location}</Row>
              <Row label="A quién no se busca">{data.profile.not_wanted}</Row>
            </div>
            <details className="fold">
              <summary>
                <span className="t-cuerpo">Pilares, servicios y modalidades</span>
                <IconChevronDown size={22} />
              </summary>
              <div className="fold-body">
                <p className="section-label">Pilares</p>
                <ul className="aj-steps">
                  {Object.entries(data.profile.pillars).map(([key, text]) => (
                    <li key={key} className="t-detalle">
                      {text}
                    </li>
                  ))}
                </ul>
                <p className="section-label">Servicios</p>
                <ul className="aj-steps">
                  {Object.entries(data.profile.services).map(([key, service]) => (
                    <li key={key} className="t-detalle">
                      {service.label}
                    </li>
                  ))}
                </ul>
                <p className="section-label">Modalidades</p>
                <ul className="aj-steps">
                  {Object.entries(data.profile.modalities).map(([key, modality]) => (
                    <li key={key} className="t-detalle">
                      {modality.purpose}
                    </li>
                  ))}
                </ul>
              </div>
            </details>
          </Card>
          <Card className="aj-card" title={`Miembros (${data.members.length})`} titleAs="h3">
            <ul className="aj-rows" aria-label="Miembros de la organización">
              {data.members.map((member) => (
                <li key={member.id} className="aj-block" data-testid={`miembro-${member.id}`}>
                  <div className="aj-cardhead">
                    <p className="t-cuerpo">{member.display_name}</p>
                    <span className="aj-badges">
                      {memberBadges(member).map((badge) => (
                        <Badge key={badge.text} tone={badge.tone}>
                          {badge.text}
                        </Badge>
                      ))}
                    </span>
                  </div>
                  <p className="t-detalle text-suave">{memberSubtitle(member)}</p>
                  <p className="t-detalle text-suave">{memberAccounts(member)}</p>
                </li>
              ))}
            </ul>
          </Card>
        </>
      ) : null}
    </Section>
  );
}
