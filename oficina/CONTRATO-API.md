# Contrato entre la oficina PWA y Django

Mismo origen en producción. Caddy sirve la PWA en `/` y reenvía `/api/*`, `/admin/*`, `/static/*` y `/health` a Django. En desarrollo, Vite hace de proxy de `/api` hacia `http://127.0.0.1:8787`.

**Autenticación:** sesión de Django más CSRF. La cookie `csrftoken` es legible por JS; todo POST, PUT o DELETE lleva la cabecera `X-CSRFToken`. Las peticiones usan `credentials: 'same-origin'`. Un 401 o 403 de sesión lleva a la pantalla de login.

**Errores:** JSON `{ "detail": "mensaje en español" }`. Códigos: 400 entrada inválida, 403 sin permiso o decisión humana requerida, 404, 409 conflicto o salvaguarda, 429.

**Listados:** los paginados devuelven `{ "count", "next", "previous", "results": [...] }` con 25 por página (`?page=`, `?page_size=` hasta 100).

## Sesión

| Método y ruta | Cuerpo | Respuesta |
| --- | --- | --- |
| GET `/api/v1/auth/session` | — | `{ authenticated, user: { username, is_superuser, permissions: [codename…] } \| null }`. Además fija la cookie CSRF. |
| POST `/api/v1/auth/login` | `{ username, password }` | 200 `{ user }`; 400 si las credenciales son inválidas; 429 si hay demasiados intentos. |
| POST `/api/v1/auth/logout` | — | 204 |

## Máquina autónoma

GET `/api/v1/operador/overview`:
```json
{
  "autopilot": { "enabled": true, "policy_version": "autonomia-v1" },
  "control": { "paused": false, "reason": "", "source": "db|env|none", "updated_at": "ISO|null", "updated_by": "username|null" },
  "window": { "start": "07:00", "end": "21:00", "timezone": "America/Bogota", "open_now": true, "min_spacing_seconds": 1200 },
  "accounts": [ { "id": "uuid", "label": "…", "provider": "unipile|fake|linkedin|linkedin_fake", "status": "running|token_expired|…",
                  "is_locked": false, "paused": false, "paused_reason": "", "last_checked_at": "ISO|null",
                  "capacity": { "INT-03": { "daily": 3, "weekly": 12, "daily_used": 1, "weekly_used": 4, "left": 2 },
                                "INT-02": { "…": "…" }, "CONT-09": { "daily": 1, "weekly": 7, "…": "…" } } } ],
  "today": { "proposals": { "proposed": 0, "approved": 1, "discarded": 2, "confirmed": 1, "…": 0 },
             "llm_spent_usd": "0.42", "llm_daily_cap_usd": "1", "drafts": 3, "drafts_daily_cap": 6,
             "editorial_llm_spent_usd": "0.43", "editorial_llm_daily_cap_usd": "1" },
  "counts": { "referents": 7, "posts": 31, "uncertain": 0 }
}
```

POST `/api/v1/operador/control` con `{ paused: bool, reason: string }`. Es la parada total de la máquina y requiere sesión humana. Responde con el objeto `control`. Si `OPERATOR_PAUSED=true` está en el entorno, la parada no se puede levantar desde la app: responde 409 con su explicación.

`editorial_llm_*` es el presupuesto propio de la publicación diaria (`EDITORIAL_DAILY_LLM_USD`), separado del de comentarios. La PWA solo lo muestra si llega; el overview no trae la próxima pieza, que se lee del calendario editorial.

GET `/api/v1/operador/feed?limit=50` devuelve los eventos recientes de `operator.*` y `job.*`, en orden descendente:
`[ { id, action, target, created_at, actor: "username|null", metadata: {…} } ]`

Rutas existentes (ver `agentes-linkedin/infra/docs/operador-linkedin.md`):
- `GET /api/v1/operador/accounts`
- `POST /api/v1/operador/accounts/<id>/pause` con `{ paused, reason }`
- `GET|POST /api/v1/operador/referents` con `{ account, identifier, reason }`
- `POST /api/v1/operador/observe` con `{ account, limit? }`
- `GET /api/v1/operador/posts?account=`
- `POST /api/v1/operador/posts/<id>/propose-comment`
- `GET /api/v1/operador/actions?state=` y `GET /api/v1/operador/actions/<id>`

Cada acción (`serializers.ActionOutput`) tiene esta forma:
```text
{ "id": "uuid", "account_id": "uuid", "capability": "INT-03|INT-02|CONT-09",
  "post": { "id", "account_id", "referent_id", "provider_post_id", "share_url", "author_name", "author_public_identifier",
            "text", "posted_at", "comments_count", "reactions_count", "is_repost", "observed_at" } | null,
  "piece_id": "uuid|null", "scheduled_for": "ISO|null",
  "payload": { "text": "…" } | { "reaction": "…" }, "payload_hash": "sha256", "version": 1, "previous_id": "uuid|null",
  "rationale": "…", "citations": ["unitId"], "risks": ["…"], "source": "agent|human", "origin_job": "…", "model": "…",
  "state": "proposed|…", "created_at": "ISO", "approved_hash": "…", "decided_by_id": 1, "decided_at": "ISO|null", "decision_note": "…",
  "execution": null | { "id", "state", "provider", "started_at", "finished_at", "external_id", "external_url", "error_kind",
                        "http_status", "note", "reconciled_at" } }
```

- **Comentario (INT-03) y reacción (INT-02):** `post` es la publicación ajena; `piece_id` y `scheduled_for` son `null`.
- **Publicación propia (CONT-09):** `post` es **siempre `null`**. `piece_id` y `scheduled_for` identifican la pieza editorial y su hora de salida, `payload.text` es el texto final en inglés y, una vez publicada, `execution.external_url` es `https://www.linkedin.com/feed/update/urn:li:share:…/`. No se puede crear a mano: la propone el circuito editorial.
- El listado filtra por `state` y por `capability`. La PWA envía `capability=<código>&page_size=100` y, por compatibilidad, vuelve a filtrar en cliente las capacidades que recibe (`/acciones?capacidad=comentarios|reacciones|publicaciones`).

Estados de una acción: `proposed`, `approved`, `rejected`, `superseded`, `discarded`, `executing`, `sent`, `confirmed`, `uncertain`, `failed` y `expired`.

Decisiones, todas con sesión humana:
- `POST /api/v1/operador/actions/<id>/reject` con `{ note }`: vetar una acción pendiente o aprobada.
- `POST /api/v1/operador/actions/<id>/approve` con `{ expected_hash, note }`: solo en capacidades configuradas en modo `approval`.
- `POST /api/v1/operador/actions/<id>/resolve` con `{ outcome: "confirmed|failed", note }`.
- `POST /api/v1/operador/actions/<id>/revise` con `{ payload }`.
- `POST /api/v1/operador/actions/<id>/reconcile`.

## Publicación diaria (editorial)

Fuente: `agentes-linkedin/infra/src/team_backend/editorial_views.py` y `docs/publicacion-diaria.md`. Lectura con el permiso `operate_linkedin`. Cada pieza sale **sola** a su hora si la política `autonomia-v1` la aprueba; la única intervención humana es el veto.

