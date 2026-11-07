# Oficina de Barrio AI (PWA)

App React + PWA que sustituye a la oficina pixel-art de `apartamento-agentes`. Muestra la oficina con la actividad real de los 16 roles, supervisa la máquina autónoma (parada total, cuenta, topes, gasto, ventana, feed), las acciones, la publicación diaria (calendario editorial, detalle de cada pieza y veto), los referentes, el conocimiento y la memoria, conecta la cuenta oficial de LinkedIn y recibe las alertas como notificaciones push.

El contrato con Django está en [`CONTRATO-API.md`](CONTRATO-API.md). La app solo habla con el backend propio (mismo origen), sin secretos, analítica ni llamadas a LinkedIn o a proveedores.

## Desarrollo

Requisitos: Node 24.

```sh
npm install
npm run dev        # http://localhost:5173, con proxy de /api, /admin, /static y /health a http://127.0.0.1:8787
```

El proxy conserva la cabecera `Host`, así que Django ve el mismo origen que el navegador y la comprobación CSRF pasa sin tocar `CSRF_TRUSTED_ORIGINS`. Si Django usa cookies `Secure`, en desarrollo por HTTP no se guardará la sesión.

En `npm run dev` no hay service worker. Para probar la instalación y las notificaciones usa `npm run build && npm run preview` (mismo proxy, puerto 4173) o el despliegue real con HTTPS.

| Script | Qué hace |
| --- | --- |
| `npm run dev` | Servidor de desarrollo con proxy al backend. |
| `npm run build` | `tsc -b` y build de producción en `dist/` (incluye `sw.js` y `manifest.webmanifest`). |
| `npm run preview` | Sirve `dist/` con el mismo proxy. |
| `npm test -- --run` | Vitest + Testing Library (jsdom). Las rutas nuevas del backend se simulan con `src/test/fakeServer.ts`. |
| `npm run lint` | ESLint (TypeScript + reglas de hooks). |
| `npm run typecheck` | TypeScript estricto para app, service worker y configuración. |
| `npm run icons` | Regenera los iconos de la PWA (ver abajo). |

## Estructura

- `src/api/`: cliente `fetch` (`credentials: 'same-origin'`, cabecera `X-CSRFToken` desde la cookie `csrftoken`, 401/403 → login, `detail` de los 409), tipos del contrato y consultas con TanStack Query.
- `src/scene/`: la escena portada a TypeScript. `roles.ts` define equipos, roles y posiciones; `simulation.ts`, la lógica pura (estado real → pose, paseos); `render.ts` dibuja en canvas con los sprites de LimeZu; `OfficeCanvas.tsx` es el componente.
- `src/pages/`: Login, Oficina, Máquina, Acciones, Contenido (calendario editorial) y Pieza (detalle), Referentes, Conocimiento, Memoria y Ajustes (LinkedIn oficial y push). `/editorial/<id>`, la URL de las notificaciones de piezas, redirige a `/contenido/<id>`.
- `src/sw.ts`: service worker propio (`injectManifest`). Precarga el shell y los sprites, maneja `push` y `notificationclick`, y nunca cachea `/api/`.
- `public/assets/`: arte original de LimeZu, copiado tal cual con su `CREDITS.txt`.

### Escena y estado real

Cada personaje refleja `GET /api/v1/oficina/actividad`:

- `trabajando`: animación de lectura (trabajo), monitor encendido y luz verde.
- `en_espera`: animación idle. Solo estos personajes dan los paseos ambientales a la cocina o al pasillo.
- `diseno`: figura atenuada e inmóvil con la etiqueta «en diseño».
- Sin dato: figura quieta y aviso en el panel. Nunca se simula trabajo.

Relaciones (`relaciones_comunidad`, `conversaciones_inbox`) se sienta en las dos sillas doradas de la mesa de la cocina. Operación (`operador_cuenta`, un servicio, no un agente de IA) está junto a la puerta, con un mueble bajo y la impresora. El paquete solo trae 13 personajes, así que los tres roles nuevos reutilizan las hojas `person5`, `person10` y `person4` en otras zonas del mapa.

`prefers-reduced-motion` pausa el ambiente al cargar; el botón «Activar ambiente» lo reanuda. La luz de tarde se activa entre las 18:00 y las 6:00 de la hora local, y se puede cambiar con su botón.

## Iconos

`scripts/generate-icons.mjs` usa `sharp` para tomar el fotograma frontal de `public/assets/person0-idle_anim.png`, recortarlo a sus píxeles visibles y escalarlo por un factor entero con *nearest-neighbor* sobre el verde de la oficina. Genera en `public/icons/`:

- `icon-192.png` e `icon-512.png`;
- `icon-maskable-512.png`, con el personaje dentro de la zona segura;
- `apple-touch-icon.png` (180 px) y `favicon-32.png`;
- `badge-96.png`, una silueta blanca para la insignia de notificación en Android.

Los PNG generados se versionan, así que el build no necesita ejecutar el script.

## Notificaciones push

En **Ajustes**, «Activar notificaciones» pide permiso, obtiene la clave VAPID (`GET /api/v1/push/key`), suscribe el service worker y envía `PushSubscription.toJSON()` al backend. El permiso se pide antes de cualquier petición de red porque iOS solo lo muestra dentro del gesto del usuario.

En iPhone o iPad (iOS 16.4 o posterior), Web Push solo funciona con la app añadida a la pantalla de inicio: Safari → Compartir → «Añadir a pantalla de inicio». La propia pantalla de Ajustes lo explica.

El service worker muestra `{title, body, tag}` y guarda `url` en la notificación. Al tocarla, enfoca una ventana que ya esté en esa URL, navega una ventana de la app o abre una nueva. Solo acepta URLs del mismo origen.

## Despliegue

```sh
docker build -t barrio-oficina .
```

El `Dockerfile` es multi-etapa: compila con `node:24-alpine` y copia `dist/` a `/srv` de una imagen `caddy:2`. El Caddyfile de producción se escribe aparte. Para que la PWA funcione, ese Caddyfile debe:

- servir `/srv` con `try_files {path} /index.html`, para que las rutas del cliente (`/maquina`, `/acciones`…) abran la app;
- reenviar `/api/*`, `/admin/*`, `/static/*` y `/health` a Django;
- servir `sw.js`, `index.html` y `manifest.webmanifest` con `Cache-Control: no-cache`, para que las actualizaciones lleguen; los ficheros de `/_app/` llevan hash y admiten caché larga;
- usar HTTPS, que es obligatorio para service workers y push.

Los recursos con hash están en `/_app/` porque `/assets/` contiene los sprites y `/static/` pertenece a Django.
