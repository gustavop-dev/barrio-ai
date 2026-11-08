# QA de la app en un emulador (Maestro + GitHub Actions)

Esta carpeta tiene los flujos de [Maestro](https://maestro.dev) que **usan la app como Gustavo**: tocan, escriben, deslizan, arrastran hojas y comprueban lo que tiene que aparecer en cada pantalla. Corren solo en GitHub Actions (`.github/workflows/qa-movil.yml`), en un emulador Android, contra una oficina de demostración sembrada en el propio runner. Nada se ejecuta en el portátil.

## Qué hace una ejecución

1. **Backend de demostración en el runner.** PostgreSQL con pgvector como servicio, `migrate`, `bootstrap_local` y `seed_qa`. Gunicorn sirve la API en `0.0.0.0:8787` con `LIVE_LINKEDIN=false`, `LIVE_PROVIDERS=false` y `OPERATOR_ALLOW_FAKE=true`: conector simulado, sin LinkedIn real ni proveedores de pago.
2. **APK de QA.** `expo prebuild` y Gradle `assembleRelease -PreactNativeArchitectures=x86_64`: una build release, con el JS empaquetado y R8, igual que la de EAS, pero para el emulador x86_64. `EXPO_PUBLIC_API_URL=http://10.0.2.2:8787`, que es el runner visto desde el emulador. El APK queda en caché mientras no cambien `movil/` (salvo esta carpeta) ni `compartido/`, así que cambiar solo los flujos o el backend no recompila.
3. **Emulador.** Android 15 x86_64 con KVM (`reactivecircus/android-emulator-runner`). La pantalla queda en **390×844 dp** (1170×2532 px a 480 dpi), el tamaño de los tableros de `diseno-movimiento/`, con las animaciones activadas y la zona horaria `America/Bogota`, la misma del backend.
4. **Flujos.** `scripts/qa/correr-maestro.sh` corre cada `NN-*.yaml` por separado y **vuelve a sembrar el backend antes de cada uno**. Así un flujo nunca depende de lo que cambió otro, y un fallo apunta a una sola pantalla. La sesión de la app se conserva entre flujos.
5. **Artefactos y resumen.** `scripts/qa/informe.py` escribe el resumen del job, un comentario en el PR y `informe.html`. El job falla si falla un flujo o si la app se cae.

### Por qué HTTP en claro solo en esta build

Android bloquea el HTTP sin cifrar en las builds release, y el backend del runner no tiene certificado. `app.config.js` añade `android:usesCleartextTraffic="true"` al manifiesto **solo cuando `OFFICE_QA_BUILD=1`**, y esa variable solo la pone este workflow. Los perfiles de EAS (`eas.json`) no la definen: el APK y el AAB de producción siguen aceptando solo HTTPS.

La misma condición apaga `updates.enabled`: el APK del emulador ejecuta el JS que lleva dentro y nunca consulta el servidor de actualizaciones de Expo al arrancar. Fuera de la QA la configuración nativa no cambia, así que la huella (`runtimeVersion: fingerprint`) de las builds de producción es la misma.

Se eligió una release con el JS empaquetado, en vez de una build debug, para probar lo mismo que se instala en el teléfono: Hermes, R8, sin Metro y sin el menú de desarrollo.

## Lanzar una QA

- **En un PR:** corre sola cuando el PR toca `movil/`, `compartido/`, `agentes-linkedin/`, `scripts/qa/` o el workflow.
- **A mano**, una vez que el workflow esté en `main`:

  ```bash
  gh workflow run qa-movil.yml                    # sobre main
  gh workflow run qa-movil.yml --ref mi-rama      # sobre otra rama
  gh run watch $(gh run list --workflow qa-movil.yml --limit 1 --json databaseId --jq '.[0].databaseId')
  ```

Una ejecución completa tarda unos 25 a 40 minutos la primera vez, porque compila el APK, y bastante menos con el APK y el AVD en caché.

## Revisar una ejecución (personas y agentes revisores)

```bash
scripts/qa/descargar.sh qa-descargas            # la última ejecución terminada
scripts/qa/descargar.sh qa-descargas --pr 42    # la última de un PR
scripts/qa/descargar.sh qa-descargas --run <id> # una concreta
```

Descarga el artefacto `qa-movil-<n>` en `qa-descargas/<run id>/`:

| Ruta | Qué es |
|---|---|
| `resumen.md` | flujos que pasan y fallan, si hubo crash, errores de JS, respuestas 5xx o 429 de la API |
| `informe.html` | el informe navegable: tabla de flujos con el motivo del fallo y, por flujo, sus capturas y su video |
| `capturas/NN-pantalla-SS-paso.png` | una captura por paso relevante, a 1170×2532 (3× los tableros de 390×844) |
| `capturas/fallos/` | la captura que Maestro toma al fallar un paso, con el nombre del flujo delante |
| `videos/NN-flujo-parteK.mp4` | la grabación de la pantalla de cada flujo, en partes de menos de 3 minutos |
| `junit/NN-flujo.xml` | el informe JUnit de Maestro de cada flujo |
| `maestro/NN-flujo.log`, `maestro/NN-flujo/` | la salida de Maestro y su carpeta de depuración (comandos, jerarquía de la vista al fallar) |
| `logcat/logcat-errores.txt` | crashes, `FATAL EXCEPTION`, señales nativas, ANR y errores de `ReactNativeJS` |
| `logcat/logcat-app.txt` | todo lo que escribió el proceso de la app y React Native |
| `logcat/logcat-completo.txt.gz` | el logcat entero, comprimido |
| `api.log` | el log de gunicorn: cada petición de la app con su código |
| `seed.log` | la salida de `seed_qa` antes de cada flujo |

Para comparar con el diseño, abre las capturas junto a los tableros `movil/diseno-movimiento/tableros/*.dc.html` (390×844) y `movil/MOTION.md`.

## El mundo de QA (`seed_qa`)

`agentes-linkedin/infra/src/team_backend/management/commands/seed_qa.py` crea un usuario `qa`, superusuario y solo de CI, con contraseña en `QA_PASSWORD`, y una oficina completa:

- las cuentas simuladas;
- una pieza en cada estado: programada para mañana y vetable, publicada con cortes de 72 h y de 7 días, bloqueada con ronda de reparación, saltada y fallida;
- comentarios y acciones de red pendientes, y acciones ya hechas para la Lista y el calendario;
- personas en cada etapa, oportunidades en varias etapas y referentes;
- todas las tarjetas de Tu turno: «¿Salió o no?», una conversación del inbox, preguntas de texto, de opción y de sí o no, una pospuesta y la orientación del analista;
- notificaciones leídas y sin leer, y «Próximo»;
- una captura transcrita y una idea usada;
- cuatro fotos generadas en la Galería;
- unos 100 días de audiencia, trabajos y sincronizaciones de red para Resultados, el resumen semanal y filas de gasto.

Es idempotente: cada ejecución vacía el mundo de QA y lo vuelve a crear con los mismos ids y textos. Por eso **se niega a correr** si no está `QA_SEED=permitido`, si hay un interruptor `LIVE_*` activado o si la base tiene una cuenta real de LinkedIn. La prueba `team_backend/tests/test_seed_qa.py` lo cubre en el CI normal.

## Los flujos

| Flujo | Qué hace |
|---|---|
| `01-entrada` | contraseña equivocada y su error; mostrar la contraseña; la correcta, la entrada animada y la Oficina |
| `02-navegacion` | las cuatro pestañas de abajo, los cuatro accesos de arriba, el «atrás» de Android por el historial y el «‹» de una ficha |
| `03-oficina` | tocar un personaje de la escena y ver su hoja, arrastrarla a altura completa y cerrarla, la tira de equipos y la Biblioteca |
| `04-tu-turno` | «¿Salió o no?» con su nota, responder una pregunta, deslizar a la derecha y a la izquierda, «Más tarde», «Pospuestas» y «Lo que el equipo sabe de ti» |
| `05-captura` | abrir la hoja, escribir, «Para qué es», grabar (o lo que muestre el emulador sin micrófono), cerrar sin enviar, mantener pulsado el botón, enviar, «Lo que enviaste» y «Deshacer» |
| `06-notificaciones` | «Próximo», filtros, tocar un aviso y llegar a la pieza o a la persona, «Marcar todo como leído» |
| `07-calendario` | Semana, Mes y Lista; tocar días y su hoja; deslizar semanas y meses; la pieza de mañana, los pliegues de «Cómo se escribió», vetar y «Deshacer»; la pieza bloqueada y su ronda de reparación |
| `08-resultados` | el resumen semanal con «Usar como orientación» y «Descartar», cada uno con «Deshacer»; el «Periodo»; la definición de un gráfico; tocar una barra |
| `09-personas` | filtros por etapa y búsqueda; la ficha de una persona con una nota nueva; mover una oportunidad de etapa (y deshacerlo); la validación al añadir un referente |
| `10-galeria` | abrir una foto, editar su nota, el interruptor de edición con IA, el visor y deslizar entre fotos |
| `11-ajustes` | todas las secciones, Autonomía, apagar un tipo de aviso, la lista de dispositivos y cerrar sesión (va al final) |

## Escribir o cambiar un flujo

- Un archivo por área (`NN-area.yaml`), que empieza con `- runFlow: comun/entrar.yaml`.
- Captura en cada paso relevante con `takeScreenshot: NN-area-SS-paso`, en minúsculas ASCII y con guiones.
- Selectores, por orden de preferencia: `id:` (el `testID` de React Native) y después el texto o la etiqueta de accesibilidad. Si falta un selector estable, añade un `testID` mínimo en la app.
- Cada interacción va seguida de lo que tiene que aparecer (`assertVisible`, `extendedWaitUntil`). Un flujo que solo hace capturas no detecta nada.
- El emulador usa render por software y es lento. Espera con `extendedWaitUntil` y timeouts de 20 a 30 s. La escena de la Oficina se anima sin parar: no uses `waitForAnimationToEnd` sin `timeout`.
- Los flujos no se prueban en el portátil: haz push y mira el PR, o lanza `gh workflow run qa-movil.yml --ref tu-rama`.

## Lo que no se automatiza

- **El micrófono.** El emulador del runner arranca con `-noaudio`: no hay entrada de audio real. El flujo de Captura mantiene pulsado el botón y comprueba lo que muestra la app, sin grabar voz de verdad.
- **Los avisos push reales.** Necesitan las credenciales de FCM y el servicio de Expo, y la QA no usa secretos ni servicios externos. Se prueba la pantalla de Ajustes › Notificaciones, no la entrega.
- **La cámara y el selector de fotos** (`-camera-back none`), y **abrir LinkedIn**: los enlaces del mundo de QA apuntan a `linkedin.example`, nunca a linkedin.com.
