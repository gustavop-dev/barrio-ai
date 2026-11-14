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
    E --> G[Reglas deterministas de CONT-09]
    G -->|sin problemas| V[e) Verificador sobre el hash del texto]
    G -->|problemas concretos| F[f) Una ronda de reparación]
    V -->|hallazgos concretos| F
    F -->|reglas y segunda revisión acotada| V2[Veredicto final]
    V2 -->|hallazgo duro| B[Pieza bloqueada + push]
    B -->|compuerta de contenido, una vez por día| T
    V -->|blocked sin hallazgos concretos| B
    V2 -->|ready_for_execution o solo blandos como observación| P[Propuesta CONT-09]
    V -->|ready_for_execution| P
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
| a) `editorial-director` | director_editorial (CONT-01/02/07) | B12 `LI-04-M005-K01`; B13 `LI-05-V022-K01/K03`; 9 enfoques `LI-05-M001-K01..K06`, `LI-05-M002-K01..K03`; formato texto `LI-05-M002-K04` | 22 000 / 16 000 / medium |
| b) `editorial-redactor` | copywriter_a y copywriter_b (CONT-03) | enfoque elegido; `LI-05-M002-K04`; B15 `LI-06-M002-K09/K10`, `LI-06-M003-K06`; guía `LI-06-M001-K01..K16` | 26 000 / 16 000 / medium |
| c) `editorial-lectores` | cinco lectores (CONT-05) | B14 `LI-05-V005-K05`, `LI-06-V020-K01` | 5 000 / 12 000 / low |
| d) `editorial-seleccion` | director_editorial | B15 y B14 | 9 000 / 16 000 / medium |
| e) `editorial-verificador` | editor_verificador (CONT-06) | B15; `LI-06-M001-K04` (promesa del gancho) y `LI-06-M001-K07` (concreción sin inventar) | 8 000 / 16 000 / high |
| f) `editorial-reparacion` | director_editorial (solo si hay hallazgos concretos) | B15; `LI-06-M001-K04` y `LI-06-M001-K07` | 9 000 / 16 000 / medium |

La salida máxima deja sitio al pensamiento de Opus 5.5, que cuenta contra `max_tokens` (fase 1 de la auditoría). Cada etapa usa el modelo por defecto (`ANTHROPIC_MODEL`, `claude-opus-5-5`) salvo que se fije `EDITORIAL_MODEL_<ETAPA>` (C3, ver abajo).

La fase 1 de imágenes amplía el brief con `format` foto/infografia/carrusel e `image` con elección, motivo y fotos. La preparación adjunta un manifiesto de archivos al hash de la propuesta. Vídeo queda pendiente. Sin claves de imagen se usa el original o una tarjeta de marca renderizada por código; nunca se publica solo texto. Los documentos llevan alt por página dentro del PDF. Los contratos nuevos de subida se implementaron offline y esperan validación de CI/despliegue; el contrato de texto de la tabla anterior es la referencia histórica.

