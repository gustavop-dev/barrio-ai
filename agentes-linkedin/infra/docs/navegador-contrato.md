# Contrato del servicio «navegador»

El conector `directo` (`team_backend/connectors_directo.py`) habla con LinkedIn sin Unipile. No llama a LinkedIn
él mismo: le pide cada llamada al servicio «navegador», que la hace desde dentro de la página de LinkedIn de la
cuenta, con su sesión abierta. El plan completo está en `docs/plan-linkedin-directo.md`.

Este documento fija lo que el backend envía y lo que espera de vuelta. El backend lo implementa en
`linkedin_directo/servicio.py` y el servicio en `agentes-linkedin/navegador` (su README explica cómo correrlo).

## Reparto del trabajo

| Parte | Qué hace |
| --- | --- |
| Backend, paquete `linkedin_directo` | Sabe todo de LinkedIn: rutas, ids de consultas, cuerpos de cada escritura y cómo leer las respuestas. Revisa cada llamada contra la lista permitida antes de pedirla. Juzga la respuesta. |
| Servicio navegador | Tiene un Chromium por cuenta con su perfil. Hace una llamada `fetch` desde la página y devuelve lo que contestó LinkedIn, sin interpretarlo. Aplica sus propias protecciones: la misma lista permitida, pausas entre llamadas, topes y parada dura. |

Una llamada del backend es una sola llamada a `www.linkedin.com`. El servicio nunca reintenta y nunca sigue una
redirección.

## Activación

| Variable | Para qué |
| --- | --- |
| `LIVE_LINKEDIN_DIRECTO` | `true` enciende el conector. Por defecto `false`: el conector falla sin llamar a nadie. |
| `NAVEGADOR_URL` | Dirección interna del servicio, `http://…` o `https://…`. |
| `NAVEGADOR_TOKEN` | Token compartido con el servicio. Va en `Authorization: Bearer …`. Nunca se registra en logs. |

Si falta la URL o el token, el conector falla con `kind='config'` y no envía nada. La cuenta en Barrio es una
`ConnectorAccount` con `provider='directo'`; su `external_account_id` es el nombre de la cuenta en el servicio (por
ejemplo `cuenta-prueba`: minúsculas, números, `-` y `_`). Nunca es una credencial de LinkedIn.

## Llamada

`POST {NAVEGADOR_URL}/v1/cuentas/{cuenta}/llamadas`

```json
{
  "method": "GET",
  "path": "/voyager/api/me",
  "kind": "voyager",
  "body": null,
  "write": false,
  "operation": "account_status",
  "request_id": "uuid4"
}
```

| Campo | Significado |
| --- | --- |
| `method` | `GET` o `POST`. |
| `path` | Ruta en `www.linkedin.com`, con la consulta ya codificada. |
| `kind` | `voyager` (API JSON), `sdui` (acciones de la interfaz del servidor; responde un flujo de componentes) o `page` (un documento HTML). |
| `body` | JSON del cuerpo, o `null`. |
| `write` | `true` si la llamada cambia algo en LinkedIn. |
| `operation` | El método del conector que la pide. Sirve para los topes y la auditoría del servicio. |
| `request_id` | Único por llamada. Si llega dos veces el mismo en una escritura, el servicio no la repite: devuelve la respuesta guardada o 409. |

Encabezados que pone el servicio según `kind`:

| `kind` | Encabezados |
| --- | --- |
| `voyager` | `accept: application/vnd.linkedin.normalized+json+2.1`, `x-restli-protocol-version: 2.0.0`; en un POST además `content-type: application/json; charset=UTF-8`. También `x-li-lang`, `x-li-track` y `x-li-page-instance` tal como los mandó la propia página en sus llamadas a Voyager al cargar |
| `sdui` | `content-type: application/json`, y el `accept` y los `x-li-*` de la última acción propia de la página |
| `page` | `accept: text/html` |

En todos añade el `csrf-token`, que lee dentro de la página. La cookie y el token de LinkedIn no salen nunca del
navegador.

### Respuesta 200

Lo que contestó LinkedIn, tal cual:

```json
{"status": 200, "text": "…", "content_type": "application/json", "url": "https://www.linkedin.com/…", "redirected": false}
```

