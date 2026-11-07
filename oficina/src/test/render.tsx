import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render } from '@testing-library/react';
import type { ReactElement } from 'react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { SessionBridge } from '../auth/session';
import { ToastProvider } from '../components/ui/Toast';

export function testQueryClient() {
  return new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: Infinity }, mutations: { retry: false } } });
}

/** Shows the current location so tests can assert navigation. */
export function LocationProbe() {
  const location = useLocation();
  return <output data-testid="location">{`${location.pathname}${location.search}`}</output>;
}

export function renderAt(path: string, routes: { path: string; element: ReactElement }[], client = testQueryClient()) {
  return {
    client,
    ...render(
      <QueryClientProvider client={client}>
        <ToastProvider>
          <MemoryRouter initialEntries={[path]}>
            <SessionBridge>
              <Routes>
                {routes.map((route) => (
                  <Route key={route.path} path={route.path} element={route.element} />
                ))}
              </Routes>
              <LocationProbe />
            </SessionBridge>
          </MemoryRouter>
        </ToastProvider>
      </QueryClientProvider>,
    ),
  };
}
