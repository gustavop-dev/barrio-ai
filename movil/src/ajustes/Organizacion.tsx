// Ajustes › Organización (GET /api/v1/organizacion, organizaciones phase 7): only its admin. The company's profile, read
// only and compact, and its members with their state: nothing private of anyone (no conversations, drafts or notes).
// The anchor around it in AjustesScreen carries testID «ajustes-organizacion».
import { useOrganizacion } from '@compartido/api/hooks';
import { isUnavailable } from '@compartido/logic/ajustes';
import { memberAccounts, memberBadges, memberSubtitle } from '@compartido/logic/miembro';
import { StyleSheet, View } from 'react-native';
import { Badge, Card, ErrorRetry, Fold, KeyValue, Section, Skeleton, T } from '@/components/ui';
import { space } from '@/theme/tokens';
import { Block, CardHead, Unavailable } from './parts';

export function OrganizacionSection() {
  const organizacion = useOrganizacion();
  const data = organizacion.data;
  return (
    <Section label="Organización" intro="Lo que comparten todos los miembros. Solo lo ves tú, como administrador.">
      {organizacion.isPending ? <Skeleton variant="card" label="Cargando la organización…" /> : null}
      {isUnavailable(organizacion.error) ? (
        <Unavailable>El servidor todavía no muestra la organización.</Unavailable>
      ) : (
        <ErrorRetry error={organizacion.error} onRetry={() => void organizacion.refetch()} />
      )}
      {data ? (
        <>
          <Card>
            <CardHead title={data.organization.name} />
            <KeyValue label="Posicionamiento">{`${data.profile.version} · ${data.profile.date}`}</KeyValue>
            <KeyValue label="Estado">{data.profile.status}</KeyValue>
            <KeyValue label="Idioma y mercado">{data.profile.language}</KeyValue>
            <KeyValue label="Dónde">{data.profile.location}</KeyValue>
            <KeyValue label="A quién no se busca">{data.profile.not_wanted}</KeyValue>
            <Fold summary="Pilares, servicios y modalidades">
              <Block label="Pilares">
                {Object.entries(data.profile.pillars).map(([key, text]) => (
                  <T key={key} variant="detalle">
                    {text}
                  </T>
                ))}
              </Block>
              <Block label="Servicios">
                {Object.entries(data.profile.services).map(([key, service]) => (
                  <T key={key} variant="detalle">
                    {service.label}
                  </T>
                ))}
              </Block>
              <Block label="Modalidades">
                {Object.entries(data.profile.modalities).map(([key, modality]) => (
                  <T key={key} variant="detalle">
                    {modality.purpose}
                  </T>
                ))}
              </Block>
            </Fold>
          </Card>
          <Card>
            <CardHead title={`Miembros (${data.members.length})`} />
            {data.members.map((member) => (
              <View key={member.id} style={styles.member} testID={`miembro-${member.id}`} collapsable={false}>
                <CardHead title={member.display_name}>
                  {memberBadges(member).map((badge) => (
                    <Badge key={badge.text} tone={badge.tone}>
                      {badge.text}
                    </Badge>
                  ))}
                </CardHead>
                <T variant="detalle" soft>
                  {memberSubtitle(member)}
                </T>
                <T variant="detalle" soft>
                  {memberAccounts(member)}
                </T>
              </View>
            ))}
          </Card>
        </>
      ) : null}
    </Section>
  );
}

const styles = StyleSheet.create({ member: { gap: space[1], paddingVertical: space[2] } });
