# 0ff1ce móvil

Es la app nativa de la oficina de 0ff1ce, hecha con Expo SDK 58, React Native 0.88 y Expo Router. Tiene el mismo diseño y las mismas funciones que la PWA (`../oficina`), pero con gestos, vibraciones y avisos nativos. Por ahora se prueba en Android con **Expo Go**, sin compilar nada. iOS saldrá más adelante del mismo código.

En esta fase ya funcionan:

- la estructura de la app: barras de arriba y de abajo, botón de captura y navegación;
- la entrada con el token del dispositivo;
- **Tu turno**, completo, con acciones deslizando la tarjeta;
- **la captura**: mantener pulsado para grabar, foto, nota y envío con «Deshacer»;
- el registro de avisos push;
- **Galería**, **Ajustes** y **Notificaciones**, completas;
- **Calendario** (Mes, Semana y Lista, deslizando la semana o el mes y con el panel del día en una hoja) y **el detalle de una pieza**, con el veto y su «Deshacer».

Las demás vistas (Oficina, Resultados, Personas y la ficha de una persona) se ven por ahora como «En construcción».

## Probarla en tu Android con Expo Go (desde este portátil con WSL)

1. Instala **Expo Go** desde Google Play. No necesitas cuenta de Expo para esto.
2. En el portátil, dentro de WSL:

   ```bash
   cd movil
   npm ci                 # la primera vez, o cuando cambie package-lock.json
   npx expo start --tunnel
   ```

3. Escanea el código QR de la terminal con la app Expo Go. En Android, Expo Go trae su propio lector de QR.
4. Entra con tu usuario y tu contraseña de Django. El teléfono queda registrado como un dispositivo de tu cuenta y guarda su token en el almacén seguro del sistema.

**Por qué `--tunnel`.** Metro, el servidor que entrega el código a Expo Go, corre dentro de WSL, y WSL tiene una red propia detrás de Windows. Por eso el teléfono no alcanza la IP de WSL aunque esté en la misma wifi. El túnel publica Metro en una URL pública temporal que el teléfono sí alcanza.

- La primera vez, Expo puede pedir instalar `@expo/ngrok`. Acepta.
- No hace falta abrir puertos en Windows ni iniciar sesión en Expo.
- Si el túnel va lento, `npx expo start --lan` funciona solo si configuras WSL en modo de red *mirrored* (`networkingMode=mirrored` en `%UserProfile%\.wslconfig`) y permites el puerto 8081 en el firewall de Windows.

Con la app abierta:

- al guardar un archivo, la app se recarga sola;
- al agitar el teléfono, se abre el menú de desarrollo;
- `r` en la terminal recarga la app.

### A qué oficina se conecta (`EXPO_PUBLIC_API_URL`)

Por defecto la app habla con la oficina real, `https://office.projectapp.co`, con tu usuario de siempre. Para usar otro backend, por ejemplo el Django de este portátil:

```bash
EXPO_PUBLIC_API_URL=https://tu-backend.example npx expo start --tunnel
```

También puedes crear `movil/.env.local` (no se sube al repositorio) con una línea `EXPO_PUBLIC_API_URL=https://…`.

- El valor queda fijo al empaquetar la app: tras cambiarlo, reinicia con `npx expo start --tunnel --clear`.
- El teléfono tiene que poder alcanzar esa URL. `localhost` o `127.0.0.1` apuntan al propio teléfono.
- Para el Django de este portátil, expón `127.0.0.1:8787` con un túnel HTTPS y pon esa URL.

## Instalarla en tu teléfono como app (APK con EAS Build)

Expo Go sirve para desarrollar. Para tener 0ff1ce en la pantalla de inicio, con su icono y su nombre, se compila un APK en la nube de Expo (EAS Build). Se compila en sus servidores, no en este portátil. `eas.json` ya trae dos perfiles:

- `preview`: un APK para instalar directamente en tu Android.
- `production`: el `.aab` para Google Play, cuando toque.

La primera vez, en `movil/`:

```
npx eas-cli@latest login                 # tu cuenta de Expo (la misma de `expo start`)
npx eas-cli@latest init                  # crea el proyecto en expo.dev y escribe su projectId en app.json
npx eas-cli@latest build -p android --profile preview
```

El build tarda unos 10 a 15 minutos. Al terminar, EAS da un enlace y un QR para descargar el APK:

1. Ábrelo en el teléfono e instálalo. Android pedirá permitir «instalar apps desconocidas» desde el navegador.
2. Queda como **0ff1ce**, con el icono de la marca, conectada a `https://office.projectapp.co`.
3. El `projectId` que escribe `eas init` en `app.json` se sube al repo.

