# Métricas y Resultados

Este bloque responde a «¿vamos bien?» con datos reales de LinkedIn. Tiene dos partes:
- **Captura** (`src/team_backend/metricas.py`): cortes de cada post propio a las 24 h, 72 h y 7 días, y una foto diaria de la audiencia.
- **Resultados** (`resultados.py` y `resultados_views.py`): el endpoint `GET /api/v1/resultados` que alimenta la vista Resultados de la oficina (sección 4 de `DISENO-VISTAS.md`).

Sigue las reglas de [datos y resultados del equipo](datos-y-resultados-del-equipo.md): el backend calcula los números, `null` significa «sin dato» y nunca se muestra como 0, y cada proporción guarda su fórmula, su numerador y su denominador.

## Por qué

Antes, las impresiones de un post propio se guardaban una sola vez, segundos después de publicar (`operador._record_metrics`), así que casi siempre valían ~0. Los seguidores y las conexiones no se capturaban. Gustavo dirige desde los resultados, no aprobando acciones, y eso exige cortes comparables.

## Fuentes

Todo se lee con la cuenta Unipile (o su simulada en pruebas). La API oficial de LinkedIn (`w_member_social`) solo publica: no permite leer métricas.

| Dato | Llamada a Unipile v2 | Campo |
| --- | --- | --- |
| Impresiones de un post propio | `GET users/me/posts`, o `GET posts/{id}` cuando ya se conoce su id | `analytics.impressions_counter` |
| Reacciones | ídem | `reactions_counter`, una lista `[{reaction, count}]` que se suma |
| Comentarios | ídem | `comments_counter` |
| Republicaciones | ídem | `reposts_counter` (número, o `null` si LinkedIn lo oculta) |
| Quién comentó | `GET posts/{id}/comments` | autor, texto e `is_sender` |
| Seguidores y conexiones | `GET users/me` | `followers_count` y `relations_count`, en la raíz del perfil |
| Visitas al perfil | `GET linkedin/analytics/profile-views?date_range=N` | `analytics.views_count` |

**Comprobado contra la cuenta real el 2026-11-06**, con dos lecturas GET y mirando solo la forma de la respuesta:
- `GET users/me` devuelve `followers_count` y `relations_count` como enteros en la raíz, no dentro de `specifics`.
- `List Profile Views` funciona con la cuenta gratuita y devuelve `analytics.views_count` y `entities`. La documentación avisa de que sin Premium los datos son limitados y los filtros no funcionan; el recuento total sí llega.
- El esquema de un post (documentación de «Get a post») trae `reposts_counter`. No hay otro contador de compartidos.

## Captura

### Cortes por post (`PostMetric`)

- **Qué se mide.** Cada publicación CONT-09 confirmada (`ActionExecution` en `confirmed`).
- **Cuándo.** Recibe tres cortes, cuando su edad alcanza 24 h, 72 h y 7 días. La edad se cuenta desde la escritura (`ActionExecution.started_at`).
- **Cortes tardíos.** Llegar tarde está bien; perder un corte, no. Si la captura estuvo parada, la siguiente vuelta toma todos los cortes pendientes a la vez. `captured_at - published_at` deja ver el retraso.
- **Nunca dos veces.** La restricción única `(piece, kind)` impide capturar el mismo corte dos veces, aunque corran dos vueltas a la vez.
- **Cómo se encuentra el post.**
  - Primero por su id de Unipile, si una lectura anterior ya lo encontró. Ese id es opaco: no es el URN de la API oficial.
  - Si no, por el texto exacto entre los posts propios recientes, como hace la conciliación (`same_text`), descartando las republicaciones.
  - Si el post ya no aparece en la lista reciente pero su id es conocido, se lee por id. Así un corte de 7 días tardío no se pierde.
- **Quién comentó.** Cada captura lee una vez los comentarios del post; si se toman varios cortes a la vez, comparten esa lectura. Se guarda una lista compacta en `PostMetric.commenters`:
  - Una entrada por comentario: `provider_user_id`, `name`, `substantive` y `role`.
  - `substantive` es verdadero con al menos 80 caracteres normalizados, el mismo umbral que usa la red para descubrir gente.
  - `role` viene de `Contact.classification.role` si la persona ya es un contacto. Se añade también `fit`.
  - Las respuestas del propio Gustavo (`is_sender`) no cuentan.
  - Si la lectura falla, `commenters` queda en `null` («no leído»), nunca en `[]`.