- **Director.** Recibe tres tipos de señales: hasta 12 posts de referentes de los últimos 7 días, marcados como datos de terceros; la memoria; y el historial de las últimas 20 piezas con la mezcla de modalidades publicadas en 30 días, para no repetirse. Cada pieza publicada del historial trae sus resultados (ver «Resultados en el historial del director»). Devuelve un brief con estos campos: lector principal, modalidad (`personal_startups`, `projectapp`, `alianzas` o `comunidad`), pilar provisional (`business_to_product`, `applied_ai` o `architecture_delivery`), tesis, enfoque, formato, valor para el lector, evidencia, criterio de éxito, qué evitar y señales usadas. El 60/40 orienta la mezcla y no es una cuota. Si no hay material genuino, responde `skip`; saltar un día es válido y ese día no se reintenta solo.
- **Redactores.** Hacen una sola llamada que devuelve dos variantes independientes. La A explora primero una decisión, un procedimiento o un caso; la B, una pregunta u objeción del founder y su mecanismo. Ambas parten del mismo brief y de las mismas fuentes, y cada una enumera sus afirmaciones con su tipo.
- **Lectores.** Comprador, recomendador, divulgador, líder y par dan fortalezas y objeciones por variante, clasificadas como `material`, `preference` o `missing_data`. Son hipótesis, no métricas. No reciben memoria ni la autoría de las variantes.
- **Selección.** El director elige A o B, las fusiona o descarta la pieza. Decide por objetivo, verdad, utilidad y voz, no por mayoría.
- **Reglas antes del verificador (R3).** Justo después de la selección, `editorial.text_rules()` aplica al texto exacto las reglas deterministas de la política (`autopiloto.post_issues`, con sus mismos patrones y límites): longitud de 200 a 2 200 caracteres, sin correos, teléfonos ni enlaces, sin pitch agresivo, como mucho 3 hashtags, sin filtración privada (`guardas.private_leaks`) y sin experiencia que los hechos públicos no respalden (`guardas.invented_experience`). Si algo falla, el verificador no se paga para ese texto. Cada guarda corre una vez por versión del texto dentro del circuito; la política las vuelve a aplicar como compuerta final.
- **Verificador.** Contrasta cada afirmación con `public_facts` y las fuentes observadas. Marca experiencias inventadas, cifras sin fuente, pitch agresivo, datos privados, filtraciones de `private_guidance`, ganchos incumplidos y piezas fuera del brief. Solo un hecho sin respaldo es material: opiniones, criterio, razonamientos y preguntas no. El veredicto final se calcula sobre el SHA-256 del texto exacto, con la severidad de [`compuertas.md`](compuertas.md), y es `blocked` en cualquiera de estos casos:
  - las reglas deterministas o las fuentes web encontraron un problema (sin reglas que pasen, el verificador no corre);
  - el modelo emite `blocked` sin hallazgos concretos;
  - hay un hallazgo `material` duro (experiencia inventada, cifra o afirmación sin respaldo, datos privados, fuga de la guía privada, pitch agresivo);
  - hay una afirmación `unsupported`.
  Un hallazgo `material` blando (`hook_not_delivered`, `off_brief`, `other`) dispara la ronda de reparación y, si sigue, la pieza sale con él en `verification.observations` y como riesgo «Conservada como observación…».
- **Ronda de reparación (R4).** Si las reglas o el verificador encuentran problemas concretos (motivos de las reglas, hallazgos `material` o afirmaciones `unsupported`), la etapa `reparacion` recibe el texto final, el brief, la memoria, las fuentes y los hallazgos exactos, y devuelve un texto corregido con el cambio mínimo, en la voz de Gustavo. Después se repiten una vez las reglas y el verificador, que esta vez es una **segunda revisión acotada** (`second_review`): recibe los hallazgos y los cambios, comprueba si cada uno quedó resuelto y solo marca lo que sigue o un problema grave nuevo. Hay una sola ronda por pieza:
  - si el texto reparado pasa, la pieza sigue como siempre y su propuesta lleva el riesgo «Reparada en una ronda…»;
  - si sigue con un hallazgo duro, la pieza termina `blocked`, como antes; si solo quedan blandos, sale con ellos como observación;
  - si la reparación descarta la pieza o no cambia el texto, se queda el texto original: `blocked` si sus hallazgos eran duros y, si eran blandos, sale con ellos como observación;
  - un `blocked` del verificador sin hallazgos concretos no tiene nada que reparar y bloquea directamente.
  La ronda pasa por `_guard()` como cualquier etapa. Si el presupuesto de IA se agota durante la ronda, la pieza termina `blocked` con los motivos originales cuando son duros (no `failed`), y ese día puede tener su segundo intento cuando haya presupuesto. El registro queda en `verification.repair` (disparador, hallazgos, texto original, primer veredicto, cambios, resultado y, tras la segunda revisión, `resolution` por hallazgo) y el detalle de la pieza lo muestra en «Ronda de reparación». `EDITORIAL_REPAIR=false` apaga la ronda.
- **Segundo intento del día.** Un día cuya pieza paró una compuerta de contenido (reglas, verificador o revisión visual) mientras se preparaba se vuelve a preparar una vez (`EDITORIAL_DAY_ATTEMPTS=2`) si quedan `EDITORIAL_RETRY_MIN_MINUTES` (90) antes de su hora; el director recibe `previous_attempts` con la tesis y los motivos del intento bloqueado. Detalle en [`compuertas.md`](compuertas.md).

### Memoria: hechos públicos y orientación privada

Los hechos confirmados de Gustavo (`namespace='user'`) se reparten en dos bloques con `knowledge.memory.confirmed_blocks()`:

- `public_facts`: valores `{"texto": …, "uso_publico": true}`. Son lo único que puede atribuirse a Gustavo en un texto público.
- `private_guidance`: el resto, incluido cualquier valor que no sea un dict con `uso_publico` (por seguridad), más la orientación privada del brief interno (`guardas.BASELINE_GUIDANCE`: prioridad 60/40, segmento de founders y condiciones). Orienta decisiones, pero nunca aparece ni se parafrasea en público.

