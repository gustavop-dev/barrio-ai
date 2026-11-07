import { IconCheck } from '../icons';

export type StageState = 'done' | 'current' | 'pending' | 'alt';

export interface Stage {
  key: string;
  label: string;
  /** «21 oct», or a status word on the right in the numbered variant. */
  date?: string | null;
  /** Extra line («6 nov · necesidad identificada»). */
  detail?: string | null;
  /** done: reached; current: where it is now; pending: not yet; alt: an alternative end (Cerrado, Descartado). */
  state: StageState;
}

export interface StageTrackProps {
  stages: Stage[];
  /**
   * path: the person's journey (24px dots joined by a line; vertical on mobile, horizontal from 900px).
   * numbered: the 5 preparation steps of a piece (32px numbered circles, «Hecho» / «Ahora» on the right).
   */
  variant?: 'path' | 'numbered';
  label?: string;
}

const SPOKEN: Record<StageState, string> = { done: 'hecho', current: 'ahora', pending: 'pendiente', alt: 'final alternativo' };
const RIGHT: Record<StageState, string> = { done: 'Hecho', current: 'Ahora', pending: '', alt: '' };

/** Stage track: steps with their date. */
export function StageTrack({ stages, variant = 'path', label }: StageTrackProps) {
  return (
    <ol className={`stages ${variant}`} aria-label={label}>
      {stages.map((stage, index) => (
        <li key={stage.key} className={`stage ${stage.state}`} aria-current={stage.state === 'current' ? 'step' : undefined}>
          <span className="stage-mark" aria-hidden="true">
            {stage.state === 'done' || (variant === 'path' && stage.state === 'current') ? <IconCheck size={variant === 'path' ? 14 : 18} /> : variant === 'numbered' ? index + 1 : null}
          </span>
          <span className="stage-text">
            <span className="stage-label">
              {stage.label}
              <span className="vh">, {SPOKEN[stage.state]}</span>
            </span>
            {variant === 'path' && (stage.date || stage.detail) ? (
              <span className="stage-date">{[stage.date, stage.detail].filter(Boolean).join(' · ')}</span>
            ) : null}
          </span>
          {variant === 'numbered' ? (
            <span className="stage-status" aria-hidden="true">
              {stage.date ?? RIGHT[stage.state]}
            </span>
          ) : null}
        </li>
      ))}
    </ol>
  );
}