- **Compatibilidad.** `EditorialPiece.metrics` guarda los últimos valores leídos de cada publicación reciente: `impressions`, `reactions`, `comments`, `reposts`, `observed_at`, `source`, `unipile_post_id` y `share_url`. Conserva las claves de antes.
- **Ventana.** Solo se leen publicaciones de los últimos `METRICS_MAX_AGE_DAYS` días (30 por defecto, y nunca menos de 8). Si un post no aparece en ese plazo, su corte queda sin dato.

### Audiencia diaria (`AudienceSnapshot`)

- Hay una foto por día local (`OPERATOR_TIMEZONE`) con `followers`, `connections`, `profile_views` y `profile_views_days`. Las tres métricas aceptan `null`.
- Las visitas son las que LinkedIn informa para una ventana móvil de `METRICS_PROFILE_VIEWS_DAYS` días, que puede ser 14, 28 (por defecto), 90 o 365. La ventana se guarda con el dato, y dos fotos con ventanas distintas no se comparan.
- Si LinkedIn rechaza las visitas, la foto se guarda igual con `profile_views=null`, y la cuenta no se pausa por eso.
- El crecimiento neto es la diferencia entre dos fotos. No dice cuántas altas y bajas hubo.

### Cadencia, topes y fallos

- **Encolado.** El autopiloto (`autopiloto._metrics`) encola `collect_metrics` más o menos cada `METRICS_EVERY_MINUTES` (180 por defecto; con 0 queda apagado).
  - Va de uno en uno, con id determinista por franja y el mismo patrón `_pending` que la red.
  - Solo encola si hay algo pendiente: un corte vencido sin capturar, o la foto de hoy.
  - Solo corre con la cuenta `unipile`, `directo` o `fake`.
- **Si falla.** Un fallo al encolar nunca detiene el resto del ciclo: el informe del tick lleva `metrics_error`.
- **Pausas.** Con la parada total no corre, como el resto del ciclo. Tampoco corre con la cuenta pausada.
- **Permiso.** El trabajo requiere `operate_linkedin`. No gasta en modelos y su `result_status` es corto, por ejemplo `cortes:2 audiencia:creada`.
- **Topes de lectura.** Las lecturas cuentan contra topes diarios propios: se apuntan en el registro de auditoría como `metrics.read`, igual que las lecturas de la red.
  - Por defecto: `posts=12`, `post=20`, `comments=20`, `profile=3` y `views=3`.
  - Se cambian con `METRICS_READ_CAPS`, por ejemplo `posts=8,comments=10`.
  - Si un tope se agota, esa parte espera a mañana y el resto sigue.
- **Errores del proveedor.** Un 401, 403 o 429 al leer posts o el perfil pausa la cuenta, como en la observación. Las visitas al perfil nunca la pausan.
- **Sin escrituras.** Nunca se escribe nada en LinkedIn.

## Semántica de `null`

- `null` es «sin dato»: LinkedIn lo ocultó, no llegó o no se leyó. `0` solo aparece cuando se observó un cero.
- **Recuentos de la base.** Un recuento sale de los registros del sistema: comentarios publicados, conexiones nuevas, invitaciones recibidas, etc. Vale `null` si su fuente no funcionó en el periodo:
  - para el equipo y el contenido, ningún trabajo ni ejecución en el periodo;
  - para la red, ningún evento `network.*`;
  - para el inbound, ninguna sincronización `network.synced`.
  Así, una máquina parada no se lee como «0».
- **Proporciones.** Si falta el denominador o es cero, el valor es `null` y `unavailable_reason` explica el motivo.
- **Gasto de IA.** El ledger registra cada llamada pagada, así que «0 USD» sí es un cero observado.
- **Interacción oculta.** Si LinkedIn oculta algún contador de un post (por ejemplo, las republicaciones), su interacción es `null`: no se calcula con un cero inventado.

## Endpoint

`GET /api/v1/resultados?dias=7|28|90&modalidad=todo|personal_startups|projectapp`

- **Valores por defecto:** `dias=28` y `modalidad=todo`. Cualquier otro valor devuelve 400.
- **Permiso:** `operate_linkedin`. Es solo lectura.
- **Periodos.** Son días locales completos:
  - el actual va de hoy − (dias − 1) hasta ahora (`datos_hasta`);
  - el anterior tiene la misma duración y termina justo antes.
