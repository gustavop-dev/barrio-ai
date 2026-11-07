import { QueryClientProvider, type QueryClient } from '@tanstack/react-query';
import { Navigate, Route, Routes, useLocation, useParams } from 'react-router-dom';
import { RequireAuth, SessionBridge } from './auth/session';
import { CaptureProvider } from './capture/CaptureContext';
import { openCaptureSheet } from './capture/store';
import { Layout } from './components/Layout';
import { ToastProvider } from './components/ui/Toast';
import { Ajustes } from './pages/Ajustes';
import { Calendario } from './pages/Calendario';
import { Galeria } from './pages/Galeria';
import { Login } from './pages/Login';
import { Notificaciones } from './pages/Notificaciones';
import { Oficina } from './pages/Oficina';
import { Persona } from './pages/Persona';
import { Personas } from './pages/Personas';
import { PiezaDetalle } from './pages/PiezaDetalle';
import { Resultados } from './pages/Resultados';
import { TuTurno } from './pages/TuTurno';

/** Old piece URLs (push notifications open /editorial/<id>) go to the piece detail. */
function PieceRedirect() {
  const { pieceId = '' } = useParams();
  return <Navigate to={pieceId ? `/calendario/pieza/${encodeURIComponent(pieceId)}` : '/calendario'} replace />;
}

/** Redirect that keeps the query string (e.g. /red?etapa=fit → /personas?etapa=fit). */
function KeepSearch({ to, extra }: { to: string; extra?: Record<string, string> }) {
  const { search } = useLocation();
  const params = new URLSearchParams(search);
  for (const [key, value] of Object.entries(extra ?? {})) params.set(key, value);
  const query = params.toString();
  return <Navigate to={`${to}${query ? `?${query}` : ''}`} replace />;
}

/** /acciones?state=uncertain was the old push target of an uncertain action: it now lives in Tu turno. */
function AccionesRedirect() {
  const { search } = useLocation();
  const uncertain = new URLSearchParams(search).get('state') === 'uncertain';
  return <Navigate to={uncertain ? '/tu-turno' : '/calendario'} replace />;
}

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        element={
          <RequireAuth>
            <Layout />
          </RequireAuth>
        }
      >
        <Route index element={<Oficina />} />
        <Route path="tu-turno" element={<TuTurno />} />
        <Route path="tu-turno/sabe" element={<TuTurno />} />
        <Route path="notificaciones" element={<Notificaciones />} />
        <Route path="calendario" element={<Calendario />} />
        <Route path="calendario/pieza/:pieceId" element={<PiezaDetalle />} />
        <Route path="resultados" element={<Resultados />} />
        <Route path="personas" element={<Personas />}>
          <Route path=":contactId" element={<Persona />} />
        </Route>
        <Route path="galeria" element={<Galeria />} />
        <Route path="ajustes" element={<Ajustes />} />

        {/* Views of the old office, redirected to where their content lives now. */}
        <Route path="editorial/:pieceId" element={<PieceRedirect />} />
        <Route path="contenido/:pieceId" element={<PieceRedirect />} />
        <Route path="editorial" element={<Navigate to="/calendario" replace />} />
        <Route path="contenido" element={<Navigate to="/calendario" replace />} />
        <Route path="acciones" element={<AccionesRedirect />} />
        <Route path="maquina" element={<Navigate to="/calendario" replace />} />
        <Route path="red" element={<KeepSearch to="/personas" />} />
        <Route path="referentes" element={<KeepSearch to="/personas" extra={{ pestana: 'referentes' }} />} />
        <Route path="memoria" element={<Navigate to="/tu-turno/sabe" replace />} />
        <Route path="conocimiento" element={<Navigate to="/" replace />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export function App({ queryClient }: { queryClient: QueryClient }) {
  return (
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <CaptureProvider onCapture={openCaptureSheet}>
          <SessionBridge>
            <AppRoutes />
          </SessionBridge>
        </CaptureProvider>
      </ToastProvider>
    </QueryClientProvider>
  );
}
