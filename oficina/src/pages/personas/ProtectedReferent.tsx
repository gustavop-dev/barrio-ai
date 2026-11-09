import { useState } from 'react';
import { useUpdateReferent } from '../../api/hooks';
import type { Referent } from '../../api/types';
import { Button, ErrorRetry, Modal } from '../../components/ui';

export function ProtectedReferent({ referent, candidates }: { referent: Referent; candidates: Referent[] }) {
  const [open, setOpen] = useState(false);
  const [protectedFlag, setProtected] = useState(Boolean(referent.protected));
  const [active, setActive] = useState(referent.active !== false);
  const [position, setPosition] = useState(referent.position ?? 0);
  const [replacement, setReplacement] = useState('');
  const update = useUpdateReferent();
  if (!referent.can_manage_protected) return null;
  return <>
    <Button size="small" onClick={() => { setProtected(Boolean(referent.protected)); setActive(referent.active !== false); setPosition(referent.position ?? 0); setReplacement(''); setOpen(true); }}>Gestionar protección de {referent.display_name}</Button>
    {open ? <Modal title={`Gestionar a ${referent.display_name}`} onClose={() => setOpen(false)} busy={update.isPending}>
      <p>Solo Gustavo. El equipo conserva la evidencia y no cambia seguimientos en LinkedIn.</p>
      <label className="field"><input type="checkbox" checked={protectedFlag} onChange={e => setProtected(e.target.checked)} />Main protegido</label>
      <label className="field"><input type="checkbox" checked={active} onChange={e => setActive(e.target.checked)} />Activo</label>
      <label className="field">Posición<input aria-label="Posición" type="number" min={0} max={15} value={position} onChange={e => setPosition(Number(e.target.value))} /></label>
      <label className="field">Reemplazar por<select aria-label="Reemplazar por" value={replacement} onChange={e => setReplacement(e.target.value)}><option value="">Conservar este perfil</option>
        {candidates.filter(r => r.id !== referent.id && !r.protected).map(r => <option key={r.id} value={r.id}>{r.display_name}</option>)}</select></label>
      <p>{replacement ? `Sale ${referent.display_name} · entra ${candidates.find(r => r.id === replacement)?.display_name}. Se transfiere su protección y posición.`
        : `${referent.protected ? 'Main protegido' : 'Variable'} → ${protectedFlag ? 'Main protegido' : 'Variable'}; ${active ? 'activo' : 'inactivo'}; posición ${referent.position ?? 0} → ${position}.`}</p>
      <p>Máximo cinco main y diez variables activos; una vacante main no se rellena automáticamente.</p>
      {referent.protection_history?.map((entry, i) => <p key={i}>{entry.actor__username ?? 'Agente'} · {entry.created_at} · {entry.metadata.source}: protegido {String(entry.metadata.before.protected ?? false)} → {String(entry.metadata.after.protected ?? false)}, activo {String(entry.metadata.before.active ?? false)} → {String(entry.metadata.after.active ?? false)}</p>)}
      <ErrorRetry error={update.error} />
      <Button variant="primary" loading={update.isPending} onClick={() => update.mutate({ referentId: referent.id,
        patch: { version: referent.revision, source: 'personas', ...(replacement ? { replacement } : { protected: protectedFlag, active, position }) } },
        { onSuccess: () => setOpen(false) })}>Guardar decisión</Button>
    </Modal> : null}
  </>;
}
