import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useEffect, useRef, useState, type FormEvent } from 'react';
import { Navigate, useNavigate, useSearchParams } from 'react-router-dom';
import { ApiError, readCookie } from '../api/client';
import { getSession, login } from '../api/endpoints';
import { keys } from '../api/queryClient';
import { useSession } from '../auth/session';
import { IconEye, IconEyeOff } from '../components/icons';
import { errorMessage } from '../components/ui/ErrorRetry';
import { usePageTitle } from '../components/ui/Page';

/** Only same-app paths are accepted as a destination after login. */
export function safeNext(value: string | null): string {
  if (!value || !value.startsWith('/') || value.startsWith('//') || value.startsWith('/login')) return '/';
  return value;
}

/** After a 429 the button stays locked this long; the server keeps its own limit anyway. */
export const LOCK_MS = 60_000;

type LoginProblem = 'credentials' | 'offline' | 'too-many' | 'other';

function problemOf(error: unknown): LoginProblem | null {
  if (!error) return null;
  if (error instanceof ApiError) {
    if (error.status === 429) return 'too-many';
    if (error.status === 400 || error.status === 401) return 'credentials';
    return 'other';
  }
  if (error instanceof TypeError || (typeof navigator !== 'undefined' && !navigator.onLine)) return 'offline';
  return 'other';
}

function CheckingSession() {
  return (
    <div className="login-checking" role="status" aria-live="polite">
      <img src="/brand/isotipo.svg" alt="0ff1ce" width={72} height={72} />
      <p>Comprobando sesión…</p>
      <div className="login-dots" aria-hidden="true">
        <span />
        <span />
        <span />
      </div>
    </div>
  );
}

/** Login, as Main.dc.html: office hero on tinta, then the Django username and password. */
export function Login() {
  usePageTitle('Entrar');
  const session = useSession();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const next = safeNext(params.get('next'));
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [locked, setLocked] = useState(false);
  const userRef = useRef<HTMLInputElement>(null);
  const passRef = useRef<HTMLInputElement>(null);

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
    onError: (error) => {
      if (error instanceof ApiError && error.status === 429) setLocked(true);
    },
  });

  useEffect(() => {
    if (!locked) return;
    const timer = window.setTimeout(() => setLocked(false), LOCK_MS);
    return () => window.clearTimeout(timer);
  }, [locked]);

  if (session.isPending) return <CheckingSession />;
  if (session.data?.authenticated && !mutation.isPending) return <Navigate to={next} replace />;

  const sending = mutation.isPending;
  const problem = problemOf(mutation.error) ?? (session.isError && session.error instanceof TypeError ? 'offline' : null);

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    if (sending || locked) return;
    if (!username.trim()) return userRef.current?.focus();
    if (!password) return passRef.current?.focus();
    mutation.mutate();
  };

  return (
    <div className="login">
      <div className="login-card">
        <div className="login-hero">
          <img
            src="/brand/login-oficina-tarde.png"
            alt="La oficina de 0ff1ce de tarde: la biblioteca con su bibliotecario, la entrada con Operación y la cocina"
            width={384}
            height={224}
          />
          <div className="login-brand">
            <img src="/brand/logo-inverso.svg" alt="0ff1ce" width={120} height={34} />
            <p>La oficina de agentes de IA que trabaja tu LinkedIn.</p>
          </div>
        </div>

        <form className="login-form" onSubmit={onSubmit} noValidate>
          <div className="page-head">
            <h1 className="page-title">Entrar</h1>
            <p className="page-subtitle">Usa tu usuario y contraseña de Django.</p>
          </div>

          {problem === 'credentials' ? (
            <p className="login-alert" role="alert">
              Usuario o contraseña incorrectos.
            </p>
          ) : null}
          {problem === 'too-many' ? (
            <p className="login-alert warn" role="alert">
              Demasiados intentos. Espera unos minutos.
            </p>
          ) : null}
          {problem === 'offline' ? (
            <p className="login-alert" role="alert">
              No pudimos conectar con la oficina. Revisa tu conexión e intenta de nuevo.
            </p>
          ) : null}
          {problem === 'other' ? (
            <p className="login-alert" role="alert">
              {errorMessage(mutation.error)}
            </p>
          ) : null}

          <div className="field">
            <label htmlFor="usuario">Usuario</label>
            <input
              ref={userRef}
              id="usuario"
              name="username"
              type="text"
              autoComplete="username"
              autoCapitalize="none"
              spellCheck={false}
              required
              value={username}
              onChange={(event) => setUsername(event.target.value)}
            />
          </div>

          <div className="field">
            <label htmlFor="clave">Contraseña</label>
            <div className="password">
              <input
                ref={passRef}
                id="clave"
                name="password"
                type={showPassword ? 'text' : 'password'}
                autoComplete="current-password"
                required
                value={password}
                onChange={(event) => setPassword(event.target.value)}
              />
              <button type="button" aria-label={showPassword ? 'Ocultar contraseña' : 'Mostrar contraseña'} aria-pressed={showPassword} onClick={() => setShowPassword((v) => !v)}>
                {showPassword ? <IconEyeOff /> : <IconEye />}
              </button>
            </div>
          </div>

          <button type="submit" className="login-submit" disabled={sending || locked} data-locked={locked && !sending ? 'true' : undefined} aria-busy={sending || undefined}>
            {sending ? 'Entrando…' : 'Entrar'}
          </button>
        </form>
      </div>
    </div>
  );
}
