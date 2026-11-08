# Acceso (`ACC`)

Cómo entra Gustavo en la PWA (sesión de Django con cookie y CSRF) y en la app (token de dispositivo), cómo sale, y quién puede decidir.

- **Código:** backend `oficina_views.py` (`session_view`, `login_view`, `logout_view`, `check_login`), `movil_views.py` (`TokenIssue`, `TokenRevoke`, `Devices`, `DeviceDetail`), `authentication.py` (`DeviceTokenAuthentication`, prefijo `0ff1ce_dt_`), `operador_views.human_session`, `permissions.require`; PWA `oficina/src/pages/Login.tsx`, `oficina/src/auth/session.tsx`, `oficina/src/api/client.ts`; app `movil/src/app/login.tsx`, `movil/src/auth/session.tsx`, `loginProblems.ts`, `movil/src/api/token.ts`, `movil/src/entrada/*`; común `compartido/src/api/client.ts`, `errors.ts`.
- **Documentación:** «Sesión» y «App móvil: login por dispositivo y push nativo» de [`CONTRATO-API.md`](../../oficina/CONTRATO-API.md), [`app-movil-backend.md`](../../agentes-linkedin/infra/docs/app-movil-backend.md).

## Resumen

| ID | Función | Dónde | Estado |
| --- | --- | --- | --- |
| [ACC-01](#acc-01) | Entrar en la PWA | PWA · backend | funciona |
| [ACC-02](#acc-02) | Entrar en la app | app · backend | con fallo conocido |
| [ACC-03](#acc-03) | Bloqueo tras demasiados intentos | PWA · app · backend | funciona |
| [ACC-04](#acc-04) | Volver a donde estaba después de entrar | PWA | funciona |
| [ACC-05](#acc-05) | Sesión caducada o revocada | PWA · app · backend | funciona |
| [ACC-06](#acc-06) | Seguir dentro al abrir la app | app · backend | con fallo conocido |
| [ACC-07](#acc-07) | Cerrar sesión en la PWA | PWA · backend | funciona |
| [ACC-08](#acc-08) | Cerrar sesión en la app | app · backend | funciona |
| [ACC-09](#acc-09) | Dispositivos con la app | PWA · app · backend | parcial |
| [ACC-10](#acc-10) | Entrada animada a la oficina | app | funciona |
| [ACC-11](#acc-11) | Quién puede decidir | backend | funciona |

---

### ACC-01 · Entrar en la PWA <a id="acc-01"></a>

- **Dónde:** PWA · backend
- **Estado:** funciona
- **Qué hace para Gustavo:** entra con su usuario y su contraseña de Django.
- **Código:** `GET /api/v1/auth/session` (fija la cookie CSRF), `POST /api/v1/auth/login {username, password}`; `Login.tsx`.
- **Criterios de aceptación:**
  1. **Dado** que no tiene sesión, **cuando** abre la PWA, **entonces** ve «Comprobando sesión…» y después la pantalla de entrada con «La oficina de agentes de IA que trabaja tu LinkedIn.», «Entrar», «Usa tu usuario y contraseña de Django.», los campos «Usuario» y «Contraseña» (con «Mostrar contraseña») y «Entrar».
  2. **Dado** credenciales correctas, **cuando** pulsa «Entrar», **entonces** el botón dice «Entrando…», la API responde 200 con el usuario y llega a la Oficina (o a la ruta de `next`).
  3. **Dado** credenciales incorrectas, **cuando** pulsa «Entrar», **entonces** la API responde 400 y ve «Usuario o contraseña incorrectos.».
  4. **Dado** que no hay conexión, **cuando** pulsa «Entrar», **entonces** ve «No pudimos conectar con la oficina. Revisa tu conexión e intenta de nuevo.».
  5. **Dado** un campo vacío, **cuando** pulsa «Entrar», **entonces** no se envía y el foco va al campo vacío.
  6. **Dado** que ya tiene sesión, **cuando** abre `/login`, **entonces** va directo a la Oficina.
- **Brechas código/docs:** si el `POST` entra pero la cookie no se guarda (por ejemplo una cookie `Secure` por HTTP en desarrollo), la PWA vuelve a `/login` sin ningún mensaje. En producción (HTTPS) no ocurre.
- **Cobertura QA:** pendiente

### ACC-02 · Entrar en la app <a id="acc-02"></a>

- **Dónde:** app · backend
- **Estado:** con fallo conocido
- **Qué hace para Gustavo:** entra en la app con su usuario y su contraseña; el teléfono queda como un dispositivo de su cuenta.
- **Código:** `POST /api/v1/auth/token {username, password, device_name}` (201 `{token, user, device}`, `Cache-Control: no-store`); `movil/src/app/login.tsx`, `loginProblems.ts`; token en `expo-secure-store` (`oficina.token-dispositivo`).
- **El fallo:** sin conexión, la app no muestra «No pudimos conectar con la oficina…» sino el mensaje técnico en inglés `fetch failed: …`. `loginProblems.ts` reconoce la falta de red por `TypeError`, y `expo/fetch` lanza `FetchError` (ver [APP-08](app-movil-instalacion.md#app-08)).
- **Criterios de aceptación:**
  1. **Dado** la app sin sesión, **cuando** la abre, **entonces** ve la puerta pixel, el logo, «Entrar», «Usa tu usuario y contraseña de Django.», los campos con «Mostrar la contraseña», «Entrar» y «Este teléfono queda como un dispositivo de tu cuenta. Puedes cerrarlo desde Ajustes.».
  2. **Dado** credenciales correctas, **cuando** pulsa «Entrar», **entonces** se envía el nombre del teléfono como `device_name`, la API responde 201 con un token que empieza por `0ff1ce_dt_`, el token queda en el almacén seguro y entra en la Oficina.
  3. **Dado** credenciales incorrectas, **cuando** pulsa «Entrar», **entonces** ve «Usuario o contraseña incorrectos.».
  4. **Dado** que no hay conexión, **cuando** pulsa «Entrar», **entonces** ve «No pudimos conectar con la oficina. Revisa tu conexión e intenta de nuevo.». **Hoy falla:** muestra `fetch failed: …` en inglés.
  5. **Dado** un campo vacío, **cuando** mira «Entrar», **entonces** está desactivado.
  6. **Dado** `device_name` vacío, **cuando** se crea el dispositivo, **entonces** se llama «App móvil»; se guardan como mucho 120 caracteres.
  7. **Dado** el token, **cuando** se guarda en el servidor, **entonces** solo queda su SHA-256 y se registra `auth.device_token` con el nombre del dispositivo.
- **Brechas código/docs:** —
- **Cobertura QA:** pendiente

### ACC-03 · Bloqueo tras demasiados intentos <a id="acc-03"></a>

- **Dónde:** PWA · app · backend
- **Estado:** funciona
- **Qué hace para Gustavo:** si alguien prueba contraseñas, la entrada se bloquea un rato.
- **Código:** `oficina_views.check_login` (10 fallos por IP y usuario en 15 minutos, contador compartido por `/auth/login` y `/auth/token`).
- **Criterios de aceptación:**
  1. **Dado** 10 fallos seguidos del mismo usuario desde la misma IP, **cuando** intenta otra vez, **entonces** la API responde 429 «Demasiados intentos; espera unos minutos.» y la interfaz muestra «Demasiados intentos. Espera unos minutos.» con el botón bloqueado 60 s.
  2. **Dado** 10 fallos en la PWA, **cuando** intenta entrar desde la app con el mismo usuario y la misma IP, **entonces** también recibe 429 (el contador es compartido).
  3. **Dado** un acierto, **cuando** entra, **entonces** el contador vuelve a cero.
  4. **Dado** que pasan 15 minutos desde el último fallo, **cuando** intenta, **entonces** ya no está bloqueado.
- **Brechas código/docs:** —
- **Cobertura QA:** pendiente

### ACC-04 · Volver a donde estaba después de entrar <a id="acc-04"></a>

- **Dónde:** PWA
- **Estado:** funciona
- **Qué hace para Gustavo:** si abre un enlace sin sesión, después de entrar llega a ese enlace.
- **Código:** `oficina/src/auth/session.tsx` (`RequireAuth`), `Login.tsx` (`safeNext`).
- **Criterios de aceptación:**
  1. **Dado** que no tiene sesión, **cuando** abre `/calendario/pieza/<id>`, **entonces** va a `/login?next=/calendario/pieza/<id>` y, tras entrar, llega a la pieza.
  2. **Dado** un `next` que apunta fuera de la PWA o a `/login`, **cuando** entra, **entonces** va a la Oficina.
  3. **Dado** la ruta `/`, **cuando** le falta sesión, **entonces** va a `/login` sin `next`.
- **Brechas código/docs:** —
- **Cobertura QA:** pendiente

### ACC-05 · Sesión caducada o revocada <a id="acc-05"></a>

- **Dónde:** PWA · app · backend
- **Estado:** funciona
- **Qué hace para Gustavo:** si su sesión caduca o se cierra desde otro dispositivo, vuelve a la pantalla de entrada sin quedarse en una pantalla rota.
- **Código:** `compartido/src/api/client.ts` (401 → `onUnauthorized`; 403 → comprueba la sesión); PWA `SessionBridge`; app `signOutLocally`.
- **Criterios de aceptación:**
  1. **Dado** una sesión caducada en la PWA, **cuando** cualquier petición responde 401, **entonces** se borran los datos en memoria y va a `/login?next=<ruta>`.
  2. **Dado** un 403 en la PWA, **cuando** pasa, **entonces** se comprueba la sesión: si ya no existe, es como un 401; si existe, se muestra el `detail` («No tienes permiso para esta acción.» por defecto).
  3. **Dado** un 403 por CSRF caducado en la PWA, **cuando** pasa, **entonces** se pide la sesión una vez para renovar la cookie y se reintenta la petición.
  4. **Dado** un token de dispositivo revocado, **cuando** la app hace cualquier petición, **entonces** la API responde 401, la app borra el token y va a la pantalla de entrada.
  5. **Dado** `GET /api/v1/auth/session` con un token revocado o desconocido, **cuando** se pide, **entonces** responde 200 `{authenticated: false, user: null}`.
- **Brechas código/docs:** —
- **Cobertura QA:** pendiente

### ACC-06 · Seguir dentro al abrir la app <a id="acc-06"></a>

- **Dónde:** app · backend
- **Estado:** con fallo conocido
- **Qué hace para Gustavo:** abre la app y sigue dentro, sin volver a escribir la contraseña, aunque esté sin conexión o el servidor esté reiniciando.
- **Código:** `movil/src/auth/session.tsx` (`restoreSession`), `movil/src/api/token.ts`, `movil/src/app/_layout.tsx`.
- **El fallo:** `restoreSession` solo conserva el token si el error es un `TypeError` («Offline launch: keep the token»). En el teléfono, `expo/fetch` lanza `FetchError` sin conexión, y un 5xx llega como `ApiError`; en los dos casos la app **borra el token y cierra la sesión**. Abrir la app sin red, o durante un despliegue (por ejemplo un 502), obliga a entrar de nuevo, y el dispositivo queda huérfano en el servidor hasta que se cierre desde la lista de dispositivos. Deducido del código; no se reprodujo en un teléfono.
- **Criterios de aceptación:**
  1. **Dado** un token válido, **cuando** abre la app con conexión, **entonces** la pantalla de inicio se mantiene hasta saber la sesión y entra en la Oficina sin pedir la contraseña.
  2. **Dado** un token válido y el teléfono sin conexión, **cuando** abre la app, **entonces** sigue dentro, las vistas muestran «Sin conexión. Mostrando lo último que cargó.» y sus errores, y al volver la red todo se recupera. **Hoy falla:** vuelve a la pantalla de entrada y el token se borra.
  3. **Dado** un token válido y el servidor respondiendo 502, **cuando** abre la app, **entonces** sigue dentro y reintenta. **Hoy falla.**
  4. **Dado** un token revocado, **cuando** abre la app, **entonces** la sesión responde `authenticated: false`, se borra el token y ve la pantalla de entrada.
  5. **Dado** que el almacén seguro no se puede leer, **cuando** abre la app, **entonces** ve la pantalla de entrada.
  6. **Dado** que la app conserva la sesión sin conexión, **cuando** vuelve la red, **entonces** recupera el usuario (para «Tu nota» y los permisos de LinkedIn), en vez de quedarse con `user: null` todo el arranque.
- **Brechas código/docs:** `app-movil-backend.md` pide «Si una petición devuelve 401, volver al login»; el código vuelve al login con cualquier error al arrancar.
- **Cobertura QA:** pendiente

### ACC-07 · Cerrar sesión en la PWA <a id="acc-07"></a>

- **Dónde:** PWA · backend
- **Estado:** funciona
- **Qué hace para Gustavo:** sale de la PWA en este navegador.
- **Código:** `POST /api/v1/auth/logout`; `ajustes/Sesion.tsx`.
- **Criterios de aceptación:**
  1. **Dado** Ajustes › Sesión y Acerca de, **cuando** lo abre, **entonces** ve «Has entrado como <usuario>.», «Cerrar sesión», «Cerrar sesión no desactiva las notificaciones de este dispositivo.», «Versión: oficina 0.1.0» y «Arte: LimeZu — Modern Interiors».
  2. **Dado** «Cerrar sesión», **cuando** lo pulsa, **entonces** dice «Cerrando…», la API responde 204, se borran los datos en memoria y va a `/login`.
  3. **Dado** un error, **cuando** vuelve, **entonces** se ve con el detalle y sigue dentro.
  4. **Dado** que cerró sesión, **cuando** llega una notificación push a ese navegador, **entonces** sigue llegando (cerrar sesión no la desactiva).
- **Brechas código/docs:** —
- **Cobertura QA:** pendiente

### ACC-08 · Cerrar sesión en la app <a id="acc-08"></a>

- **Dónde:** app · backend
- **Estado:** funciona
- **Qué hace para Gustavo:** sale de la app en este teléfono, que deja de recibir avisos y olvida su acceso.
- **Código:** `movil/src/auth/session.tsx` (`signOut`: `DELETE /api/v1/push/expo`, `POST /api/v1/auth/token/revocar`, `signOutLocally`); `movil/src/ajustes/Sesion.tsx`.
- **Criterios de aceptación:**
  1. **Dado** Ajustes › Sesión, **cuando** lo abre, **entonces** ve «Has entrado como <usuario>.», «Oficina: office.projectapp.co», «Cerrar sesión» con «Cerrar sesión en este teléfono también apaga sus avisos.» y «Versión: app 0.1.0».
  2. **Dado** «Cerrar sesión», **cuando** lo pulsa, **entonces** pide confirmación: «Este teléfono deja de recibir avisos y olvida su acceso. Para volver, entra con tu usuario y contraseña.».
  3. **Dado** que confirma, **cuando** termina, **entonces** se quita el token de push (`DELETE /api/v1/push/expo`), se revoca el token del dispositivo (204), se borra del almacén seguro y ve la pantalla de entrada.
  4. **Dado** que el servidor no responde, **cuando** cierra sesión, **entonces** sale igualmente en el teléfono (los errores se ignoran a propósito).
  5. **Dado** un token revocado, **cuando** se usa en cualquier petición, **entonces** la API responde 401 y sus tokens de push quedan inactivos (`device_revoked`).
  6. **Dado** `POST /api/v1/auth/token/revocar` con la sesión de la PWA, **cuando** se llama, **entonces** responde 400 «Solo se revoca un token de dispositivo; la sesión de la oficina se cierra con /auth/logout.».
- **Brechas código/docs:** la app no muestra un estado «Cerrando…»; la confirmación se cierra al momento.
- **Cobertura QA:** pendiente

### ACC-09 · Dispositivos con la app <a id="acc-09"></a>

- **Dónde:** PWA · app · backend
- **Estado:** parcial
- **Qué hace para Gustavo:** ve los teléfonos con la app abierta en su cuenta, cuál es el actual y si reciben avisos, y cierra la sesión de uno perdido o viejo.
- **Código:** `GET /api/v1/auth/dispositivos`, `DELETE /api/v1/auth/dispositivos/<id>`, `ajustes.devices`, `ajustes.expo_push`; app `movil/src/ajustes/Notificaciones.tsx`. La PWA no tiene esta sección.
- **Criterios de aceptación:**
  1. **Dado** dos teléfonos con sesión, **cuando** abre «Dispositivos con la app» en la app, **entonces** ve los dos, del más nuevo al más viejo, con el nombre, la última vez que se usó, cuál es este y si recibe avisos.
  2. **Dado** otro teléfono, **cuando** pulsa «Cerrar» y confirma «Cerrar la sesión de <nombre>» («Ese dispositivo tendrá que volver a entrar con usuario y contraseña, y deja de recibir avisos.»), **entonces** la API responde 204, desaparece de la lista y ese teléfono vuelve a la pantalla de entrada en su siguiente petición.
  3. **Dado** un id que no existe, ya revocado o de otro usuario, **cuando** se pide cerrarlo, **entonces** la API responde 404.
  4. **Dado** la PWA, **cuando** abre Ajustes, **entonces** ve también «Dispositivos con la app» para cerrar un teléfono perdido. **Hoy falla:** la PWA no tiene la sección, aunque `GET /api/v1/ajustes` ya trae `devices`.
- **Brechas código/docs:** un comentario de `movil/src/auth/session.tsx` dice que la PWA lista los dispositivos; no lo hace (`listDevices` no se usa en `oficina/src`). `last_used_at` se actualiza como mucho cada 5 minutos.
- **Cobertura QA:** pendiente

### ACC-10 · Entrada animada a la oficina <a id="acc-10"></a>

- **Dónde:** app
- **Estado:** funciona
- **Qué hace para Gustavo:** al entrar, la puerta pixel se abre y la imagen se funde con la Oficina en vivo.
- **Código:** `movil/src/entrada/useEntrada.ts`, `PixelDoor.tsx`, `door.ts`; `movil/src/app/login.tsx`.
- **Criterios de aceptación:**
  1. **Dado** un acierto en «Entrar», **cuando** termina, **entonces** la puerta se pliega, la imagen se acerca en saltos (2× y 3×) y se funde con la Oficina, que ya está montada debajo.
  2. **Dado** «reducir movimiento» en el teléfono, **cuando** entra, **entonces** solo hay un fundido.
  3. **Dado** que la app arranca con la sesión ya abierta, **cuando** se abre, **entonces** no hay animación de entrada.
- **Brechas código/docs:** —
- **Cobertura QA:** pendiente

### ACC-11 · Quién puede decidir <a id="acc-11"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Qué hace para Gustavo:** solo él (con su sesión en la PWA o su teléfono) puede tomar decisiones; un token de servicio solo puede leer.
- **Código:** `operador_views.human_session` (acepta la sesión de Django o un `DeviceToken`), `permissions.require` (`operate_linkedin`, `approve_actions`, `confirm_memory`, `use_paid_providers`).
- **Criterios de aceptación:**
  1. **Dado** un token de servicio (`ApiCredential`), **cuando** intenta vetar, parar la máquina, responder una pregunta, enviar una captura o cambiar la Galería, **entonces** recibe 403.
  2. **Dado** el token de dispositivo de Gustavo, **cuando** hace esas mismas acciones, **entonces** se aceptan, sin cookie ni `X-CSRFToken`.
  3. **Dado** la sesión de la PWA sin `X-CSRFToken`, **cuando** hace una escritura, **entonces** recibe 403.
  4. **Dado** un usuario sin `approve_actions`, **cuando** intenta enviar una captura o vetar, **entonces** recibe 403, también desde la app.
  5. **Dado** un Bearer que empieza por `0ff1ce_dt_` pero no existe, **cuando** se usa, **entonces** recibe 401 y no tapa a un token de servicio con el mismo prefijo.
- **Brechas código/docs:** —
- **Cobertura QA:** pendiente

## Retiradas

Ninguna.
