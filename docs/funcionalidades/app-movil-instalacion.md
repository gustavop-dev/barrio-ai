# App móvil: instalación (`APP`)

Cómo se compila e instala la app nativa de 0ff1ce, a qué servidor se conecta, qué permisos pide y qué falta para que todo funcione en un teléfono real.

- **Código:** `movil/eas.json`, `movil/app.json`, `movil/src/api/config.ts`, `movil/src/api/transport.ts`, `movil/src/api/token.ts`, `movil/package.json`; CI `.github/workflows/barrio-ai.yml` (trabajo `movil`).
- **Documentación:** [`movil/README.md`](../../movil/README.md), [`movil/AGENTS.md`](../../movil/AGENTS.md), [`app-movil-backend.md`](../../agentes-linkedin/infra/docs/app-movil-backend.md).

## Resumen

| ID | Función | Dónde | Estado |
| --- | --- | --- | --- |
| [APP-01](#app-01) | Compilar e instalar la app (APK) | app | funciona |
| [APP-02](#app-02) | A qué oficina se conecta | app | funciona |
| [APP-03](#app-03) | Nombre, icono y paquete | app | funciona |
| [APP-04](#app-04) | Permisos del teléfono | app | parcial |
| [APP-05](#app-05) | Instalar una versión nueva sin perder la sesión | app | funciona |
| [APP-06](#app-06) | Probar con Expo Go | app | funciona |
| [APP-07](#app-07) | Build de desarrollo | app | no implementado |
| [APP-08](#app-08) | Mensajes de error de red en español | app | con fallo conocido |
| [APP-09](#app-09) | App para iPhone | app | no implementado |
| [APP-10](#app-10) | Comprobaciones automáticas de la app | app | funciona |

---

### APP-01 · Compilar e instalar la app (APK) <a id="app-01"></a>

- **Dónde:** app
- **Estado:** funciona
- **Qué hace para Gustavo:** compila la app en la nube de Expo y la instala en su Android con un enlace o un QR.
- **Código:** `movil/eas.json` (perfil `preview`: `distribution: internal`, `android.buildType: apk`; perfil `production`: `app-bundle`, `autoIncrement`); `extra.eas.projectId` en `app.json`.
- **Criterios de aceptación:**
  1. **Dado** la cuenta de Expo de Gustavo (`owner: gustavoperez`) y el proyecto `704ea73a-9382-4918-b361-ea6d83bd582e`, **cuando** ejecuta `npx eas-cli@latest build -p android --profile preview`, **entonces** la build termina (unos 10–15 minutos) y da un enlace y un QR para descargar el APK.
  2. **Dado** el APK, **cuando** lo abre en el teléfono y permite «instalar apps desconocidas», **entonces** queda instalada como «0ff1ce» con su icono.
  3. **Dado** la build, **cuando** compila, **entonces** lo hace solo para `arm64-v8a` (`ORG_GRADLE_PROJECT_reactNativeArchitectures`), para que Skia no se quede sin memoria en la máquina gratuita de EAS.
  4. **Dado** el perfil `production`, **cuando** se compila, **entonces** produce un `.aab` para Google Play e incrementa el número de build solo.
- **Brechas código/docs:** `movil/README.md` también dice, en otra sección, que «No hay cuentas de Expo ni builds de EAS hechas» y propone el paquete `co.projectapp.oficina`; ya hay proyecto de EAS y el paquete es `co.projectapp.office`.
- **Cobertura QA:** pendiente

### APP-02 · A qué oficina se conecta <a id="app-02"></a>

- **Dónde:** app
- **Estado:** funciona
- **Qué hace para Gustavo:** la app instalada habla con su oficina real; para desarrollo se puede apuntar a otro servidor.
- **Código:** `movil/src/api/config.ts` (`EXPO_PUBLIC_API_URL`, por defecto `https://office.projectapp.co`, sin barra final), `eas.json` (los dos perfiles fijan esa URL).
- **Criterios de aceptación:**
  1. **Dado** la build de `preview` o `production`, **cuando** hace cualquier petición, **entonces** va a `https://office.projectapp.co/api/v1/…` con `Authorization: Bearer <token>`, sin cookies ni `X-CSRFToken`.
  2. **Dado** `EXPO_PUBLIC_API_URL=https://otro.ejemplo` al arrancar Metro (o en `movil/.env.local`), **cuando** se empaqueta, **entonces** la app usa esa URL; cambiarla exige reiniciar con `--clear`.
  3. **Dado** las imágenes privadas, el audio y el enlace a la PWA para conectar LinkedIn, **cuando** se construyen, **entonces** usan la misma URL base.
  4. **Dado** Ajustes › Sesión, **cuando** lo abre, **entonces** ve «Oficina: office.projectapp.co».
- **Brechas código/docs:** —
- **Cobertura QA:** pendiente

### APP-03 · Nombre, icono y paquete <a id="app-03"></a>

- **Dónde:** app
- **Estado:** funciona
- **Qué hace para Gustavo:** la app se reconoce en el teléfono como 0ff1ce.
- **Código:** `movil/app.json` (`name: 0ff1ce`, `slug: oficina-0ff1ce`, `scheme: oficina0ff1ce`, `version: 0.1.0`, `android.package: co.projectapp.office`, icono adaptativo, `orientation: portrait`, pantalla de inicio).
- **Criterios de aceptación:**
  1. **Dado** la app instalada, **cuando** mira la pantalla de inicio, **entonces** ve «0ff1ce» con el icono adaptativo (fondo `#0FF1CE`) y, en Android 13+, el icono monocromo.
  2. **Dado** que la abre, **cuando** carga, **entonces** ve la pantalla de inicio de la marca hasta que cargan las fuentes y se conoce la sesión.
  3. **Dado** un enlace `oficina0ff1ce://…`, **cuando** lo abre, **entonces** abre la app.
  4. **Dado** la app, **cuando** gira el teléfono, **entonces** se queda en vertical.
  5. **Dado** Ajustes › Sesión, **cuando** lo abre, **entonces** ve «Versión: app 0.1.0».
- **Brechas código/docs:** la versión mostrada es la de `app.json`; el número de build de EAS no aparece en ninguna parte.
- **Cobertura QA:** pendiente

### APP-04 · Permisos del teléfono <a id="app-04"></a>

- **Dónde:** app
- **Estado:** parcial
- **Qué hace para Gustavo:** la app pide el micrófono, la cámara y las notificaciones cuando hacen falta, explicando para qué.
- **Código:** `app.json` (permisos Android `RECORD_AUDIO`, `MODIFY_AUDIO_SETTINGS`, `FOREGROUND_SERVICE`, `FOREGROUND_SERVICE_MEDIA_PLAYBACK`; textos de `expo-audio` y `expo-image-picker`), `movil/src/capture/*`, `movil/src/push/register.ts`.
- **Criterios de aceptación:**
  1. **Dado** el micrófono, **cuando** va a grabar por primera vez, **entonces** la app explica antes «Para grabar, 0ff1ce necesita el micrófono» y después aparece el aviso del sistema ([CAP-13](captura.md#cap-13)).
  2. **Dado** la cámara, **cuando** pulsa «Tomar foto» por primera vez, **entonces** aparece el aviso del sistema y, si lo niega, una explicación con una forma de ir a los ajustes. **Hoy:** aparece el aviso sin explicación previa y, si lo niega, solo una línea roja sin botón a los ajustes.
  3. **Dado** las fotos, **cuando** pulsa «Galería», **entonces** se abre el selector de fotos del sistema sin pedir permiso.
  4. **Dado** las notificaciones, **cuando** entra en la app por primera vez, **entonces** se explica para qué antes del aviso del sistema. **Hoy falla:** el aviso del sistema aparece nada más entrar ([PUS-07](notificaciones-push.md#pus-07)).
  5. **Dado** iOS, **cuando** se pidan permisos, **entonces** se usan los textos «0ff1ce usa el micrófono solo mientras grabas un audio para el equipo.», «0ff1ce usa la cámara solo para tomar la foto que adjuntas a una captura.» y «0ff1ce abre tus fotos solo para adjuntar las que elijas a una captura.».
- **Brechas código/docs:** no se pudo comprobar el manifiesto final de Android (si quedan declarados `CAMERA` y `POST_NOTIFICATIONS`, que suelen venir de las bibliotecas).
- **Cobertura QA:** pendiente

### APP-05 · Instalar una versión nueva sin perder la sesión <a id="app-05"></a>

- **Dónde:** app
- **Estado:** funciona
- **Qué hace para Gustavo:** instala la build nueva encima de la anterior y sigue dentro.
- **Código:** token en `expo-secure-store` (`oficina.token-dispositivo`), mismo paquete `co.projectapp.office`.
- **Criterios de aceptación:**
  1. **Dado** la app instalada con sesión, **cuando** instala un APK nuevo del mismo paquete y firma, **entonces** al abrirla sigue dentro sin escribir la contraseña.
  2. **Dado** que desinstala la app, **cuando** la vuelve a instalar, **entonces** tiene que entrar de nuevo y el dispositivo viejo queda en la lista hasta que lo cierre ([ACC-09](acceso.md#acc-09)).
- **Brechas código/docs:** no hay `expo-updates`: cada cambio exige una build nueva.
- **Cobertura QA:** pendiente

### APP-06 · Probar con Expo Go <a id="app-06"></a>

- **Dónde:** app
- **Estado:** funciona
- **Qué hace para Gustavo:** prueba la app en su Android sin compilar, con Expo Go.
- **Código:** `movil/README.md` («Probarla en tu Android con Expo Go»), `npx expo start --tunnel`.
- **Criterios de aceptación:**
  1. **Dado** Expo Go en Android, **cuando** escanea el QR de `npx expo start --tunnel`, **entonces** la app abre, entra con su usuario y funcionan la interfaz, los gestos, las vibraciones, la grabación, la cámara y las fotos privadas.
  2. **Dado** Expo Go en Android, **cuando** abre Ajustes › Notificaciones, **entonces** ve «Expo Go no recibe avisos push en Android: llegan con la build de desarrollo.» (los avisos remotos no llegan en Expo Go).
- **Brechas código/docs:** en Expo Go también se aplica el fallo de subida de audio y fotos ([CAP-04](captura.md#cap-04)), porque también usa `expo/fetch`.
- **Cobertura QA:** pendiente

### APP-07 · Build de desarrollo <a id="app-07"></a>

- **Dónde:** app
- **Estado:** no implementado
- **Qué hace para Gustavo:** tendría una build propia para desarrollar con avisos push reales, como pide el README.
- **Código:** no existe. `eas.json` no tiene perfil `development` y `package.json` no incluye `expo-dev-client`.
- **Criterios de aceptación:**
  1. **Dado** `npx eas-cli@latest build --profile development -p android`, **cuando** se ejecuta, **entonces** produce una build de desarrollo instalable.
  2. **Dado** esa build, **cuando** se conecta a Metro, **entonces** recarga al guardar como en Expo Go y recibe avisos push reales.
- **Brechas código/docs:** `movil/README.md` («Necesitará una build de desarrollo») manda usar `eas build --profile development`, que no existe en `eas.json`.
- **Cobertura QA:** pendiente

### APP-08 · Mensajes de error de red en español <a id="app-08"></a>

- **Dónde:** app
- **Estado:** con fallo conocido
- **Qué hace para Gustavo:** cuando el teléfono no tiene conexión, cada pantalla le dice en español que no hay conexión.
- **Código:** `compartido/src/api/errors.ts` (`errorMessage`), `movil/src/auth/loginProblems.ts`, `movil/src/auth/session.tsx`; `expo/src/winter/fetch/FetchErrors.ts` (`FetchError extends Error`).
- **El fallo:** Expo SDK 58 sustituye el `fetch` global por `expo/fetch` (`EXPO_PUBLIC_USE_RN_FETCH` no está definido). Un fallo de red llega como `FetchError`, no como `TypeError`, y los tres sitios que reconocen la falta de red por `instanceof TypeError` no la reconocen: todos los avisos de error muestran `fetch failed: <mensaje del sistema en inglés>`, la entrada no muestra su mensaje de sin conexión ([ACC-02](acceso.md#acc-02)) y abrir la app sin red cierra la sesión ([ACC-06](acceso.md#acc-06)). Las pruebas de Jest no lo detectan porque sustituyen `fetch` por un simulacro.
- **Criterios de aceptación:**
  1. **Dado** el teléfono en modo avión, **cuando** cualquier pantalla falla al cargar, **entonces** muestra «No hay conexión con el servidor. Comprueba tu red.».
  2. **Dado** una acción que falla sin conexión (vetar, responder, enviar), **cuando** vuelve el error, **entonces** el mensaje está en español.
  3. **Dado** cualquier error, **cuando** se muestra, **entonces** nunca aparece texto técnico en inglés (`fetch failed: …`, `Unsupported FormDataPart implementation`).
  4. **Dado** la barra superior, **cuando** no hay red, **entonces** muestra «Sin conexión. Mostrando lo último que cargó.» (esto ya funciona, con NetInfo).
- **Brechas código/docs:** —
- **Cobertura QA:** pendiente

### APP-09 · App para iPhone <a id="app-09"></a>

- **Dónde:** app
- **Estado:** no implementado
- **Qué hace para Gustavo:** tendría la app también en su iPhone, «del mismo código», como anuncia el README.
- **Código:** no existe la configuración. `app.json` solo tiene `ios.supportsTablet: false`, sin `bundleIdentifier`; `eas.json` no tiene ajustes de iOS.
- **Criterios de aceptación:**
  1. **Dado** la configuración de iOS, **cuando** se compila con EAS, **entonces** produce una build instalable en el iPhone de Gustavo.
  2. **Dado** esa build, **cuando** la usa, **entonces** cumple las mismas fichas que la app de Android, incluidos los avisos push por APNs.
- **Brechas código/docs:** `movil/README.md`: «iOS saldrá más adelante del mismo código».
- **Cobertura QA:** pendiente

### APP-10 · Comprobaciones automáticas de la app <a id="app-10"></a>

- **Dónde:** app
- **Estado:** funciona
- **Qué hace para Gustavo:** cada PR que toca la app o el código compartido pasa tipos, lint, pruebas y un empaquetado de Android antes de fusionarse.
- **Código:** `.github/workflows/barrio-ai.yml`, trabajo `movil` (`npm ci && npm run typecheck && npm run lint && npm test -- --ci && npx expo export --platform android`).
- **Criterios de aceptación:**
  1. **Dado** un PR que cambia `movil/`, `compartido/` o el workflow, **cuando** corre CI, **entonces** pasa el trabajo `movil` completo.
  2. **Dado** un PR que no toca esas carpetas, **cuando** corre CI, **entonces** el trabajo `movil` se salta.
  3. **Dado** CI, **cuando** termina, **entonces** no compila ninguna build de EAS: el APK se compila a mano.
- **Brechas código/docs:** las pruebas de la app simulan `fetch` (`movil/src/test/server.ts`), así que no cubren el comportamiento real de `expo/fetch` (multipart y errores de red). El filtro de rutas del workflow no incluye `docs/`: un PR solo de documentación no dispara CI.
- **Cobertura QA:** pendiente

## Retiradas

Ninguna.