GET `/api/v1/editorial/calendar?desde=AAAA-MM-DD&dias=15` (por defecto `desde` = hoy − 7 y `dias` = 15; `dias` va de 1 a 60; parámetros inválidos → 400):
```json
{ "timezone": "America/Bogota", "post_time": "08:30|null", "lead_hours": 12.0, "config_error": "texto|null", "today": "2026-11-06",
  "days": [ { "date": "2026-11-07",
              "pieces": [ { "id": "uuid", "slot_date": "2026-11-07", "scheduled_for": "ISO", "state": "preparing|skipped|blocked|failed|ready",
                            "status": "…", "stage": "director|redactor|lectores|seleccion|verificador|", "note": "…",
                            "modality": "personal_startups|projectapp|alianzas|comunidad|null",
                            "pillar": "business_to_product|applied_ai|architecture_delivery|null",
                            "primary_reader": "lector_comprador|…|null", "thesis": "…|null", "approach": "LI-05-M001-K02|null",
                            "action": { "id": "uuid", "state": "proposed|approved|…", "payload_hash": "sha256" } | null,
                            "external_url": "https://www.linkedin.com/feed/update/…|null", "created_at": "ISO" } ] } ] }
```

Un día con `pieces: []` es un hueco visible: nunca se rellena sin motivo. `status` vale `preparing`, `skipped`, `blocked` o `failed` mientras no existe la acción CONT-09; después sigue a la acción: `awaiting_approval` (proposed), `scheduled` (approved), `publishing` (executing), `published` (sent o confirmed), `uncertain`, `failed`, `vetoed` (rejected), `discarded`, `expired` o `superseded`.

GET `/api/v1/editorial/pieces/<id>` devuelve lo mismo que una pieza del calendario más:
- `brief`: `{ decision: "write|skip", skip_reason, primary_reader, modality, pillar, thesis, approach, format: "text_only", reader_value, evidence: [{ kind, ref, note }], success_criterion, avoid: [], signals_used: [], citations: [], rationale }`.
- `variants`: `{ variant_a: { angle, text, claims: [{ text, kind, ref }], uncertainties: [] }, variant_b: {…}, citations: [] }`.
- `panel`: `{ readers: [{ reader, variant_a: { strengths: [], objections: [{ text, severity: "material|preference|missing_data" }] }, variant_b: {…} }], summary, citations }`.
- `selection`: `{ decision: "A|B|merge|discard", final_text, rationale, claims, resolved_objections: [], kept_objections: [], citations }`.
- `verification`: `{ verdict: "ready_for_execution|blocked", model_verdict, blocking_reasons: [], findings: [{ issue, severity: "material|minor", quote, detail }], checked_claims: [{ text, status, ref }], summary, citations, text_sha256 }`. `verdict` es el final (modelo más guardas deterministas) sobre el hash del texto exacto.
- `final_text`, `citations: [unitId]`, `signals: [{ id, author, why_followed, posted_at, reactions, comments, text }]` (datos de terceros), `usage: [{ stage, model, estimated_usd, request_id, units, missing_units }]` y `action_detail`: la acción CONT-09 completa o `null`.

Los bloques de una etapa que aún no ha corrido llegan como `{}`. `metrics` lleva los últimos valores leídos del post (ver la sección «Resultados»), y `snapshots` y `commenters` traen los cortes a 24 h, 72 h y 7 días y quién comentó. Un dato ausente no es cero.

POST `/api/v1/editorial/plan` con `{ request_id? }` (requiere `use_paid_providers`: el circuito llama a Claude y cuesta dinero; la PWA pide confirmación). Encola la preparación del próximo hueco sin pieza abierta en los próximos siete días: 202 `{ slot_date: "AAAA-MM-DD", job: { id, owner_id, agent, task, execute, mode, status, result_status, error, created_at, started_at, finished_at } }`. Con un `request_id` ya usado devuelve 200 con el mismo trabajo o 409 si ya no corresponde; nunca encola una segunda preparación. 409 si LinkedIn no está conectado, si la publicación está en pausa o desactivada (`LIVE_LINKEDIN_OFFICIAL`) o si no hay hueco.

**Vetar** una pieza es rechazar su acción antes de la hora: `POST /api/v1/operador/actions/<action.id>/reject` con `{ note }` (sesión humana y `approve_actions`). Solo vale con la acción en `proposed` o `approved`; si ya se está ejecutando, 409. El día queda sin publicación (`status: "vetoed"`).

Las notificaciones de piezas (lista, bloqueada, descartada, publicada) abren `/editorial/<id>`; la PWA redirige esa ruta a `/contenido/<id>`.

## LinkedIn oficial

Fuente: `agentes-linkedin/infra/src/team_backend/linkedin_views.py` y `connectors_linkedin.status_payload()`.

GET `/api/v1/linkedin/status` (permiso `operate_linkedin`). Nunca incluye el token:
```json
{ "configured": true, "live": false, "api_version": "202610|null", "scopes_required": ["openid", "profile", "w_member_social"],
  "connected": true, "member_urn": "urn:li:person:…|null", "member_name": "…|null", "scopes": ["openid", "profile", "w_member_social"],
  "expires_at": "ISO|null", "days_left": 59, "expired": false, "expiring_soon": false,
  "account": { "id": "uuid", "paused": false, "paused_reason": "" } | null, "connected_at": "ISO" }
```
`connected_at` solo aparece cuando hay credencial. `connected` es falso con el token caducado (`expired: true`); `expiring_soon` se activa siete días antes de caducar. `live: false` significa que el servidor no publica nada (`LIVE_LINKEDIN_OFFICIAL=false`).

GET `/api/v1/linkedin/oauth/start`: **navegación completa** del navegador (un enlace, nunca `fetch`). Exige sesión humana (con Bearer, 403) y `approve_actions`. Guarda un `state` de un solo uso y válido diez minutos y responde 302 a LinkedIn con `scope=openid profile w_member_social`; si la app de LinkedIn no está configurada responde 503 `{ detail }`. La PWA solo ofrece el botón si `configured` es cierto y el usuario tiene `approve_actions`.

GET `/api/v1/linkedin/oauth/callback`: lo llama LinkedIn. Como la cookie de sesión es `SameSite=Strict`, la primera llegada rebota una vez por una página mínima del mismo sitio. Termina con 302 a `/ajustes?linkedin=ok` o a `/ajustes?linkedin=error&motivo=…`:

| `motivo` | Qué pasó |
| --- | --- |
| `sesion` | La sesión no volvió con la redirección o había caducado. |
| `permiso` | El usuario no tiene `approve_actions`. |
| `state` | `state` ausente, falsificado, caducado (10 min) o ya usado. |
| `denegado` | Gustavo canceló o denegó la autorización en LinkedIn. |
| `code` | Falta el `code` o es inválido. |
| `scope` | LinkedIn no concedió `w_member_social`; no se guarda nada. |
| `canje` | Falló el canje del código o la lectura de `/v2/userinfo`. |

La PWA muestra un mensaje en español para cada motivo y quita `linkedin` y `motivo` de la URL.

## Red (crecer la red)

Fuente del bloque: DESC-02/05/07 y RED-01/02/03/04/09. La máquina descubre a quien comenta en los posts de los referentes y a quien sale en búsquedas por palabras clave, clasifica a cada candidato con un modelo y propone seguirlo, invitarlo sin nota o aceptar su invitación. Toda acción pasa por el flujo de siempre (propuesta → aprobación → ejecución). En el modo de ensayo, cada capacidad está en `approval` y espera a Gustavo en `/acciones`.

### Acciones de red

| Código | Etiqueta en la PWA | `payload` | Objetivo |
| --- | --- | --- | --- |
| `RED-01` | Seguir | `{ "user_id": "ACo…" }` | `contact` |
| `RED-02` | Invitación sin nota | `{ "user_id": "ACo…" }` | `contact` |
| `RED-04` | Aceptar invitación | `{ "request_id": "…", "user_id": "ACo…" }` | `contact` |