- **Modalidad.** Filtra las secciones 1 y 2 por `classification.modality`. Seguidores, conexiones y visitas son de toda la cuenta: no se separan, y su definición lo dice. El contenido y el equipo tampoco se separan.

### Ficha de KPI

Todas las fichas tienen la misma forma:

```json
{ "value": 1030, "previous": 1010, "delta": 20, "delta_pct": 2.0, "comparable": true,
  "series": [{ "date": "2026-11-06", "value": 1030 }] | null,
  "definition": "texto en español", "formula": "texto" | null, "unavailable_reason": "texto" | null }
```

- **`value`** es `null` sin dato. En ese caso, `unavailable_reason` dice por qué.
- **`delta`** es `value − previous`. En las fichas en %, va en puntos porcentuales.
- **`delta_pct`** es el cambio relativo, en %, con un decimal. Es `null` si `previous` es 0.
- **`comparable`** solo es `true` cuando los dos periodos tienen dato y el anterior quedó cubierto entero por su fuente. Por ejemplo, la máquina ya funcionaba antes de que empezara. Si no, `delta` y `delta_pct` van en `null` y la PWA muestra «sin comparación».
- **Campos extra de algunas fichas:**
  - `numerator` y `denominator` en las proporciones;
  - `cut` (`7d` o `24h`), `posts_measured` y `posts_total` en el contenido;
  - `measured: {from, to}` en la audiencia, con las fechas de las dos fotos comparadas;
  - `window_days` en las visitas.

### Secciones

1. **`negocio`** (¿genera negocio?):
   - `disponible: false` y `motivo`, hasta que exista el modelo de oportunidades. Hay un `TODO(oportunidades)` en `resultados.negocio`.
   - `inbound`: personas que encajan y te invitaron sin buscarlas. Son contactos con `source=incoming` y `classification.fit=true`, por la fecha en que la red los registró. Respeta la modalidad.
2. **`audiencia`** (¿llegamos a la gente correcta?):
   - `followers` y `connections`: el total en la última foto del periodo. La variación es el crecimiento neto desde la última foto del periodo anterior, y la serie lleva las fotos diarias.
   - `profile_views`: puede faltar.
   - `new_fit_connections`: contactos con `connected_at` en el periodo y `fit=true`.
   - `roles`: composición por rol de esas conexiones.
   - `acceptance_rate`: conectados / (conectados + cerrados), sobre las invitaciones enviadas por Gustavo (`invited_at`) que se resolvieron en el periodo. La resolución es el primer evento `connected` o `closed` de `Contact.history` después de invitar; si el historial se recortó, sirve `connected_at`.
   - `funnel`: lo mismo que `red/summary.stages`, filtrado por modalidad, con `order` y `aside`.
   - `recurrent_people`: `null`, porque aún no se mide.
3. **`contenido`** (¿el contenido aporta?):
   - **Misma edad.** Los posts se comparan siempre con la misma edad:
     - El corte de 7 días si algún post del periodo ya lo tiene.
     - Si ninguno lo tiene, el de 24 h para ambos periodos, con `cut: "24h"` y el aviso en la definición.
   - `kpis`:
     - `median_impressions`: mediana de impresiones por post.
     - `engagement_pct`: (reacciones + comentarios + republicaciones) / impresiones × 100, sumando los contadores de los posts con todos los datos.
     - `substantive_comments`: comentarios con sustancia de otras personas.
     - `consistency`: días publicados frente a días previstos. Un día previsto es uno con pieza del circuito cuya hora ya pasó, se haya publicado, saltado, bloqueado o vetado.
   - `chart`: una barra por post, con las impresiones a 7 días; si aún no los cumple, las de 24 h con `fallback: true`. Incluye la mediana de las 4 semanas anteriores al periodo, a 7 días y a 24 h.
   - `best_post`: el post con más impresiones en el corte común. Desempata la interacción.
   - `by_pillar`: interacción media por pilar.
   - `posts`: la tabla del periodo, con impresiones a 24 h y a 7 días, reacciones, comentarios, republicaciones e interacción del último corte (`cut`), y `commenters_by_role`: personas únicas por rol, con `sin_clasificar`.