Director, redactores, selección y verificador reciben ambos bloques; el panel de lectores no recibe ninguno. Los comentarios (`propose_comment`) usan la misma separación sin la orientación del brief. Con la memoria vacía, como hoy, las piezas aportan criterio, preguntas y aprendizajes generales, sin vivencias de Gustavo. `guardas.private_leaks()` detecta 60/40, segmentos como «Spanish-speaking founders», bandas salariales, LLC y Beloz, además de fragmentos literales de la orientación privada. No cita lo que encontró, porque el motivo viaja en avisos y push. La usan las reglas previas al verificador y la compuerta de comentarios.

`guardas.invented_experience()` compara cada afirmación en primera persona («I built», «my clients», «construí», «en mi empresa»…, la frase entera) con los hechos públicos confirmados. Sin hechos públicos, cualquier experiencia en primera persona es inventada. Con hechos, marca la afirmación si trae una cifra que ningún hecho contiene, o si no comparte ninguna palabra de contenido ni ninguna cifra con ellos. Es estrecha a propósito: basta una palabra en común, y equipo, empresa, estudio, agencia, startup y clientes cuentan como una sola familia en inglés y en español. El verificador sigue siendo el juez principal. Antes, un solo hecho público apagaba la regla.

### Voz de Gustavo (`voz.py`)

El documento «Tono de voz» que escribió Gustavo se guarda tal cual en `src/team_backend/recursos/tono-de-voz.md`. `voz.with_voice()` lo añade, precedido de `voz.VOICE_GUIDE`, al final del system de los agentes que escriben texto público: redactores A/B, selección y reparación (`editorial.VOICED_STAGES`) y redactor de comentarios. El director, el panel de lectores y el verificador no lo reciben.

`VOICE_GUIDE` adapta el documento a LinkedIn:
- Aplica la «versión cuidada» que el propio documento describe. En publicaciones propias se conservan la cadencia, los matices y el remate cotidiano, pero no hay risas escritas, vocales alargadas, groserías ni deformaciones afectivas. Los comentarios admiten algo más de reacción.
- En inglés, la cadencia se traslada con equivalentes naturales, sin traducir modismos.
- La voz decide cómo se dice algo, nunca qué le pasó a Gustavo. Una anécdota en primera persona («yo pensé que…») solo puede contar un hecho de `public_facts`.

El verificador sabe que el registro informal no es un defecto y que una anécdota sin respaldo sí es `invented_experience`. `guardas.EXPERIENCE` reconoce también las formas en español («construí», «lanzamos», «mi equipo», «nuestros clientes»). Desde ahora se aplica igualmente a la compuerta de comentarios.

Para cambiar la voz, Gustavo edita ese archivo y se despliega una imagen nueva. El bloque ocupa unas 5 000 tokens, va en el system cacheado y añade como mucho unos 0,03 USD por llamada con opus.

## Posicionamiento (`posicionamiento.py`)

La dirección de Gustavo vive en una sola fuente versionada (`posicionamiento.VERSION`, hoy `posicionamiento-v1`): quién es, pilares, modalidades con su propósito y su barrio, y límites. De ella salen `editorial.DIRECTION` (director, redactores, selección y reparación), `red.CLASSIFY_SYSTEM` (clasificador de la red) y `lider.CRITERIA_DEL_BARRIO` (líder). Cada brief guarda `positioning_version`. Sigue siendo una propuesta interna que Gustavo supervisa; las prioridades privadas (60/40, segmento) están en `guardas.BASELINE_GUIDANCE`, no aquí.

Los valores guardados no cambian de nombre. `posicionamiento.VOCABULARIES` es la correspondencia explícita:

| Modalidad canónica | Pieza (`brief.modality`) | Persona (`classification.modality`) | Oportunidad (`Opportunity.modality`) |
| --- | --- | --- | --- |
| `personal_startups` | `personal_startups` | `personal_startups` | `personal_startups` |
| `projectapp` | `projectapp` | `projectapp` | `projectapp` |
| `alianzas` | `alianzas` | `alianzas` | — (`por_clasificar`) |
| `comunidad` | `comunidad` | `comunidad_autoridad` | — (`por_clasificar`) |

