# Publicación diaria autónoma

Fecha: 2026-11-06. Estado: **implementado y probado sin red ni gasto** (conector simulado y Claude parcheado). La publicación real espera la app de LinkedIn Developers, el OAuth de Gustavo y `LIVE_LINKEDIN_OFFICIAL=true`.

Cubre CONT-01..07 y CONT-09 del [catálogo](catalogo-acciones-linkedin.md) con el diseño editorial acordado (director_editorial, copywriter_a/b, cinco lectores y editor_verificador). Sigue la decisión vigente de Gustavo: «todo debe funcionar como una máquina autónoma». Cada pieza sale sin revisión humana. Una política automática la aprueba solo si pasa la verificación, y Gustavo supervisa desde la PWA: puede vetar, pausar y recibe notificaciones push.

## Recorrido

```mermaid
flowchart LR
    T[Autopiloto: hueco del día] -->|EDITORIAL_LEAD_HOURS antes| D[a) Director: brief o skip]
    D -->|skip| S[Día sin pieza]
    D --> R[b) Redactores A y B: dos variantes en inglés]
    R --> L[c) Panel de 5 lectores]
    L --> E[d) Director: elige o fusiona; texto final]
    E --> V[e) Verificador sobre el hash del texto]
    V -->|blocked| B[Pieza bloqueada + push]
    V -->|ready_for_execution| P[Propuesta CONT-09]
    P -->|política autonomia-v1| A[Aprobada + push: se puede vetar]
    A -->|EDITORIAL_POST_TIME| X[Operador: Posts API, una sola vez]
    X -->|201 + URN| C[Confirmada / conciliada por Unipile]
    X -->|timeout o 5xx| U[Incierta: nunca se repite]
```

## Conector de la API oficial (`connectors_linkedin.py`)

### Contrato verificado el 2026-11-06