4. **`equipo`** (¿el equipo trabaja bien?):
   - `comments_published`. `comments_replied` va en `null`, porque aún no se leen las respuestas.
   - `follows`, `invites` y `accepts`: ejecuciones confirmadas.
   - `pieces_published`, `pieces_blocked` y `pieces_vetoed`: por día de la pieza.
   - `spend`: gasto de Anthropic de hoy por área (`general`, `editorial`, `network` y `other` para lo demás), con `budget: null`: desde el 10/11/2026 las áreas no tienen tope propio y hay un solo presupuesto de IA para todo el equipo (`knowledge/presupuesto.py`).
     El bloque `month` da lo mismo para el mes; `month.total` suma todos los proveedores del mes frente a `AI_MONTHLY_LIMIT_USD`, y `daily_fuse` es el tope de seguridad diario (`AI_DAILY_FUSE_USD`). `accumulated` da el total de Anthropic en el ledger y `other_providers` separa OpenAI y los demás; su `budget` es el techo opcional del proveedor (`<PROVEEDOR>_LIMIT_USD`, mensual por defecto) o `null` si no está fijado.

### Ejemplo (recortado)

```json
{
  "periodo": { "desde": "2026-10-31", "hasta": "2026-11-06", "dias": 7, "datos_hasta": "2026-11-06T18:20:00-05:00",
               "anterior": { "desde": "2026-10-24", "hasta": "2026-10-30" } },
  "modalidad": "todo",
  "zona_horaria": "America/Bogota",
  "negocio": {
    "disponible": false,
    "motivo": "Mediremos oportunidades cuando registres la primera o conectemos el inbox",
    "inbound": { "value": 1, "previous": 1, "delta": 0, "delta_pct": 0.0, "comparable": true, "series": null,
                 "definition": "Personas que encajan y te invitaron sin que las buscáramos: …", "formula": null, "unavailable_reason": null }
  },
  "audiencia": {
    "followers": { "value": 1030, "previous": 1010, "delta": 20, "delta_pct": 2.0, "comparable": true,
                   "series": [{ "date": "2026-11-06", "value": 1030 }], "definition": "Seguidores de la cuenta en la última captura …",
                   "formula": null, "unavailable_reason": null, "measured": { "from": "2026-10-30", "to": "2026-11-06" } },
    "profile_views": { "value": 31, "previous": 25, "delta": 6, "delta_pct": 24.0, "comparable": true, "series": […],
                       "definition": "Visitas al perfil que LinkedIn informa para los últimos 28 días …", "formula": null,
                       "unavailable_reason": null, "window_days": 28 },
    "new_fit_connections": { "value": 3, "previous": 1, "delta": 2, "delta_pct": 200.0, "comparable": true, … },
    "roles": { "items": [{ "role": "comprador", "value": 2 }, { "role": "par", "value": 1 }, …], "definition": "…", "unavailable_reason": null },
    "acceptance_rate": { "value": 50.0, "previous": 100.0, "delta": -50.0, "delta_pct": -50.0, "comparable": true,
                         "formula": "conectados / (conectados + cerrados) × 100", "numerator": 1, "denominator": 2, … },
    "funnel": { "stages": { "candidate": 4, "fit": 2, "followed": 3, "invited": 1, "connected": 8, "discarded": 5, "closed": 1, "incoming": 4 },
                "order": ["candidate", "fit", "followed", "invited", "connected"], "aside": ["discarded", "closed", "incoming"], "definition": "…" },
    "recurrent_people": { "value": null, "previous": null, "delta": null, "delta_pct": null, "comparable": false, "series": null,
                          "definition": "Personas que interactuaron 2 o más veces en el periodo.", "formula": null,
                          "unavailable_reason": "Aún no medimos las interacciones repetidas por persona.", "top": null }
  },
  "contenido": {
    "kpis": {
      "median_impressions": { "value": 210, "previous": 200, "delta": 10, "delta_pct": 5.0, "comparable": true, "cut": "24h",
                              "posts_measured": 2, "posts_total": 2,
                              "definition": "Mediana de impresiones por post a las 24 h. Los posts del periodo aún no cumplen 7 días: …", … },
      "engagement_pct": { "value": 5.0, "previous": 3.0, "delta": 2.0, "delta_pct": 66.7, "comparable": true, "cut": "24h",
                          "formula": "(reacciones + comentarios + republicaciones) / impresiones × 100", "numerator": 15, "denominator": 300, … },
      "substantive_comments": { "value": 1, "previous": 1, "delta": 0, "delta_pct": 0.0, "cut": "24h", … },
      "consistency": { "value": 50.0, "previous": 100.0, "formula": "días publicados / días previstos × 100", "numerator": 2, "denominator": 4, … }
    },
    "chart": { "bars": [{ "piece_id": "uuid", "date": "2026-11-04", "impressions": 300, "cut": "24h", "fallback": true }],
               "median_previous_4_weeks": { "7d": 500, "24h": 200 }, "definition": "…" },
    "best_post": { "piece_id": "uuid", "first_line": "Before writing a line of code …", "date": "2026-11-04", "pillar": "applied_ai",
                   "impressions": 300, "engagement_pct": 5.0, "cut": "24h" },
    "by_pillar": { "cut": "24h", "formula": "…", "items": [{ "pillar": "applied_ai", "value": 5.0, "posts": 1 },
                                                         { "pillar": "business_to_product", "value": null, "posts": 0 }, …] },
    "posts": [{ "piece_id": "uuid", "date": "2026-11-04", "published_at": "ISO", "first_line": "…", "pillar": "applied_ai",
                "url": "https://www.linkedin.com/feed/update/…", "impressions_24h": 300, "impressions_7d": null, "reactions": 10,
                "comments": 5, "reposts": 0, "engagement_pct": 5.0, "cut": "24h",
                "commenters_by_role": { "comprador": 1, "sin_clasificar": 1 } }]
  },
  "equipo": {
    "comments_published": { "value": 1, "previous": 0, "delta": 1, "delta_pct": null, "comparable": true, … },
    "comments_replied": { "value": null, "unavailable_reason": "Aún no leemos las respuestas a tus comentarios.", … },
    "follows": { … }, "invites": { … }, "accepts": { … },
    "pieces_published": { "value": 2, … }, "pieces_blocked": { "value": 0, … }, "pieces_vetoed": { "value": 1, … },
    "spend": {
      "today": { "general": { "spent": 0.05, "budget": null }, "editorial": { "spent": 0.5, "budget": null },
                 "network": { "spent": 0.1, "budget": null }, "other": { "spent": 0.0, "budget": null } },
      "month": { "general": { "spent": 0.05, "budget": null }, …, "total": { "spent": 0.7, "budget": 100.0 } },
      "accumulated": { "spent": 0.85, "budget": null },
      "other_providers": { "openai": { "today": 0.05, "month": 0.05, "accumulated": 0.05, "budget": null } },
      "daily_fuse": 15.0, "month_start": "2026-11-01", "definition": "…"
    }
  }
}
```