En estas acciones, `post` y `piece_id` son **siempre `null`**. Se aprueban, vetan y resuelven con las rutas de siempre (`/api/v1/operador/actions/<id>/approve|reject|resolve`), con `expected_hash` al aprobar. Si Gustavo veta una acción de red, el contacto pasa a `discarded` y no vuelve a proponerse; la PWA lo avisa en el diálogo del veto.

`ActionOutput` añade `contact`, que es `null` en INT-* y CONT-09:
```json
"contact": { "id": "uuid", "display_name": "…", "headline": "…", "profile_url": "https://www.linkedin.com/in/…", "public_identifier": "…",
             "network_distance": "FIRST_DEGREE|SECOND_DEGREE|THIRD_DEGREE|OUT_OF_NETWORK|", "stage": "fit", "source": "commenter",
             "evidence": { "post_id": "uuid|null", "post_url": "https://…|null", "referent": "…|null", "comment": "…|null",
                           "query": "…|null", "invitation_message": "…|null" },
             "classification": { "fit": true, "role": "comprador", "modality": "projectapp", "affinity": "desconocida",
                                 "reason": "…", "confidence": 0.8, "model": "…", "classified_at": "ISO" } }
```

`GET /api/v1/operador/actions?capability=RED-01` filtra por capacidad. La PWA la sigue filtrando también en cliente (`/acciones?capacidad=seguimientos|invitaciones|invitaciones-recibidas`). En `/acciones`, una acción de red muestra la persona (nombre enlazado al perfil en otra pestaña, titular, grado y origen; si comentó, el referente y un extracto del comentario), su clasificación (rol, modalidad y motivo), la acción propuesta y la justificación del agente.

### Contactos

`GET /api/v1/red/contacts?stage=&source=&account=` (permiso `operate_linkedin`) devuelve una lista paginada, ordenada por `updated_at` descendente. `GET /api/v1/red/contacts/<id>` devuelve un contacto. Cada contacto (`ContactOutput`) tiene esta forma:
```text
{ "id": "uuid", "account_id": "uuid", "provider_user_id": "ACo…", "public_identifier": "…", "display_name": "…",
  "headline": "…", "profile_url": "https://www.linkedin.com/in/…", "location": "…",
  "source": "commenter|search|incoming|manual",
  "evidence": { "post_id", "post_url", "referent", "comment", "query", "invitation_message" },
  "network_distance": "FIRST_DEGREE|SECOND_DEGREE|THIRD_DEGREE|OUT_OF_NETWORK|", "is_following": false,
  "stage": "candidate|fit|discarded|followed|invited|connected|closed|incoming",
  "classification": {} | { "fit", "role", "modality", "affinity", "reason", "confidence", "model", "classified_at" },
  "history": [ { "at": "ISO", "event": "discovered|classified|followed|invited|connected|closed|discarded|rejected|incoming|note", "detail": "…" } ],
  "followed_at": "ISO|null", "invited_at": "ISO|null", "connected_at": "ISO|null", "discovered_at": "ISO", "updated_at": "ISO",
  "open_action": { "id": "uuid", "capability": "RED-01", "state": "proposed" } | null }
```

`classification` vale `{}` mientras no se haya clasificado (la PWA muestra «Sin clasificar todavía»). En `evidence`, el campo que no corresponde a su `source` llega `null`.

| `stage` | Etiqueta en la PWA | Significado |
| --- | --- | --- |
| `candidate` | Por clasificar | Descubierto; pendiente de clasificar. |
| `fit` | Encaja | Encaja; se propondrá seguirlo. |
| `discarded` | Descartado | No encaja o Gustavo lo descartó; no se vuelve a proponer. |
| `followed` | Seguido | Seguido; se espera al menos 48 h antes de invitar. |
| `invited` | Invitado | Invitación sin nota enviada. |
| `connected` | Conectado | Conexión de primer grado. |
| `closed` | Cerrado | Invitación ignorada o retirada; no se reinvita sin Gustavo. |
| `incoming` | Te invitó | Te invitó; se aceptará si encaja. |

Valores que muestra la PWA:
- `role`: `par` → Par, `recomendador` → Recomendador, `lider` → Líder, `comprador` → Comprador, `divulgador` → Divulgador, `aliado` → Aliado.
- `modality`: `personal_startups` → «Startups (personal)», `projectapp` → «ProjectApp», `alianzas` → «Alianzas», `comunidad_autoridad` → «Comunidad». Son las modalidades de la red; el calendario editorial usa las suyas (`comunidad`, «Personal · startups»).
- `affinity`: `hispanohablante_declarada` → «Hispanohablante (declarado)», `otra` → «Otra», `desconocida` → «Sin dato».
- `source`: `commenter` → «Comentó en un post de <referent>», `search` → «Búsqueda: <query>», `incoming` → «Te invitó», `manual` → «Añadido a mano».
- `network_distance`: «1.er grado», «2.º grado», «3.er grado», «Fuera de tu red»; vacío no se muestra.
- `confidence` (0 a 1) se muestra como porcentaje entero.

POST `/api/v1/red/contacts/<id>/discard` con `{ note }`, nota obligatoria. Requiere sesión humana con CSRF y el permiso `approve_actions`. Pone el contacto en `discarded`, veta su acción abierta si la tiene y devuelve `ContactOutput`. Responde 409 si el contacto ya está en `connected`, `invited`, `closed` o `discarded`; por eso la PWA solo ofrece «Descartar» en `candidate`, `fit`, `followed` e `incoming`.

### Resumen

GET `/api/v1/red/summary` (permiso `operate_linkedin`):
```json
{ "enabled": true,
  "stages": { "candidate": 3, "fit": 5, "discarded": 9, "followed": 2, "invited": 1, "connected": 0, "closed": 0, "incoming": 1 },
  "capacity": { "RED-01": { "daily": 10, "daily_used": 2, "weekly": 40, "weekly_used": 6, "left": 8, "mode": "approval" },
                "RED-02": { "…": "…" }, "RED-04": { "…": "…" } },
  "reads_today": { "comments": 4, "search": 1, "profile": 7, "sync": 1 },
  "read_caps": { "comments": 60, "search": 20, "profile": 30, "sync": 4 },
  "llm": { "spent_today": 0.04, "daily": 0.3, "model": "…" },
  "invites_blocked": { "blocked": false, "reason": "" },
  "last_discovery_at": "ISO|null", "last_sync_at": "ISO|null" }
```

- `mode` es el modo de autonomía de la capacidad: `auto`, `approval` u `off` (la PWA muestra «Modo auto», «Modo aprobación» o «Modo apagado»).
- `llm` llega en números JSON, no en cadenas decimales como el gasto del overview.
- `invites_blocked.blocked=true` significa que LinkedIn rechazó invitaciones por límite en los últimos 7 días y que las invitaciones están en pausa. La PWA lo avisa siempre, con `reason`.
- `enabled=false` significa que el bloque está apagado (`NETWORK_ENABLED=false`). La PWA lo avisa y sigue mostrando lo guardado.

La pantalla `/red` muestra el resumen (capacidad de hoy con su modo, lecturas frente a sus topes, gasto del modelo frente a su presupuesto y avisos) y la lista de contactos, filtrable por etapa (`/red?etapa=fit`) con fichas que llevan el recuento de cada etapa. Cada contacto enseña su clasificación, su evidencia, los tres últimos eventos del historial, su acción abierta (enlazada a `/acciones` con su estado y capacidad) y, cuando corresponde, «Descartar».

### Trabajos y roles (escena de la oficina)

Hay cuatro trabajos nuevos (`Job.kind`). Sus roles se derivan en `/api/v1/oficina/actividad`, sin cambios en la PWA:

| Trabajo | Rol |
| --- | --- |
| `discover_network` | `investigador_referentes` |
| `classify_contacts` | `investigador_referentes` |
| `plan_network` | `relaciones_comunidad` |
| `sync_network` | `relaciones_comunidad` |

## Oficina (escena)

GET `/api/v1/oficina/actividad`:
```json
{ "updated_at": "ISO",
  "roles": { "<role_id>": { "status": "trabajando|en_espera|diseno", "detail": "texto corto", "since": "ISO|null" } } }
```

Los 16 `role_id`, agrupados por equipo:
- **Estrategia y perfil:** `posicionamiento`, `perfil`.
- **Observatorio:** `investigador_referentes`, `analista_barrio_resultados`.
- **Mesa editorial:** `director_editorial`, `copywriter_a`, `copywriter_b`.
- **El barrio (lectores):** `lector_comprador`, `lector_recomendador`, `lector_divulgador`, `lector_lider`, `lector_par`.
- **Revisión:** `editor_verificador`.
- **Relaciones (nuevo):** `relaciones_comunidad`, `conversaciones_inbox`.
- **Operación (nuevo):** `operador_cuenta`, que es un servicio y no un agente de IA.

El estado `diseno` significa que el rol tiene contrato pero aún no está implementado. Nunca se simula actividad.

## Notificaciones push (Web Push con VAPID)

| Método y ruta | Cuerpo | Respuesta |
| --- | --- | --- |
| GET `/api/v1/push/key` | — | `{ public_key }` en base64url, para `applicationServerKey`. |
| POST `/api/v1/push/subscriptions` | `PushSubscription.toJSON()` = `{ endpoint, keys: { p256dh, auth } }` | 201 o 200 |
| POST `/api/v1/push/unsubscribe` | `{ endpoint }` | 204 |
| POST `/api/v1/push/test` | — | 202, y envía una notificación de prueba a las suscripciones del usuario. |

El payload de cada push es JSON `{ title, body, url, tag }`. El service worker muestra la notificación y, al tocarla, abre o enfoca `url` (por ejemplo `/maquina`, `/acciones?state=uncertain`, `/editorial/<id>` o `/ajustes` cuando LinkedIn caduca pronto).

## Conocimiento y memoria (rutas existentes)

- `POST /api/v1/search` con `{ query, limit: 1-20, mode: "lexical" }` responde `{ results: [{ id, title, session, score, channels }], relations, warnings }`. El modo `hybrid` cuesta dinero: no se ofrece en la interfaz.
- `GET /api/v1/units/<id>` devuelve la unidad original con `sources`. `GET /api/v1/sources/<clase:clave>` devuelve la evidencia.
- `GET /api/v1/memory` devuelve una lista de `{ id, namespace, key, version, value, status, author, evidence, created_at }`.
- `POST /api/v1/memory/proposals` con `{ namespace: "user", key, value, evidence, expected_version }`.
- `POST /api/v1/memory/<id>/confirm` con `{ expected_version }`, que requiere sesión humana.
- `POST /api/v1/runs` con `{ agent: "posicionamiento|perfil", task, execute: false, mode: "lexical" }` responde 202 con un trabajo. `GET /api/v1/runs/<id>` devuelve el trabajo con `result.payload`, que es una vista previa con contexto. Ejecutar con IA (`execute: true`) cuesta dinero y solo se ofrece con una confirmación explícita.

## Resultados

Fuente: `agentes-linkedin/infra/src/team_backend/resultados.py` y `docs/metricas-resultados.md`, donde están el ejemplo completo y las fuentes. Es solo lectura, con el permiso `operate_linkedin`.

GET `/api/v1/resultados?dias=7|28|90&modalidad=todo|personal_startups|projectapp`
- Por defecto, `dias=28` y `modalidad=todo`. Otro valor devuelve 400.
- `modalidad` filtra solo las secciones 1 y 2 (por `classification.modality`). Seguidores, conexiones y visitas son de toda la cuenta.

```json
{ "periodo": { "desde": "AAAA-MM-DD", "hasta": "AAAA-MM-DD", "dias": 28, "datos_hasta": "ISO",
               "anterior": { "desde": "AAAA-MM-DD", "hasta": "AAAA-MM-DD" } },
  "modalidad": "todo", "zona_horaria": "America/Bogota",
  "negocio": { "disponible": false, "motivo": "Mediremos oportunidades cuando registres la primera o conectemos el inbox", "inbound": KPI },
  "audiencia": { "followers": KPI, "connections": KPI, "profile_views": KPI, "new_fit_connections": KPI,
                 "roles": { "items": [{ "role", "value" }] | null, "definition", "unavailable_reason" },
                 "acceptance_rate": KPI, "funnel": { "stages": { "<etapa>": n }, "order": [...], "aside": [...], "definition" },
                 "recurrent_people": KPI },
  "contenido": { "kpis": { "median_impressions": KPI, "engagement_pct": KPI, "substantive_comments": KPI, "consistency": KPI },
                 "chart": { "bars": [{ "piece_id", "date", "impressions", "cut": "7d|24h|null", "fallback" }],
                            "median_previous_4_weeks": { "7d", "24h" }, "definition" },
                 "best_post": { "piece_id", "first_line", "date", "pillar", "impressions", "engagement_pct", "cut" } | null,
                 "by_pillar": { "cut", "formula", "items": [{ "pillar", "value", "posts" }] },
                 "posts": [{ "piece_id", "date", "published_at", "first_line", "pillar", "url", "impressions_24h", "impressions_7d",
                             "reactions", "comments", "reposts", "engagement_pct", "cut", "commenters_by_role": { "<rol>": n } | null }] },
  "equipo": { "comments_published": KPI, "comments_replied": KPI, "follows": KPI, "invites": KPI, "accepts": KPI,
              "pieces_published": KPI, "pieces_blocked": KPI, "pieces_vetoed": KPI,
              "spend": { "today": { "general|editorial|network": { "spent", "budget" }, "other": { "spent", "budget": null } },
                         "month": { "general|editorial|network|other": { "spent", "budget": null }, "total": { "spent", "budget" } },
                         "accumulated": { "spent", "budget" }, "other_providers": { "<proveedor>": { "today", "month", "accumulated", "budget" } },
                         "month_start", "definition" } } }
```

Cada `KPI` tiene la forma `{ value, previous, delta, delta_pct, comparable, series: [{ date, value }] | null, definition, formula | null, unavailable_reason | null }`, y algunas fichas añaden campos:
- `numerator` y `denominator` en las proporciones;
- `cut`, `posts_measured` y `posts_total` en el contenido;
- `measured: { from, to }` en la audiencia;
- `window_days` en las visitas;
- `top` en `recurrent_people`.

Reglas para la PWA:
- **Sin dato.** `value: null` es «sin dato»: la ficha muestra un guion largo y `unavailable_reason`, nunca 0. Una proporción con denominador 0 o ausente también llega en `null`, con su motivo.
- **Variación.** `delta` y `delta_pct` solo llegan con `comparable: true`, es decir, cuando los dos periodos tienen dato y el anterior quedó cubierto entero por su fuente. Si no, la variación va en gris: «sin comparación».
  - `delta_pct` está en % con un decimal y es `null` si el valor anterior es 0.
  - En las fichas en %, `delta` va en puntos porcentuales.
