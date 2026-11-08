# Notificaciones push (`PUS`)

Los avisos que llegan al teléfono o al navegador aunque 0ff1ce esté cerrada: Web Push con VAPID para la PWA y push nativa por Expo para la app, con los mismos textos y los mismos interruptores por tipo. La bandeja dentro de la aplicación está en [notificaciones.md](notificaciones.md).

- **Código:** backend `notificaciones.py` (`avisar`, `INBOX_KINDS`, `FEED_KINDS`, `push_enabled`, `push_types`), `alerts.notify`, `push.py`, `expo.py`, `oficina_views.PushKey`, `PushSubscriptions`, `PushUnsubscribe`, `PushTest`, `movil_views.ExpoPush`; PWA `oficina/src/push/push.ts`, `payload.ts`, `oficina/src/sw.ts`, `pages/ajustes/Notificaciones.tsx`; app `movil/src/push/register.ts`, `routes.ts`, `movil/src/app/(app)/_layout.tsx`, `movil/src/ajustes/Notificaciones.tsx`.
- **Documentación:** «Notificaciones push» y «App móvil: login por dispositivo y push nativo» de [`CONTRATO-API.md`](../../oficina/CONTRATO-API.md), [`app-movil-backend.md`](../../agentes-linkedin/infra/docs/app-movil-backend.md).

## Resumen