| Tema | Fuente |
| --- | --- |
| OAuth de 3 patas: `authorization` y `accessToken`, `state` contra CSRF, tokens de 60 días; la renovación programática solo existe para socios seleccionados | [Authorization Code Flow](https://learn.microsoft.com/en-us/linkedin/shared/authentication/authorization-code-flow) |
| `openid profile`; `GET https://api.linkedin.com/v2/userinfo` devuelve `sub` | [Sign In with LinkedIn using OpenID Connect](https://learn.microsoft.com/en-us/linkedin/consumer/integrations/self-serve/sign-in-with-linkedin-v2) |
| `w_member_social` con el producto Share on LinkedIn; el URN de persona sale de OpenID Connect | [Share on LinkedIn](https://learn.microsoft.com/en-us/linkedin/consumer/integrations/self-serve/share-on-linkedin) |
| `POST https://api.linkedin.com/rest/posts` con un cuerpo de solo texto; responde 201 con el URN en `x-restli-id`; leer posts de un miembro exige `r_member_social`, que está restringido | [Posts API](https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/posts-api) |
| `commentary` en formato `little`: los caracteres reservados se escapan con barra invertida | [little Text Format](https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/little-text-format) |
| La versión más reciente es 202610. Cada versión tiene soporte durante al menos un año, y 202511 se retira el 16-nov-2026 | [Versioning](https://learn.microsoft.com/en-us/linkedin/marketing/versioning) |

**Versión elegida: `LINKEDIN_API_VERSION=202610`** (octubre de 2026, la más reciente publicada). Se puede configurar y tiene soporte hasta octubre de 2027 como mínimo. Para migrar basta con cambiar la variable a una versión posterior, después de leer su *changelog*.

### OAuth

- `GET /api/v1/linkedin/oauth/start` exige una sesión humana (nunca un token Bearer) y el permiso `approve_actions`. Guarda un `state` aleatorio de 32 bytes en la sesión, válido 10 minutos y de un solo uso, y redirige a LinkedIn con `scope=openid profile w_member_social`.
- `GET /api/v1/linkedin/oauth/callback` valida el `state` con comparación en tiempo constante. Después canjea el `code`, lee `sub` en `/v2/userinfo` y exige que el permiso concedido incluya `w_member_social`. Por último guarda el token cifrado y redirige a `/ajustes?linkedin=ok`. Si algo falla, redirige a `/ajustes?linkedin=error&motivo=state|sesion|permiso|denegado|code|canje|scope`.
- **SameSite=Strict.** La cookie de sesión no viaja en la redirección que llega desde linkedin.com. Por eso la primera llegada sin sesión responde con una página mínima (meta refresh, `no-store`, `no-referrer`) que vuelve a pedir la misma URL, ahora como navegación del mismo sitio y con `rebote=1`. Si tampoco hay sesión entonces, devuelve `motivo=sesion`.
- **Modelo `LinkedInCredential`.** Guarda una fila por miembro, en relación uno a uno con un `ConnectorAccount(provider='linkedin', external_account_id='urn:li:person:<sub>')`. Sus campos son `member_urn`, `member_name`, `scopes`, `token_encrypted`, `expires_at`, `connected_by`, `connected_at` y `expiry_alerted_at`. El token se cifra con Fernet usando `FIELD_ENCRYPTION_KEY`, que admite varias claves separadas por comas para rotarlas: la primera cifra y todas descifran. El token nunca se registra, nunca se devuelve por la API y no aparece en `/admin/`.
- **Caducidad.** Siete días antes llega una push («LinkedIn caduca pronto») y se envía una sola vez por token. Al caducar, la cuenta oficial se pausa con el motivo «Token de LinkedIn caducado…», también con push. Reconectar desde Ajustes guarda el token nuevo y levanta solo esa pausa. Mientras el token siga vigente y Gustavo tenga la sesión de LinkedIn abierta, LinkedIn salta la pantalla de consentimiento al reconectar.

### Publicar (CONT-09)

Cuerpo enviado, con las cabeceras `LinkedIn-Version: 202610` y `X-Restli-Protocol-Version: 2.0.0`:

```json
{"author":"urn:li:person:<sub>","commentary":"<texto escapado en little>","visibility":"PUBLIC",
 "distribution":{"feedDistribution":"MAIN_FEED","targetEntities":[],"thirdPartyDistributionChannels":[]},
 "lifecycleState":"PUBLISHED","isReshareDisabledByAuthor":false}
```

El conector sigue la misma semántica que `connectors.py`:

| Resultado | Clasificación | Efecto |
| --- | --- | --- |
| 201 con `x-restli-id` (`urn:li:share:…` o `urn:li:ugcPost:…`) | Éxito | Se guardan el URN y la URL `https://www.linkedin.com/feed/update/<urn>/` |
| Fallo de conexión antes de enviar | Definitivo, `not_sent` | No se envió nada |
| 401, 403 o 429 | Definitivo con pausa | Cuenta en pausa y push |
| Otros 4xx | Definitivo | No aplicado |
| 5xx, timeout tras enviar, respuesta sin URN | Incierto | **Nunca se repite**; se concilia |

Conciliación: `w_member_social` no permite leer. Si hay una cuenta Unipile conectada, el operador lee los posts propios (`list_user_posts('me')`) y los **compara por texto**, porque los IDs de Unipile son opacos y no se convierten a URN. También se hace antes de escribir: si ya existe un post propio idéntico, la acción se confirma sin publicar otro. Sin Unipile, un 201 con URN se confirma por esa respuesta y un resultado incierto queda en `uncertain` para que Gustavo lo resuelva (`/operador/actions/<id>/resolve`). Al conciliar, las impresiones que devuelve Unipile se guardan en `EditorialPiece.metrics` como primera métrica (APRE-01). Un dato ausente no equivale a cero.

`LIVE_LINKEDIN_OFFICIAL=false` por defecto: sin ese interruptor no se publica nada. El conector simulado (`provider='linkedin_fake'`) requiere `OPERATOR_ALLOW_FAKE=true` y tiene los mismos modos de fallo que el de Unipile.

## Circuito editorial (`editorial.py`)

Cada etapa es una llamada a `knowledge.providers.claude()` con estas características: streaming, `output_schema` JSON, `effort`, un `purpose` propio en el registro de gasto y reserva previa. Recibe unidades completas del curso dentro de un presupuesto de tokens (`operador.course_context`); las citas que no estén en el contexto se descartan.

| Etapa (`purpose`) | Rol del diseño | Unidades (prioridad) | Presupuesto de contexto / salida máx. / effort |
| --- | --- | --- | --- |
| a) `editorial-director` | director_editorial (CONT-01/02/07) | B12 `LI-04-M005-K01`; B13 `LI-05-V022-K01/K03`; 9 enfoques `LI-05-M001-K01..K06`, `LI-05-M002-K01..K03`; formato texto `LI-05-M002-K04` | 22 000 / 4 000 / medium |
| b) `editorial-redactor` | copywriter_a y copywriter_b (CONT-03) | enfoque elegido; `LI-05-M002-K04`; B15 `LI-06-M002-K09/K10`, `LI-06-M003-K06`; guía `LI-06-M001-K01..K16` | 26 000 / 6 000 / medium |
| c) `editorial-lectores` | cinco lectores (CONT-05) | B14 `LI-05-V005-K05`, `LI-06-V020-K01` | 5 000 / 4 000 / low |
| d) `editorial-seleccion` | director_editorial | B15 y B14 | 9 000 / 4 000 / medium |
| e) `editorial-verificador` | editor_verificador (CONT-06) | B15; `LI-06-M001-K04` (promesa del gancho) y `LI-06-M001-K07` (concreción sin inventar) | 8 000 / 4 000 / high |

