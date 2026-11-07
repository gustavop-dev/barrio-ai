import type { ReactNode } from 'react';
import { charCount } from './copy';
import { CopyButton } from './CopyButton';

export interface BeforeAfterProps {
  /** The current text read from the profile; null when it could not be read. */
  current: string | null | undefined;
  proposed: string;
  /** LinkedIn limit (titular 220, Acerca de 2.600): shows «105 / 220», alerta when over. */
  limit?: number;
  currentLabel?: string;
  proposedLabel?: string;
  /** Under the current text, e.g. «Leído el 5 nov». */
  currentMeta?: ReactNode;
  unavailableText?: string;
  onCopied?: () => void;
}

/**
 * Before / after comparison: «Propuesto» first on mobile, «Ahora» and «Propuesto» side by side
 * from 900px. The proposed text has a character counter and «Copiar».
 */
export function BeforeAfter({
  current,
  proposed,
  limit,
  currentLabel = 'Ahora',
  proposedLabel = 'Propuesto',
  currentMeta,
  unavailableText = 'No pudimos leer tu perfil actual.',
  onCopied,
}: BeforeAfterProps) {
  const count = charCount(proposed);
  const over = limit !== undefined && count > limit;
  return (
    <div className="beforeafter">
      <div className="ba-block ba-after">
        <div className="ba-head">
          <p className="section-label">{proposedLabel}</p>
          {limit !== undefined ? (
            <span className={over ? 'ba-count over' : 'ba-count'}>
              {count} / {limit}
              {over ? <span className="vh"> caracteres: supera el límite de LinkedIn</span> : <span className="vh"> caracteres</span>}
            </span>
          ) : null}
        </div>
        <p className="ba-text proposed">{proposed}</p>
        <CopyButton text={proposed} block onCopied={onCopied} />
      </div>
      <div className="ba-block ba-before">
        <p className="section-label">{currentLabel}</p>
        {current ? <p className="ba-text current">{current}</p> : <p className="ba-missing">{unavailableText}</p>}
        {currentMeta ? <p className="ba-meta">{currentMeta}</p> : null}
      </div>
    </div>
  );
}
