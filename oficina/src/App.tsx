import { QueryClientProvider, type QueryClient } from '@tanstack/react-query';
import { Navigate, Route, Routes } from 'react-router-dom';
import { RequireAuth, SessionBridge } from './auth/session';
import { Layout } from './components/Layout';
import { Acciones } from './pages/Acciones';
import { Ajustes } from './pages/Ajustes';
import { Conocimiento } from './pages/Conocimiento';
import { Contenido, EditorialRedirect } from './pages/Contenido';
import { Login } from './pages/Login';
import { Maquina } from './pages/Maquina';
import { Memoria } from './pages/Memoria';
import { Oficina } from './pages/Oficina';
import { Pieza } from './pages/Pieza';
import { Red } from './pages/Red';
import { Referentes } from './pages/Referentes';

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
        <Route path="maquina" element={<Maquina />} />
        <Route path="acciones" element={<Acciones />} />
        <Route path="contenido" element={<Contenido />} />
        <Route path="contenido/:pieceId" element={<Pieza />} />
        {/* Push notifications of the backend point at /editorial/<id>. */}
        <Route path="editorial" element={<EditorialRedirect />} />
        <Route path="editorial/:pieceId" element={<EditorialRedirect />} />
        <Route path="referentes" element={<Referentes />} />
        <Route path="red" element={<Red />} />
        <Route path="conocimiento" element={<Conocimiento />} />
        <Route path="memoria" element={<Memoria />} />
        <Route path="ajustes" element={<Ajustes />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export function App({ queryClient }: { queryClient: QueryClient }) {
  return (
    <QueryClientProvider client={queryClient}>
      <SessionBridge>
        <AppRoutes />
      </SessionBridge>
    </QueryClientProvider>
  );
}
