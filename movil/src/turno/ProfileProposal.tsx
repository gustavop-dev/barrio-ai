import { useState } from 'react';
import { Linking, View } from 'react-native';
import { profileDownload, useProfile, useProfileDecision } from '@compartido/api/perfil';
import { applicationLabel, needsProfileNote, PROFILE_ACTION_LABELS, PROFILE_ASSET_LABELS, PROFILE_UNREADABLE, profileAvailability, profileQuestions, sectionActions } from '@compartido/logic/perfil';
import { sameOrigin } from '@compartido/api/capturas';
import { ApiImage, Button, CopyButton, ErrorRetry, Field, T } from '@/components/ui';
import { apiUrl } from '@/api/config';
import { space } from '@/theme/tokens';

export function ProfileProposal({ id }: { id: string }) {
  const [open, setOpen] = useState(false);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [notes, setNotes] = useState<Record<string, string>>({});
  const [error, setError] = useState<unknown>(null);
  const [documentOpen, setDocumentOpen] = useState(false);
  const [assetsOpen, setAssetsOpen] = useState(false);
  const [referencesOpen, setReferencesOpen] = useState(false);
  const query = useProfile(id, open);
  const decision = useProfileDecision(id);
  const proposal = query.data;
  const download = async (resource = 'documento') => {
    try {
      const ticket = await profileDownload(id, resource);
      const path = sameOrigin(ticket.url);
      if (!path?.startsWith(`/api/v1/perfil/${id}/descarga/`)) throw new Error('Enlace de descarga inválido');
      await Linking.openURL(apiUrl(path)); setError(null);
    } catch (cause) { setError(cause); }
  };
  return <View style={{ gap: space[3] }}>
    <Button testID="profile-open" onPress={() => setOpen(!open)}>{open ? 'Cerrar propuesta de perfil' : 'Abrir propuesta de perfil'}</Button>
    {open ? <>
      {query.isPending ? <T>Cargando propuesta…</T> : null}
      <ErrorRetry error={query.error} onRetry={() => void query.refetch()} />
      {proposal ? <>
        <T>Versión {proposal.version} · {proposal.state} · Aplicación manual</T>
        <T>{profileAvailability(proposal)}</T>
        {proposal.can_prepare_assets ? <Button testID="profile-prepare-assets" disabled={decision.isPending || proposal.assets_pending}
          onPress={() => decision.mutate({ revision: proposal.revision, action: 'prepare_assets' })}>
          Generar fotos y banner
        </Button> : null}
        {proposal.assets_pending ? <T>Preparando fotos y banner; el texto se conserva.</T> : null}
        {proposal.findings.map((finding, index) => <T key={index}>{finding}</T>)}
        <Button onPress={() => void download()}>Descargar Markdown</Button>
        <Button onPress={() => setDocumentOpen(!documentOpen)}>Documento Markdown</Button>
        {documentOpen ? <><T selectable>{proposal.markdown}</T><CopyButton text={proposal.markdown} /></> : null}
        <T>{proposal.microphone_note}</T>
        <Button onPress={() => setAssetsOpen(!assetsOpen)}>Fotos, banner y previews</Button>
        {assetsOpen ? proposal.assets.map((asset) => <View key={asset.id} style={{ gap: space[2] }}>
          <T>{PROFILE_ASSET_LABELS[asset.kind] ?? asset.kind} · {asset.width}×{asset.height}</T>
          <ApiImage path={asset.url} style={{ width: '100%', aspectRatio: asset.width / asset.height }} recyclingKey={asset.id} />
          <Button onPress={() => void download(asset.id)}>Descargar {PROFILE_ASSET_LABELS[asset.kind] ?? asset.kind}</Button>
          {['A', 'B', 'banner'].includes(asset.kind) ? Object.entries(asset.review.options ?? {}).filter(([option]) => option === asset.kind).map(([option, review]) => <View key={option}>
            <T>Revisión de {option} · comprobaciones e identidad</T>
            {review.checks.map((check) => <T key={check.point}>{check.point}. {check.ok ? 'Pasa' : 'Pendiente'} · {check.reason}</T>)}
            <T>Identidad 03: {review.identity_03 ? 'Pasa' : 'Pendiente'} · Sonrisa 01: {review.smile_01 ? 'Pasa' : 'Pendiente'} · Gafas claras: {review.clear_glasses ? 'Pasa' : 'Pendiente'}</T>
          </View>) : null}
        </View>) : null}
        <Button onPress={() => setReferencesOpen(!referencesOpen)}>Referencias privadas para comparar</Button>
        {referencesOpen ? proposal.references.map((ref) => <View key={ref.id}>
          <ApiImage path={ref.url} style={{ width: '100%', aspectRatio: 1 }} recyclingKey={ref.id} />
          <T>{ref.role} · v{ref.version} · {ref.note}</T>
        </View>) : null}
        <T accessibilityRole="header">Checklist por sección</T>
        {[...proposal.sections].sort((a, b) => Number(b.readiness === 'ready') - Number(a.readiness === 'ready')).map((row) => <View key={row.id} style={{ gap: space[2] }}>
          <Button testID={`profile-section-${row.id}`} onPress={() => setExpanded(expanded === row.id ? null : row.id)}>{row.title}</Button>
          <T>{applicationLabel(row)}</T>
          {expanded === row.id ? <>
            <T>{row.action === 'keep' ? 'Conservar' : row.action === 'not_applicable' ? 'No aplica' : row.action === 'missing' ? 'Falta información' : 'Cambiar'}</T>
            <T>{row.current ? `${row.current.text} · ${row.current.source} · ${row.current.at}` : PROFILE_UNREADABLE}</T>
            <T>{row.audience} · {row.benefit}</T><T>{row.reason}</T>
            {row.citations.map((cite) => <T key={cite.unit_id}>[{cite.unit_id}] {cite.reason}</T>)}
            {row.evidence.length ? <T>Evidencia: {row.evidence.join(', ')}</T> : null}
            {row.readiness === 'needs_input' && row.copy ? <T>Completa los placeholders con tus datos antes de pegar.</T> : null}
            {row.copy ? <><T selectable>{row.copy}</T><CopyButton text={row.copy} /></> : null}
            <T>{row.copy.length} caracteres · {row.limit ? `límite comprobado: ${row.limit}` : 'Límite pendiente de comprobar'}</T>
            {row.steps.map((step, index) => <T key={index}>{index + 1}. {step}</T>)}
            {row.issues?.map((issue, index) => <T key={index}>{issue}</T>)}
            {row.id === 'banner' ? <T>{proposal.microphone_note}</T> : null}
            {row.id === 'photo' ? <T>Opción elegida: {proposal.photo_choice || 'Ninguna'}</T> : null}
            {row.applied_at ? <T>{applicationLabel(row)} · {row.applied_at}</T> : null}
            {row.applied_text ? <T selectable>{row.applied_text}</T> : null}
            <Field label="Motivo, ajuste o texto que usaste" value={notes[row.id] ?? ''} multiline
              onChangeText={(text) => setNotes({ ...notes, [row.id]: text })} testID={`profile-note-${row.id}`} />
            {sectionActions(row, proposal).map((action) => <Button key={action} testID={`profile-${row.id}-${action}`}
              disabled={decision.isPending || (needsProfileNote(action) && !notes[row.id]?.trim())}
              onPress={() => decision.mutate({ revision: proposal.revision, section: row.id, action, note: notes[row.id] ?? '' })}>
              {PROFILE_ACTION_LABELS[action]}
            </Button>)}
          </> : null}
        </View>)}
        {profileQuestions(proposal).length ? <View><T accessibilityRole="header">Preguntas pendientes</T>
          {profileQuestions(proposal).map((question) => <T key={`${question.section}:${question.key}`}>{question.title}: {question.question}</T>)}
        </View> : null}
        <ErrorRetry error={decision.error} /><ErrorRetry error={error} />
        <Button disabled={decision.isPending} onPress={() => decision.mutate({ revision: proposal.revision, action: 'later' })}>Más tarde</Button>
      </> : null}
    </> : null}
  </View>;
}
