import { Pressable, StyleSheet, View } from 'react-native';
import { STATUS_LABEL, STATUS_TONE, roleActivity, summarize, summaryText } from '@compartido/scene/activity';
import { detailOf, SERVICE_NOTE, type PanelData } from '@compartido/scene/panels';
import { CHARACTER_BY_ID, LIBRARIAN_ID, rolesOfTeam, teamById, zoneName, type CharacterId, type TeamId } from '@compartido/scene/roles';
import { timeAgo } from '@compartido/logic/format';
import { AgentPortrait, Badge, Button, Note, T } from '@/components/ui';
import { openLink } from '@/navigation';
import { colors, space } from '@/theme/tokens';

export function TeamPanel({ team: teamId, data, onRole }: { team: TeamId; data: PanelData; onRole: (id: CharacterId) => void }) {
  const team = teamById(teamId);
  const members = rolesOfTeam(teamId);
  const summary = summarize(members.map((m) => m.id), Object.fromEntries(members.map((m) => [m.id, data.statusOf(m.id)])));
  return <>
    <View style={styles.row}><T variant="etiqueta" soft>ESPACIO DEL EQUIPO</T><T variant="etiqueta">{team.number}</T>{team.isNew ? <Badge tone="warn">Nuevo</Badge> : null}</View>
    <T accessibilityRole="header" variant="subtitulo">{team.name}</T>
    <T soft>{team.purpose}</T>
    <T variant="etiqueta" soft>{members.length} {members.length === 1 ? 'INTEGRANTE' : 'INTEGRANTES'} · {team.place.toUpperCase()}</T>
    <T variant="detalle">{summaryText(summary)}</T>
    {members.map((m) => <Pressable key={m.id} accessibilityRole="button" accessibilityLabel={`${m.name}, ${STATUS_LABEL[data.statusOf(m.id)]}`} onPress={() => onRole(m.id)} style={styles.member}>
      <AgentPortrait role={m.id} />
      <View style={styles.memberText}><T>{m.name}</T><T variant="detalle" soft>{detailOf(m.id, data)}</T><Badge tone={STATUS_TONE[data.statusOf(m.id)]}>{STATUS_LABEL[data.statusOf(m.id)]}</Badge></View>
    </Pressable>)}
  </>;
}
export function RolePanel({ id, data, onTeam }: { id: CharacterId; data: PanelData; onTeam: (id: TeamId) => void }) {
  const role = CHARACTER_BY_ID[id]; const librarian = id === LIBRARIAN_ID;
  const status = data.statusOf(id); const info = roleActivity(data.activity, id);
  const recent = data.snapshot.feed.filter((entry) => entry.role === id).slice(0, 3);
  const zone = zoneName(role.team);
  const since = status !== 'desconocido' && !data.snapshot.doing[id] && info?.since ? `En este estado desde ${timeAgo(info.since, data.now)}` : '';
  return <>
    <View style={styles.row}><AgentPortrait role={id} size="lg" /><View style={styles.memberText}>
      <T variant="etiqueta" soft>{role.service ? 'SERVICIO' : 'AGENTE'} · {zone.toUpperCase()}</T>
      <T accessibilityRole="header" variant="subtitulo">{role.name}</T>
      <Badge tone={STATUS_TONE[status]}>{STATUS_LABEL[status]}</Badge>
    </View></View>
    {SERVICE_NOTE[id] ? <Note tone="info">{SERVICE_NOTE[id]}</Note> : null}
    <T accessibilityRole="header" variant="etiqueta" soft>MISIÓN</T><T>{role.purpose}</T>
    <T accessibilityRole="header" variant="etiqueta" soft>ESTADO REAL</T>
    <T>{status === 'desconocido' ? 'Sin datos de actividad.' : `${STATUS_LABEL[status]} · ${detailOf(id, data)}`}</T>
    {since ? <T variant="detalle" soft>{since}</T> : null}
    {status === 'diseno' ? <Note>Este rol está en diseño. Aparece en la oficina, pero todavía no trabaja.</Note> : null}
    <T accessibilityRole="header" variant="etiqueta" soft>LO ÚLTIMO QUE HIZO</T>
    {recent.length ? recent.map((entry) => <View key={entry.key} style={styles.recent}><T>{entry.text}</T><T variant="detalle" soft>{timeAgo(new Date(entry.at).toISOString(), data.now)}</T></View>) : <T variant="detalle" soft>Nada todavía en esta sesión.</T>}
    {!librarian ? <Button onPress={() => openLink(id === 'editor_visual' && info?.piece_id ? `/calendario/pieza/${info.piece_id}` : '/calendario')}>{id === 'editor_visual' && info?.piece_id ? 'Ver pieza' : 'Ver en el Calendario'}</Button> : null}
    <Button block onPress={() => onTeam(librarian ? 'observatorio' : role.team as TeamId)}>{librarian ? 'Ver quién la usa · Observatorio' : `Ver su equipo · ${zone}`}</Button>
  </>;
}
const styles = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', gap: space[3], flexWrap: 'wrap' },
  member: { minHeight: 64, flexDirection: 'row', alignItems: 'center', paddingVertical: space[3], gap: space[3], borderTopWidth: 1, borderColor: colors.line },
  memberText: { flex: 1, gap: space[1] },
  recent: { borderTopWidth: 1, borderColor: colors.line, paddingVertical: space[2] },
});