- **Contenido.** Se compara a la misma edad: `cut` vale `7d`, o `24h` mientras ningún post del periodo cumpla 7 días. En `chart.bars`, `fallback: true` marca un post que aún no cumple 7 días y se pinta con sus impresiones a 24 h.
- **Gasto.** `spend` llega en números JSON. `ANTHROPIC_LIMIT_USD` (el `budget` de `month.total` y de `accumulated`) es un techo **acumulado** sobre todo el ledger, no mensual.
- **Oportunidades.** Mientras `negocio.disponible` sea `false`, la sección 1 muestra un único bloque con `motivo` y la ficha de inbound.

**Detalle de una pieza.** `GET /api/v1/editorial/pieces/<id>` añade dos campos:
- `snapshots: [{ kind: "24h|72h|7d", impressions, reactions, comments, reposts, engagement_pct, captured_at, age_hours }]`;
- `commenters: [{ provider_user_id, name, substantive, role, fit }] | null`, que es `null` si los comentarios nunca se leyeron.

`metrics` sí se serializa: lleva los últimos valores leídos (`impressions`, `reactions`, `comments`, `reposts`, `observed_at`, `source`, `unipile_post_id` y `share_url`).

Hay un trabajo nuevo, `collect_metrics`, que el autopiloto encola más o menos cada `METRICS_EVERY_MINUTES`. No tiene rol en la escena de la oficina.


## Rediseño (DISENO-VISTAS.md): Tu turno, Calendario, Personas, Ajustes

Detalle y semántica en `agentes-linkedin/infra/docs/rediseno-backend.md`. Las escrituras requieren sesión humana con CSRF; un token de servicio recibe 403. Las horas son ISO en UTC; los días del calendario se calculan en `America/Bogota`.

### Tu turno

**`GET /api/v1/tu-turno`**

```json
{ "count": 4, "critical": true, "counts": { "avisos": 2, "preguntas": 2, "tareas": 0 },
  "top": Card | null,
  "alerts": [Card], "questions": [Card], "later": [Card],
  "tasks": { "perfil": [], "conversaciones": [] },
  "recent": [{ "kind": "question | alert", "id": "…", "title": "…", "at": "iso", "how": "Respondida | No quisiste compartirla | Confirmaste que se aplicó | Reconectado | Reanudada" }],
  "summary": { "done_today": { "posts": 1, "comments": 6, "reactions": 3, "follows": 4, "invites": 2, "accepts": 0 }, "next_piece": { "id": "uuid", "scheduled_for": "iso" } | null } }
```

- **Contador.** `count` suma avisos, preguntas pendientes y tareas.
  - No cuenta las preguntas pospuestas ni las vencidas: esas van en `later`, con tono `muted`.
  - `critical` indica si hay algún aviso crítico, para pintar el contador en rojo.
- **`top`.** Es el elemento más urgente, para la tarjeta de la Oficina. Va en este orden: avisos críticos, luego los demás avisos, luego preguntas por plazo.
- **`Card`:**

```json
{ "id": "linkedin_expired | linkedin_expiring | uncertain:<proposal_id> | machine_paused | machine_paused_env | account_paused:<id> | question:<id>",
  "type": "aviso | pregunta | perfil | conversacion", "critical": true, "tone": "bad | warn | info | ok | muted",
  "agent": "operador_cuenta | director_editorial | …", "agent_label": "Operador de cuenta", "title": "¿Salió o no?",
  "body": "…", "deadline": "iso" | null, "created_at": "iso" | null,
  "actions": [{ "label": "Sí, se aplicó", "endpoint": "/api/v1/operador/actions/<id>/resolve", "body": { "outcome": "confirmed" }, "note_required": true, "primary": true }
              | { "label": "Reconectar LinkedIn", "href": "/api/v1/linkedin/oauth/start", "primary": true }],
  "attempt": { "capability": "INT-03", "label": "Comentario", "text": "…", "reaction": null,
               "target": { "kind": "post | person | own", "name": "…", "url": "…" }, "at": "iso", "url": "…" },
  "question": QuestionOutput }
```

- `attempt` solo viene en avisos `uncertain`; `question`, solo en las preguntas.
- **Al ejecutar una acción,** se envía su `body` más `note` cuando `note_required`. «Reanudar» la máquina es `POST /api/v1/operador/control {"paused": false}`, con `reason` opcional.
- **Los avisos informativos no entran aquí:** invitaciones limitadas por LinkedIn, piezas bloqueadas o presupuesto. Están en Personas (`red/summary.invites_blocked`), en el Calendario y en Ajustes.

**Preguntas del equipo**
- `GET /api/v1/preguntas?state=open|answered|declined` devuelve una lista paginada de `QuestionOutput`:

```json
{ "id": "uuid", "kind": "ask | confirm", "agent": "director_editorial", "agent_label": "Director editorial",
  "question": "¿Has liderado la migración de un monolito a microservicios?", "purpose": "Para el post del jueves…",
  "answer_type": "text | yes_no | choice | number | date", "options": ["Tiempo completo", "Parcial"],
  "memory_key": "experiencia.migracion", "proposed_value": { "texto": "…", "uso_publico": true }, "suggested_public": true,
  "deadline": "iso" | null, "postponed_until": "iso" | null, "pending": true, "expired": false,
  "origin": "piece:<id> | memoria", "state": "open", "answer": "", "public_use": null, "answered_at": null, "created_at": "iso" }
```

- `POST /api/v1/preguntas/<id>/responder` recibe `{ "text": "…", "value": "si | no | <opción> | <número> | AAAA-MM-DD", "public_use": true|false|null, "accept": false }`.

  | `answer_type` | Campos |
  | --- | --- |
  | `text` | `text` |
  | `yes_no` | `value` (si o no) y `text` opcional como detalle |
  | `choice` | `value` (una de `options`) y `text` opcional |
  | `number` y `date` | `value` |

  En `kind=confirm`, `{ "accept": true }` confirma el dato propuesto y `text` lo corrige. Responde 400 si el valor no es válido y 409 si la pregunta ya no está abierta.
- `POST /api/v1/preguntas/<id>/deshacer`: dentro de los 15 minutos siguientes a responder, devuelve la memoria a su estado anterior y reabre la pregunta (409 después).
- `POST /api/v1/preguntas/<id>/mas-tarde`: la pospone 3 días y la saca del contador.
- `POST /api/v1/preguntas/<id>/no-compartir`: cierra la clave para siempre.

**Lo que el equipo sabe de ti**
- `GET /api/v1/memoria/hechos`:

```json
[{ "key": "experiencia.primer_cliente_ia", "topic": "¿Cuál fue tu primer cliente con IA?", "text": "…", "public_use": true,
   "version": 4, "edits": 2, "origin": { "kind": "question | manual | memoria", "agent": "director_editorial", "agent_label": "Director editorial", "question": "…" },
   "updated_at": "iso" }]
```

- `edits` es el número de versión que se muestra: v2 significa que se editó una vez.
- `POST /api/v1/memoria/hechos` recibe `{ "text": "…", "public_use": false, "topic": "Límites" }`: «Añadir algo que quieras que sepan». Se confirma directamente y responde 201 con la lista.
- `POST /api/v1/memoria/hechos/<key>/corregir` recibe `{ "text": "…", "public_use": true }`.
- `POST /api/v1/memoria/hechos/<key>/retirar` recibe `{ "reason": "…" }`.

**Orientación**
- `GET /api/v1/orientacion` devuelve `{ "text", "updated_at", "updated_by" }`.
- `PUT /api/v1/orientacion` recibe `{ "text" }`, de 4000 caracteres como máximo.

### Calendario

**`GET /api/v1/calendario?desde=AAAA-MM-DD&hasta=AAAA-MM-DD`**. Por defecto cubre el mes en curso; el máximo es de 93 días. Un rango inválido devuelve 400.

