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

| Código | Significado | Lo que hace el backend |
| --- | --- | --- |
| 400 | Petición mal formada | Error `contract` |
| 401, 403 | Falta el token (401) o no es el del servicio (403) | Error `config`; la cuenta se pausa |
| 404 | Cuenta desconocida en el servicio | Error `config`; la cuenta se pausa |
| 409 | Cuenta detenida por el servicio (LinkedIn frenó antes), o una escritura con un `request_id` que ya salió o está saliendo y cuya respuesta no quedó guardada | Error `stopped`; la cuenta se pausa y el motivo dice qué hacer: revisarla a mano y reanudarla en el servicio (`python -m navegador reanudar <cuenta>`) y en Barrio |
| 422 | Fuera de la lista permitida; no salió nada | Error `refused` |
| 422 con `code: budget` | Tope de la cuenta agotado (lecturas o escrituras por hora o por día, o un tipo de escritura por día); no salió nada | Error `budget` con `retry_after`. No pausa la cuenta y no cuenta como límite de LinkedIn: la acción queda aprobada y se reintenta pasado ese tiempo; una lectura espera a la siguiente vuelta |
| 423 | Sin sesión: alguien tiene que entrar a mano en ese navegador | Error `login`; la cuenta se pausa y el motivo dice qué hacer: `python -m navegador login <cuenta>` y reanudarla en Barrio |
| 503 | Navegador no listo (no abrió, o el perfil lo tiene otro navegador), ocupado (la llamada no pudo salir en los 35 s siguientes a su llegada) o con una salida a internet distinta de la última de su sesión, que alguien tiene que aceptar; no salió nada | Error `not_sent`: como `budget`, se reintenta más tarde (30 min si nadie dice otra cosa) |
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
`not_sent` o `network` la deja «sin correr» y se reintenta a la hora.

`GET {NAVEGADOR_URL}/health` (sin token) contesta `{"status": "ok"}` mientras el servicio está arriba; no abre ningún
navegador.

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

Son los mismos que usan los llamadores con Unipile, para que una cuenta pueda cambiar de proveedor.

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