Los otros cinco formatos del curso (foto, infografías, carrusel, vídeo y cita: `LI-05-M002-K05..K08` y `LI-05-M003-K01..K03`) quedan registrados para la fase de imágenes. En esta fase el esquema solo admite `text_only`.

- **Director.** Recibe tres tipos de señales: hasta 12 posts de referentes de los últimos 7 días, marcados como datos de terceros; la memoria; y el historial de las últimas 20 piezas con la mezcla de modalidades publicadas en 30 días, para no repetirse. Devuelve un brief con estos campos: lector principal, modalidad (`personal_startups`, `projectapp`, `alianzas` o `comunidad`), pilar provisional (`business_to_product`, `applied_ai` o `architecture_delivery`), tesis, enfoque, formato, valor para el lector, evidencia, criterio de éxito, qué evitar y señales usadas. El 60/40 orienta la mezcla y no es una cuota. Si no hay material genuino, responde `skip`; saltar un día es válido y ese día no se reintenta solo.
- **Redactores.** Hacen una sola llamada que devuelve dos variantes independientes. La A explora primero una decisión, un procedimiento o un caso; la B, una pregunta u objeción del founder y su mecanismo. Ambas parten del mismo brief y de las mismas fuentes, y cada una enumera sus afirmaciones con su tipo.
- **Lectores.** Comprador, recomendador, divulgador, líder y par dan fortalezas y objeciones por variante, clasificadas como `material`, `preference` o `missing_data`. Son hipótesis, no métricas. No reciben memoria ni la autoría de las variantes.
- **Selección.** El director elige A o B, las fusiona o descarta la pieza. Decide por objetivo, verdad, utilidad y voz, no por mayoría.
- **Verificador.** Contrasta cada afirmación con `public_facts` y las fuentes observadas. Marca experiencias inventadas, cifras sin fuente, pitch agresivo, datos privados, filtraciones de `private_guidance`, ganchos incumplidos y piezas fuera del brief. El veredicto final se calcula sobre el SHA-256 del texto exacto y es `blocked` en cualquiera de estos casos:
  - el modelo emite `blocked`;
  - hay un hallazgo `material`;
  - hay una afirmación `unsupported`;
  - la guarda determinista detecta experiencia en primera persona sin hechos públicos confirmados;
  - se filtra orientación privada.

### Memoria: hechos públicos y orientación privada

Los hechos confirmados de Gustavo (`namespace='user'`) se reparten en dos bloques con `knowledge.memory.confirmed_blocks()`:

- `public_facts`: valores `{"texto": …, "uso_publico": true}`. Son lo único que puede atribuirse a Gustavo en un texto público.
- `private_guidance`: el resto, incluido cualquier valor que no sea un dict con `uso_publico` (por seguridad), más la orientación privada del brief interno (`guardas.BASELINE_GUIDANCE`: prioridad 60/40, segmento de founders y condiciones). Orienta decisiones, pero nunca aparece ni se parafrasea en público.

Director, redactores, selección y verificador reciben ambos bloques; el panel de lectores no recibe ninguno. Los comentarios (`propose_comment`) usan la misma separación sin la orientación del brief. Con la memoria vacía, como hoy, las piezas aportan criterio, preguntas y aprendizajes generales, sin vivencias de Gustavo. `guardas.private_leaks()` detecta 60/40, segmentos como «Spanish-speaking founders», bandas salariales, LLC y Beloz, además de fragmentos literales de la orientación privada. La usan el verificador de piezas y la compuerta de comentarios.

## Compuerta autónoma (`autopiloto.policy_review`, `autonomia-v1`)

CONT-09 se aprueba solo si se cumplen todas estas condiciones:
- la longitud está entre 200 y 2 200 caracteres;
- no hay correos, teléfonos ni enlaces;
- no hay pitch agresivo ni petición de contacto (mencionar ProjectApp está permitido);
- hay 3 hashtags como máximo;
- no hay filtración privada ni experiencia sin hechos públicos;
- el verificador dio `ready_for_execution` sobre el mismo `text_sha256`;
- no hay afirmaciones pendientes;
- hay al menos una unidad del curso citada.

Si cualquier edición cambia el texto, invalida el veredicto y la política descarta esa versión. Para publicar un texto editado a mano, usa `OPERATOR_AUTONOMY=…,CONT-09=approval` y apruébalo con su hash.

