// Deep links of Galería, Ajustes and Notificaciones (a push's `data.url`, a notification's `link`, a
// card's `href`), including the legacy paths the PWA redirects (oficina/src/App.tsx).
import { router } from 'expo-router';
import { openLink } from '@/navigation';
import { routeForUrl } from './routes';

describe('deep links of Galería, Ajustes and Notificaciones', () => {
  it('maps the gallery and its filter', () => {
    expect(routeForUrl('/galeria')).toEqual({ pathname: '/galeria', params: {} });
    expect(routeForUrl('/galeria?filtro=sin_usar')).toEqual({ pathname: '/galeria', params: { filtro: 'sin_usar' } });
  });

  it('maps the Ajustes anchors and the OAuth return', () => {
    expect(routeForUrl('/ajustes')).toEqual({ pathname: '/ajustes', params: {} });
    expect(routeForUrl('/ajustes#maquina')).toEqual({ pathname: '/ajustes', params: { ancla: 'maquina' } });
    expect(routeForUrl('/ajustes#autonomia')).toEqual({ pathname: '/ajustes', params: { ancla: 'autonomia' } });
    expect(routeForUrl('/ajustes#notificaciones')).toEqual({ pathname: '/ajustes', params: { ancla: 'notificaciones' } });
    expect(routeForUrl('/ajustes?linkedin=error&motivo=state')).toEqual({ pathname: '/ajustes', params: { linkedin: 'error', motivo: 'state' } });
  });

  it('maps Notificaciones and «Lo que el equipo sabe de ti»', () => {
    expect(routeForUrl('/notificaciones')).toEqual({ pathname: '/notificaciones', params: {} });
    expect(routeForUrl('/tu-turno/sabe')).toEqual({ pathname: '/tu-turno', params: { tab: 'sabe' } });
  });

  it('redirects the legacy paths as the PWA does', () => {
    expect(routeForUrl('/maquina')).toEqual({ pathname: '/calendario', params: {} });
    expect(routeForUrl('/memoria')).toEqual({ pathname: '/tu-turno', params: { tab: 'sabe' } });
  });

  it('opens them in the app', () => {
    openLink('/ajustes#notificaciones');
    expect(router.navigate).toHaveBeenLastCalledWith({ pathname: '/ajustes', params: { ancla: 'notificaciones' } });
    openLink('/galeria?filtro=publicadas');
    expect(router.navigate).toHaveBeenLastCalledWith({ pathname: '/galeria', params: { filtro: 'publicadas' } });
    openLink('/memoria');
    expect(router.navigate).toHaveBeenLastCalledWith({ pathname: '/tu-turno', params: { tab: 'sabe' } });
  });
});