Los dos perfiles compilan solo para `arm64-v8a`, la arquitectura de casi todos los Android actuales (`ORG_GRADLE_PROJECT_reactNativeArchitectures` en `eas.json`). Con las cuatro arquitecturas por defecto, el compilador de C++ de Skia se quedaba sin memoria en la máquina gratuita de EAS («Killed» en la fase Run gradlew).

Un APK nuevo se instala encima del anterior, sin perder la sesión. Solo hace falta cuando cambia algo nativo: los cambios de JavaScript llegan solos como actualización OTA (sección siguiente). Las notificaciones push en el APK necesitan además las credenciales de FCM (Firebase), que se cargan en EAS con `npx eas-cli@latest credentials`.

## Actualizaciones OTA (sin reinstalar el APK)

Desde el próximo APK, la app trae `expo-updates`. Los cambios de JavaScript llegan solos al teléfono, sin compilar ni reinstalar: es una actualización OTA («over the air») de EAS Update.

### Cómo funciona

- Cada APK lleva dentro su canal (`channel` en `eas.json`): `preview` si sale del perfil `preview`, `production` si sale del perfil `production`.
- Al abrirse, la app pregunta a `https://u.expo.dev/<projectId>` (`updates.url` en `app.json`) si hay una actualización más nueva para su canal y su `runtimeVersion`.
- Si la hay, la descarga en segundo plano y la usa **en el siguiente arranque**. La app nunca espera a la red para arrancar: son los valores por defecto, `checkAutomatically: ON_LOAD` y `fallbackToCacheTimeout: 0`.
- Para verla ya, cierra la app del todo y vuelve a abrirla. A veces hace falta dos veces: una la descarga y la otra la aplica.
- Cada canal lee la rama de EAS Update con su mismo nombre: el canal `preview` lee la rama `preview`.

### Quién publica: GitHub Actions

`.github/workflows/eas-update.yml` publica en la rama `preview`:

- en cada push a `main` que cambie `movil/` o `compartido/` (salvo los `.md` y `diseno-movimiento/`);
- a mano, desde Actions › «Actualización OTA (preview)» › Run workflow.

Antes de publicar repite las comprobaciones del job `movil` de CI (tipos, lint y pruebas) sobre ese commit. Si fallan, no publica nada. Después corre:

```bash
npx eas-cli@latest update --branch preview --environment preview --platform android \
  --non-interactive --message "<asunto del commit>"
```

- `--environment` es obligatorio desde el SDK 55: elige qué variables de entorno de EAS se usan. Hoy no hay ninguna.
- `eas update` no lee el `env` de los perfiles de `eas.json`. `EXPO_PUBLIC_API_URL` se queda en su valor por defecto, `https://office.projectapp.co` (`src/api/config.ts`), el mismo que usa el APK. Para cambiarlo en las OTA, crea la variable en expo.dev para el entorno `preview`.
- Solo Android: todavía no hay build de iOS.
- Sin el secreto `EXPO_TOKEN`, el workflow termina en verde con un aviso y no publica nada.

Producción no publica sola. Cuando haya builds de `production`, se publica a mano desde `movil/`:

```bash
npx eas-cli@latest update --channel production --environment production --platform android --message "…"
```

### `runtimeVersion`: política `fingerprint`

`app.json` lleva `"runtimeVersion": { "policy": "fingerprint" }`. Expo calcula un hash de todo lo que afecta al código nativo: las dependencias con código nativo y sus versiones, los plugins y campos nativos de `app.json`, y el SDK.

- Ese hash es la `runtimeVersion` del APK y de cada actualización.
- Una actualización solo llega a los APK que tienen el mismo hash.
- Si un cambio toca lo nativo, el hash cambia. La actualización se publica igual, pero ningún APK instalado la recibe hasta que se compila uno nuevo. Así, una OTA nunca llama a código nativo que el APK no tiene.

La otra opción era `appVersion`, donde la `runtimeVersion` es el campo `version` de `app.json`. Con ella hay que acordarse de subir `version` cada vez que cambia algo nativo. Si se olvida, la OTA llega a un APK incompatible y la app falla al usar ese código. Con `fingerprint` no hay nada que recordar, y el `versionCode` que sube EAS en cada build de producción no cambia el hash. El precio es compilar un APK cada vez que cambia algo nativo, que es justo cuando hace falta.

### ¿APK nuevo o actualización OTA?

| Cambio | Cómo llega |
|---|---|
| Código de `movil/src` o `compartido/src`: pantallas, textos, estilos, lógica, hooks | OTA |
| Imágenes y fuentes que se importan desde el código | OTA |
| Una dependencia solo de JavaScript, sin código nativo | OTA |
| Instalar, quitar o actualizar un módulo nativo: un `expo-*` con código nativo, un `react-native-*`, Skia… | APK nuevo |
| Subir el SDK de Expo o la versión de React Native | APK nuevo |
| Campos nativos de `app.json`: `plugins`, permisos, `android.*`, icono, splash, nombre, `scheme`, `updates`, `runtimeVersion` | APK nuevo |
| La compilación en `eas.json` (perfiles, `env`, arquitecturas) y las credenciales, como FCM | APK nuevo |
| Los `scripts` de `package.json` | No cambian el APK, pero sí el fingerprint: las OTA siguientes solo llegan a un APK nuevo |

