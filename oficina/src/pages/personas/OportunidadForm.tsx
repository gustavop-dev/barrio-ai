import { useQuery } from '@tanstack/react-query';
import { useEffect, useId, useState, type FormEvent } from 'react';
import { asList, listContacts } from '../../api/endpoints';
import { useCreateOportunidad, useDeleteOportunidad, useUpdateOportunidad } from '../../api/hooks';
import { keys } from '../../api/queryClient';
import type { Opportunity, OpportunityAttribution, OpportunityChannel, OpportunityInput, OpportunityModality, OpportunityStage } from '../../api/types';
import { OPPORTUNITY_STAGES } from '../../api/types';
import { IconSearch } from '../../components/icons';
import { Avatar, Button, ErrorRetry, Modal, Segmented, useToast } from '../../components/ui';
import { ATTRIBUTION_LABEL, CHANNEL_LABEL, fromDateInput, OPPORTUNITY_MODALITY_LABEL, OPPORTUNITY_STAGE_LABEL, toDateInput } from './labels';
import './personas.css';

/** The person the form starts with (Marcar como oportunidad, from the person card). */
export interface OpportunityPerson {
  id: string;
  display_name: string;
  headline?: string;
  /** classification.modality: prefills the modality when it is one of the two business ones. */
  modality?: string | null;
}

export interface OportunidadFormProps {
  /** Edit mode when given. */
  opportunity?: Opportunity | null;
  person?: OpportunityPerson | null;
  onClose: () => void;
  onSaved?: (opportunity: Opportunity) => void;
}

type PersonMode = 'red' | 'fuera';

const MODALITIES = Object.keys(OPPORTUNITY_MODALITY_LABEL) as OpportunityModality[];
const CHANNELS = Object.keys(CHANNEL_LABEL) as OpportunityChannel[];
const ATTRIBUTIONS = Object.keys(ATTRIBUTION_LABEL) as OpportunityAttribution[];

function initialModality(opportunity: Opportunity | null | undefined, person: OpportunityPerson | null | undefined): OpportunityModality | '' {
  if (opportunity) return opportunity.modality;
  const modality = person?.modality;
  return modality === 'personal_startups' || modality === 'projectapp' ? modality : '';
}