```json
{ "timezone": "America/Bogota", "today": "2026-11-07", "lead_hours": 12,
  "layers": { "tuyo": true, "publicaciones": true, "red": true, "conversaciones": "parcial", "sistema": true },
  "days": [{ "date": "2026-11-07",
             "counts": { "comments": 6, "reactions": 3, "follows": 4, "invites": 2, "accepts": 0, "connections_fit": 1 },
             "events": [{ "id": "…", "layer": "tuyo | publicaciones | red | conversaciones | sistema", "kind": "…", "at": "iso" | null,
                          "title": "…", "state": "…" | null, "important": true, "link": "/calendario/pieza/<id> | /personas/<id> | /tu-turno | …" | null,
                          "people": [{ "id": "uuid", "name": "…", "role": "par" }], "impressions": 1200, "skip_reason": "…", "estimate": true }] }] }
```

- `kind` por capa:

  | Capa | Valores de `kind` |
  | --- | --- |
  | `publicaciones` | `piece_published`, `piece_scheduled`, `piece_preparing`, `piece_skipped`, `piece_blocked`, `piece_failed`, `piece_uncertain`, `piece_vetoed`, `piece_discarded` y `piece_publishing` |
  | `red` | `connection_fit` (agrupado, con `people`), `invitation_received`, `invitation_accepted` e `invite_expected` (estimación, `important:false`, con `people`) |
  | `tuyo` | `deadline` (plazo de una pregunta), `meeting` y `opportunity_next` (siguiente acción de una oportunidad), `linkedin_expiry` y `resolved` (`important:false`) |
  | `conversaciones` | `opportunity` (creada o que cambia de etapa; el inbox llega después) |
  | `sistema` | `machine_paused`, `machine_resumed`, `account_paused`, `action_uncertain`, `action_failed` y `linkedin_expired` |

- Los eventos llegan ordenados por prioridad de capa (Tuyo > Sistema > Publicaciones > Conversaciones > Red) y luego por hora.

**Vista Lista, «Próximo» y «Ver todo lo del día»**
- La ruta es `GET /api/v1/actividad`. Parámetros:

  | Parámetro | Valores |
  | --- | --- |
  | `tipo` | `todo`, `publicaciones`, `comentarios`, `reacciones` o `red` |
  | `desde` y `hasta` | AAAA-MM-DD |
  | `no_salio` | `1` muestra también lo vetado, descartado, caducado o sustituido |
  | `limit` y `offset` | paginación |

- Respuesta:

```json
{ "upcoming": { "pieces": [{ "piece_id": "uuid", "slot_date": "2026-11-08", "scheduled_for": "iso", "status": "scheduled | preparing | publishing | awaiting_approval",
                             "stage": "director | redactor | lectores | seleccion | verificador", "thesis": "…", "excerpt": "3 primeras líneas",
                             "pillar": "applied_ai", "modality": "projectapp", "primary_reader": "lector_comprador",
                             "action": { "id": "uuid", "state": "approved" } | null, "vetoable": true, "impressions": null, "skip_reason": null, "note": "" }],
                "queued": [Item + { "expected_at": "iso" }] },
  "items": [Item], "next_offset": 50 | null }
```

- `Item`:

```json
{ "id": "uuid", "capability": "INT-03", "label": "Comentario", "agent": "relaciones_comunidad", "state": "confirmed",
  "state_label": null | "En curso" | "Incierta" | "Fallida" | "Vetada por ti" | "Descartada por la política" | "Caducada" | "Sustituida",
  "important": false, "at": "iso", "date": "2026-11-07", "text": "…" | null, "reaction": "linkedin_like" | null,
  "target": { "kind": "post | person | own", "name": "…", "headline": "…", "url": "…", "post_excerpt": "…", "contact_id": "uuid", "role": "par" },
  "url": "enlace en LinkedIn", "rationale": "…", "decided_by": "gustavo | lider | politica | null", "decision_note": "…",
  "execution_note": "…", "review": { "decision": "approve | discard", "answers": { "aporta": 0.92 }, "reasons": [], "model": "jev-1.14.0" }, "piece_id": "uuid" | null }
```

- Un `tipo` desconocido devuelve 404.
- Vetar una pieza o una acción en cola es `POST /api/v1/operador/actions/<id>/reject {"note"}`. En una acción de red, descarta a la persona.

### Personas

- **`GET /api/v1/red/contacts`.** Además de `stage` y `source`, admite:
  - `stage=opportunity`, que filtra por las personas con una oportunidad abierta;
  - `q` (nombre o titular), `role` y `modality`.
- **Campos nuevos de `ContactOutput`:**

```json
{ "display_stage": "candidate | fit | followed | invited | connected | incoming | closed | discarded | opportunity",
  "notes": [{ "id": "…", "at": "iso", "text": "…", "by": "gustavo" }],
  "opportunity": { "id": "uuid", "stage": "reunion", "stage_label": "Reunión", "modality": "projectapp", "next_action": "…", "next_action_at": "iso" } | null,
  "next_step": { "owner": "equipo | gustavo | null", "text": "El equipo la invitará cuando termine la espera", "at": "iso" | null,
                 "action": { "id": "uuid", "capability": "RED-02", "state": "approved" } },
  "your_turn": false, "last_event": { "at": "iso", "event": "followed", "detail": "…" } | null }
```

- **`POST /api/v1/red/contacts/<id>/notas`** recibe `{ "text" }`, añade una nota y devuelve el contacto (201).
- **`GET /api/v1/red/summary`.** `stages` añade `opportunity` (número) y `conversation` (`null` hasta que llegue el inbox).
- **Oportunidades.** `GET /api/v1/oportunidades?stage=&modality=&contact=` devuelve una lista paginada de `OpportunityOutput`:

```json
{ "id": "uuid", "person": "Laura Gómez", "contact": { "id": "uuid", "display_name": "…", "headline": "…", "profile_url": "…", "stage": "connected", "role": "comprador" } | null,
  "person_name": "", "company": "Retail SAS", "modality": "personal_startups | projectapp | por_clasificar",
  "channel": "linkedin | email | llamada | evento | otro",
  "stage": "conversacion | necesidad | cualificada | reunion | propuesta | acuerdo | sin_acuerdo",
  "attribution": "cito_contenido | lo_dijo | inferido | desconocido", "need": "…", "budget": "…", "dedication": "…",
  "next_action": "…", "next_action_at": "iso" | null, "notes": "…", "history": [{ "at": "iso", "event": "created | stage", "detail": "Conversación → Reunión" }],
  "days_in_stage": 3, "created_at": "iso", "updated_at": "iso", "stage_changed_at": "iso", "closed_at": "iso" | null }
```

- **Escrituras de oportunidades:**
  - `POST /api/v1/oportunidades` exige `modality` y además `contact` o `person_name` (400 si falta la persona).
  - `PATCH /api/v1/oportunidades/<id>` acepta cualquier campo del formulario.
  - `DELETE /api/v1/oportunidades/<id>` devuelve 204.
- **Referentes:**
  - `ReferentOutput` añade `contacts_count`: las personas del barrio que salieron de sus posts.
  - `PATCH /api/v1/operador/referents/<id>` recibe `{ "active": false, "reason": "…" }` para desactivar, reactivar o cambiar el motivo.
  - `DELETE /api/v1/operador/referents/<id>` lo quita y devuelve 204.

### Ajustes

**`GET /api/v1/ajustes`**