Una alianza o una persona de la comunidad no es por sí misma una oportunidad de negocio, así que Oportunidades solo tiene las dos modalidades de negocio y `por_clasificar`. `to_canonical()` y `to_stored()` traducen entre dominios. Las etiquetas de la PWA (`lib/editorial.ts`, `lib/format.ts`, `personas/labels.ts`) siguen igual, y una prueba comprueba que cada valor guardado tiene etiqueta.

## Resultados en el historial del director

Cada pieza publicada del historial lleva `results` con sus cortes de `PostMetric` (`metricas.py`) a 72 h y 7 d: impresiones, reacciones, comentarios, compartidos, comentarios con sustancia y `engagement_pct`. Un corte es `"pendiente"` si aún no cumplió su edad y `"sin_dato"` si la cumplió pero no se pudo leer; un contador `null` es un dato que falta, nunca un cero.

`performance_30d` resume de forma determinista lo publicado en 30 días, en total (`all`), por pilar y por modalidad: cuántas piezas, cuántas tienen cada corte y las medianas de impresiones, reacciones y comentarios sobre las que tienen dato. El system del director explica cómo usarlo: insistir en lo que funciona sin repetir tesis ni apertura, volver a probar lo que no tiene datos, tratar menos de tres piezas medidas como una pista y no perseguir impresiones por encima de la dirección, la mezcla de modalidades ni la orientación de Gustavo.

## Modelo por etapa (C3)

`EDITORIAL_MODEL_DIRECTOR`, `EDITORIAL_MODEL_REDACTOR`, `EDITORIAL_MODEL_LECTORES`, `EDITORIAL_MODEL_SELECCION`, `EDITORIAL_MODEL_VERIFICADOR` y `EDITORIAL_MODEL_REPARACION` cambian el modelo de una sola etapa. La reparación usa el de la selección si no tiene el suyo. Sin ninguna, todas usan el modelo por defecto, como hasta ahora. Un modelo sin tarifa verificada en `providers.MODEL_PRICES` hace fallar la pieza antes de pagar nada. El cambio real espera la evaluación (fase 3 de la auditoría).

## Compuerta autónoma (`autopiloto.policy_review`, `autonomia-v1`)

CONT-09 se aprueba solo si se cumplen todas estas condiciones (las mismas reglas deterministas ya corrieron en el circuito antes del verificador; la política las repite como compuerta final):
- la longitud está entre 200 y 2 200 caracteres;
- no hay correos, teléfonos ni enlaces;
- no hay pitch agresivo ni petición de contacto (mencionar ProjectApp está permitido; un tipo de post con `gate_policy.cta_max=1` admite una sola invitación conversacional, nunca venta dura);
- hay 3 hashtags como máximo;
- no hay filtración privada ni experiencia sin hechos públicos;
- el verificador dio `ready_for_execution` sobre el mismo `text_sha256` (puede llevar observaciones blandas);
- no hay afirmaciones pendientes;
- hay al menos una unidad del curso citada.

Si cualquier edición cambia el texto, invalida el veredicto y la política descarta esa versión. Para publicar un texto editado a mano, usa `OPERATOR_AUTONOMY=…,CONT-09=approval` y apruébalo con su hash.

## Programación (`autopiloto.tick`)

