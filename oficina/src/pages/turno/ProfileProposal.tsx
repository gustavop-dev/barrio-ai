import { useState } from 'react';
import { useProfile, useProfileDecision, type ProfileSection } from '../../api/perfil';
import { applicationLabel, needsProfileNote, PROFILE_ACTION_LABELS, PROFILE_ASSET_LABELS, PROFILE_UNREADABLE, profileAvailability, profileQuestions, sectionActions } from '../../../../compartido/src/logic/perfil';
import { sameOrigin } from '../../api/capturas';
import { Button, ErrorRetry } from '../../components/ui';

export function ProfileProposal({ id }: { id: string }) {
  const [open, setOpen] = useState(false);
  const query = useProfile(id, open);
  const decision = useProfileDecision(id);
  const [notes, setNotes] = useState<Record<string, string>>({});
  const [copyError, setCopyError] = useState<unknown>(null);
  const proposal = query.data;
  const copy = async (text: string) => { try { await navigator.clipboard.writeText(text); setCopyError(null); } catch (error) { setCopyError(error); } };
  const section = (row: ProfileSection) => (
    <details key={row.id}>
      <summary>{row.title} · {applicationLabel(row)}</summary>
      <p>{row.action === 'keep' ? 'Conservar' : row.action === 'not_applicable' ? 'No aplica' : row.action === 'missing' ? 'Falta información' : 'Cambiar'}</p>
      <p>{row.current ? `${row.current.text} · ${row.current.source} · ${row.current.at}` : PROFILE_UNREADABLE}</p>
      <p>{row.audience} · {row.benefit}</p><p>{row.reason}</p>
      {row.citations.map((cite) => <p key={cite.unit_id}>[{cite.unit_id}] {cite.reason}</p>)}
      {row.evidence.length ? <p>Evidencia: {row.evidence.join(', ')}</p> : null}
      {row.readiness === 'needs_input' && row.copy ? <p>Completa los placeholders con tus datos antes de pegar.</p> : null}
      {row.copy ? <><pre style={{ whiteSpace: 'pre-wrap' }}>{row.copy}</pre><Button onClick={() => void copy(row.copy)}>Copiar</Button></> : null}
      <p>{row.copy.length} caracteres · {row.limit ? `límite comprobado: ${row.limit}` : 'Límite pendiente de comprobar'}</p>
      {row.steps.map((step, index) => <p key={index}>{index + 1}. {step}</p>)}
      {row.issues?.map((issue, index) => <p key={index}>{issue}</p>)}
      {row.id === 'banner' ? <p>{proposal?.microphone_note}</p> : null}
      {row.id === 'photo' ? <p>Opción elegida: {proposal?.photo_choice || 'Ninguna'}</p> : null}
      {row.applied_at ? <p>{applicationLabel(row)} · {row.applied_at}</p> : null}
      {row.applied_text ? <pre style={{ whiteSpace: 'pre-wrap' }}>{row.applied_text}</pre> : null}
      <label>Motivo, ajuste o texto que usaste
        <textarea aria-label={`Nota · ${row.title}`} value={notes[row.id] ?? ''} onChange={(e) => setNotes({ ...notes, [row.id]: e.target.value })} />
      </label>
      {proposal ? sectionActions(row, proposal).map((action) => <Button key={action}
        disabled={decision.isPending || (needsProfileNote(action) && !notes[row.id]?.trim())}
        onClick={() => decision.mutate({ revision: proposal.revision, section: row.id, action, note: notes[row.id] ?? '' })}>
        {PROFILE_ACTION_LABELS[action]}
      </Button>) : null}
    </details>
  );
  return <div>
    <Button onClick={() => setOpen(!open)}>{open ? 'Cerrar propuesta de perfil' : 'Abrir propuesta de perfil'}</Button>
    {open ? <>
      {query.isPending ? <p>Cargando propuesta…</p> : null}
      <ErrorRetry error={query.error} onRetry={() => void query.refetch()} />
      {proposal ? <>
        <p>Versión {proposal.version} · {proposal.state} · Aplicación manual</p>
        <p>{profileAvailability(proposal)}</p>
        {proposal.can_prepare_assets ? <Button disabled={decision.isPending || proposal.assets_pending}
          onClick={() => decision.mutate({ revision: proposal.revision, action: 'prepare_assets' })}>
          Generar fotos y banner
        </Button> : null}
        {proposal.assets_pending ? <p>Preparando fotos y banner; el texto se conserva.</p> : null}
        {proposal.findings.map((finding, index) => <p key={index}>{finding}</p>)}
        <a href={sameOrigin(proposal.document_url) ?? undefined} download>Descargar Markdown</a>
        <Button onClick={() => void copy(proposal.markdown)}>Copiar documento Markdown</Button>
        <details><summary>Documento Markdown</summary><pre style={{ whiteSpace: 'pre-wrap' }}>{proposal.markdown}</pre></details>
        <p>{proposal.microphone_note}</p>
        <details><summary>Fotos, banner y previews</summary>{proposal.assets.map((asset) => <figure key={asset.id}>
          <img src={sameOrigin(asset.url) ?? undefined} alt={PROFILE_ASSET_LABELS[asset.kind] ?? asset.kind} style={{ width: '100%', maxWidth: 800 }} />
          <figcaption>{PROFILE_ASSET_LABELS[asset.kind] ?? asset.kind} · {asset.width}×{asset.height}</figcaption>
          <a href={sameOrigin(asset.url) ?? undefined} download>Descargar {PROFILE_ASSET_LABELS[asset.kind] ?? asset.kind}</a>
          {Object.entries(asset.review.options ?? {}).map(([option, review]) => <details key={option}><summary>Revisión de {option} · comprobaciones e identidad</summary>
            {review.checks.map((check) => <p key={check.point}>{check.point}. {check.ok ? 'Pasa' : 'Pendiente'} · {check.reason}</p>)}
            <p>Identidad 03: {review.identity_03 ? 'Pasa' : 'Pendiente'} · Sonrisa 01: {review.smile_01 ? 'Pasa' : 'Pendiente'} · Gafas claras: {review.clear_glasses ? 'Pasa' : 'Pendiente'}</p>
          </details>)}
        </figure>)}</details>
        <details><summary>Referencias privadas para comparar</summary>{proposal.references.map((ref) => <figure key={ref.id}>
          <img src={sameOrigin(ref.url) ?? undefined} alt={`Referencia ${ref.role}`} style={{ maxWidth: '100%' }} /><figcaption>{ref.role} · v{ref.version} · {ref.note}</figcaption>
        </figure>)}</details>
        <div aria-label="Checklist por sección">{[...proposal.sections].sort((a, b) => Number(b.readiness === 'ready') - Number(a.readiness === 'ready')).map(section)}</div>
        {profileQuestions(proposal).length ? <section aria-label="Preguntas pendientes"><h3>Preguntas pendientes</h3>
          {profileQuestions(proposal).map((question) => <p key={`${question.section}:${question.key}`}>{question.title}: {question.question}</p>)}
        </section> : null}
        <ErrorRetry error={decision.error} /><ErrorRetry error={copyError} />
        <Button disabled={decision.isPending} onClick={() => decision.mutate({ revision: proposal.revision, action: 'later' })}>Más tarde</Button>
      </> : null}
    </> : null}
  </div>;
}
