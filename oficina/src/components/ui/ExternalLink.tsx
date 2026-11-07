import type { ReactNode } from 'react';
import { IconExternal } from '../icons';

/** Rendered once by the Layout; every external link points its aria-describedby at it. */
export const EXTERNAL_HINT_ID = 'enlace-externo-aviso';

export function isHttps(href: string | null | undefined): href is string {
  return Boolean(href && /^https:\/\//i.test(href));
}

export interface ExternalLinkProps {
  href: string | null | undefined;
  children: ReactNode;
  className?: string;
}

/** LinkedIn and other outside links: https only (otherwise nothing renders), new tab, noopener, ↗. */
export function ExternalLink({ href, children, className }: ExternalLinkProps) {
  if (!isHttps(href)) return null;
  return (
    <a href={href} target="_blank" rel="noopener noreferrer" className={['extlink', className ?? ''].filter(Boolean).join(' ')} aria-describedby={EXTERNAL_HINT_ID}>
      {children}
      <IconExternal size={18} />
    </a>
  );
}