| ID | Función | Dónde | Estado |
| --- | --- | --- | --- |
| [PUS-01](#pus-01) | Activar las notificaciones en la PWA | PWA · backend | con fallo conocido |
| [PUS-02](#pus-02) | Probar una notificación | PWA · app · backend | funciona |
| [PUS-03](#pus-03) | Desactivar las notificaciones en este dispositivo | PWA · app · backend | parcial |
| [PUS-04](#pus-04) | Encender o apagar la push de cada tipo | PWA · app · backend | funciona |
| [PUS-05](#pus-05) | Qué tipos envían push | backend | funciona |
| [PUS-06](#pus-06) | Mostrar y abrir una Web Push | PWA | funciona |
| [PUS-07](#pus-07) | Registrar el teléfono para recibir avisos | app · backend | parcial |
| [PUS-08](#pus-08) | Tocar un aviso en el teléfono | app | funciona |
| [PUS-09](#pus-09) | Envío desde el servidor | backend | funciona |
| [PUS-10](#pus-10) | Avisos con la app abierta | app | funciona |
| [PUS-11](#pus-11) | Copia de las alertas a un webhook | backend | funciona |

---

### PUS-01 · Activar las notificaciones en la PWA <a id="pus-01"></a>

- **Dónde:** PWA · backend
- **Estado:** con fallo conocido
- **Qué hace para Gustavo:** en Ajustes › Notificaciones activa los avisos en este navegador o en la PWA instalada en su teléfono.
- **Código:** `GET /api/v1/push/key`, `POST /api/v1/push/subscriptions`; `push.ts` (`enablePush`, `currentSubscription`).
- **El fallo:** si el navegador se suscribe pero `POST /api/v1/push/subscriptions` falla, la pantalla dice «Activadas» y ofrece «Probar» y «Desactivar», porque el estado se lee solo del navegador (`pushManager.getSubscription()`); solo el texto del error indica que el servidor no guardó nada.
- **Criterios de aceptación:**
  1. **Dado** un navegador compatible, **cuando** abre la sección, **entonces** ve el estado («Activadas», «Bloqueadas», «Desactivadas», «Comprobando…», «No disponibles» o «Instala la app») y «Te avisan aquí de lo que pide tu acción (Tu turno) y de lo importante que pasa (Notificaciones).».
  2. **Dado** «Activar notificaciones», **cuando** lo pulsa, **entonces** el permiso del sistema se pide antes de cualquier petición de red; al aceptarlo se obtiene la clave VAPID, el service worker se suscribe, se envía la suscripción y aparece «Notificaciones activadas en este dispositivo.».
  3. **Dado** que rechaza el permiso, **cuando** vuelve, **entonces** ve «Las notificaciones están bloqueadas. Actívalas…» (o «No se concedió el permiso de notificaciones.» si cerró el aviso).
  4. **Dado** un iPhone con la PWA sin instalar, **cuando** pulsa «Activar notificaciones», **entonces** ve «En iPhone, primero añade 0ff1ce a la pantalla de inicio y ábrela desde allí.» y los pasos resaltados.
  5. **Dado** el servidor sin VAPID, **cuando** se pide la clave, **entonces** la API responde 503 «Notificaciones no configuradas en el servidor (VAPID).».
  6. **Dado** que el servidor no guardó la suscripción, **cuando** termina, **entonces** el estado no dice «Activadas» y se puede reintentar. **Hoy falla.**
  7. **Dado** un endpoint que no es HTTPS o sin claves `p256dh`/`auth`, **cuando** llega a la API, **entonces** responde 400.
  8. **Dado** la misma suscripción enviada otra vez, **cuando** llega, **entonces** responde 200 y la actualiza; la primera vez, 201.
- **Brechas código/docs:** —
- **Cobertura QA:** pendiente

### PUS-02 · Probar una notificación <a id="pus-02"></a>

- **Dónde:** PWA · app · backend
- **Estado:** funciona
- **Qué hace para Gustavo:** comprueba que los avisos le llegan.
- **Código:** `POST /api/v1/push/test` (`oficina_views.PushTest`).
- **Criterios de aceptación:**
  1. **Dado** las notificaciones activadas, **cuando** pulsa «Probar notificación», **entonces** la API responde 202 `{sent}` y llega «Barrio AI» con «Notificación de prueba: las alertas llegarán aquí.» a sus suscripciones de la PWA y a sus teléfonos, con prioridad alta y destino `/ajustes`.
  2. **Dado** la respuesta, **cuando** vuelve, **entonces** ve «Notificación de prueba enviada. Debería llegar en unos segundos.».
  3. **Dado** el servidor sin VAPID y sin teléfonos registrados, **cuando** lo pide, **entonces** recibe 403 «Notificaciones no configuradas en el servidor (VAPID).».
  4. **Dado** un token de servicio, **cuando** lo pide, **entonces** recibe 403.
- **Brechas código/docs:** las dos interfaces ignoran `sent`: con `sent: 0` también dicen que se envió.
- **Cobertura QA:** E2E `06-notificaciones-avisos` (criterio 3: sin VAPID ni teléfonos, «No se pudo completar» con el motivo). El 1 necesita FCM.

### PUS-03 · Desactivar las notificaciones en este dispositivo <a id="pus-03"></a>

- **Dónde:** PWA · app · backend
- **Estado:** parcial
- **Qué hace para Gustavo:** deja de recibir avisos en un dispositivo sin tocar los demás.
- **Código:** PWA `push.ts` (`disablePush`: `POST /api/v1/push/unsubscribe {endpoint}` y `subscription.unsubscribe()`); app solo `DELETE /api/v1/push/expo` al cerrar sesión ([ACC-08](acceso.md#acc-08)).
- **Criterios de aceptación:**
  1. **Dado** la PWA con avisos activos, **cuando** pulsa «Desactivar» y confirma «¿Desactivar las notificaciones aquí?» («Este dispositivo deja de recibir avisos. Los demás siguen igual y puedes volver a activarlas cuando quieras.»), **entonces** se borra la suscripción en el servidor (204) y en el navegador, y aparece «Notificaciones desactivadas en este dispositivo.».
  2. **Dado** que el borrado en el servidor falla, **cuando** termina, **entonces** el navegador se da de baja igual y el error se ve en la confirmación.
  3. **Dado** la app, **cuando** quiere dejar de recibir avisos en el teléfono sin cerrar sesión, **entonces** tiene un «Desactivar» en Ajustes › Notificaciones. **Hoy falla:** solo puede cerrar sesión o quitar el permiso en el sistema.
  4. **Dado** `DELETE /api/v1/push/expo {token}`, **cuando** el token es suyo, **entonces** responde 204 y lo quita.
- **Brechas código/docs:** —
- **Cobertura QA:** pendiente

### PUS-04 · Encender o apagar la push de cada tipo <a id="pus-04"></a>

- **Dónde:** PWA · app · backend
- **Estado:** funciona
- **Qué hace para Gustavo:** elige qué tipos de aviso le llegan como push; el aviso sigue apareciendo en Tu turno o en Notificaciones.
- **Código:** `push_types` de `GET /api/v1/ajustes`, `PATCH /api/v1/ajustes/preferencias {push_disabled, push_enabled}` (`OfficePreference.push_disabled` y `push_enabled`), `notificaciones.push_enabled`; `pushPreferencesPatch` en `compartido/src/logic/ajustes.ts`.
- **Criterios de aceptación:**
  1. **Dado** el pliegue «Por tipo de notificación», **cuando** lo abre, **entonces** ve un interruptor por tipo con «Va a Tu turno» o «Va a Notificaciones» e «Apagar la push de un tipo no lo borra: el aviso sigue llegando a Tu turno o a Notificaciones.».
  2. **Dado** los valores por defecto, **cuando** lo abre, **entonces** están encendidos todos los de Tu turno (acción incierta, LinkedIn caducado, máquina detenida desde la app, LinkedIn caduca pronto, cuenta en pausa, conversación, pregunta, tarea de perfil) y, de Notificaciones, pieza lista o programada, pieza publicada, pieza bloqueada, máquina detenida desde el servidor, el líder no aprueba nada y resumen de la semana.
  3. **Dado** que apaga «Pieza publicada», **cuando** se guarda, **entonces** se envían `push_disabled` con todos los tipos apagados y `push_enabled` con los encendidos, aparece «Push apagada: Pieza publicada.» y la próxima pieza publicada aparece en Notificaciones sin push, en la PWA y en el teléfono.
  6. **Dado** un tipo apagado por defecto («Conexión nueva que encaja»), **cuando** lo enciende, **entonces** aparece «Push activada: Conexión nueva que encaja.», sigue encendido al volver a abrir la app y la próxima conexión que encaja llega como push. Un cliente que solo envía `push_disabled` no lo apaga salvo que lo incluya.
  4. **Dado** un tipo desconocido o un cuerpo vacío, **cuando** llega a la API, **entonces** responde 400.
  5. **Dado** que guardar falla, **cuando** vuelve el error, **entonces** el interruptor vuelve a su valor y aparece un aviso de error.
- **Brechas código/docs:** en la PWA el pliegue no tiene estado de carga: sale vacío mientras carga `/ajustes`.
- **Cobertura QA:** E2E `06-notificaciones-avisos` (criterio 6: encender un tipo apagado por defecto y que siga encendido al reabrir) y `11-ajustes` (3, apagar uno). Backend `PushSwitchTests`.

### PUS-05 · Qué tipos envían push <a id="pus-05"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Qué hace para Gustavo:** cada tipo que tiene push encendida le llega cuando pasa.
- **Código:** llamadas a `notificaciones.avisar` en `operador.py` (`set_global_pause`, `check_env_pause`, `set_account_pause`), `autopiloto.py`, `editorial.py`, `red.py`, `connectors_linkedin.py` (`check_tokens`), `resumen_semanal.py`, `oportunidades.py`, `capturas.py`, `conversaciones.py`, `preguntas.py`.
- **Criterios de aceptación:**
  1. **Dado** cada tipo con push encendida, **cuando** ocurre el evento, **entonces** llega su push: acción incierta («¿Salió o no?»), LinkedIn caduca pronto, cuenta en pausa, conversación que le toca, pregunta nueva («<Rol> te pregunta»), pieza lista, publicada o bloqueada, el líder no aprueba nada y resumen de la semana.
  2. **Dado** un aviso de Tu turno, **cuando** llega la push, **entonces** abre `/tu-turno`; uno de Notificaciones abre su enlace (o `/notificaciones`).
  3. **Dado** los tipos urgentes (acción incierta, LinkedIn caducado, máquina detenida), **cuando** se envían, **entonces** van con prioridad alta en el teléfono.
  4. **Dado** que el token de LinkedIn caduca, **cuando** el autopiloto lo ve, **entonces** pausa la cuenta y llega la push urgente «LinkedIn caducado» (una vez), no «LinkedIn: cuenta en pausa».
  5. **Dado** que la máquina se detiene desde el servidor (`OPERATOR_PAUSED`), **cuando** el autopiloto lo ve, **entonces** llega una vez la push urgente «Máquina detenida desde el servidor» con destino `/notificaciones`; no se guarda en el feed («Próximo» la muestra mientras dura) y una parada nueva, tras levantarla, vuelve a avisar.
  6. **Dado** que Gustavo detiene la máquina desde la app, **cuando** pasa, **entonces** llega la push urgente «Máquina detenida» con el motivo. «Tarea de perfil nueva» no tiene evento hasta que exista el ciclo de Perfil ([TUR-18](tu-turno.md#tur-18)): Ajustes no ofrece su interruptor y la API lo sigue aceptando.
- **Brechas código/docs:** —
- **Cobertura QA:** Backend (`PushEmitterTests`, `LinkedInExpiredTests`, `test_publicacion`).

### PUS-06 · Mostrar y abrir una Web Push <a id="pus-06"></a>

- **Dónde:** PWA
- **Estado:** funciona
- **Qué hace para Gustavo:** el aviso aparece aunque la PWA esté cerrada, y al tocarlo se abre la vista correcta.
- **Código:** `oficina/src/sw.ts` (`push`, `notificationclick`), `oficina/src/push/payload.ts` (`safeTargetUrl`).
- **Criterios de aceptación:**
  1. **Dado** una push `{title, body, url, tag}`, **cuando** llega, **entonces** se muestra con el título (o «0ff1ce»), el cuerpo, el icono y la insignia de 0ff1ce.
  2. **Dado** que toca el aviso y ya hay una ventana en esa URL, **cuando** lo toca, **entonces** se enfoca esa ventana; si hay otra ventana de la PWA, navega a la URL; si no, abre una nueva.
  3. **Dado** una URL de otro origen, **cuando** toca el aviso, **entonces** abre `/`.
  4. **Dado** las URL que envía el backend (`/tu-turno`, `/calendario/pieza/<id>`, `/resultados#resumen`, `/?enviado=1`, `/ajustes`, `/calendario?vista=lista&…`), **cuando** se abren, **entonces** cada una lleva a su vista.
  5. **Dado** un contenido que no es JSON, **cuando** llega, **entonces** se muestra igualmente con lo que haya.
- **Brechas código/docs:** —
- **Cobertura QA:** pendiente

### PUS-07 · Registrar el teléfono para recibir avisos <a id="pus-07"></a>

- **Dónde:** app · backend
- **Estado:** parcial
- **Qué hace para Gustavo:** al entrar en la app, el teléfono queda registrado para recibir los avisos, y en Ajustes ve si funciona.
- **Código:** `movil/src/push/register.ts` (`registerForPush`: canal Android `default`, permiso, `getExpoPushTokenAsync({projectId})`, `POST /api/v1/push/expo`), `movil/src/auth/session.tsx` (una vez por arranque con sesión), `movil/src/ajustes/Notificaciones.tsx`; `app.json`.
- **Lo que falta:** `app.json` no tiene `android.googleServicesFile` ni hay `google-services.json` en el repositorio. En una build de Android, Expo necesita Firebase para dar el token de push, así que lo esperable es que `getExpoPushTokenAsync` falle y Ajustes muestre «No se pudieron activar los avisos». No se pudo comprobar en un teléfono. Además, el permiso se pide nada más entrar, sin explicar antes para qué.
- **Criterios de aceptación:**
  1. **Dado** la build instalada en un Android real y la sesión abierta, **cuando** arranca la app, **entonces** se crea el canal `default` («Avisos de 0ff1ce», importancia alta), se obtiene el token de Expo y se registra con `POST /api/v1/push/expo` (201), y Ajustes › Notificaciones dice «Activadas» con «Avisos activos en este teléfono». **Hoy, probablemente falla** por la falta de Firebase.
  2. **Dado** el primer arranque, **cuando** la app va a pedir el permiso de notificaciones, **entonces** explica antes para qué los usa, como hace con el micrófono. **Hoy falla:** aparece directamente el aviso del sistema.
  3. **Dado** que rechaza el permiso, **cuando** abre Ajustes, **entonces** ve «Avisos bloqueados» con «Permite las notificaciones de 0ff1ce en los ajustes del teléfono para recibirlos.» y «Abrir los ajustes del teléfono».
  4. **Dado** que vuelve tras permitirlas en el sistema, **cuando** abre Ajustes, **entonces** el estado se actualiza sin reiniciar la app. **Hoy falla:** sigue «Bloqueadas» hasta el siguiente arranque.
  5. **Dado** Expo Go en Android, un simulador o una build sin proyecto de EAS, **cuando** abre Ajustes, **entonces** ve «Avisos push aún no disponibles» con el motivo («Expo Go no recibe avisos push en Android: llegan con la build de desarrollo.», «Los avisos push solo llegan a un teléfono real.» o «Falta el proyecto de Expo (EAS) que firma los avisos…»).
  6. **Dado** un error al registrar, **cuando** abre Ajustes, **entonces** ve «No se pudieron activar los avisos» con el detalle en español y «Activar notificaciones» para reintentar.
  7. **Dado** el servidor, **cuando** abre Ajustes, **entonces** ve «Teléfonos que reciben avisos», «Último aviso entregado» y «Último error de Expo» (`ajustes.expo_push`).
  8. **Dado** el mismo token registrado otra vez, **cuando** llega, **entonces** se actualiza y reactiva con el mismo `id`; un token sin formato `ExponentPushToken[…]` recibe 400 «Token de Expo inválido: se espera ExponentPushToken[…].».
- **Brechas código/docs:** `movil/README.md` dice que las push «necesitan además las credenciales de FCM (Firebase), que se cargan en EAS con `npx eas-cli@latest credentials`» y que hace falta una build de desarrollo; `eas.json` no tiene perfil `development` ([APP-07](app-movil-instalacion.md#app-07)).
- **Cobertura QA:** E2E `06-notificaciones-avisos` (criterios 5 y 7: «Avisos push aún no disponibles · Los avisos push solo llegan a un teléfono real.» y «Teléfonos que reciben avisos»). El 1 a 4 necesitan un teléfono real con FCM.

### PUS-08 · Tocar un aviso en el teléfono <a id="pus-08"></a>

- **Dónde:** app
- **Estado:** funciona
- **Qué hace para Gustavo:** toca un aviso y la app se abre en la vista de ese aviso.
- **Código:** `movil/src/app/(app)/_layout.tsx` (`getLastNotificationResponse` y el listener), `push/routes.ts` (`isInAppPath`, `routeForUrl`), `navigation.ts` (`openLink`).
- **Criterios de aceptación:**
  1. **Dado** la app cerrada, **cuando** toca un aviso con `data.url = /calendario/pieza/<id>`, **entonces** la app arranca y abre esa pieza.
  2. **Dado** la app en segundo plano, **cuando** toca un aviso con `/tu-turno`, **entonces** abre Tu turno.
  3. **Dado** `/resultados#resumen`, `/?enviado=1`, `/tu-turno/sabe`, `/editorial/<id>` o `/acciones?state=uncertain`, **cuando** toca el aviso, **entonces** abre el bloque del resumen, «Lo que enviaste», «Lo que el equipo sabe de ti», la pieza o Tu turno.
  4. **Dado** una URL absoluta o que empieza por `/api/`, **cuando** toca el aviso, **entonces** no navega.
  5. **Dado** una ruta que la app no tiene, **cuando** toca el aviso, **entonces** ve «Esta vista no existe» con «Ir a la Oficina».
- **Brechas código/docs:** no se comprobó qué pasa si toca un aviso con la sesión cerrada.
- **Cobertura QA:** Sin E2E: necesita una push real (FCM y el servicio de Expo). Los enlaces `oficina0ff1ce://` los recorre `02-navegacion`.

### PUS-09 · Envío desde el servidor <a id="pus-09"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Qué hace para Gustavo:** cada aviso sale a la vez a la PWA y a sus teléfonos; un fallo del envío nunca rompe el trabajo del equipo.
- **Código:** `alerts.notify` (`push.broadcast` y `expo.broadcast`, cada uno en su `try`), `expo._send`, `expo.check_receipts`.
- **Criterios de aceptación:**
  1. **Dado** un aviso, **cuando** se envía, **entonces** la Web Push lleva `{title, body, url, tag}` (título hasta 120 y cuerpo hasta 200 caracteres) y el mensaje de Expo lleva el mismo título y cuerpo, `data: {url, tag}`, `channelId: default`, `ttl: 86400` y `priority` alta solo en los urgentes.
  2. **Dado** más de 100 tokens de Expo, **cuando** se envía, **entonces** va en lotes de 100.
  3. **Dado** un ticket `DeviceNotRegistered` (en el envío o en el recibo), **cuando** llega, **entonces** ese token queda inactivo; otro error se guarda en `last_error` y el token sigue activo.
  4. **Dado** una suscripción Web Push que responde 404 o 410, **cuando** se envía, **entonces** se borra; otros fallos suman `failures` y a los 5 deja de enviarse.
  5. **Dado** que Expo no responde, **cuando** se envía, **entonces** se registra en el log sin datos personales, no se desactiva ningún token y el trabajo que avisaba sigue.
  6. **Dado** un dispositivo revocado, **cuando** se envía, **entonces** su token de push no recibe nada.
  7. **Dado** `EXPO_ACCESS_TOKEN` definido, **cuando** se envía a Expo, **entonces** va como `Authorization: Bearer` y nunca aparece en el log.
- **Brechas código/docs:** —
- **Cobertura QA:** pendiente

### PUS-10 · Avisos con la app abierta <a id="pus-10"></a>

- **Dónde:** app
- **Estado:** funciona
- **Qué hace para Gustavo:** si llega un aviso mientras usa la app, lo ve arriba y la campana se mueve.
- **Código:** `movil/src/push/register.ts` (manejador en primer plano), `movil/src/notificaciones/arrival.ts`, `TopBar.tsx`.
- **Criterios de aceptación:**
  1. **Dado** la app abierta, **cuando** llega un aviso, **entonces** se muestra como banner, sin sonido ni número en el icono.
  2. **Dado** ese aviso, **cuando** llega, **entonces** Notificaciones y Tu turno se actualizan, la campana se balancea y el teléfono vibra una vez.
- **Brechas código/docs:** —
- **Cobertura QA:** Sin E2E: necesita una push real con la app abierta.

### PUS-11 · Copia de las alertas a un webhook <a id="pus-11"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Qué hace para Gustavo:** puede recibir las mismas alertas en ntfy o en un canal compatible con Slack.
- **Código:** `alerts.notify` (`OPERATOR_ALERT_WEBHOOK`).
- **Criterios de aceptación:**
  1. **Dado** `OPERATOR_ALERT_WEBHOOK` con una URL de ntfy, **cuando** se envía una alerta, **entonces** se publica el cuerpo con las cabeceras `Title` y `Priority: high`.
  2. **Dado** otra URL, **cuando** se envía, **entonces** se manda `{"text": "<título>\n<mensaje>"}`.
  3. **Dado** que el webhook falla, **cuando** se envía, **entonces** se registra en el log y el resto sigue.
- **Brechas código/docs:** —
- **Cobertura QA:** pendiente

## Retiradas

Ninguna.