El hash no cambia con `version` de `app.json`, con el `versionCode` ni con `eas.json` (preset `balanced` de `@expo/fingerprint`). Si dudas, compara el hash del proyecto con el de un build:

```bash
npx eas-cli@latest fingerprint:compare --build-id <id del build>
```

El log de `eas update` muestra la `runtimeVersion` publicada, y expo.dev › Updates indica si algún build la comparte.

### El primer APK con OTA

Los APK compilados antes de este cambio no tienen `expo-updates` y no reciben nada. El primero con OTA será el próximo `npx eas-cli@latest build -p android --profile preview` desde `main`. Se instala una vez encima del anterior y, desde ahí, recibe las actualizaciones.

### Preparar el token (una vez)

1. En expo.dev, con la cuenta `gustavoperez`, abre https://expo.dev/settings/access-tokens y pulsa **Create token**. Ponle un nombre como `github-barrio-ai` y copia el token: solo se muestra una vez.
2. En GitHub, abre `gustavop-dev/barrio-ai` › Settings › Secrets and variables › Actions › **New repository secret**. Nombre: `EXPO_TOKEN`. Valor: el token.
   - Desde la terminal también vale: `gh secret set EXPO_TOKEN --repo gustavop-dev/barrio-ai`, y pega el token cuando lo pida.
3. Si el token se filtra, revócalo en la misma página de expo.dev y crea otro.

El token nunca va en el repositorio ni en `eas.json`.

### Ver y deshacer

Desde `movil/`:

```bash
npx eas-cli@latest update:list --branch preview       # lo publicado
npx eas-cli@latest channel:view preview               # qué rama sirve el canal
npx eas-cli@latest update:rollback                    # interactivo: la actualización anterior o el código del APK
npx eas-cli@latest update:roll-back-to-embedded --branch preview --platform android --message "Vuelta al APK"
npx eas-cli@latest update:republish --group <id>      # vuelve a publicar una actualización concreta
npx eas-cli@latest channel:pause preview              # deja de servir actualizaciones (channel:resume las reanuda)
```

- `update:rollback` vuelve a publicar la actualización anterior. Si no hay ninguna, vuelve al código del APK.
- `update:roll-back-to-embedded` hace que los teléfonos vuelvan a usar el código que trae el APK.
- Los teléfonos reciben la vuelta atrás como cualquier actualización: al abrir la app, y se ve en el siguiente arranque.
- La siguiente publicación, por ejemplo el próximo push a `main`, vuelve a llegar a todos.
- Si una actualización hace fallar la app al arrancar, `expo-updates` intenta volver solo a la última que funcionaba.

### Criterios de aceptación

