import { useState } from 'react';
import { useUpdateReferent } from '@compartido/api/hooks';
import type { Referent } from '@compartido/api/types';
import { Button, ErrorRetry, Field, Sheet, T } from '@/components/ui';
import { Select } from '@/components/ui/Select';

export function ProtectedReferent({ referent, candidates }: { referent: Referent; candidates: Referent[] }) {
  const [open, setOpen] = useState(false);
  const [protectedFlag, setProtected] = useState(Boolean(referent.protected));
  const [active, setActive] = useState(referent.active !== false);
  const [position, setPosition] = useState(String(referent.position ?? 0));
  const [replacement, setReplacement] = useState('');
  const update = useUpdateReferent();
  if (!referent.can_manage_protected) return null;
  return <>
    <Button size="small" onPress={() => { setProtected(Boolean(referent.protected)); setActive(referent.active !== false); setPosition(String(referent.position ?? 0)); setReplacement(''); setOpen(true); }} testID={`protect-${referent.id}`}>Gestionar protección de {referent.display_name}</Button>
    {open ? <Sheet label={`Gestionar a ${referent.display_name}`} onClose={() => setOpen(false)} suspended={update.isPending} testID="referent-protection">
      <T>Solo Gustavo. El equipo conserva la evidencia y no cambia seguimientos en LinkedIn.</T>
      <Select label="Protección" value={protectedFlag ? 'main' : 'variable'} onChange={v => setProtected(v === 'main')}
        options={[{ value: 'main', label: 'Main protegido' }, { value: 'variable', label: 'Variable' }]} />
      <Select label="Actividad" value={active ? 'active' : 'inactive'} onChange={v => setActive(v === 'active')}
        options={[{ value: 'active', label: 'Activo' }, { value: 'inactive', label: 'Inactivo' }]} />
      <Field label="Posición" value={position} onChangeText={setPosition} keyboardType="number-pad" />
      <Select label="Reemplazar por" value={replacement} onChange={setReplacement} options={[{ value: '', label: 'Conservar este perfil' },
        ...candidates.filter(r => r.id !== referent.id && !r.protected).map(r => ({ value: r.id, label: r.display_name ?? r.id }))]} />
      <T>{replacement ? `Sale ${referent.display_name} · entra ${candidates.find(r => r.id === replacement)?.display_name}. Se transfiere su protección y posición.`
        : `${referent.protected ? 'Main protegido' : 'Variable'} → ${protectedFlag ? 'Main protegido' : 'Variable'}; ${active ? 'activo' : 'inactivo'}; posición ${referent.position ?? 0} → ${position}.`}</T>
      <T>Máximo cinco main y diez variables activos; una vacante main no se rellena automáticamente.</T>
      {referent.protection_history?.map((entry, i) => <T key={i} variant="detalle">{entry.actor__username ?? 'Agente'} · {entry.created_at} · {entry.metadata.source}: protegido {String(entry.metadata.before.protected ?? false)} → {String(entry.metadata.after.protected ?? false)}, activo {String(entry.metadata.before.active ?? false)} → {String(entry.metadata.after.active ?? false)}</T>)}
      <ErrorRetry error={update.error} />
      <Button variant="primary" loading={update.isPending} onPress={() => update.mutate({ referentId: referent.id,
        patch: { version: referent.revision, source: 'personas', ...(replacement ? { replacement } : { protected: protectedFlag, active, position: Number(position) }) } },
        { onSuccess: () => setOpen(false) })}>Guardar decisión</Button>
    </Sheet> : null}
  </>;
}
