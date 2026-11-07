import { QueryClientProvider } from '@tanstack/react-query';
import { render } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { vi } from 'vitest';
import { CaptureProvider } from '../../capture/CaptureContext';
import { Layout } from '../../components/Layout';
import { ToastProvider } from '../../components/ui/Toast';
import { Calendario } from '../../pages/Calendario';
import { PiezaDetalle } from '../../pages/PiezaDetalle';
import { LocationProbe, testQueryClient } from '../render';

/**
 * The calendar and the piece detail inside the real shell (top bar, back link), with a spy for the capture
 * sheet. Independent of App.tsx so these tests only depend on the files they test.
 */
export function renderCalendario(path: string) {
  const client = testQueryClient();
  const onCapture = vi.fn();
  const utils = render(
    <QueryClientProvider client={client}>
      <ToastProvider>
        <CaptureProvider onCapture={onCapture}>
          <MemoryRouter initialEntries={[path]}>
            <Routes>
              <Route element={<Layout />}>
                <Route path="calendario" element={<Calendario />} />
                <Route path="calendario/pieza/:pieceId" element={<PiezaDetalle />} />
                <Route path="*" element={<p>Otra vista</p>} />
              </Route>
            </Routes>
            <LocationProbe />
          </MemoryRouter>
        </CaptureProvider>
      </ToastProvider>
    </QueryClientProvider>,
  );
  return { ...utils, client, onCapture };
}