Están en el catálogo de funcionalidades: [APP-11 · Actualizaciones OTA sin reinstalar](../docs/funcionalidades/app-movil-instalacion.md#app-11).

## Qué funciona en Expo Go y qué necesitará una build de desarrollo

Funciona en Expo Go:

- toda la interfaz, las animaciones (Reanimated 4) y los gestos (Gesture Handler 3);
- las vibraciones (`expo-haptics`) y las fuentes Ubuntu (`expo-font`);
- el token en el almacén seguro (`expo-secure-store`);
- grabar audio (`expo-audio`), con el permiso del micrófono explicado antes de que lo pida el sistema;
- la cámara y la galería (`expo-image-picker`);
- las fotos privadas de la Galería con el token (`expo-image`) y el navegador dentro de la app para conectar LinkedIn (`expo-web-browser`);
- la conexión de red (`@react-native-community/netinfo`);
- las notificaciones *locales*, y abrir la vista correcta al tocar una notificación.

Necesitará una **build de desarrollo** (`eas build --profile development` o `npx expo run:android`, con tu cuenta de Expo):

- **Los avisos push reales.** Expo Go para Android no recibe notificaciones remotas desde el SDK 53. Además, el token de Expo necesita un proyecto de EAS (`extra.eas.projectId` en `app.json`) y las credenciales de FCM de Google. Mientras tanto, la app no falla: Ajustes › Notificaciones explica por qué todavía no llegan avisos.
  - En cada arranque con sesión, la app registra su token con `POST /api/v1/push/expo`. El canal de Android se llama `default`.
  - Al tocar un aviso, se abre su `data.url` dentro de la app.
- El icono, la pantalla de inicio y el nombre propios de la app. En Expo Go se ven los de Expo Go; en una build salen de `app.json` y de `assets/`.
- Más adelante, la escena de la oficina con `@shopify/react-native-skia`. Skia viene en Expo Go, pero aún no está instalado: llegará con esa pantalla.
- Firmar y publicar en Google Play.

No hay cuentas de Expo ni builds de EAS hechas: eso le toca a Gustavo con su cuenta. Cuando exista el proyecto, se añade su `projectId` a `app.json` y se elige el identificador de Android, por ejemplo `co.projectapp.oficina`.

## Estructura

```
movil/
  app.json              nombre, esquema, icono, splash, permisos, plugins, OTA (updates, runtimeVersion)
  eas.json              perfiles de EAS Build (preview: APK, production: AAB) y sus canales OTA
  metro.config.js       vigila ../compartido y define los alias @/ y @compartido/
  jest.config.js        jest-expo, con los mismos alias y la cobertura de movil y compartido
  MOTION.md             todos los tokens de movimiento y dónde se usan
  src/
    app/                rutas de Expo Router (login, (app)/(tabs)/…, detalles)
    api/                transporte nativo (Bearer), token, QueryClient
    auth/               sesión con token del dispositivo
    capture/            botón para mantener pulsado, hoja de captura, grabadora
    turno/              Tu turno: lista, tarjetas, deslizar, preguntas, «lo que sabe»
    calendario/         Calendario: semana, mes, lista, panel del día, veto con «Deshacer»
    pieza/              detalle de una pieza: cortes, texto final, comentarios, «Cómo se escribió»
    components/         interfaz (ui/), barras (shell/) e iconos
    push/               registro de avisos y rutas de data.url
    theme/              tokens.ts (colores, tipos, espacios) y motion.ts
../compartido/src/      tipos, endpoints, claves, hooks y lógica pura que usa también la PWA
```

### Código compartido con la PWA

`../compartido` tiene lo que no depende de cómo viaja una petición:

- los tipos de la API, los endpoints, las claves de consulta y la tabla `REFRESH`;
- los hooks de TanStack Query;
- la lógica de Tu turno (orden, prioridades, fechas), los formatos, las fechas del calendario, las etiquetas de Personas y de la captura, y los roles del atlas.

El cliente HTTP es inyectable: cada app instala su transporte al arrancar.

- La PWA envía la cookie de sesión y CSRF (`oficina/src/api/client.ts`).
- La app nativa envía `Authorization: Bearer <token>` contra `EXPO_PUBLIC_API_URL` (`src/api/transport.ts`). Un 401 la devuelve a la pantalla de entrada.

`compartido/` no tiene `node_modules` propios. Su única dependencia (`@tanstack/react-query`) sale de la app que lo usa:

- los tipos, del `paths` de `tsconfig.json`;
- en Metro, de `nodeModulesPaths`;
- en Jest, de `modulePaths`;
- en la PWA, de `resolve.dedupe` de Vite.

Desde aquí se le pasan el lint, el chequeo de tipos y las pruebas, y la PWA vuelve a comprobar sus tipos.

## Comandos

```bash
npm run typecheck    # tsc (movil + compartido)
npm run lint         # eslint (movil + compartido)
npm test             # jest: movil y compartido, con red y módulos nativos simulados
npm run test:cobertura  # lo mismo con cobertura de movil y compartido en coverage/ (lcov-report/index.html)
npm run export       # npx expo export --platform android: prueba que el paquete se construye
npm run doctor       # npx expo-doctor (versión fija)
npm run icons        # regenera iconos, splash y retratos desde oficina/public/brand
```

Las pruebas no llaman a la red ni a servicios de pago: `fetch`, el almacén seguro, el audio, la cámara, las notificaciones y las vibraciones están simulados (`jest.setup.tsx`, `src/test/`).

## Seeing changes instantly on the phone (development build)

You don't need to rebuild the APK to see a JavaScript change. Install the **development build** once, and from then on every change shows on the phone in 1–2 seconds (Fast Refresh).

1. Build it once, about 15 min on EAS:
   ```bash
   cd movil && npx eas-cli@latest build -p android --profile development
   ```
   Install the APK from the link it prints. It shows up as «0ff1ce» with the Expo development menu.
2. Each working session, on the laptop:
   ```bash
   cd movil && npx expo start --dev-client
   ```
   Open the app on the phone and pick the laptop's server. The phone and the laptop must be on the same Wi-Fi; otherwise add `--tunnel`. Every file you save reloads on the phone right away.
3. The development build talks to `https://office.projectapp.co`, the same backend as the installed app.

Rebuild the development build only when a native dependency or `app.json` changes. Metro is much lighter than a local emulator or Gradle. The Maestro tests still run on GitHub (`qa-movil.yml`).