`status` es el código HTTP de LinkedIn. Vale `0` si LinkedIn no contestó: tiempo agotado o error de red dentro de
la página. Una redirección no se sigue: llega con `status` 0 y `redirected: true`. El backend decide qué significa:

- Redirección, 401, 403, 429, 999, una página de login o de verificación, o HTML donde se esperaban datos: la
  cuenta se pausa (`pause=True`).
- Una escritura sin respuesta, con 5xx o con respuesta ilegible queda incierta (`ConnectorUncertain`) y se concilia
  leyendo.
- Otro 4xx es un error normal, con el código de LinkedIn en `kind` (`linkedin/<código>`).

### Respuestas del servicio

Si el servicio no hace la llamada, contesta con su propio código y un JSON `{"reason": "texto corto"}`. Ese texto
no debe llevar datos de LinkedIn.

Cuando lo que se agotó es un tope de la cuenta, el 422 lo dice y dice cuándo vuelve a haber cupo (en segundos, también
en el encabezado `Retry-After`):

```json
{"reason": "tope de invitaciones por día agotado; no salió nada", "code": "budget", "retry_after": 3600}
```

Cuando no abre la cuenta porque su salida a internet no es la de su última sesión (o el perfil se importó de otro
equipo), el 503 lo dice con su propio código y desde cuándo lo rechaza. Ese momento es el mismo en todos los rechazos
de un episodio y empieza de nuevo cuando la cuenta vuelve a abrirse por su salida o alguien acepta la nueva:

```json
{"reason": "la salida a internet cambió; no salió nada. Para abrirla por esta salida: …", "code": "egress", "since": "2026-11-13T12:00:00+00:00"}
```

| Código | Significado | Lo que hace el backend |
| --- | --- | --- |
| 400 | Petición mal formada | Error `contract` |
| 401, 403 | Falta el token (401) o no es el del servicio (403) | Error `config`; la cuenta se pausa |
| 404 | Cuenta desconocida en el servicio | Error `config`; la cuenta se pausa |
| 409 | Cuenta detenida por el servicio (LinkedIn frenó antes), o una escritura con un `request_id` que ya salió o está saliendo y cuya respuesta no quedó guardada | Error `stopped`; la cuenta se pausa y el motivo dice qué hacer: revisarla a mano y reanudarla en el servicio (`python -m navegador reanudar <cuenta>`) y en Barrio |
| 422 | Fuera de la lista permitida; no salió nada | Error `refused` |
| 422 con `code: budget` | Tope de la cuenta agotado (lecturas o escrituras por hora o por día, o un tipo de escritura por día); no salió nada | Error `budget` con `retry_after`. No pausa la cuenta y no cuenta como límite de LinkedIn: la acción queda aprobada y se reintenta pasado ese tiempo; una lectura espera a la siguiente vuelta |
| 423 | Sin sesión: alguien tiene que entrar a mano en ese navegador | Error `login`; la cuenta se pausa y el motivo dice qué hacer: `python -m navegador login <cuenta>` y reanudarla en Barrio |
| 503 | Navegador no listo (no abrió, no tiene pantalla, o el perfil lo tiene otro navegador) u ocupado (la llamada no pudo salir en los 35 s siguientes a su llegada); no salió nada | Error `not_sent`: como `budget`, se reintenta más tarde (30 min si nadie dice otra cosa) |
| 503 con `code: conexion` | Alguien está entrando a mano en esa cuenta desde la app (ver «Conectar desde la app»); no salió nada. `retry_after` dice cuánto puede durar como mucho | Error `not_sent`: espera y se reintenta, sin pausar la cuenta ni avisar |
| 503 con `code: egress` | La salida a internet de la cuenta no es la de su última sesión: no la abre hasta que alguien acepte la nueva en el servidor (`python -m navegador salida <cuenta> --aceptar`) o vuelva a poner la de antes; no salió nada | Error `egress`: espera y se reintenta como `not_sent`, sin pausar la cuenta. Avisa en Notificaciones (`navegador_salida`) una sola vez por episodio (su `since`), con qué hacer |
| 504 u otro 5xx | La página falló durante la llamada: pudo salir y no se sabe qué pasó | Escritura: incierta. Lectura: error `network` |