```json
{ "autonomy": { "INT-03": "auto", "INT-02": "auto", "CONT-09": "auto", "RED-01": "auto", "RED-02": "auto", "RED-04": "auto" },
  "lead": { "enabled": true, "capabilities": ["INT-03","CONT-09","RED-01","RED-02","RED-04"], "model": "jev-1.14.0" },
  "limits": { "INT-03": { "daily": 3, "weekly": 12 } },
  "window": { "start": "07:00", "end": "21:00", "timezone": "America/Bogota", "open_now": true, "min_spacing_seconds": 1200 },
  "ai_spend": { "today": [{ "budget": "general | editorial | red", "label": "General (comentarios)", "spent_usd": 0.13, "limit_usd": 0.6 }],
                "month_usd": 4.2, "total_usd": 9.8, "limit_usd": 50, "lead_month_usd": 0.01 },
  "facts_count": 12, "orientation": { "text": "…", "updated_at": "iso", "updated_by": "gustavo" } }
```

### Notificaciones push

| Notificación | Destino |
| --- | --- |
| Pieza lista, publicada, bloqueada o descartada | `/calendario/pieza/<id>` |
| Acción incierta, cuenta en pausa, LinkedIn caduca pronto | `/tu-turno` |
| Pregunta nueva («{Rol} te pregunta: …») | `/tu-turno` |

## Captura y Galería

Backend: `agentes-linkedin/infra/docs/capturas-galeria.md`.
- **Escrituras:** exigen sesión humana con CSRF (`X-CSRFToken`) y el permiso `approve_actions`. Un token de servicio recibe 403.
- **Lecturas:** exigen `operate_linkedin`.
- **Archivos:** nunca son públicos. Se piden con la misma cookie de sesión (`<audio src>` e `<img src>` del mismo origen) y responden con `Cache-Control: private`.

### Enviar una captura

**`POST /api/v1/capturas`** (`multipart/form-data`). Todos los campos son opcionales, pero no puede ir vacía:

| Campo | Valor |
| --- | --- |
| `audio` | Un archivo de hasta 25 MB: webm/opus, mp4/m4a, ogg, mp3, aac, wav o flac. Se sube al guardar, no mientras se graba |
| `audio_duration_s` | La duración que midió la PWA, en segundos (≤ 1800). Sirve para reservar el coste de la transcripción |
| `fotos` | Varias partes con el mismo nombre, hasta 10 por envío y 10 MB cada una: JPEG, PNG, WebP o HEIC |
| `nota` | Texto, hasta 4.000 caracteres |
| `para` | `post` (Idea para un post), `dato` (Dato sobre mí), `respuesta` (Responde una pregunta) o `galeria` (Foto para la galería; exige fotos). Vacío: el equipo decide |
| `contexto_tipo` y `contexto_id` | `pregunta` (una `TeamQuestion` abierta), `persona` (un contacto) o `pieza` (una pieza editorial), con su `id` |
| `public_use` | `true` o `false`: la visibilidad elegida al responder una pregunta. Si no va, se usa la que sugiere la pregunta |

**Respuestas:**
- `201` con `CaptureOutput` en estado `recibida`; el trabajo `process_capture` queda encolado;
- `400` si va vacía o tiene un tipo, tamaño o contexto inválido;
- `409` si la pregunta ya no está abierta;
- `413` si el cuerpo es demasiado grande.

Tras el `201`, la PWA consulta `GET /api/v1/capturas/<id>` cada 2–3 s mientras el estado sea `recibida`, `transcribiendo` o `procesando`.

**`CaptureOutput`:**

```json
{ "id": "uuid", "created_at": "iso", "note": "Esto es para el post del jueves",
  "purpose": "post | dato | respuesta | galeria | null", "purpose_label": "Idea para un post | null",
  "team_decided": { "purpose": "post | dato | galeria", "label": "Dato sobre mí", "reason": "Cuenta una preferencia suya." } | null,
  "context": { "tipo": "pregunta | persona | pieza", "id": "uuid", "label": "¿Cuál fue tu primer agente en producción?" } | null,
  "has_audio": true, "audio_duration_s": 42.0, "audio_mime": "audio/webm", "audio_url": "/api/v1/capturas/<id>/audio" | null,
  "transcript": "Hoy en una llamada salió algo bueno…", "transcript_language": "es" | null,
  "state": "recibida | transcribiendo | procesando | dato_guardado | anotado | idea | usado | sin_usar | error | deshecha",
  "state_label": "Procesando",
  "outcome": { "kind": "procesando", "text": "Mesa editorial lo está leyendo", "link": null },
  "photos": [{ "id": "uuid", "url": "/api/v1/galeria/<id>/imagen" }],
  "error": null, "undo_until": "iso", "can_undo": true }
```

- `team_decided` aparece cuando Gustavo no eligió «Para qué es» y el equipo lo clasificó. `outcome.reason` repite el motivo.
- `audio_duration_s` pasa a ser la duración real cuando AssemblyAI termina.

**Estados y lo que muestra la tarjeta (`outcome.text`):**

| `state` | `state_label` | `outcome.text` | `outcome.link` |
| --- | --- | --- | --- |
| `recibida` | Recibida | El equipo lo recibió | — |
| `transcribiendo` | Transcribiendo | Transcribiendo el audio | — |
| `procesando` | Procesando | Mesa editorial lo está leyendo | — |
| `dato_guardado` | Dato guardado | Está en Lo que el equipo sabe de ti · Público/Privado | `/tu-turno/sabe` |
| `dato_guardado` (galería) | Dato guardado | Está en tu Galería | `/galeria` |
| `anotado` (persona) | Anotado | Quedó en las notas de Ana Founder | `/personas/<id>` |
| `anotado` (pieza) | Anotado | Quedó como comentario para el equipo en la pieza del jueves 12 | `/calendario/pieza/<id>` |
| `idea` | En la mesa editorial | Mesa editorial lo tendrá en cuenta | — |
| `usado` | Usado | El Director editorial lo usó en el brief del jueves 12 | `/calendario/pieza/<id>` |
| `sin_usar` | Sin usar | Pasaron 14 días sin que encajara en un brief | — |
| `error` | No se pudo procesar | No se pudo procesar (el detalle va en `error`) | — |
| `deshecha` | Deshecha | Deshiciste este envío | — |

### Historial, Deshacer y audio

- **`GET /api/v1/capturas?estado=`** es «Lo que enviaste». Devuelve una lista paginada (`{count, next, previous, results}`) de `CaptureOutput`, la más reciente primero, sin las deshechas.
- **`GET /api/v1/capturas/<id>`** devuelve una captura.
- **`DELETE /api/v1/capturas/<id>`** es «Deshacer». Solo funciona durante 2 minutos (`undo_until`); después devuelve `409`. Hace cuatro cosas:
  - cancela el trabajo si no había empezado;
  - revierte lo creado: reabre la pregunta, retira el dato o quita la nota de la persona;
  - borra el audio y las fotos;
  - devuelve `200` con la captura en `deshecha`.
- **`GET /api/v1/capturas/<id>/audio`** sirve el audio con su tipo y admite `Range` (206), así que funciona con `<audio>` en Safari.

### Galería

- **`GET /api/v1/galeria?filtro=todas|sin_usar|elegidas|publicadas`** devuelve una lista paginada de `PhotoOutput`, la más reciente primero. Un filtro desconocido da 400.
  - `sin_usar` incluye las nuevas.
  - `elegidas` incluye las editadas.
- **`POST /api/v1/galeria`** (`multipart`, varias partes `fotos`) devuelve `201` con la lista de fotos creadas.
- **`GET /api/v1/galeria/<id>`** devuelve una foto.
- **`PATCH /api/v1/galeria/<id>`** recibe `{ "note": "…", "allow_ai_edit": false }` (cualquiera de los dos) y devuelve la foto.
- **`DELETE /api/v1/galeria/<id>`** borra la foto y su archivo, y devuelve 204.
- **`GET /api/v1/galeria/<id>/imagen`** sirve la imagen.

