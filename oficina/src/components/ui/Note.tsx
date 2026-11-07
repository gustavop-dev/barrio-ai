import type { ReactNode } from 'react';

export type NoteTone = 'info' | 'ok' | 'warn' | 'error';

export interface NoteProps {
  tone?: NoteTone;
  title?: ReactNode;
  children?: ReactNode;
  /** Buttons or links under the text. */
  actions?: ReactNode;
  /** Defaults to alert for error and warn, status for the rest. Pass null for none. */
  role?: 'alert' | 'status' | null;
  className?: string;
  id?: string;
}

/**
 * Notice. info: #3d5a7a on #e4ecf3; ok: 0ff1ce-hondo on 0ff1ce-claro; warn: tinta on post-it;
 * error: alerta border and title on superficie. The title is regular weight: Ubuntu Bold is reserved
 * for the name 0ff1ce.
 */
export function Note({ tone = 'info', title, children, actions, role, className, id }: NoteProps) {
  const resolvedRole = role === null ? undefined : (role ?? (tone === 'error' || tone === 'warn' ? 'alert' : 'status'));
  return (
    <div id={id} className={['note', tone, className ?? ''].filter(Boolean).join(' ')} role={resolvedRole}>
      {title ? <p className="note-title">{title}</p> : null}
      {children ? <div className="note-body">{children}</div> : null}
      {actions ? <div className="note-actions">{actions}</div> : null}
    </div>
  );
}
