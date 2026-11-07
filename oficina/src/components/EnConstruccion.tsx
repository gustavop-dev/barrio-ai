import type { ReactNode } from 'react';
import { ButtonLink } from './ui/Button';
import { EmptyState } from './ui/EmptyState';
import { Page, type PageProps } from './ui/Page';

/** Phase 1 placeholder of a view that phase 2 builds. */
export function EnConstruccion({ title, subtitle, width, children }: Pick<PageProps, 'title' | 'subtitle' | 'width'> & { children?: ReactNode }) {
  return (
    <Page title={title} subtitle={subtitle} width={width}>
      <EmptyState
        title="En construcción"
        action={
          <ButtonLink to="/" variant="secondary">
            Volver a la Oficina
          </ButtonLink>
        }
      >
        El equipo está montando esta vista. Mientras tanto, la Oficina sigue mostrando lo que pasa.
      </EmptyState>
      {children}
    </Page>
  );
}