**`PhotoOutput`:**

```json
{ "id": "uuid", "url": "/api/v1/galeria/<id>/imagen", "created_at": "iso",
  "state": "sin_usar | elegida | editada | publicada", "display_state": "nueva | sin_usar | elegida | editada | publicada",
  "label": "Elegida · dom 8", "tone": "info | muted | ok", "note": "Úsala en el post del domingo, la de la pizarra.",
  "allow_ai_edit": true, "used_in": { "piece_id": "uuid", "date": "2026-11-08", "text": "Elegida para el post del domingo 8" } | null,
  "capture_id": "uuid" | null, "mime": "image/jpeg", "size_bytes": 482113, "width": null, "height": null }
```

| `display_state` | `label` | `tone` |
| --- | --- | --- |
| `nueva` (sin usar y subida hace menos de 24 h) | Nueva | info |
| `sin_usar` | Sin usar | muted |
| `elegida` | Elegida · {día} | info |
| `editada` | Editada con IA | ok |
| `publicada` | Publicada · {fecha} | ok |

Si `used_in` es `null`, la hoja muestra «Todavía sin usar». Por ahora las piezas publican solo texto: los estados `elegida`, `editada` y `publicada` llegarán con la fase de imagen.

### Preferencias

- **`GET /api/v1/ajustes/preferencias`** devuelve `{ "gallery_ai_edit_default": true, "updated_at": "iso" | null }`.
- **`PATCH /api/v1/ajustes/preferencias`** recibe `{ "gallery_ai_edit_default": false }`. Es «El equipo puede editar mis fotos con IA», y cada foto nueva toma este valor por defecto.

### Cambios en rutas existentes

- **`GET /api/v1/editorial/pieces/<id>`** añade `team_comments`:

  ```json
  [{ "id": "uuid", "text": "…", "note": "…", "transcript": "…", "has_audio": true, "audio_url": "/api/v1/capturas/<id>/audio", "created_at": "iso", "by": "gustavo" }]
  ```

- **Notas de una persona.** Las que llegan por la captura llevan `"source": "captura"` y `"capture": "<id>"`.
- **`GET /api/v1/ajustes`.** `ai_spend` añade `transcription_month_usd` (AssemblyAI).
- **Escena.** El trabajo `process_capture` cuenta como `operador_cuenta` en `/api/v1/oficina/actividad`. Al rutear, `/api/v1/oficina/eventos` recibe una `entrega` desde `operador_cuenta` hacia quien recibe:
  - `director_editorial` para ideas, fotos y comentarios de pieza;
  - `posicionamiento` para los datos;
  - el agente que hizo la pregunta, para una respuesta;
  - `relaciones_comunidad` para las personas.

## Notificaciones y prioridades de Tu turno (rev 18)

Si solo Gustavo puede resolverlo, va a Tu turno; si no, va a Notificaciones, donde se guarda 7 días. La lógica está en `agentes-linkedin/infra/src/team_backend/notificaciones.py`.

**`GET /api/v1/tu-turno`** suma estos campos:

| Campo | Contenido |
| --- | --- |
| `priority` (en cada tarjeta) | `urgente` \| `importante` \| `cuando_puedas` |
| `state` (en cada tarjeta) | `nueva` \| `vista` \| `pospuesta` \| `caducada` |
| `items` | Todas las tarjetas activas, ordenadas por prioridad, luego por el plazo más cercano y luego por la más reciente |
| `later` | Las pospuestas y las caducadas |
| `count` | Las tarjetas en estado `nueva` o `vista` |
| `critical` | Si alguna tarjeta es urgente |
| `urgent_count` | Número de tarjetas urgentes |
| `notifications_unread` | Notificaciones sin leer |

Reglas de prioridad:
- **Urgente:** acción incierta, LinkedIn caducado y máquina detenida desde la app.
- **Importante:** LinkedIn caduca en 3 días o menos (antes de eso es Cuando puedas), cuenta en pausa y preguntas con plazo en menos de 48 h.
- **Cuando puedas:** el resto de las preguntas.
- **Parada desde el servidor:** ya no es una tarjeta, sino un elemento de `upcoming` en Notificaciones.

**`POST /api/v1/tu-turno/vistos`** recibe `{ "ids": ["<id de tarjeta>"] }` y devuelve `{ "seen": n }`. Pasa las tarjetas de Nueva a Vista.

**`GET /api/v1/notificaciones?filtro=todas|sin_leer`**

```json
{ "upcoming": [ { "id": "piece_scheduled:<piece>", "kind": "piece_scheduled | invites_expected | machine_paused_env", "layer": "publicaciones",
                  "title": "Sale la pieza «…»", "detail": "Puedes vetarla en el detalle hasta las 08:30.", "link": "/calendario/pieza/<id>", "at": "iso" } ],
  "items": [ { "id": "uuid", "kind": "piece_scheduled | piece_published | piece_blocked | piece_discarded | connection_fit | opportunity | observatory | capture_processed",
               "layer": "tuyo | publicaciones | red | conversaciones | sistema", "title": "…", "detail": "…", "link": "/…", "at": "iso", "read": false } ],
  "unread": 3 }
```

- Los elementos de `upcoming` se calculan en cada consulta y nunca cuentan como no leídos.
- `capture_processed` enlaza a `/?enviado=1`, que abre «Lo que enviaste».

**`POST /api/v1/notificaciones/leer`** recibe `{ "ids": [...] }` o `{ "todas": true }` y devuelve `{ "unread": n }`.

**Push.** `GET /api/v1/ajustes` suma `push_types: [{ kind, label, goes_to: "tu_turno" | "notificaciones", default, enabled }]`. `PATCH /api/v1/ajustes/preferencias` recibe `{ "push_disabled": ["kind", …] }`, opcionalmente junto con `gallery_ai_edit_default`, y responde 400 si hay un tipo desconocido o el cuerpo llega vacío. Las push de Tu turno llevan a `/tu-turno`; las de Notificaciones, a su `link`. Push activadas por defecto:

| Va a | Tipos con push |
| --- | --- |
| Tu turno | Todos |
| Notificaciones | `piece_scheduled`, `piece_published`, `piece_blocked` y `machine_paused_env` |

## Escena de la Oficina: feed de eventos

**`GET /api/v1/oficina/eventos?desde=<iso>`** (permiso `operate_linkedin`) devuelve los eventos de trabajo real que mueven a los personajes, del más antiguo al más reciente. Sin `desde`, trae los de los últimos 10 minutos; como máximo trae 50.

```json
{ "events": [ { "id": 812, "ts": "iso", "tipo": "consulta_biblioteca | entrega | publicacion",
                "rol": "copywriter_a", "destino": "biblioteca | <rol que recibe> | linkedin", "detalle": "Unidades del curso para la etapa redactor" } ],
  "now": "iso" }
```

Cada evento lo emite el backend en un momento concreto:

| Evento | Cuándo se emite |
| --- | --- |
| `consulta_biblioteca` | Antes de que una etapa editorial o el redactor de comentarios lea unidades del curso |
| `entrega` | Al terminar una etapa (director → copywriter_a → lector_comprador → director → verificador → operador), al redactar un comentario (relaciones → operador) y al enrutar una captura (operador → quien la recibe) |
| `publicacion` | Cuando LinkedIn confirma un post propio o un comentario |

Un `desde` inválido devuelve 400.
