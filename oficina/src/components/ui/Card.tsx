import type { HTMLAttributes, ReactNode } from 'react';

export interface CardProps extends Omit<HTMLAttributes<HTMLElement>, 'title'> {
  as?: 'div' | 'section' | 'article' | 'li';
  /** Border colour: bad for critical (alerta), warn for post-it, dashed for an empty slot. */
  tone?: 'default' | 'bad' | 'warn' | 'ok' | 'info' | 'dashed';
  /** 12px padding instead of 16px (KPI tiles, dense lists). */
  compact?: boolean;
  /** Small UPPERCASE label above the title. */
  eyebrow?: ReactNode;
  title?: ReactNode;
  titleAs?: 'h2' | 'h3' | 'p';
  /** Badges shown on the right of the header. */
  badges?: ReactNode;
  /** Action row at the bottom. */
  actions?: ReactNode;
  /** Footer line in tinta-suave («Creada hace 3 h»). */
  footer?: ReactNode;
}

/** Card: header (eyebrow, title, badges), body and action row. superficie on papel, linea border, 12px radius. */
export function Card({
  as: Tag = 'div',
  tone = 'default',
  compact = false,
  eyebrow,
  title,
  titleAs: Title = 'h2',
  badges,
  actions,
  footer,
  className,
  children,
  ...rest
}: CardProps) {
  const hasHead = eyebrow || title || badges;
  return (
    <Tag className={['card', tone !== 'default' ? `tone-${tone}` : '', compact ? 'compact' : '', className ?? ''].filter(Boolean).join(' ')} {...rest}>
      {hasHead ? (
        <div className="card-head">
          <div className="card-heading">
            {eyebrow ? <p className="card-eyebrow">{eyebrow}</p> : null}
            {title ? <Title className="card-title">{title}</Title> : null}
          </div>
          {badges ? <div className="card-badges">{badges}</div> : null}
        </div>
      ) : null}
      {children}
      {actions ? <div className="card-actions">{actions}</div> : null}
      {footer ? <p className="card-footer">{footer}</p> : null}
    </Tag>
  );
}
