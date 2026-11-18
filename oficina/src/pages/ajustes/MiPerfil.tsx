// Ajustes › Mi perfil (GET/PATCH /api/v1/yo/perfil, organizaciones phase 7): who the team writes as. Only she edits it
// (also while her member is in onboarding); each save is a revision with who, when and what changed.
import { useId, useState } from 'react';
import type { MemberProfile, MemberProfileField } from '../../../../compartido/src/api/types';
import {
  fieldCounter,
  hasChanges,
  PROFILE_FIELDS,
  profileIssues,
  profileOrigin,
  profilePatch,
  revisionLine,
  savedMessage,
  type ProfileFieldSpec,
} from '../../../../compartido/src/logic/miembro';
import { useMiPerfil, useSaveMiPerfil } from '../../api/hooks';
import { IconChevronDown } from '../../components/icons';
import { Button, Card, ErrorRetry, Note, Section, Skeleton } from '../../components/ui';
import { isUnavailable, SwitchRow, Unavailable } from './shared';

export function MiPerfilSection() {
  const perfil = useMiPerfil();
  const save = useSaveMiPerfil();
  /** null while the form shows the saved profile. */
  const [draft, setDraft] = useState<MemberProfile | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const saved = perfil.data?.profile;
  const values = draft ?? saved;
  const issues = values ? profileIssues(values) : {};
  const invalid = Object.keys(issues).length > 0;
  const patch = saved && values ? profilePatch(saved, values) : {};
  const changed = hasChanges(patch);

  const edit = (key: MemberProfileField, value: string | boolean) => {
    if (!values) return;
    setStatus(null);
    setDraft({ ...values, [key]: value });
  };

  const submit = () => {
    if (!changed || invalid || save.isPending) return;
    save.mutate(patch, {
      onSuccess: (answer) => {
        setDraft(null);
        setStatus(savedMessage(answer.saved));
      },
    });
  };

  return (
    <Section
      label="Mi perfil"
      id="perfil"
      intro="Quién eres para el equipo: cómo te nombra, cómo te presenta y lo que nunca escribe en tu nombre. Solo tú lo cambias."
    >
      {perfil.isPending ? <Skeleton variant="card" label="Cargando tu perfil…" /> : null}
      {isUnavailable(perfil.error) ? (
        <Unavailable>El servidor todavía no guarda tu perfil.</Unavailable>
      ) : (
        <ErrorRetry error={perfil.error} onRetry={() => void perfil.refetch()} />
      )}
      {perfil.isSuccess && values ? (
        <Card className="aj-card">
          {profileOrigin(perfil.data) ? <p className="t-detalle text-suave">{profileOrigin(perfil.data)}</p> : null}
          <form
            className="aj-form"
            noValidate
            onSubmit={(event) => {
              event.preventDefault();
              submit();
            }}
          >
            {PROFILE_FIELDS.map((field) =>
              field.key === 'personal_startups' ? (
                <SwitchRow
                  key={field.key}
                  label={field.label}
                  hint={perfil.data.help.personal_startups ?? field.hint}
                  checked={values.personal_startups}
                  disabled={save.isPending}
                  onChange={(checked) => edit('personal_startups', checked)}
                />
              ) : (
                <ProfileField
                  key={field.key}
                  field={field}
                  value={String(values[field.key] ?? '')}
                  help={perfil.data.help[field.key] ?? field.hint}
                  error={issues[field.key]}
                  disabled={save.isPending}
                  onChange={(value) => edit(field.key, value)}
                />
              ),
            )}
            <ErrorRetry error={save.error} />
            <div className="aj-actions">
              <Button type="submit" variant="primary" disabled={!changed || invalid} loading={save.isPending} loadingLabel="Guardando…">
                Guardar perfil
              </Button>
              {draft !== null ? (
                <Button
                  variant="ghost"
                  disabled={save.isPending}
                  onClick={() => {
                    setDraft(null);
                    save.reset();
                  }}
                >
                  Descartar cambios
                </Button>
              ) : null}
            </div>
            {status ? (
              <p className="t-detalle" role="status">
                {status}
              </p>
            ) : null}
          </form>
          <details className="fold">
            <summary>
              <span className="t-cuerpo">Historial ({perfil.data.history.length})</span>
              <IconChevronDown size={22} />
            </summary>
            <div className="fold-body">
              {perfil.data.history.length ? (
                <ul className="aj-steps" aria-label="Historial de tu perfil">
                  {perfil.data.history.map((revision) => (
                    <li key={revision.number} className="t-detalle">
                      {revisionLine(revision)}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="t-detalle text-suave">Sin cambios todavía.</p>
              )}
            </div>
          </details>
        </Card>
      ) : null}
      {perfil.isSuccess && !perfil.data.member.active ? (
        <Note tone="info">Mientras tu cuenta está en alta, tu perfil se guarda pero el equipo todavía no escribe en tu nombre.</Note>
      ) : null}
    </Section>
  );
}

function ProfileField({
  field,
  value,
  help,
  error,
  disabled,
  onChange,
}: {
  field: ProfileFieldSpec;
  value: string;
  help: string;
  error: string | undefined;
  disabled: boolean;
  onChange: (value: string) => void;
}) {
  const fieldId = useId();
  const hintId = useId();
  const common = {
    id: fieldId,
    value,
    disabled,
    'aria-describedby': hintId,
    'aria-invalid': error ? true : undefined,
    'aria-required': field.required || undefined,
  };
  return (
    <div className="field">
      <label htmlFor={fieldId}>
        {field.label}
        {field.required ? <span className="field-flag"> · obligatorio</span> : null}
      </label>
      {field.multiline ? (
        <textarea {...common} rows={3} onChange={(event) => onChange(event.target.value)} />
      ) : (
        <input {...common} type="text" onChange={(event) => onChange(event.target.value)} />
      )}
      <p id={hintId} className={error ? 'field-error' : 'field-hint'}>
        {error ?? help}
        {field.max !== undefined ? ` · ${fieldCounter(value, field.max)}` : ''}
      </p>
    </div>
  );
}