## Programación (`autopiloto.tick`)

- **Hueco diario.** La hora es `EDITORIAL_POST_TIME` (08:30 por defecto), en `OPERATOR_TIMEZONE`, y debe caer dentro de `OPERATOR_WINDOW`. La preparación empieza `EDITORIAL_LEAD_HOURS` antes (12 h por defecto). Así hay margen para vetar y llega una push «pieza lista» con la hora de salida.
- **Una preparación cada vez.** El trabajo `prepare_piece` tiene un id determinista por hueco, así que el autopiloto lo intenta una sola vez por día. Una preparación interrumpida pasa a `failed` sin repetir el gasto.
- **No se prepara una pieza que no podría salir.** Hace falta una cuenta oficial conectada, sin pausa y con `LIVE_LINKEDIN_OFFICIAL=true`, CONT-09 distinto de `off` y cupo semanal.
- **Topes.** CONT-09 admite 1 al día y 7 a la semana (`publicaciones` del reparto), configurables en `OPERATOR_DAILY_LIMITS` y `OPERATOR_WEEKLY_LIMITS`. Además, la base de datos impide más de una pieza abierta por día y más de una acción abierta por pieza.
- **Presupuesto propio.** `EDITORIAL_DAILY_LLM_USD` (1 USD por defecto) suma el gasto de hoy con `purpose LIKE 'editorial-%'`, separado del de comentarios (`OPERATOR_DAILY_LLM_USD`). Se comprueba antes de encolar y antes de cada etapa, y al agotarse la pieza se detiene. El techo acumulado `ANTHROPIC_LIMIT_USD` sigue vigente.
- **Ejecución.** Pasa por `operador.execute()`, que añade una compuerta: no se publica antes de `scheduled_for`. Valen también todas las salvaguardas de siempre: parada global, pausa de cuenta, ventana, espaciado y topes. El espaciado entre escrituras públicas pasa a ser común a todos los conectores, porque todos actúan como el mismo miembro.
- **Caducidad.** Una pieza aprobada que no sale caduca `OPERATOR_PROPOSAL_TTL_HOURS` después de su hora programada, no de su creación.

## Coste estimado por pieza

Tokens aproximados: unas 62 000 de unidades del curso entre las cinco etapas, unas 16 000 de instrucciones y datos (señales, memoria, borradores y panel) y entre 6 000 y 10 000 de salida.

| Modelo (`providers.MODEL_PRICES`, USD por millón de tokens de entrada / salida) | Pieza completa | Día con `skip` (solo el director) |
| --- | --- | --- |
| `claude-opus-5-5` (4 / 20), por defecto | ≈ 0,43–0,51 USD | ≈ 0,12 USD |
| `claude-sonnet-5-5` (2 / 10) | ≈ 0,22–0,26 USD | ≈ 0,06 USD |
| `claude-haiku-5-5` (0,10 / 0,50) | ≈ 0,01 USD | < 0,01 USD |

Con opus salen unos 13–15 USD al mes con una pieza diaria. Cada etapa reserva primero su peor caso: con opus, unos 0,26 USD como máximo en la del redactor. Las etapas son secuenciales y se liquidan antes de pasar a la siguiente, así que el tope diario de 1 USD cubre una pieza.

## API para la PWA

| Ruta | Uso |
| --- | --- |
| `GET /api/v1/linkedin/oauth/start` | Inicia la conexión (sesión humana con `approve_actions`): 302 a LinkedIn. |
| `GET /api/v1/linkedin/oauth/callback` | Retorno de LinkedIn: 302 a `/ajustes?linkedin=ok` o a `…=error&motivo=…`. |
| `GET /api/v1/linkedin/status` | `configured`, `live`, `api_version`, `connected`, `member_urn`, `member_name`, `scopes`, `expires_at`, `days_left`, `expired`, `expiring_soon`, `account{id,paused,paused_reason}`. Nunca incluye el token. |
| `GET /api/v1/editorial/calendar?desde=AAAA-MM-DD&dias=15` | `timezone`, `post_time`, `lead_hours`, `today` y `days[{date, pieces[…]}]`; un día vacío es un hueco visible. Cada pieza trae `id`, `slot_date`, `scheduled_for`, `state`, `status`, `stage`, `modality`, `pillar`, `primary_reader`, `thesis`, `approach`, `note`, `action{id,state,payload_hash}` y `external_url`. |
| `GET /api/v1/editorial/pieces/<id>` | Lo mismo, más `brief`, `variants`, `panel`, `selection`, `verification`, `final_text`, `citations`, `signals`, `usage` (modelo, coste estimado y `request_id` por etapa) y `action_detail` (la acción completa). |
| `POST /api/v1/editorial/plan` | `{request_id?}`: encola la preparación del próximo hueco sin pieza abierta (202 `{slot_date, job}`). Responde 409 si LinkedIn no está conectado, si la publicación está pausada o desactivada, o si no hay hueco en 7 días. Requiere `use_paid_providers`. |
| `POST /api/v1/operador/actions/<id>/reject` | **Vetar** una pieza antes de su hora (sesión humana). El día queda sin publicación. |
| `POST /api/v1/operador/control` | Parada total (sin cambios). |