/** Buscador de Personas: name or headline, two letters at least. */
function PersonSearch({ onPick }: { onPick: (person: OpportunityPerson) => void }) {
  const [text, setText] = useState('');
  const [query, setQuery] = useState('');
  const inputId = useId();
  useEffect(() => {
    const timer = window.setTimeout(() => setQuery(text.trim()), 250);
    return () => window.clearTimeout(timer);
  }, [text]);
  const results = useQuery({
    queryKey: [...keys.redAll, 'picker', query],
    queryFn: async () => asList(await listContacts({ q: query })),
    enabled: query.length >= 2,
  });
  return (
    <div className="field">
      <label htmlFor={inputId}>Buscar en Personas</label>
      <div className="opp-search">
        <IconSearch size={20} />
        <input id={inputId} type="search" autoComplete="off" placeholder="Nombre o titular" value={text} onChange={(event) => setText(event.target.value)} />
      </div>
      {query.length >= 2 ? (
        <div className="opp-results" aria-live="polite">
          {results.isPending ? <p className="field-hint">Buscando…</p> : null}
          <ErrorRetry error={results.error} onRetry={() => void results.refetch()} />
          {results.isSuccess && !results.data.length ? <p className="field-hint">Nadie coincide con «{query}».</p> : null}
          {results.data?.length ? (
            <ul className="opp-result-list" aria-label="Personas encontradas">
              {results.data.slice(0, 8).map((contact) => (
                <li key={contact.id}>
                  <button
                    type="button"
                    className="opp-result"
                    onClick={() => onPick({ id: contact.id, display_name: contact.display_name, headline: contact.headline, modality: contact.classification?.modality })}
                  >
                    <Avatar name={contact.display_name} size={32} />
                    <span className="opp-result-text">
                      <span>{contact.display_name}</span>
                      {contact.headline ? <span className="opp-result-sub">{contact.headline}</span> : null}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

/** «Nueva oportunidad» / «Editar oportunidad» (DISENO-VISTAS, Personas → Oportunidades). */
export function OportunidadForm({ opportunity, person, onClose, onSaved }: OportunidadFormProps) {
  const editing = Boolean(opportunity);
  const toast = useToast();
  const create = useCreateOportunidad();
  const update = useUpdateOportunidad();
  const remove = useDeleteOportunidad();
  const ids = { company: useId(), name: useId(), modality: useId(), channel: useId(), stage: useId(), attribution: useId(), need: useId(), budget: useId(), dedication: useId(), next: useId(), nextAt: useId(), notes: useId() };

  const startPerson: OpportunityPerson | null = opportunity?.contact
    ? { id: opportunity.contact.id, display_name: opportunity.contact.display_name, headline: opportunity.contact.headline }
    : (person ?? null);
  const [mode, setMode] = useState<PersonMode>(opportunity && !opportunity.contact ? 'fuera' : 'red');
  const [picked, setPicked] = useState<OpportunityPerson | null>(startPerson);
  const [personName, setPersonName] = useState(opportunity?.person_name ?? '');
  const [company, setCompany] = useState(opportunity?.company ?? '');
  const [modality, setModality] = useState<OpportunityModality | ''>(initialModality(opportunity, person));
  const [channel, setChannel] = useState<OpportunityChannel>(opportunity?.channel ?? 'linkedin');
  const [stage, setStage] = useState<OpportunityStage>(opportunity?.stage ?? 'conversacion');
  const [attribution, setAttribution] = useState<OpportunityAttribution | ''>(opportunity?.attribution ?? '');
  const [need, setNeed] = useState(opportunity?.need ?? '');
  const [budget, setBudget] = useState(opportunity?.budget ?? '');
  const [dedication, setDedication] = useState(opportunity?.dedication ?? '');
  const [nextAction, setNextAction] = useState(opportunity?.next_action ?? '');
  const [nextAt, setNextAt] = useState(toDateInput(opportunity?.next_action_at));
  const [notes, setNotes] = useState(opportunity?.notes ?? '');
  const [touched, setTouched] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);

  const personError = mode === 'red' ? (picked ? null : 'Elige a alguien de Personas.') : personName.trim() ? null : 'Escribe el nombre de la persona.';
  const errors = {
    person: personError,
    modality: modality ? null : 'Elige la modalidad.',
    attribution: attribution ? null : 'Elige cómo llegó.',
  };
  const invalid = Object.values(errors).some(Boolean);
  const saving = create.isPending || update.isPending;

  const submit = (event: FormEvent) => {
    event.preventDefault();
    setTouched(true);
    if (invalid || saving) return;
    const input: OpportunityInput = {
      contact: mode === 'red' ? (picked?.id ?? null) : null,
      person_name: mode === 'fuera' ? personName.trim() : '',
      company: company.trim(),
      modality: modality as OpportunityModality,
      channel,
      stage,
      attribution: attribution as OpportunityAttribution,
      need: need.trim(),
      budget: budget.trim(),
      dedication: dedication.trim(),
      next_action: nextAction.trim(),
      next_action_at: nextAt ? fromDateInput(nextAt) : null,
      notes: notes.trim(),
    };
    const done = (saved: Opportunity) => {
      toast.show(editing ? 'Cambios guardados' : 'Oportunidad registrada');
      onSaved?.(saved);
      onClose();
    };
    if (opportunity) update.mutate({ opportunityId: opportunity.id, patch: input }, { onSuccess: done });
    else create.mutate(input, { onSuccess: done });
  };

  const show = (error: string | null) => (touched ? error : null);
  const fieldError = (id: string, error: string | null) =>
    show(error) ? (
      <p id={`${id}-error`} className="field-error">
        {error}
      </p>
    ) : null;
  const invalidProps = (id: string, error: string | null) => ({
    'aria-invalid': Boolean(show(error)),
    'aria-describedby': show(error) ? `${id}-error` : undefined,
  });

  if (opportunity && confirmDelete) {
    return (
      <Modal title="Eliminar la oportunidad" onClose={onClose} busy={remove.isPending}>
        <div className="confirm">
          <p className="confirm-text">
            Se borra la oportunidad con {opportunity.person || 'esta persona'} y su historial. Deja de contar en Resultados. No se puede deshacer.
          </p>
          <ErrorRetry error={remove.error} />
          <div className="confirm-actions">
            <Button onClick={() => setConfirmDelete(false)} disabled={remove.isPending}>
              Volver
            </Button>
            <Button
              variant="danger"
              loading={remove.isPending}
              loadingLabel="Eliminando…"
              onClick={() =>
                remove.mutate(opportunity.id, {
                  onSuccess: () => {
                    toast.show('Oportunidad eliminada');
                    onClose();
                  },
                })
              }
            >
              Eliminar
            </Button>
          </div>
        </div>
      </Modal>
    );
  }

  return (
    <Modal title={editing ? 'Editar oportunidad' : 'Nueva oportunidad'} onClose={onClose} busy={saving}>
      <form className="opp-form" onSubmit={submit} noValidate>
        <fieldset className="opp-person">
          <legend className="field-label">
            Persona <span className="field-flag">· obligatoria</span>
          </legend>
          <Segmented<PersonMode>
            label="Quién es"
            options={[
              { value: 'red', label: 'De Personas' },
              { value: 'fuera', label: 'Alguien fuera de la red' },
            ]}
            value={mode}
            onChange={setMode}
          />
          {mode === 'red' ? (
            picked ? (
              <div className="opp-picked">
                <Avatar name={picked.display_name} size={32} />
                <span className="opp-result-text">
                  <span>{picked.display_name}</span>
                  {picked.headline ? <span className="opp-result-sub">{picked.headline}</span> : null}
                </span>
                <Button variant="ghost" size="small" onClick={() => setPicked(null)}>
                  Cambiar
                </Button>
              </div>
            ) : (
              <>
                <PersonSearch
                  onPick={(chosen) => {
                    setPicked(chosen);
                    if (!modality && (chosen.modality === 'personal_startups' || chosen.modality === 'projectapp')) setModality(chosen.modality);
                  }}
                />
                {show(errors.person) ? (
                  <p className="field-error" role="alert">
                    {errors.person}
                  </p>
                ) : null}
              </>
            )
          ) : (
            <div className="field">
              <label htmlFor={ids.name}>Nombre</label>
              <input id={ids.name} value={personName} maxLength={200} onChange={(event) => setPersonName(event.target.value)} {...invalidProps(ids.name, errors.person)} />
              {fieldError(ids.name, errors.person)}
            </div>
          )}
          <div className="field">
            <label htmlFor={ids.company}>
              Empresa <span className="field-flag">· opcional</span>
            </label>
            <input id={ids.company} value={company} maxLength={200} onChange={(event) => setCompany(event.target.value)} />
          </div>
        </fieldset>

        <div className="opp-grid">
          <div className="field">
            <label htmlFor={ids.modality}>Modalidad</label>
            <select id={ids.modality} value={modality} onChange={(event) => setModality(event.target.value as OpportunityModality)} {...invalidProps(ids.modality, errors.modality)}>
              <option value="" disabled>
                Elige…
              </option>
              {MODALITIES.map((value) => (
                <option key={value} value={value}>
                  {OPPORTUNITY_MODALITY_LABEL[value]}
                </option>
              ))}
            </select>
            {fieldError(ids.modality, errors.modality)}
          </div>
          <div className="field">
            <label htmlFor={ids.channel}>Canal</label>
            <select id={ids.channel} value={channel} onChange={(event) => setChannel(event.target.value as OpportunityChannel)}>
              {CHANNELS.map((value) => (
                <option key={value} value={value}>
                  {CHANNEL_LABEL[value]}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor={ids.stage}>Etapa</label>
            <select id={ids.stage} value={stage} onChange={(event) => setStage(event.target.value as OpportunityStage)}>
              {OPPORTUNITY_STAGES.map((value) => (
                <option key={value} value={value}>
                  {OPPORTUNITY_STAGE_LABEL[value]}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor={ids.attribution}>Cómo llegó</label>
            <select
              id={ids.attribution}
              value={attribution}
              onChange={(event) => setAttribution(event.target.value as OpportunityAttribution)}
              {...invalidProps(ids.attribution, errors.attribution)}
            >
              <option value="" disabled>
                Elige…
              </option>
              {ATTRIBUTIONS.map((value) => (
                <option key={value} value={value}>
                  {ATTRIBUTION_LABEL[value]}
                </option>
              ))}
            </select>
            {fieldError(ids.attribution, errors.attribution)}
          </div>
        </div>

        <div className="field">
          <label htmlFor={ids.need}>
            Necesidad <span className="field-flag">· opcional</span>
          </label>
          <input id={ids.need} value={need} onChange={(event) => setNeed(event.target.value)} />
        </div>
        <div className="opp-grid">
          <div className="field">
            <label htmlFor={ids.budget}>
              Presupuesto o compensación <span className="field-flag">· opcional</span>
            </label>
            <input id={ids.budget} value={budget} maxLength={200} placeholder="Texto o rango" onChange={(event) => setBudget(event.target.value)} />
          </div>
          <div className="field">
            <label htmlFor={ids.dedication}>
              Dedicación <span className="field-flag">· opcional</span>
            </label>
            <input id={ids.dedication} value={dedication} maxLength={200} onChange={(event) => setDedication(event.target.value)} />
          </div>
        </div>
        <div className="opp-grid">
          <div className="field">
            <label htmlFor={ids.next}>
              Siguiente acción <span className="field-flag">· opcional</span>
            </label>
            <input id={ids.next} value={nextAction} maxLength={300} onChange={(event) => setNextAction(event.target.value)} />
          </div>
          <div className="field">
            <label htmlFor={ids.nextAt}>
              Fecha <span className="field-flag">· opcional</span>
            </label>
            <input id={ids.nextAt} type="date" value={nextAt} onChange={(event) => setNextAt(event.target.value)} />
          </div>
        </div>
        <div className="field">
          <label htmlFor={ids.notes}>
            Notas <span className="field-flag">· opcional</span>
          </label>
          <textarea id={ids.notes} rows={3} value={notes} onChange={(event) => setNotes(event.target.value)} />
        </div>

        {touched && invalid ? (
          <p className="field-error" role="alert">
            Falta algo obligatorio: revisa los campos marcados.
          </p>
        ) : null}
        <ErrorRetry error={create.error ?? update.error} />
        <div className="confirm-actions">
          {opportunity ? (
            <Button variant="danger" className="opp-delete" onClick={() => setConfirmDelete(true)} disabled={saving}>
              Eliminar
            </Button>
          ) : null}
          <Button onClick={onClose} disabled={saving}>
            Cancelar
          </Button>
          <Button type="submit" variant="primary" loading={saving} loadingLabel="Guardando…">
            {editing ? 'Guardar cambios' : 'Registrar oportunidad'}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
