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
  "accounts": [ { "id": "uuid", "label": "…", "provider": "unipile|fake", "status": "running|…", "is_locked": false,
                  "paused": false, "paused_reason": "", "last_checked_at": "ISO|null",
                  "capacity": { "INT-03": { "daily": 3, "weekly": 12, "daily_used": 1, "weekly_used": 4, "left": 2 },
                                "INT-02": { "…": "…" } } } ],
  "today": { "proposals": { "proposed": 0, "approved": 1, "discarded": 2, "confirmed": 1, "…": 0 },
             "llm_spent_usd": "0.42", "llm_daily_cap_usd": "1", "drafts": 3, "drafts_daily_cap": 6 },
  "counts": { "referents": 7, "posts": 31, "uncertain": 0 }
}
```

POST `/api/v1/operador/control` con `{ paused: bool, reason: string }`. Es la parada total de la máquina y requiere sesión humana. Responde con el objeto `control`. Si `OPERATOR_PAUSED=true` está en el entorno, la parada no se puede levantar desde la app: responde 409 con su explicación.

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

Cada acción tiene esta forma:
`{ id, capability: "INT-03|INT-02", payload: { text } | { reaction }, payload_hash, version, state, source: "agent|human", rationale, citations: [unitId], risks: [string], decision_note, decided_at, created_at, post: { id, author_name, text, share_url, posted_at }, execution: null | { state, external_id, external_url, note, http_status, started_at, finished_at } }`

Estados de una acción: `proposed`, `approved`, `rejected`, `superseded`, `discarded`, `executing`, `sent`, `confirmed`, `uncertain`, `failed` y `expired`.

Decisiones, todas con sesión humana:
- `POST /api/v1/operador/actions/<id>/reject` con `{ note }`: vetar una acción pendiente o aprobada.
- `POST /api/v1/operador/actions/<id>/approve` con `{ expected_hash, note }`: solo en capacidades configuradas en modo `approval`.
- `POST /api/v1/operador/actions/<id>/resolve` con `{ outcome: "confirmed|failed", note }`.
- `POST /api/v1/operador/actions/<id>/revise` con `{ payload }`.
- `POST /api/v1/operador/actions/<id>/reconcile`.

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

El payload de cada push es JSON `{ title, body, url, tag }`. El service worker muestra la notificación y, al tocarla, abre o enfoca `url` (por ejemplo `/maquina` o `/acciones?state=uncertain`).

## Conocimiento y memoria (rutas existentes)

- `POST /api/v1/search` con `{ query, limit: 1-20, mode: "lexical" }` responde `{ results: [{ id, title, session, score, channels }], relations, warnings }`. El modo `hybrid` cuesta dinero: no se ofrece en la interfaz.
- `GET /api/v1/units/<id>` devuelve la unidad original con `sources`. `GET /api/v1/sources/<clase:clave>` devuelve la evidencia.
- `GET /api/v1/memory` devuelve una lista de `{ id, namespace, key, version, value, status, author, evidence, created_at }`.
- `POST /api/v1/memory/proposals` con `{ namespace: "user", key, value, evidence, expected_version }`.
- `POST /api/v1/memory/<id>/confirm` con `{ expected_version }`, que requiere sesión humana.
- `POST /api/v1/runs` con `{ agent: "posicionamiento|perfil", task, execute: false, mode: "lexical" }` responde 202 con un trabajo. `GET /api/v1/runs/<id>` devuelve el trabajo con `result.payload`, que es una vista previa con contexto. Ejecutar con IA (`execute: true`) cuesta dinero y solo se ofrece con una confirmación explícita.
