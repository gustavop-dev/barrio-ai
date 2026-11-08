# Red del barrio (`BAR`)

El equipo descubre personas que encajan con Gustavo, las clasifica, las sigue, las invita sin nota y acepta las invitaciones que encajan. Gustavo puede descartar a cualquiera. La interfaz de Personas que muestra a estas personas está en [personas-oportunidades.md](personas-oportunidades.md).

- **Código:** `agentes-linkedin/infra/src/team_backend/red.py`, `red_views.py`, `autopiloto._network`, `operador.execute` (capacidades `RED-01`, `RED-02`, `RED-04`).
- **Documentación:** [`red-barrio.md`](../../agentes-linkedin/infra/docs/red-barrio.md), sección «Red» de [`CONTRATO-API.md`](../../oficina/CONTRATO-API.md).
- **Entorno de prueba:** `NETWORK_ENABLED=true` (por defecto `false`), cuenta `fake` con `OPERATOR_ALLOW_FAKE=true` y el clasificador parcheado, como en `tests/test_red.py`.

## Resumen

| ID | Función | Dónde | Estado |
| --- | --- | --- | --- |
| [BAR-01](#bar-01) | Descubrir personas en los comentarios de los referentes | backend | funciona |
| [BAR-02](#bar-02) | Descubrir personas por búsqueda | backend | funciona |
| [BAR-03](#bar-03) | Clasificar a cada persona | backend | funciona |
| [BAR-04](#bar-04) | Seguir a quien encaja (RED-01) | backend | funciona |
| [BAR-05](#bar-05) | Invitar sin nota tras la espera (RED-02) | backend | funciona |
| [BAR-06](#bar-06) | Registrar y aceptar invitaciones recibidas (RED-03, RED-04) | backend | funciona |
| [BAR-07](#bar-07) | Comprobación previa a cada escritura | backend | funciona |
| [BAR-08](#bar-08) | Topes de lectura, de escritura y de gasto | backend | funciona |
| [BAR-09](#bar-09) | Pausa de invitaciones si LinkedIn las limita | backend | funciona |
| [BAR-10](#bar-10) | Descartar a una persona o vetar su acción | PWA · app · backend | funciona |
| [BAR-11](#bar-11) | Resumen de la red | PWA · app · backend | funciona |
| [BAR-12](#bar-12) | Aviso de conexión nueva que encaja | backend | funciona |
| [BAR-13](#bar-13) | Aprobar acciones de red en modo aprobación | PWA · app · backend | funciona |

---

### BAR-01 · Descubrir personas en los comentarios de los referentes <a id="bar-01"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Qué hace para Gustavo:** quien comenta con sustancia en los posts de sus referentes entra en el barrio como candidato.
- **Código:** `red.discover`, trabajo `discover_network` cada `NETWORK_DISCOVER_EVERY_MINUTES` (360).
- **Criterios de aceptación:**
  1. **Dado** posts de referentes observados en los últimos `NETWORK_SCAN_DAYS` días, **cuando** corre el descubrimiento, **entonces** quien comentó con al menos `NETWORK_MIN_COMMENT_CHARS` (80) caracteres pasa a ser un `Contact` en `candidate` con `source: commenter` y `evidence` con el post, el referente y el comentario.
  2. **Dado** un saludo corto, una cuenta de empresa, un referente, Gustavo o alguien que ya es contacto, **cuando** corre, **entonces** no se crea un contacto.
  3. **Dado** 40 candidatos sin clasificar (`NETWORK_DISCOVER_MAX_BACKLOG`), **cuando** toca descubrir, **entonces** el autopiloto no encola el trabajo; si corre igual, no lee nada y registra `network.discovery_held`.
  4. **Dado** `NETWORK_ENABLED=false`, **cuando** corre el autopiloto, **entonces** no descubre.
- **Brechas código/docs:** —
- **Cobertura QA:** pendiente

### BAR-02 · Descubrir personas por búsqueda <a id="bar-02"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Qué hace para Gustavo:** el equipo busca personas con las palabras clave configuradas.
- **Código:** `red.discover` (`NETWORK_SEARCH_QUERIES`, rotación).
- **Criterios de aceptación:**
  1. **Dado** dos búsquedas configuradas, **cuando** corren dos turnos de descubrimiento, **entonces** cada turno ejecuta una búsqueda distinta y los contactos nuevos llevan `source: search` y `evidence.query`.
  2. **Dado** un resultado de primer grado, **cuando** se procesa, **entonces** no se crea contacto.
  3. **Dado** búsquedas configuradas, **cuando** se reparte el cupo del turno, **entonces** los comentaristas ocupan como mucho dos tercios.
- **Brechas código/docs:** —
- **Cobertura QA:** pendiente

### BAR-03 · Clasificar a cada persona <a id="bar-03"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Qué hace para Gustavo:** un modelo decide si la persona encaja con su barrio, con qué rol y modalidad, y por qué.
- **Código:** `red.classify`, `red._enrich`, `CLASSIFY_SYSTEM` (de `posicionamiento.network_criteria`), `NETWORK_CLASSIFIER_MODEL`.
- **Criterios de aceptación:**
  1. **Dado** candidatos sin titular, **cuando** corre la clasificación, **entonces** antes se lee su perfil (una lectura del cupo `profile`); si el cupo se agotó, esa persona espera al día siguiente sin juzgarse.
  2. **Dado** un lote de hasta 10 personas, **cuando** el modelo responde `fit` con confianza ≥ `NETWORK_MIN_CONFIDENCE` (0,6), **entonces** la persona pasa a `fit` con `classification` (`fit`, `role`, `modality`, `affinity`, `reason`, `confidence`, `model`, `classified_at`); si no, pasa a `discarded`.
  3. **Dado** que la afinidad hispanohablante no está declarada en el perfil, **cuando** se clasifica, **entonces** `affinity` vale `desconocida`, nunca se deduce del nombre.
  4. **Dado** que lo gastado hoy llega a `NETWORK_DAILY_LLM_USD`, **cuando** toca clasificar, **entonces** falla con «Presupuesto diario de la red agotado (NETWORK_DAILY_LLM_USD).».
  5. **Dado** una respuesta que no es JSON válido, **cuando** se procesa, **entonces** falla con «El clasificador no devolvió JSON válido.» y nadie cambia de etapa.
- **Brechas código/docs:** —
- **Cobertura QA:** pendiente

### BAR-04 · Seguir a quien encaja (RED-01) <a id="bar-04"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Qué hace para Gustavo:** el equipo sigue a las personas que encajan, dentro de los topes.
- **Código:** `red.plan`, `red.execute_action`, `red.on_confirmed`.
- **Criterios de aceptación:**
  1. **Dado** contactos en `fit` y cupo de RED-01, **cuando** corre `plan_network`, **entonces** se crea una propuesta RED-01 con `payload: {user_id}` por persona, descontando las que ya están abiertas.
  2. **Dado** la propuesta aprobada y ejecutada con éxito, **cuando** se confirma, **entonces** el contacto pasa a `followed` con `followed_at` e `is_following: true`.
  3. **Dado** que el perfil ya muestra que Gustavo lo sigue, **cuando** se ejecuta, **entonces** se confirma sin escribir (`wrote=False`) y pasa a `followed`.
- **Brechas código/docs:** —
- **Cobertura QA:** pendiente

### BAR-05 · Invitar sin nota tras la espera (RED-02) <a id="bar-05"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Qué hace para Gustavo:** 48 horas después de seguir a alguien que sigue en 2.º o 3.er grado, el equipo le manda una invitación sin nota.
- **Código:** `red.plan` (`NETWORK_INVITE_AFTER_HOURS`), `red.execute_action`, `red.network_issues`.
- **Criterios de aceptación:**
  1. **Dado** un contacto `followed` hace 49 h, **cuando** corre `plan_network`, **entonces** se propone RED-02 con `payload` igual a `{user_id}` y nada más.
  2. **Dado** un contacto `followed` hace 47 h, **cuando** corre, **entonces** no se propone.
  3. **Dado** una propuesta RED-02 con algo más que `user_id` en `payload` (por ejemplo una nota), **cuando** la revisa la compuerta en modo `auto`, **entonces** se descarta.
  4. **Dado** la invitación enviada, **cuando** se confirma, **entonces** el contacto pasa a `invited` con `invited_at`.
  5. **Dado** que la persona salió del 2.º y 3.er grado, **cuando** se ejecuta, **entonces** no se escribe, sigue en `followed` con `out_of_network` y no se vuelve a proponer hasta `NETWORK_RETRY_AFTER_HOURS` (48).
- **Brechas código/docs:** —
- **Cobertura QA:** pendiente

### BAR-06 · Registrar y aceptar invitaciones recibidas (RED-03, RED-04) <a id="bar-06"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Qué hace para Gustavo:** quien le invita entra al barrio; si encaja, el equipo acepta la invitación. Las que no encajan se quedan pendientes, nunca se declinan.
- **Código:** `red.sync` (trabajo `sync_network`), `red.plan`, `red.execute_action`.
- **Criterios de aceptación:**
  1. **Dado** una invitación recibida nueva, **cuando** corre la sincronización, **entonces** la persona se registra en `incoming` con `source: incoming` sin clasificar, y el calendario muestra «<nombre> te invitó».
  2. **Dado** un `incoming` clasificado como `fit`, **cuando** corre el plan, **entonces** se propone RED-04 con `{request_id, user_id}`; uno sin clasificar o que no encaja no se propone.
  3. **Dado** RED-04 confirmada, **cuando** termina, **entonces** el contacto pasa a `connected` con `connected_at` y `network_distance: FIRST_DEGREE`.
  4. **Dado** que la invitación ya no está en la lista de recibidas al ejecutar, **cuando** se comprueba, **entonces** pasa a `connected` si ya hay conexión, o a `closed` (`invitation_gone`) si no.
  5. **Dado** una invitación enviada que ya no aparece, **cuando** corre la sincronización, **entonces** se relee el perfil y pasa a `connected` o a `closed`.
- **Brechas código/docs:** —
- **Cobertura QA:** pendiente

### BAR-07 · Comprobación previa a cada escritura <a id="bar-07"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Qué hace para Gustavo:** el equipo nunca sigue dos veces a alguien, ni reinvita, ni escribe sin mirar antes el perfil.
- **Código:** `red._precheck`, `red._settle`, `red._unreachable`.
- **Criterios de aceptación:**
  1. **Dado** una ejecución RED-01 o RED-02, **cuando** empieza, **entonces** se lee el perfil antes de escribir y la lectura se cuenta como `network.read` de tipo `execution`.
  2. **Dado** un perfil de primer grado, **cuando** se comprueba, **entonces** no se escribe y el contacto pasa a `connected` (`already_connected`).
  3. **Dado** una invitación previa ignorada o retirada, **cuando** se comprueba, **entonces** no se escribe y pasa a `closed` (`previous_invitation`).
  4. **Dado** un perfil restringido, **cuando** se comprueba, **entonces** pasa a `discarded` (`restricted`).
  5. **Dado** que la ejecución no escribió, **cuando** se calculan topes y espaciado, **entonces** no cuenta.
  6. **Dado** un resultado incierto, **cuando** se concilia, **entonces** se relee el perfil y nunca se repite la escritura.
- **Brechas código/docs:** —
- **Cobertura QA:** pendiente

### BAR-08 · Topes de lectura, de escritura y de gasto <a id="bar-08"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Qué hace para Gustavo:** la red trabaja dentro de límites conservadores para no arriesgar su cuenta.
- **Código:** `red.read_caps`, `red._read`, `operador.limits`, `operador.capacity_left`, `operador.spacing_ok`.
- **Criterios de aceptación:**
  1. **Dado** los topes por defecto, **cuando** se consulta `GET /api/v1/red/summary`, **entonces** `capacity` muestra RED-01 10/día y 40/semana, RED-02 5 y 20, RED-04 10 y 40, y `read_caps` muestra `comments` 60, `search` 20, `profile` 30, `sync` 4.
  2. **Dado** que se agotó el cupo de lecturas de perfil, **cuando** toca clasificar, **entonces** se detiene y lo dice en su error; la comprobación previa de una ejecución sigue funcionando.
  3. **Dado** una escritura de red, un comentario y una publicación, **cuando** se programan, **entonces** comparten el espaciado mínimo común.
- **Brechas código/docs:** —
- **Cobertura QA:** pendiente

### BAR-09 · Pausa de invitaciones si LinkedIn las limita <a id="bar-09"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Qué hace para Gustavo:** si LinkedIn rechaza una invitación por límite, el equipo deja de invitar siete días y se lo dice.
- **Código:** `red.invites_blocked`, `red.network_issues`, `GET /api/v1/red/summary` (`invites_blocked`).
- **Criterios de aceptación:**
  1. **Dado** un 429 o un error cuyo tipo o nota menciona *limit*, *quota*, *throttle* o *exceed* al invitar, **cuando** se registra, **entonces** `red/summary.invites_blocked` vale `{blocked: true, reason}` durante 7 días.
  2. **Dado** invitaciones bloqueadas, **cuando** la compuerta revisa una RED-02 en `auto`, **entonces** la descarta.
  3. **Dado** invitaciones bloqueadas, **cuando** Notificaciones calcula lo próximo, **entonces** no muestra «El equipo invitará a N personas…».
- **Brechas código/docs:** —
- **Cobertura QA:** pendiente

### BAR-10 · Descartar a una persona o vetar su acción <a id="bar-10"></a>

- **Dónde:** PWA · app · backend
- **Estado:** funciona
- **Qué hace para Gustavo:** si alguien no le interesa, lo descarta con un motivo y el equipo no vuelve a proponerlo nunca.
- **Código:** `POST /api/v1/red/contacts/<id>/discard` (`red.discard`), `POST /api/v1/operador/actions/<id>/reject` (`red.on_rejected`). La interfaz está en [PRS-06](personas-oportunidades.md#prs-06) y [CAL-13](calendario-piezas.md#cal-13).
- **Criterios de aceptación:**
  1. **Dado** un contacto en `candidate`, `fit`, `followed` o `incoming`, **cuando** Gustavo lo descarta con una nota, **entonces** pasa a `discarded`, sus acciones `proposed` o `approved` pasan a `rejected` con «Persona descartada: <nota>» y la respuesta es el contacto actualizado.
  2. **Dado** una nota vacía, **cuando** envía el descarte, **entonces** recibe 400 «Indica por qué descartas a esta persona».
  3. **Dado** un contacto en `connected`, `invited`, `closed` o `discarded`, **cuando** lo intenta, **entonces** recibe 409 «Solo se descartan personas aún en curso (sin invitación ni conexión).».
  4. **Dado** una acción de la persona en `executing`, `sent` o `uncertain`, **cuando** lo intenta, **entonces** recibe 409 «Hay una acción ejecutándose para esta persona; espera a que termine.».
  5. **Dado** que Gustavo veta una acción RED-* pendiente, **cuando** se rechaza, **entonces** la persona pasa a `discarded` (salvo si ya está `connected`, `invited` o `closed`).
  6. **Dado** un token de servicio, **cuando** intenta descartar, **entonces** recibe 403.
- **Brechas código/docs:** —
- **Cobertura QA:** pendiente

### BAR-11 · Resumen de la red <a id="bar-11"></a>

- **Dónde:** PWA · app · backend
- **Estado:** funciona
- **Qué hace para Gustavo:** ve cuántas personas hay en cada etapa, cuánto cupo queda hoy y si algo está frenado.
- **Código:** `GET /api/v1/red/summary` (`red.summary`, `red_views.Summary`). La interfaz está en [PRS-01](personas-oportunidades.md#prs-01).
- **Criterios de aceptación:**
  1. **Dado** contactos en varias etapas, **cuando** se pide el resumen, **entonces** `stages` trae el recuento de `candidate`, `fit`, `discarded`, `followed`, `invited`, `connected`, `closed` e `incoming`, más `opportunity` (personas con una oportunidad abierta) y `conversation: null`.
  2. **Dado** `NETWORK_ENABLED=false`, **cuando** se pide, **entonces** `enabled` vale `false` y el resto de datos guardados sigue llegando.
  3. **Dado** lecturas de hoy, **cuando** se pide, **entonces** `reads_today` las suma por tipo, con `execution` sin tope.
  4. **Dado** gasto del clasificador, **cuando** se pide, **entonces** `llm` trae `spent_today` y `daily` como números JSON.
- **Brechas código/docs:** `stages.conversation` sigue en `null` aunque el inbox ya está implementado ([INB-01](inbox.md#inb-01)); el filtro `stage=conversation` de `/red/contacts` devuelve siempre vacío.
- **Cobertura QA:** pendiente

### BAR-12 · Aviso de conexión nueva que encaja <a id="bar-12"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Qué hace para Gustavo:** cuando alguien que encaja pasa a ser conexión, aparece en Notificaciones.
- **Código:** `red.notify_connection`, `avisar('connection_fit', …)`.
- **Criterios de aceptación:**
  1. **Dado** un contacto con `classification.fit` que pasa a `connected`, **cuando** se registra, **entonces** se guarda una Notificación `connection_fit` (capa `red`) con el titular y el rol como detalle y el enlace `/personas/<id>`, sin push por defecto.
  2. **Dado** el mismo contacto, **cuando** se vuelve a notificar, **entonces** no se duplica (`ref` único `connection:<id>`).
  3. **Dado** un contacto sin `fit`, **cuando** conecta, **entonces** no hay Notificación.
- **Brechas código/docs:** —
- **Cobertura QA:** pendiente

### BAR-13 · Aprobar acciones de red en modo aprobación <a id="bar-13"></a>

- **Dónde:** PWA · app · backend
- **Estado:** funciona
- **Qué hace para Gustavo:** si una capacidad de red está en modo aprobación, puede aprobar cada seguimiento, invitación o aceptación antes de que salga.
- **Código:** `POST /api/v1/operador/actions/<id>/approve` (`operador_views.ActionApprove`); tarjetas `approval:<id>` de Tu turno (`rediseno_views.awaiting_approval`, `_approval_card`) y filas con `awaiting_approval` en `upcoming.queued` de `/api/v1/actividad`; `useApproveAction` en `compartido/src/api/hooks.ts`; app `movil/src/turno/TurnoCard.tsx`, `movil/src/calendario/Veto.tsx` (`ApproveButton`), `ActivityList.tsx` (`QueuedRow`); PWA `pages/turno/TurnoCardView.tsx`, `pages/calendario/Veto.tsx`, `ActivityList.tsx`. `autopiloto.autonomy` deja RED-01, RED-02 y RED-04 en `approval` por defecto.
- **Criterios de aceptación:**
  1. **Dado** `OPERATOR_AUTONOMY` sin RED-01 (modo `approval` por defecto), **cuando** se crea una propuesta RED-01, **entonces** queda en `proposed` y la política no la toca.
  2. **Dado** esa propuesta, **cuando** se envía `POST …/approve` con su `expected_hash` desde una sesión humana con `approve_actions`, **entonces** pasa a `approved` y se ejecuta en su turno.
  3. **Dado** esa propuesta, **cuando** Gustavo abre Tu turno en la PWA o la app, **entonces** ve la tarjeta «¿Apruebas seguir a <persona>?» (Importante, con el plazo hasta que caduca) con «Aprobar», «Vetar» y «Ver ficha»; «Aprobar» envía su `payload_hash`, aparece «Aprobada. Sale cuando lo permitan la ventana y los topes.», la tarjeta sale y «Hecho recientemente» dice «Aprobada».
  4. **Dado** que nadie la aprueba, **cuando** pasan `OPERATOR_PROPOSAL_TTL_HOURS`, **entonces** caduca.
  5. **Dado** esa propuesta, **cuando** abre Calendario › Lista, **entonces** «En cola» la muestra primero con «Espera tu aprobación · caduca <día> a las HH:MM», «Aprobar» y «Vetar»; aprobada, pasa a «Saldrá … según el espaciado».
- **Brechas código/docs:** — (Producción está en modo `auto` para todo; el mundo de QA deja la red en `approval`.)
- **Cobertura QA:** E2E `04-tu-turno-aprobar` (criterios 3 y 5: la tarjeta de Tu turno y «En cola»). Backend `ApprovalTests`.

## Retiradas

Ninguna.