`status` de una pieza: `preparing`, `skipped`, `blocked` o `failed` mientras no exista la acción. Después sigue el ciclo de esta: `awaiting_approval`, `scheduled`, `publishing`, `published`, `uncertain`, `vetoed`, `discarded`, `expired` o `superseded`.

Acciones (`/api/v1/operador/actions…`): `post` puede ser `null`. En ese caso `piece_id` y `scheduled_for` identifican la pieza propia. CONT-09 no se puede crear a mano desde esta ruta. `GET /api/v1/operador/overview` añade `today.editorial_llm_spent_usd` y `today.editorial_llm_daily_cap_usd`. `/oficina/actividad` muestra la etapa en curso con su rol: director, redactores, lectores o verificador.

Notificaciones push (y `OPERATOR_ALERT_WEBHOOK`):
- pieza lista, con la hora y la opción de vetar;
- pieza bloqueada;
- pieza descartada por la política;
- pieza publicada;
- acción incierta;
- LinkedIn caduca pronto;
- cuenta en pausa, también por token caducado.

## Qué debe configurar Gustavo

1. **App en LinkedIn Developers.** Créala en https://www.linkedin.com/developers/apps/new. LinkedIn pide asociarla a una página de empresa, por ejemplo la de ProjectApp. En la pestaña *Products*, añade **Share on LinkedIn** y **Sign In with LinkedIn using OpenID Connect**; ambos son de autoservicio.
2. **URL de retorno.** En la pestaña *Auth*, añade la URL exacta `https://<BARRIO_DOMAIN>/api/v1/linkedin/oauth/callback`, sin `#`; LinkedIn ignora los parámetros. Copia el *Client ID* y el *Client Secret*.
3. **Variables en el `.env` del servidor:**
   ```
   LINKEDIN_CLIENT_ID=…
   LINKEDIN_CLIENT_SECRET=…
   LINKEDIN_REDIRECT_URI=https://<BARRIO_DOMAIN>/api/v1/linkedin/oauth/callback
   LINKEDIN_API_VERSION=202610
   FIELD_ENCRYPTION_KEY=…   # docker compose -f compose.prod.yaml run --rm --no-deps api python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   LIVE_LINKEDIN_OFFICIAL=false   # true cuando quiera que salga la primera pieza
   EDITORIAL_POST_TIME=08:30
   EDITORIAL_LEAD_HOURS=12
   EDITORIAL_DAILY_LLM_USD=1
   OPERATOR_AUTONOMY=INT-03=auto,INT-02=auto,CONT-09=auto
   ```
   Para la primera pieza conviene `CONT-09=approval`: Gustavo la aprueba con su hash y luego pasa a `auto`. Si se pierde `FIELD_ENCRYPTION_KEY`, basta con reconectar LinkedIn.
4. **Despliegue.** `up -d` aplica la migración `0007_publicacion_diaria`. Después, con la sesión iniciada en la PWA, hay que abrir `https://<BARRIO_DOMAIN>/api/v1/linkedin/oauth/start`; el botón de Ajustes debe apuntar ahí. Para comprobarlo, `GET /api/v1/linkedin/status` debe mostrar `connected: true`.
5. **Encendido.** Con `LIVE_LINKEDIN_OFFICIAL=true` y `OPERATOR_AUTOPILOT=true`, el autopiloto prepara la pieza del día siguiente. Cada unos 60 días toca reconectar; la push avisa con 7 días de margen.

## Límites y pendientes

- Solo texto. Imágenes, carruseles y vídeo (CONT-04) llegan en una fase posterior.
- Mientras la memoria esté vacía, no hay casos ni experiencias de Gustavo. Cuando confirme hechos con `uso_publico: true`, las piezas podrán usarlos.
- No hay edición ni retirada de posts (CONT-10/11), ni analítica oficial (r_member_postAnalytics); la única métrica son las impresiones que lee Unipile.
- La PWA todavía debe mostrar el calendario, el detalle con el botón de veto y el botón «Conectar LinkedIn».