El servicio juzga además lo mismo que el backend para detenerse: si una respuesta de LinkedIn trae una señal de
parada (redirección, 401, 403, 429, 999, login, verificación, HTML donde se esperaban datos), o la página termina
en una de esas pantallas o pierde la cookie de sesión, devuelve esa respuesta tal cual (200) y deja la cuenta
detenida en disco. Desde ahí todo recibe 409 hasta que alguien la reanuda (`python -m navegador reanudar <cuenta>`).

La pausa avisa una sola vez: los trabajos que ya estaban en cola y chocan con la misma parada solo actualizan el
motivo.

**Prueba diaria.** El backend no tiene un endpoint aparte para ella: el trabajo `check_linkedin` hace las 14 lecturas
del conector (16 llamadas) por `/llamadas`, como cualquier otra, así que gasta los topes y se detiene igual. Qué se
lee y qué campos debe traer cada respuesta vive en `linkedin_directo/canario.py`; `python -m navegador canario
<cuenta>` corre lo mismo a mano. Un 409 o 423 en la prueba pausa la cuenta como en cualquier lectura; un `budget`,
`not_sent`, `egress` o `network` la deja «sin correr» y se reintenta a la hora (un `egress` además avisa en el acto,
como en cualquier llamada).

## Conectar desde la app

Para entrar a mano en LinkedIn sin túnel SSH (Ajustes › Máquina, «Conectar LinkedIn»). Apagado salvo
`NAVEGADOR_CONEXION=true` en el servicio (sin eso, 404). Una conexión a la vez por servicio. Mismo token que las
llamadas. Diseño completo en el README del servicio, «Conectar desde la app».

| Petición | Respuesta |
| --- | --- |
| `POST /v1/cuentas/{cuenta}/conexion` | 201 con el estado (abajo) cuando la pantalla, la vista y la página de entrada están listas (hasta 45 s), o ya terminó si no abrió (`fallida`). 409 `code: conexion` si ya hay otra en curso; 503 `code: egress` si la salida no es la de la última sesión; 503 si la cuenta está ocupada con llamadas |
| `GET /v1/conexiones/{sesion}` | El estado; 404 si el servicio no la conoce (se reinició) |
| `DELETE /v1/conexiones/{sesion}` | La cancela y devuelve el estado final |

```json
{"sesion": "…", "cuenta": "cuenta-prueba", "estado": "esperando", "motivo": "", "inicio": "…", "vence": "…",
 "fin": null, "detenida": false, "parada": ""}
```

`estado`: `abriendo`, `esperando`, `conectada` (la pestaña llegó al inicio con la cookie de sesión y el perfil en disco
la guardó), `vencida` (10 min sin eso, `NAVEGADOR_CONEXION_MIN`), `cancelada` o `fallida`. `detenida` dice si la cuenta
sigue detenida en el servicio tras terminar: una conexión que termina `conectada` quita solo una parada por la sesión
(página de login o verificación, cookie perdida), nunca un 429, un 999 o un reto en una respuesta. El estado final
aparece solo cuando el navegador, la vista y la pantalla ya se cerraron y se miró la sesión en disco: un `conectada`
no cambia después. Cada espera del servicio tiene un plazo en tiempo real: una conexión que no atiende la cancelación
en 10 s se corta (su cierre sigue, con plazo por paso), y una que no abrió en 45 s termina `fallida`.

La vista remota escucha en `NAVEGADOR_PUERTO_PANTALLA` (8791, red interna) solo mientras dura la conexión, y cada
petición necesita `X-Pantalla-Clave` = HMAC-SHA256(token, `pantalla:` + sesión) en hexadecimal; si no, 403. Esa clave
la pone Caddy con lo que le devuelve el backend; nunca la ve el navegador de la persona.

`GET {NAVEGADOR_URL}/health` (sin token) contesta `{"status": "ok"}` mientras el servicio está arriba; no abre ningún
navegador. Si el navegador (con ventana) no tiene pantalla donde dibujar, contesta `503 {"status": "sin_pantalla"}`: el
contenedor necesita un reinicio, y cada llamada recibe 503 sin que salga nada.

Si no se puede conectar con el servicio, la llamada no salió (`not_sent`). Si se cae la conexión ya enviada, una
escritura queda incierta. El backend espera 75 s como máximo: el servicio pausa de 3 a 7 s antes de cada llamada y le
da 30 s a LinkedIn.

## Consultas vivas