- **Hueco diario.** La hora es `EDITORIAL_POST_TIME` (08:30 por defecto), en `OPERATOR_TIMEZONE`, y debe caer dentro de `OPERATOR_WINDOW`. La preparación empieza `EDITORIAL_LEAD_HOURS` antes (12 h por defecto). Así hay margen para vetar y llega una push «pieza lista» con la hora de salida.
- **Las ideas de Gustavo tienen fecha al llegar y se preparan ya** (`urgente.assign_slots`). Sin fecha van al siguiente día libre de la cola y se escriben según el tipo GASP de ese día; una idea que claramente es de un tipo toma el día de ese tipo más cercano (`docs/plan-estrategia-semanal.md`). «Cuanto antes» toma el primer hueco libre. Un día y una hora pedidos («publícalo mañana a las 10», leídos por `cuando.py` del fragmento literal) son una orden desde el 14/11/2026: el post sale ese día a esa hora como post extra, junto al diario, que no se mueve; sin hora, a `EDITORIAL_EXTRA_TIME`. Si la fecha no se puede cumplir (pasada, dentro del veto, fuera de la ventana, a más de 14 días, ambigua o un día que ya tiene dos posts), la Bandeja pregunta en el momento y la idea espera (EDI-24). Cada idea con fecha se prepara en cuanto la tiene, no `EDITORIAL_LEAD_HOURS` antes. Si el director no toma la idea reservada, la idea vuelve a la mesa sin fecha propia y ese día vuelve al post diario. Lo mismo vale para un día cuyas únicas piezas eran para la idea y no salieron (saltadas, bloqueadas o fallidas). Cada pieza de su hueco que termina bloqueada o fallida por algo que no es dinero cuenta un intento, una sola vez por pieza; tras dos intentos la idea pierde su fecha y sigue en la mesa del director para un día normal. Push «Tu idea ya tiene fecha» con el día y la hora.
- **Quedarse sin presupuesto no gasta el día.** Una pieza detenida solo por dinero (`failed` o `blocked` con la nota «Presupuesto de IA agotado», la antigua «Presupuesto editorial diario agotado» o «Ciclo detenido: cost_cap») no ocupa su día: el autopiloto lo vuelve a intentar desde el día local siguiente, cuando hay presupuesto, con un trabajo nuevo, y para una idea de Gustavo ese día sigue libre. Cualquier otro fallo no se reintenta solo.
- **No se empieza lo que no se puede terminar.** Una preparación, del autopiloto o de una idea, no empieza si del presupuesto de IA quedan menos de `EDITORIAL_PREPARE_MIN_USD` (3 USD por defecto, lo que reserva una pieza con imágenes): se detendría a medias. Espera a que haya presupuesto; la idea lo dice con «Preparación pendiente de presupuesto de IA.».
- **Una preparación cada vez.** El trabajo `prepare_piece` tiene un id determinista por hueco e intento, así que el autopiloto lo intenta una sola vez por día, salvo el segundo intento tras una compuerta de contenido ([`compuertas.md`](compuertas.md)). Una preparación interrumpida pasa a `failed` sin repetir el gasto.
- **No se prepara una pieza que no podría salir.** Hace falta una cuenta oficial conectada, sin pausa y con `LIVE_LINKEDIN_OFFICIAL=true`, CONT-09 distinto de `off` y cupo semanal.
- **Topes.** CONT-09 admite 1 al día y 7 a la semana (`publicaciones` del reparto), configurables en `OPERATOR_DAILY_LIMITS` y `OPERATOR_WEEKLY_LIMITS`. Además, la base de datos impide más de una pieza abierta por día y más de una acción abierta por pieza.
- **Presupuesto de IA.** La publicación no tiene tope propio: gasta del presupuesto único del equipo (`knowledge/presupuesto.py`), `AI_MONTHLY_LIMIT_USD` (100 USD por mes calendario en `OPERATOR_TIMEZONE`) con el tope de seguridad diario `AI_DAILY_FUSE_USD` (15 USD), que suman todos los proveedores y áreas, incluidas las reservas pendientes o inciertas. Se comprueba antes de encolar (`EDITORIAL_PREPARE_MIN_USD`), antes de cada etapa (`_guard()`) y en cada reserva (`providers.reserve`); al agotarse, la pieza se detiene. El ciclo `pieza_diaria` tiene además un tope de 8 USD por ciclo sobre sus reservas, contra gastos desbocados. `<PROVEEDOR>_LIMIT_USD` es opcional: si se fija, añade un techo mensual a ese proveedor.
- **Ejecución.** Pasa por `operador.execute()`, que añade una compuerta: no se publica antes de `scheduled_for`. Valen también todas las salvaguardas de siempre: parada global, pausa de cuenta, ventana, espaciado y topes. El espaciado entre escrituras públicas pasa a ser común a todos los conectores, porque todos actúan como el mismo miembro.
- **Caducidad.** Una pieza aprobada que no sale caduca `OPERATOR_PROPOSAL_TTL_HOURS` después de su hora programada, no de su creación.

## Coste estimado por pieza

Tokens aproximados: unas 62 000 de unidades del curso entre las cinco etapas, unas 16 000 de instrucciones y datos (señales, memoria, borradores y panel) y entre 6 000 y 10 000 de salida.

| Modelo (`providers.MODEL_PRICES`, USD por millón de tokens de entrada / salida) | Pieza completa | Día con `skip` (solo el director) |
| --- | --- | --- |
| `claude-opus-5-5` (4 / 20), por defecto | ≈ 0,43–0,51 USD | ≈ 0,12 USD |
| `claude-sonnet-5-5` (2 / 10) | ≈ 0,22–0,26 USD | ≈ 0,06 USD |
| `claude-haiku-5-5` (0,10 / 0,50) | ≈ 0,01 USD | < 0,01 USD |

