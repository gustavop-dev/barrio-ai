import { QueryClientProvider, type QueryClient } from '@tanstack/react-query';
import { Navigate, Route, Routes } from 'react-router-dom';
import { RequireAuth, SessionBridge } from './auth/session';
import { Layout } from './components/Layout';
import { Acciones } from './pages/Acciones';
import { Ajustes } from './pages/Ajustes';
import { Conocimiento } from './pages/Conocimiento';
import { Login } from './pages/Login';
import { Maquina } from './pages/Maquina';
import { Memoria } from './pages/Memoria';
import { Oficina } from './pages/Oficina';
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
        <Route path="referentes" element={<Referentes />} />
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