`GET {NAVEGADOR_URL}/v1/cuentas/{cuenta}/consultas?prefixes=messengerConversations,…&variables=mailboxUrn`

Los ids de las consultas GraphQL cambian con cada despliegue de LinkedIn. El servicio guarda las llamadas GraphQL
que hizo la página por sí sola al cargar (abre la página de inicio si aún no estaba abierta; eso no cuenta para los
topes) y devuelve la más reciente cuya operación empiece por uno de los `prefixes` y use las mismas `variables`:

```json
{"path": "/voyagerMessagingGraphQL/graphql", "query_id": "messengerConversations.<hash>", "variables": ["mailboxUrn"], "source": "page"}
```

`path` va relativo a `/voyager/api`; también se acepta con el prefijo. Si no tiene ninguna, el servicio contesta 404.
Cualquier fallo aquí solo hace que el backend use el id fijo que trae. Con la cuenta del 2026-11-13, la página de
inicio hizo la consulta de conversaciones pero no la de mensajes: la lectura de mensajes usa el id fijo.

## Lista permitida

El servicio aplica la misma revisión que el backend (`linkedin_directo/permitidas.py`, función `check`) antes de
llamar. Si no pasa, contesta 422 y no envía nada.

- **Lecturas:**
  - cualquier GET bajo `/voyager/api/`;
  - la página de un post (`/feed/update/urn:li:activity:<n>/`) y la búsqueda de personas
    (`/search/results/people/?…`);
  - dos lecturas de la interfaz del servidor para los filtros de búsqueda: la barra de filtros y el autocompletado de
    ubicación;
  - la exportación de la analítica de creador: `POST /flagship-web/rsc-action/actions/navigation` con la pantalla
    `…creatoranalytics.AggregateAnalyticsExportModal`, sin marcar como escritura. El cuerpo tiene que ser exactamente
    el que arma `rutas.analytics_export`, con solo `startDate` y `endDate`: dos fechas ISO en orden y como mucho 366
    días. La misma ruta abre otras pantallas, así que cualquier otra pantalla o cuerpo no sale. Se envía desde la
    página de inicio, la que el servicio ya tiene abierta: no hace falta abrir la página de analítica (comprobado con
    la cuenta de pruebas el 2026-11-13). Detalle en [metricas-resultados.md](metricas-resultados.md#analítica-de-linkedin-cuenta-directo).
- **Escrituras:** solo cinco, cada una con su cuerpo revisado:
  - reaccionar a un post o a un comentario;
  - seguir a un miembro (solo `FOLLOW_ACTIVE`);
  - comentar con la plantilla de la página del post;
  - invitar con nota de hasta 300 caracteres;
  - aceptar una invitación recibida.

  La misma ruta o acción también deshace, retira, ignora o deja de seguir, y nada de eso pasa. Los mensajes
  directos no existen en esta lista: el conector solo los lee.

## Ids que devuelve el conector

Los campos son los mismos que con Unipile. Los ids, solo para las personas y los comentarios: los demás son los de
LinkedIn, y Unipile los envuelve (abajo, «Cambiar de proveedor», cómo se traducen).

| Objeto | Id |
| --- | --- |
| Persona | Id del perfil (`ACo…`), el mismo que Unipile llama provider id. También se acepta el id público (`/in/<id>`) o `me`. |
| Post | El número de la actividad (`urn:li:activity:<n>`). La fecha sale del id: `n >> 22` son milisegundos desde 1970. |
| Comentario | Su número. El post va aparte en cada llamada. |
| Invitación | El número de `fs_relInvitation`. El secreto para aceptarla lo guarda el conector al leer las recibidas. |
| Conversación | El id del hilo (`2-…`), el de `linkedin.com/messaging/thread/<id>/`. |
| Mensaje | El id que va tras la coma en su urn. |

Seguir a alguien necesita su número de miembro. El conector lo guarda de cada lectura que lo trae (perfil, comentario,
búsqueda, post). Si no lo tiene, lee el perfil antes.

## Cambiar de proveedor

`operador cambiar-proveedor` pasa una cuenta de Unipile a directo, o al revés, en la misma fila, y en la misma
transacción traduce los ids que la cuenta guarda: sus contactos, posts observados, propuestas abiertas, bandeja e
historia siguen con ella, sin filas repetidas ni nada que vuelva a parecer nuevo (`team_backend/proveedor.py`; las dos
formas de id, en `team_backend/ids_linkedin.py`).

```bash
# Antes: pausar la cuenta (o la máquina) y esperar a que acabe la vuelta en curso.
python manage.py operador --usuario gustavo cambiar-proveedor --cuenta <uuid> --a directo --slug <cuenta> --prueba
python manage.py operador --usuario gustavo cambiar-proveedor --cuenta <uuid> --a directo --slug <cuenta>
python manage.py operador --usuario gustavo comprobar --cuenta <uuid>   # y después reanudarla
# Volver, con los ids originales (también admite --prueba):
python manage.py operador --usuario gustavo cambiar-proveedor --cuenta <uuid> --volver
```

**La prueba** (`--prueba`) no escribe nada. Dice, por tabla y campo, cuántos ids se traducen, se restauran (al volver)
o quedan idénticos y cuántos no se pueden traducir; cuántas claves de evidencia y huellas de propuestas abiertas se
recalculan y cuántas propuestas caducarían; las fuentes y retiradas del estudio de comunidad; cuántas conversaciones
quedan marcadas; y cada fila que no se puede traducir, con la forma de su valor (cifras como 9 y letras como x), nunca
el id. Lo mismo sale al cambiar de verdad, y el resumen queda en la auditoría (`operator.account_provider_switched`).

**Formas de los ids.** Las de Unipile, leídas de la base de producción (solo la forma, nunca los valores):

| Objeto | Unipile | Directo |
| --- | --- | --- |
| Persona | `ACo…`, el id del perfil | El mismo. |
| Comentario | El número de LinkedIn | El mismo. |
| Post | Base64 de una lista JSON: `["activity:<n>"]`, `["activity:<n>","ugcPost:<m>"]` o `["activity:<a>","activity:<b>"]` | El número de la actividad. |
| Invitación | `SENT_<n>` o `RECEIVED_<n>_<secreto>` | `<n>`. |
| Conversación | `CLASSIC_2-…` | El hilo, `2-…`. |
| Mensaje | Su id en Unipile | El de LinkedIn. No hay regla entre los dos (abajo, la bandeja). |

Un post con dos actividades es una republicación: los números de actividad crecen con el tiempo (`n >> 22` es la
fecha) y la republicación es posterior al post que comparte. Directo da a esa fila, en la actividad de una persona, la
actividad de quien republica: la mayor de las dos. Al revés, un post se escribe con la forma de una actividad; las de
dos urns, y el secreto de una invitación recibida, solo vuelven desde el original guardado. Cualquier otra forma no se
traduce: no se adivina nunca.

**Qué se toca.**

| Campo | Qué guarda | Al cambiar |
| --- | --- | --- |
| `ObservedPost.provider_post_id`, `PostComment.provider_post_id`, `PersonEvidence.post_id` | Post | Traducido. |
| `PostMetric.provider_post_id`, `EditorialPiece.metrics.unipile_post_id` | Post propio | Traducido si la cuenta es la que lee los posts propios (`respuestas.reader_account`). `unipile_post_id` es el nombre del campo, y se lee como id (métricas, respuestas). |
| `Contact.invitation_id` | Invitación: enviada si el contacto está `invited`, recibida si `incoming` o `discarded` | Traducido. |
| `PersonEvidence.source_id` (`received:<id>`) | Invitación recibida | Traducido. |
| `payload.request_id` de RED-04 abiertas | Invitación recibida | Traducido. |
| `ActionExecution.external_id` de RED-02 | Invitación enviada | Traducido. |
| `Conversation.provider_chat_id` | Conversación | Traducido. |
| Autores de `ObservedPost` y `PostComment`, `EvidencePerson`, `Contact` y `Referent` (`provider_user_id`), `Conversation.attendee_provider_id` | Persona | Idéntico (se comprueba la forma). |
| `PostComment.provider_comment_id` y `thread_id`, `PersonEvidence.interaction_id`, `ActionExecution.external_id` de INT-03 e INT-04 | Comentario | Idéntico (se comprueba la forma). |
| `PersonEvidence.key`, `payload_hash` y `approved_hash` de las propuestas abiertas, `CommunitySource.target` y `key`, `CommunityWithdrawal.key` | Huellas de ids | Recalculadas. |
| `Conversation.messages[].id`, `assessment.message_id`, `closed_message_id`, `InboxSeen` | Mensaje | Sin traducir: la marca `Conversation.carry` (abajo). |
| `AuditEvent` `network.search_location` y `replies.scanned` | Ids que se vuelven a usar | No se usan los de antes del cambio (`ConnectorAccount.switched_at`): se buscan de nuevo. |
| Otros `AuditEvent`, `ReferentReview.dossier`, `WeeklySummary.stats`, `CycleLedger`, `CommunityStudy.coverage` | Historia | Quedan como estaban, a propósito. |
| `ActionExecution.external_id` de CONT-09 (`urn:li:share…`), `external_url`, `Contact.evidence.post_url`, `CommunitySource.url`, `metrics.share_url` | Urn de la API oficial y enlaces | No son de un proveedor: quedan. |
| `EditorialPiece.metrics.source: unipile` | Etiqueta | No es un id: queda. |
| `AnalyticsPost`, prueba diaria | Solo de directo | Quedan; al volver a Unipile, sin leerse. |

Lo que no es de LinkedIn (ids de filas, `Contact.evidence.post_id`, `Job.params`, la cobertura y la atribución) no
cambia.

**Lo que queda igual que antes del cambio.**

- Posts y comentarios: la siguiente observación encuentra las mismas filas. Ni filas repetidas, ni aviso de posts
  nuevos, ni un segundo comentario en el mismo post.
- Propuestas abiertas: su huella se recalcula con el post o la invitación traducidos. Una aprobación válida sigue
  válida (el mismo texto sobre el mismo objeto de LinkedIn, con otro nombre) y se ejecuta con el proveedor nuevo. Una
  RED-04 aún sin aprobar puede pasar una vez más por las comprobaciones de red.
- Bandeja: los mensajes no se pueden traducir, así que cada conversación queda marcada. En su siguiente lectura, si el
  último mensaje recibido es el mismo de antes (el mismo texto y la misma hora, con 2 minutos de margen), lo que tenía
  el id viejo pasa al nuevo: el juicio de Jev, el cierre de Gustavo y la tarjeta vista en Tu turno. Nada se vuelve a
  juzgar, avisar ni mostrar como nuevo. Un mensaje llegado después se juzga como siempre. La marca se borra en esa
  lectura.
- Estudio de comunidad: sus fuentes y retiradas se recalculan desde los pares post y comentario que guarda la cuenta.
  Una fuente sin rastro se queda (caduca a los 90 días); una retirada sin rastro cuenta como un id sin traducir.

**Volver.** La fila guarda el proveedor y el id externo que tenía (`previous_provider`), y cada id reescrito queda con
el que reemplazó (`ProviderIdOriginal`). `--volver` pone de nuevo el proveedor anterior y, en cada campo que no cambió
desde entonces, el valor original exacto; uno que cambió se traduce. Ida y vuelta se repiten sin perder nada. Los
originales solo se borran con `--olvidar-originales` (auditado: `operator.provider_originals_forgotten`); después, volver
traduce, y una invitación recibida ya no puede volver a Unipile.

**Cuándo no cambia.**

- La cuenta ya es de ese proveedor o no es de ninguno de los dos, o el id no tiene la forma del proveedor (directo: el
  nombre en el servicio; Unipile: `acc_…`), o ya lo tiene otra fila (la cuenta del rodaje, por ejemplo).
- La cuenta no está en pausa (ni la máquina): una vuelta a medias podría guardar ids del proveedor anterior.
- Hay una acción ejecutándose, enviada sin confirmar o incierta (se concilia con el proveedor que la envió), una
  conexión desde la app en curso, un trabajo de la cuenta en marcha o un estudio de comunidad armándose.
- Hay un id que no se puede traducir: una forma desconocida, o uno que chocaría con otra fila de la cuenta una vez
  traducido. Lo lista y no cambia nada. Solo como salida de emergencia, `--aceptar-ids-viejos` cambia dejando esas
  filas como estaban, y las propuestas abiertas sobre ellas caducan en vez de ejecutarse con el id del otro proveedor.

Tras el cambio, el estado de la cuenta queda «sin comprobar» y la pausa sigue: `comprobar` y reanudarla.