Una pieza que necesita la ronda de reparación suma una llamada de reparación y, si cambió el texto, un segundo verificador (la segunda revisión acotada, que solo añade los hallazgos y los cambios a su entrada): unos 0,2–0,3 USD más con opus. Un día con segundo intento paga otra preparación completa, como mucho una vez ([`compuertas.md`](compuertas.md)). Una pieza que las reglas frenan antes del verificador se ahorra ese verificador. Con opus salen unos 13–15 USD al mes con una pieza diaria. Cada etapa reserva primero su peor caso: con opus, unos 0,26 USD como máximo en la del redactor. Las etapas son secuenciales y se liquidan antes de pasar a la siguiente, así que `EDITORIAL_PREPARE_MIN_USD` (3 USD) cubre una pieza con imágenes y el tope de 8 USD del ciclo solo frena un gasto desbocado.

## API para la PWA

| Ruta | Uso |
| --- | --- |
| `GET /api/v1/linkedin/oauth/start` | Inicia la conexión (sesión humana con `approve_actions`): 302 a LinkedIn. |
| `GET /api/v1/linkedin/oauth/callback` | Retorno de LinkedIn: 302 a `/ajustes?linkedin=ok` o a `…=error&motivo=…`. |
| `GET /api/v1/linkedin/status` | `configured`, `live`, `api_version`, `connected`, `member_urn`, `member_name`, `scopes`, `expires_at`, `days_left`, `expired`, `expiring_soon`, `account{id,paused,paused_reason}`. Nunca incluye el token. |
| `GET /api/v1/editorial/calendar?desde=AAAA-MM-DD&dias=15` | `timezone`, `post_time`, `lead_hours`, `today` y `days[{date, pieces[…]}]`; un día vacío es un hueco visible. Cada pieza trae `id`, `slot_date`, `scheduled_for`, `state`, `status`, `stage`, `modality`, `pillar`, `primary_reader`, `thesis`, `approach`, `note`, `action{id,state,payload_hash}` y `external_url`. |
| `GET /api/v1/editorial/pieces/<id>` | Lo mismo, más `brief`, `variants`, `panel`, `selection`, `verification`, `final_text`, `citations`, `signals`, `usage` (modelo, coste estimado y `request_id` por etapa) y `action_detail` (la acción completa). `verification.rules` y `verification.repair` describen las reglas previas y la ronda de reparación (`oficina/CONTRATO-API.md`). |
| `POST /api/v1/editorial/plan` | `{request_id?}`: encola la preparación del próximo hueco sin pieza abierta (202 `{slot_date, job}`). Responde 409 si LinkedIn no está conectado, si la publicación está pausada o desactivada, o si no hay hueco en 7 días. Requiere `use_paid_providers`. |
| `POST /api/v1/operador/actions/<id>/reject` | **Vetar** una pieza antes de su hora (sesión humana). El día queda sin publicación. |
| `POST /api/v1/operador/control` | Parada total (sin cambios). |

`status` de una pieza: `preparing`, `skipped`, `blocked` o `failed` mientras no exista la acción. Después sigue el ciclo de esta: `awaiting_approval`, `scheduled`, `publishing`, `published`, `uncertain`, `vetoed`, `discarded`, `expired` o `superseded`.

Acciones (`/api/v1/operador/actions…`): `post` puede ser `null`. En ese caso `piece_id` y `scheduled_for` identifican la pieza propia. CONT-09 no se puede crear a mano desde esta ruta. `GET /api/v1/operador/overview` añade `today.editorial_llm_spent_usd` y `today.editorial_llm_daily_cap_usd`; este último es el tope de seguridad diario de todo el equipo (`AI_DAILY_FUSE_USD`), no uno propio. `/oficina/actividad` muestra la etapa en curso con su rol: director, redactores, lectores o verificador.

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
   EDITORIAL_PREPARE_MIN_USD=3      # con menos presupuesto de IA disponible, la preparación espera
   AI_MONTHLY_LIMIT_USD=100         # presupuesto de IA de todo el equipo por mes
   AI_DAILY_FUSE_USD=15             # su tope de seguridad diario
   EDITORIAL_REPAIR=true            # ronda de reparación (R4); false la apaga
   EDITORIAL_DAY_ATTEMPTS=2         # segundo intento de un día que paró una compuerta (docs/compuertas.md); 1 lo apaga
   EDITORIAL_RETRY_MIN_MINUTES=90   # margen mínimo antes de la hora para ese segundo intento
   # EDITORIAL_MODEL_LECTORES=…     # C3: modelo de una etapa; sin fijar, el de siempre
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
