import { forwardRef, type AnchorHTMLAttributes, type ButtonHTMLAttributes, type ReactNode } from 'react';
import { Link, type LinkProps } from 'react-router-dom';

/**
 * - primary: 0ff1ce fill, tinta text. One per card or screen.
 * - secondary: superficie with a tinta-suave border.
 * - danger: alerta outline (Vetar, Retirar, Descartar, Desactivar).
 * - ghost: text button in 0ff1ce-hondo (Más tarde); add `quiet` for tinta-suave.
 * - stop / resume: the big full-width PARADA TOTAL (alerta fill) and REANUDAR (0ff1ce fill).
 */
export type ButtonVariant = 'primary' | 'secondary' | 'danger' | 'ghost' | 'stop' | 'resume';

interface CommonProps {
  variant?: ButtonVariant;
  /** Full width: main actions on mobile. stop/resume are always full width. */
  block?: boolean;
  /** 44px tall instead of 48px, for buttons inside rows. */
  size?: 'normal' | 'small';
  /** ghost only: tinta-suave instead of 0ff1ce-hondo, for the least important option. */
  quiet?: boolean;
  /** Leading icon (an icon component from components/icons). */
  icon?: ReactNode;
}

export function buttonClass({ variant = 'secondary', block, size, quiet }: CommonProps, extra?: string): string {
  return ['btn', variant, block ? 'block' : '', size === 'small' ? 'small' : '', quiet ? 'quiet' : '', extra ?? '']
    .filter(Boolean)
    .join(' ');
}

export interface ButtonProps extends CommonProps, ButtonHTMLAttributes<HTMLButtonElement> {
  /** Disables the button, marks it busy and shows a spinner with `loadingLabel`. */
  loading?: boolean;
  loadingLabel?: ReactNode;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = 'secondary', block, size, quiet, icon, loading = false, loadingLabel = 'Enviando…', className, children, disabled, type = 'button', ...rest },
  ref,
) {
  return (
    <button
      ref={ref}
      type={type}
      className={buttonClass({ variant, block, size, quiet }, [loading ? 'loading' : '', className ?? ''].join(' ').trim())}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      {...rest}
    >
      {loading ? <span className="spinner" aria-hidden="true" /> : icon}
      {loading ? loadingLabel : children}
    </button>
  );
});

type ButtonLinkProps = CommonProps &
  (
    | ({ to: LinkProps['to']; href?: never } & Omit<LinkProps, 'to'>)
    | ({ href: string; to?: never } & AnchorHTMLAttributes<HTMLAnchorElement>)
  );

/**
 * A link dressed as a button. `to` navigates inside the app; `href` is a full navigation
 * (for example the LinkedIn OAuth start, which must never be fetched).
 */
export function ButtonLink(props: ButtonLinkProps) {
  const { variant = 'secondary', block, size, quiet, icon, className, children, ...rest } = props;
  const cls = buttonClass({ variant, block, size, quiet }, className);
  if ('to' in rest && rest.to !== undefined) {
    return (
      <Link className={cls} {...(rest as LinkProps)}>
        {icon}
        {children}
      </Link>
    );
  }
  return (
    <a className={cls} {...(rest as AnchorHTMLAttributes<HTMLAnchorElement>)}>
      {icon}
      {children}
    </a>
  );
}
