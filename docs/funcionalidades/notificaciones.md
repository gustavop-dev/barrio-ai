# Notificaciones (`NOT`)

La bandeja de lo que viene o ya pasó y no le pide nada a Gustavo: la próxima pieza, piezas publicadas o bloqueadas, conexiones nuevas, oportunidades. Lo que solo él puede resolver va a Tu turno. Las push están en [notificaciones-push.md](notificaciones-push.md).

- **Código:** backend `notificaciones.py` (`avisar`, `upcoming`, `purge`, `unread`, `FEED_KINDS`), `rediseno_views.Notifications`, `NotificationsRead`, modelo `Notification`; PWA `oficina/src/pages/Notificaciones.tsx`; app `movil/src/notificaciones/NotificacionesScreen.tsx`; lógica común `compartido/src/logic/notificaciones.ts`, `compartido/src/api/notificaciones.ts`.
- **Documentación:** sección «Notificaciones y prioridades de Tu turno (rev 18)» de [`CONTRATO-API.md`](../../oficina/CONTRATO-API.md).

## Resumen

| ID | Función | Dónde | Estado |
| --- | --- | --- | --- |
| [NOT-01](#not-01) | Ver las notificaciones de los últimos 7 días | PWA · app · backend | funciona |
| [NOT-02](#not-02) | Filtrar «Sin leer» y marcar como leído | PWA · app · backend | funciona |
| [NOT-03](#not-03) | «Próximo»: lo que va a pasar | PWA · app · backend | funciona |
| [NOT-04](#not-04) | Abrir el destino de una notificación | PWA · app · backend | funciona |
| [NOT-05](#not-05) | Punto de novedades en la campana | PWA · app · backend | funciona |
| [NOT-06](#not-06) | Qué eventos llegan a Notificaciones | backend | funciona |

---

### NOT-01 · Ver las notificaciones de los últimos 7 días <a id="not-01"></a>

- **Dónde:** PWA · app · backend
- **Estado:** funciona
- **Qué hace para Gustavo:** abre Notificaciones y ve lo que pasó, agrupado por día, con lo no leído marcado.
- **Código:** `GET /api/v1/notificaciones?filtro=todas` (`rediseno_views.Notifications`, `notificaciones.purge`).
- **Criterios de aceptación:**
  1. **Dado** notificaciones de hoy, de ayer y de hace 3 días, **cuando** abre la vista, **entonces** las ve en los grupos «Hoy», «Ayer» y «<día d de mes>», cada una con el punto de color de su capa, la hora, el título, el detalle y «Nueva» si no está leída.
  2. **Dado** una notificación de hace 8 días, **cuando** se consulta, **entonces** ya no aparece: se borra a los 7 días.
  3. **Dado** más de 200 notificaciones en 7 días, **cuando** se consulta, **entonces** llegan las 200 más recientes.
  4. **Dado** ninguna notificación, **cuando** abre la vista, **entonces** ve «No hay nada nuevo. Lo de días anteriores sigue en el Calendario.».
  5. **Dado** la carga en curso, **cuando** abre la vista, **entonces** ve «Cargando notificaciones…».
  6. **Dado** un error, **cuando** falla, **entonces** ve el error con «Reintentar» (o «No se pudo actualizar» si ya había datos).
  7. **Dado** el pie de la vista, **cuando** se pinta, **entonces** dice «Se guardan 7 días. Lo anterior está en el Calendario.».
- **Brechas código/docs:** —
- **Cobertura QA:** E2E `06-notificaciones` (criterios 1 y 7) y `06-notificaciones-estados` (4 vacío y 6 «No se pudo actualizar» con el interruptor de fallos). El 2 y el 3, backend.

### NOT-02 · Filtrar «Sin leer» y marcar como leído <a id="not-02"></a>

- **Dónde:** PWA · app · backend
- **Estado:** funciona
- **Qué hace para Gustavo:** ve solo lo nuevo y lo marca como leído, una por una o todo de golpe.
- **Código:** `GET /api/v1/notificaciones?filtro=sin_leer`, `POST /api/v1/notificaciones/leer`; `useMarkNotificacionesRead` (actualización optimista).
- **Criterios de aceptación:**
  1. **Dado** el chip «Sin leer», **cuando** lo elige, **entonces** solo aparecen las no leídas.
  2. **Dado** «Marcar todo como leído», **cuando** lo pulsa, **entonces** se envía `{todas: true}`, todas pierden «Nueva» al momento y la respuesta trae `unread: 0`.
  3. **Dado** una notificación no leída con enlace, **cuando** la abre, **entonces** se marca como leída (`{ids: [id]}`).
  4. **Dado** que marcar como leído falla, **cuando** vuelve el error, **entonces** las etiquetas «Nueva» vuelven y se ve «No se pudo marcar como leído».
  5. **Dado** un cuerpo sin `ids` ni `todas: true`, **cuando** se envía, **entonces** la API responde 400 «Envía ids o todas: true».
- **Brechas código/docs:** —
- **Cobertura QA:** E2E `06-notificaciones` (criterios 1 a 3), `06-notificaciones-destinos` (3) y `06-notificaciones-estados` (4: «No se pudo marcar como leído» y vuelven las «Nueva»). El 5, backend.

### NOT-03 · «Próximo»: lo que va a pasar <a id="not-03"></a>

- **Dónde:** PWA · app · backend
- **Estado:** funciona
- **Qué hace para Gustavo:** arriba de la bandeja ve la próxima pieza que saldrá (con hasta cuándo puede vetarla), las invitaciones previstas y si la máquina está parada desde el servidor.
- **Código:** `notificaciones.upcoming` (se calcula en cada consulta; nunca cuenta como no leído).
- **Criterios de aceptación:**
  1. **Dado** una pieza `ready` con su acción `proposed` o `approved` que sale en las próximas 48 h, **cuando** abre Notificaciones, **entonces** «Próximo» muestra «Sale la pieza «<tesis>»» con «Puedes vetarla en el detalle hasta las HH:MM.» y enlace a `/calendario/pieza/<id>`.
  2. **Dado** contactos seguidos cuya espera de 48 h termina en las próximas 24 h y las invitaciones sin bloqueo, **cuando** abre Notificaciones, **entonces** ve «El equipo invitará a N personas que encajan» con «Si los topes del día lo permiten.», sin enlace: Personas solo lista las conexiones ([PRS-01](personas-oportunidades.md#prs-01)).
  3. **Dado** `OPERATOR_PAUSED=true`, **cuando** abre Notificaciones, **entonces** ve «La máquina está detenida desde el servidor» con «La parada viene de OPERATOR_PAUSED y no se levanta desde la app.» y enlace a `/ajustes#maquina`.
  4. **Dado** los elementos de «Próximo», **cuando** se calcula `unread`, **entonces** no cuentan.
- **Brechas código/docs:** —
- **Cobertura QA:** E2E `06-notificaciones` (criterios 1 y 2). El 3 (parada del servidor), backend.

### NOT-04 · Abrir el destino de una notificación <a id="not-04"></a>

- **Dónde:** PWA · app · backend
- **Estado:** funciona
- **Qué hace para Gustavo:** toca una notificación y llega a lo que trata: la pieza, la persona, Resultados o «Lo que enviaste».
- **Código:** campo `link` de cada notificación.
- **Criterios de aceptación:**
  1. **Dado** una notificación de pieza (`piece_scheduled`, `piece_published`, `piece_blocked`, `piece_discarded`), **cuando** la toca, **entonces** abre `/calendario/pieza/<id>`.
  2. **Dado** `connection_fit` u `opportunity` con contacto, **cuando** la toca, **entonces** abre `/personas/<id>`.
  3. **Dado** `weekly_summary`, **cuando** la toca, **entonces** abre Resultados en `#resumen`.
  4. **Dado** `capture_processed` (enlace `/?enviado=1`), **cuando** la toca, **entonces** se abre la hoja de captura en «Lo que enviaste».
  5. **Dado** `lead_silent`, **cuando** la toca, **entonces** abre la Lista del calendario filtrada con lo que no salió.
  6. **Dado** una notificación sin enlace ya leída, **cuando** la toca, **entonces** no pasa nada.
- **Brechas código/docs:** la oportunidad sin contacto enlaza a `/personas?pestana=oportunidades` desde la notificación y a `/personas?tab=oportunidades` desde el calendario; la PWA solo entiende `pestana` (ver [PRS-07](personas-oportunidades.md#prs-07)).
- **Cobertura QA:** E2E `06-notificaciones` (criterios 1 y 2) y `06-notificaciones-destinos` (3 resumen semanal, 4 «Lo que enviaste» y la oportunidad sin contacto).

### NOT-05 · Punto de novedades en la campana <a id="not-05"></a>

- **Dónde:** PWA · app · backend
- **Estado:** funciona
- **Qué hace para Gustavo:** la campana muestra un punto (sin número) cuando hay algo nuevo.
- **Código:** `notifications_unread` de `GET /api/v1/tu-turno`; PWA `Layout.tsx`; app `TopBar.tsx`.
- **Criterios de aceptación:**
  1. **Dado** al menos una notificación sin leer, **cuando** carga cualquier vista, **entonces** la campana muestra un punto y su etiqueta accesible dice «Notificaciones, hay novedades».
  2. **Dado** 0 sin leer, **cuando** carga, **entonces** no hay punto.
  3. **Dado** que marca todo como leído, **cuando** termina, **entonces** el punto desaparece sin esperar a la siguiente consulta.
- **Brechas código/docs:** —
- **Cobertura QA:** E2E `06-notificaciones` (criterios 1 a 3).

### NOT-06 · Qué eventos llegan a Notificaciones <a id="not-06"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Qué hace para Gustavo:** cada cosa que pasa y no le pide nada aparece una sola vez en su bandeja.
- **Código:** llamadas a `notificaciones.avisar` con un tipo de `FEED_KINDS`; `ref` único para no duplicar.
- **Criterios de aceptación:**
  1. **Dado** cada uno de estos eventos, **cuando** ocurre, **entonces** se guarda su Notificación: pieza lista (`piece_scheduled`), publicada, bloqueada, descartada, conexión que encaja, oportunidad nueva o que cambia de etapa, posts nuevos del Observatorio (`observatory`), captura procesada, líder sin aprobar en 7 días (`lead_silent`), la prueba diaria de LinkedIn rota, sin correr en todo el día o de nuevo bien (`linkedin_canary`) y resumen de la semana.
  2. **Dado** el mismo evento dos veces (mismo `ref`), **cuando** se avisa, **entonces** solo hay una Notificación.
  3. **Dado** `invites_expected` y `machine_paused_env`, **cuando** ocurren, **entonces** aparecen solo en «Próximo» (se calculan, no se guardan).
  4. **Dado** que la máquina se detiene desde el servidor, **cuando** el autopiloto lo ve, **entonces** llega una push una vez por parada ([PUS-05](notificaciones-push.md#pus-05)), sin guardarla en el feed.
  5. **Dado** que la prueba diaria de una cuenta `directo` encuentra una lectura rota, **cuando** termina, **entonces** llega «La prueba diaria de LinkedIn encontró lecturas rotas» con las lecturas que fallan; si al día siguiente sigue rota no llega otra, y cuando vuelve a pasar llega «La prueba diaria de LinkedIn vuelve a pasar».
  6. **Dado** que la prueba diaria no pudo correr (servicio caído, ocupado o sin cupo), **cuando** falla el tercer intento del día, **entonces** llega «La prueba diaria de LinkedIn no pudo correr hoy»; los dos primeros intentos no avisan.
  7. **Dado** que en la prueba diaria el servicio paró la cuenta o no tiene sesión, **cuando** termina, **entonces** no llega `linkedin_canary`: la cuenta queda en pausa y llega la de «cuenta en pausa» (Tu turno) una sola vez, con qué hacer en el motivo.
- **Brechas código/docs:** la app todavía no muestra la última prueba diaria; el backend la sirve en `canary` de cada cuenta.
- **Cobertura QA:** Backend (`test_notificaciones`): eventos, `ref` único, tipos calculados y la push de la parada del servidor. `test_canario`: los criterios 5 a 7.

## Retiradas

Ninguna.
