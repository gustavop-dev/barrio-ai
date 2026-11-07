import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useState, type FormEvent } from 'react';
import { Navigate, useNavigate, useSearchParams } from 'react-router-dom';
import { ApiError, readCookie } from '../api/client';
import { getSession, login } from '../api/endpoints';
import { keys } from '../api/queryClient';
import { useSession } from '../auth/session';
import { ErrorNote, Loading } from '../components/ui';

/** Only same-app paths are accepted as a destination after login. */
export function safeNext(value: string | null): string {
  if (!value || !value.startsWith('/') || value.startsWith('//') || value.startsWith('/login')) return '/';
  return value;
}

export function Login() {
  const session = useSession();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const next = safeNext(params.get('next'));
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');

  const mutation = useMutation({
    mutationFn: async () => {
      // GET session sets the CSRF cookie that the login POST needs.
      if (!readCookie('csrftoken')) await getSession();
      await login(username.trim(), password);
      return getSession();
    },
    onSuccess: (fresh) => {
      queryClient.setQueryData(keys.session, fresh);
      setPassword('');
      navigate(next, { replace: true });
    },
  });

  if (session.isPending) return <Loading label="Comprobando sesión…" full />;
  if (session.data?.authenticated && !mutation.isPending) return <Navigate to={next} replace />;

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    if (!username.trim() || !password || mutation.isPending) return;
    mutation.mutate();
  };

  const error = mutation.error;
  const tooMany = error instanceof ApiError && error.status === 429;

  return (
    <div className="loginpage">
      <form className="logincard" onSubmit={onSubmit} noValidate>
        <img src="/icons/icon-192.png" alt="" width="72" height="72" className="loginicon" />
        <p className="eyebrow">BARRIO AI · OFICINA</p>
        <h1>Entrar</h1>
        <p className="muted">Usa tu usuario y contraseña de Django.</p>
        <label htmlFor="username">Usuario</label>
        <input
          id="username"
          name="username"
          autoComplete="username"
          autoCapitalize="none"
          spellCheck={false}
          required
          value={username}
          onChange={(event) => setUsername(event.target.value)}
        />
        <label htmlFor="password">Contraseña</label>
        <input
          id="password"
          name="password"
          type="password"
          autoComplete="current-password"
          required
          value={password}
          onChange={(event) => setPassword(event.target.value)}
        />
        {error ? (
          tooMany ? (
            <div className="note warn" role="alert">
              <strong>Demasiados intentos</strong>
              <p>{error instanceof ApiError ? error.detail : ''} Espera unos minutos antes de volver a intentarlo.</p>
            </div>
          ) : (
            <ErrorNote error={error} />
          )
        ) : null}
        <button type="submit" className="primary" disabled={mutation.isPending || !username.trim() || !password}>
          {mutation.isPending ? 'Entrando…' : 'Entrar'}
        </button>
      </form>
    </div>
  );
}