### Detalle de una pieza

`GET /api/v1/editorial/pieces/<id>` añade dos campos para la sección «Resultado» del detalle:
- `snapshots`: `[{ kind: "24h|72h|7d", impressions, reactions, comments, reposts, engagement_pct, captured_at, age_hours }]`, en orden de edad. Es una lista vacía mientras no haya cortes.
- `commenters`: los del corte más reciente con comentarios leídos, `[{ provider_user_id, name, substantive, role, fit }]`, con el rol actualizado con la clasificación de hoy. Es `null` si nunca se leyeron.

## Configuración

| Variable | Por defecto | Qué hace |
| --- | --- | --- |
| `METRICS_EVERY_MINUTES` | 180 | Frecuencia aproximada de `collect_metrics`; con 0 queda apagado. |
| `METRICS_MAX_AGE_DAYS` | 30 | Hasta qué edad se buscan los posts propios (mínimo 8). |
| `METRICS_POSTS_LIMIT` | 20 | Cuántos posts propios recientes se leen por vuelta (1 a 100). |
| `METRICS_PROFILE_VIEWS_DAYS` | 28 | Ventana de las visitas al perfil: 14, 28, 90 o 365. |
| `METRICS_READ_CAPS` | — | Topes diarios de lectura, por ejemplo `posts=12,post=20,comments=20,profile=3,views=3`. |

## Pendiente

- **Oportunidades.** La sección 1 se completa cuando exista su modelo, en el `TODO(oportunidades)`.
- **Mediciones que faltan.** Personas recurrentes y respuestas a los comentarios de Gustavo.
- **Un solo número de visitas.** Las visitas al perfil llegan como una sola cifra para la ventana configurada. Con 7 días no hay una ventana de LinkedIn exacta: se muestra la cifra de la ventana configurada y su definición lo dice.
