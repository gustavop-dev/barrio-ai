# 0ff1ce móvil

Es la app nativa de la oficina de 0ff1ce, hecha con Expo SDK 58, React Native 0.88 y Expo Router. Tiene el mismo diseño y las mismas funciones que la PWA (`../oficina`), pero con gestos, vibraciones y avisos nativos. Por ahora se prueba en Android con **Expo Go**, sin compilar nada. iOS saldrá más adelante del mismo código.

En esta fase ya funcionan:

- la estructura de la app: barras de arriba y de abajo, botón de captura y navegación;
- la entrada con el token del dispositivo;
- **Tu turno**, completo, con acciones deslizando la tarjeta;
- **la captura**: mantener pulsado para grabar, foto, nota y envío con «Deshacer»;
- el registro de avisos push;
- **Galería**, **Ajustes** y **Notificaciones**, completas.

Las demás vistas (Oficina, Resultados, Personas, Calendario, la ficha de una persona y el detalle de una pieza) se ven por ahora como «En construcción».

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
  app.json              nombre, esquema, icono, splash, permisos, plugins
  metro.config.js       vigila ../compartido y define los alias @/ y @compartido/
  jest.config.js        jest-expo, con los mismos alias
  MOTION.md             todos los tokens de movimiento y dónde se usan
  src/
    app/                rutas de Expo Router (login, (app)/(tabs)/…, detalles)
    api/                transporte nativo (Bearer), token, QueryClient
    auth/               sesión con token del dispositivo
    capture/            botón para mantener pulsado, hoja de captura, grabadora
    turno/              Tu turno: lista, tarjetas, deslizar, preguntas, «lo que sabe»
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
npm run export       # npx expo export --platform android: prueba que el paquete se construye
npm run doctor       # npx expo-doctor (versión fija)
npm run icons        # regenera iconos, splash y retratos desde oficina/public/brand
```

Las pruebas no llaman a la red ni a servicios de pago: `fetch`, el almacén seguro, el audio, la cámara, las notificaciones y las vibraciones están simulados (`jest.setup.tsx`, `src/test/`).
