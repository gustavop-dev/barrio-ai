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
| [BAR-14](#bar-14) | Procedencia de referentes para Relaciones y el analista | backend | no implementado |
| [BAR-15](#bar-15) | Ritmo diario, rampa semanal y configuración del operador | PWA · app · backend | no implementado |
| [BAR-16](#bar-16) | Cuenta gratuita y notas de invitación reservadas por encaje | PWA · app · backend | no implementado |

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

### BAR-14 · Procedencia de referentes para Relaciones y el analista <a id="bar-14"></a>

- **Dónde:** backend
- **Estado:** no implementado
- **Qué hace para Gustavo:** el equipo puede explicar en qué conversación de un referente encontró a una persona y qué relación tiene con la participación y el aprendizaje del barrio.
- **Responsable:** `relaciones_comunidad` usa la procedencia; `investigador_referentes` descubre/clasifica; `analista_barrio_resultados` mide.
- **Cadencia:** en cada descubrimiento, nueva evidencia y planificación de relaciones; corte semanal/mensual para el analista.
- **Tu turno:** ninguna aprobación nueva de lecturas o clasificación. Las acciones conservan su autonomía/aprobación actual, y altas/bajas de referentes siempre van por TUR-20.
- **Datos necesarios y disponibilidad:** BAR-01 ya descubre autores de comentarios de referentes; `Contact.evidence` guarda post, URL, nombre del referente y extracto, y `classification` guarda encaje. Falta historial de varias procedencias y su enlace a experimentos; reactores y seguidores identificados no están disponibles hoy ([matriz](observatorio-referentes.md#datos-conectores)).
- **Código:** no existe el historial ampliado. Referencias: `red.discover/classify/plan`, `models.Contact`, `operador.propose_comment`.
- **Criterios de aceptación:**
  1. **Dado** un contacto descubierto en el post de un referente, **cuando** Relaciones prepara su siguiente paso, **entonces** dispone del referente/post, fuente, fecha, evidencia concreta y encaje del contacto, y conserva esa procedencia en la decisión; la audiencia de un referente no equivale a su lista completa de seguidores.
  2. **Dado** una persona ya conocida que aparece en otro referente o vuelve a comentar, **cuando** se observa, **entonces** añade la evidencia al mismo contacto, sin duplicarlo ni sustituir su procedencia anterior; el analista puede reconstruir asociaciones compartidas según OBS-03.
  3. **Dado** un experimento de foco aprobado, **cuando** Relaciones planifica, **entonces** relaciona la evidencia y acciones con el experimento y mantiene clasificación, reglas, topes, pausas y veto existentes. No sigue/invita a alguien solo porque pertenece a esa audiencia ni inicia mensajes privados.
  4. **Dado** un referente dado de baja, **cuando** se revisa su audiencia, **entonces** conserva la evidencia histórica y los contactos, pero no inicia nuevos barridos de ese referente; su baja no descarta automáticamente personas que ya encajan.
  5. **Dado** identidad ambigua, comentario inaccesible o solo contador de reacciones, **cuando** se registra, **entonces** conserva la limitación y no crea una identidad ni un vínculo causal. Si en el futuro se conecta lectura de reactores, registra esa fuente separadamente tras validarla.
- **Brechas código/docs:** confirma el uso actual de comentarios de referentes (BAR-01) y añade trazabilidad/múltiples fuentes; `red.discover` hoy omite personas ya conocidas. Los criterios de biblioteca para red están en [BIB-03](biblioteca-equipos.md#bib-03).
- **Cobertura QA:** pendiente

## Política y coordinación previstas

[BIB-08](biblioteca-equipos.md#bib-08) fija el reparto literal del curso y lunes–viernes, máximo 20 invitaciones/día y 100/semana. BAR-15 incorpora la rampa desde 5/20, interacción diaria y nuevos defaults. [ARQ-02](arquitectura-agentes.md#arq-02) conserva Relaciones como orquestador y gates vigentes. Son capacidades **no implementado**; BAR-01–13 siguen describiendo el código actual.

### BAR-15 · Ritmo diario, rampa semanal y configuración del operador <a id="bar-15"></a>

- **Dónde:** PWA · app · backend
- **Estado:** no implementado
- **Qué hace para Gustavo:** el barrio recibe participación útil todos los días, con objetivo semanal de al menos unas 100 interacciones de distintos tipos tras una rampa gradual, sin ráfagas ni comentarios de relleno.
- **Responsable:** Relaciones prepara el plan; backend calcula agenda, reservas, salud y contadores; Operación es el único escritor. Investigador y analista aportan perfiles/evidencia; verificador/líder conservan reglas del curso.
- **Cadencia:** plan semanal en America/Bogota, agenda distinta por día, ejecución solo en OPERATOR_WINDOW, revisión diaria de salud y conciliación; fines de semana más ligeros, sin invitaciones salientes.
- **Tu turno:** ninguna aprobación adicional para acciones cuya autonomía sea auto; conserva veto/modos actuales. Avisos de límite, aceptación baja, meta no alcanzada y presupuesto agotado; no pide incrementar topes para completar una cuota.
- **Datos necesarios y disponibilidad:** propuestas/ejecuciones, lecturas auditadas, invitaciones/conexiones y fechas existen parcialmente. Faltan contadores unificados, cohortes de aceptación, rampa persistida, agenda aleatoria y reservas conjuntas de lecturas. No se inspeccionó el env privado del servidor; Gustavo informa que tiene overrides.
- **Código:** no existe este ritmo. Referencias actuales: `operador.DEFAULT_LIMITS/limits/within_window/min_spacing`, `autopiloto._network/_comments`, `red.plan/read_caps/invites_blocked`, `deploy/.env.example`. Hoy el espaciado es fijo (1200 s), ventana 07:00–21:00, semana ISO local; no hay rampa ni variación diaria. El conector `get_profile` lee sin notificar una visita: no se simula una visita pública.

**Defaults que deberá tener la implementación en `operador.py` (día/semana local):**

| Capacidad | Hoy en DEFAULT_LIMITS | Nuevo default de techo | Regla de uso |
| --- | --- | --- | --- |
| INT-03 · comentarios | 3 / 12 | **5 / 25** | Oportunidades diarias, calidad/aporte antes que cantidad; reglas del curso y cooldown por autor, hoy 48 h. |
| INT-02 · reacciones | 15 / 60 | **20 / 100** | Solo contenido pertinente leído; no reaccionar en serie para llenar meta. |
| CONT-09 · pieza propia | 1 / 7 | **1 / 7** | Mantener; se informa aparte, no rellena el objetivo de participación en el barrio. |
| RED-01 · seguir | 10 / 40 | **10 / 50** | Encaje y evidencia; no seguir solo por cupo. |
| RED-02 · invitar | 5 / 20 | **20 / 100** | Techo tras rampa, solo lunes–viernes; empieza efectivamente en 5 / 20. |
| RED-04 · aceptar | 10 / 40 | **10 / 40** | Solo entradas reales con encaje; no existe una meta obligatoria de aceptaciones. |

Los nuevos caps de comentarios/reacciones/seguimientos y parámetros de salud son defaults operativos elegidos para concretar el mandato; no límites oficiales ni cifras atribuidas al curso. El **techo de invitaciones 20/día, 100/semana**, interacción diaria y subida en 2–3 semanas vienen de Gustavo. Su referencia a un límite observado de LinkedIn de unas 100 invitaciones/semana (algunos proveedores hablan de hasta 200) y a unas 80–100 visitas/día es contexto aportado, no verificación de red ni garantía de capacidad de esta cuenta. No se sube a 200. No se conocen aquí límites publicados de comentarios/reacciones/follows: el proveedor puede restringir por comportamiento y sus respuestas prevalecen.

**Plan y rampa:** objetivo de actividad útil 50 → 75 → **al menos aproximadamente 100 por semana** en tres etapas de una semana como mínimo. Cuenta comentarios, reacciones, follows, invitaciones/aceptaciones confirmadas y búsquedas/lecturas de perfil hechas por investigación con propósito y resultado. Distingue acciones sociales de investigación; no cuenta borradores, fallos, resultados inciertos, lecturas de preflight/conciliación ni relecturas técnicas para inflar la meta. Un mismo perfil puede tener acciones distintas, pero cada ejecución cuenta una vez. Ejemplo de semana estable: 16 acciones útiles por día laborable y 10 por día de fin de semana = 100; no exige 100 invitaciones ni ejecutar todos los máximos simultáneamente.

Rampa RED-02: etapa 1 **5/día, 20/semana**, etapa 2 **10/50**, etapa 3 **20/100**, sin saltar por cambiar env o reintentar. Revisa diariamente y avanza solo después de al menos siete días en la etapa con salud suficiente. Default de salud: tasa de aceptación ≥40 % sobre ≥20 invitaciones únicas de cohortes con al menos siete días de maduración, enviadas en los últimos 28 días; desconocidas se muestran aparte. Sin muestra suficiente mantiene etapa, aunque tarde más de tres semanas. Tasa por debajo de 40 % o caída de ≥10 puntos porcentuales frente al último corte comparable reduce una etapa y congela crecimiento siete días; por debajo de 25 % pausa invitaciones siete días. No reduce repetidamente por el mismo corte. Son umbrales configurables de producto, no una promesa de LinkedIn.

**Errores:** 429, cuota/throttle o restricción de cuenta pausa invitaciones al menos siete días (o el plazo mayor indicado por proveedor), avisa y reanuda desde una etapa menor tras comprobar estado. El 422 con tipo `cannot_resend_yet` reportado por Gustavo bloquea ese destinatario sin reenvío, reduce una etapa y congela crecimiento; si se repite en dos destinatarios durante 24 h, aplica pausa de cuenta de siete días. Guarda código/tipo/alcance; no considera todo 422 un límite global ni prueba otro conector para eludirlo. Sin fecha válida para reinvitar a ese destinatario, queda bloqueado hasta aclararla, no se prueba periódicamente.

**Agenda:** OPERATOR_WINDOW 07:00–21:00, America/Bogota; separación común entre escrituras aleatoria **1200–2400 s**, con horas de inicio y descansos variables dentro de la ventana. Reservar/persistir `next_action_at` por cuenta para evitar que dos workers formen una ráfaga; reiniciar no sortea otra espera más corta. Plan nuevo por fecha, sin clonar la secuencia de ayer; si coincide, reprogramar antes de ejecutar. Sábado/domingo factor **0,5** sobre objetivos y caps diarios de interacción (redondeo hacia abajo), cero RED-02; no reduce CONT-09. No recuperar una cola con ráfagas al volver. Los caps son máximos, no agenda obligatoria; esta variación no garantiza ausencia de restricciones ni permite ignorarlas.

**Cambios necesarios en el env del servidor al desplegar, no ejecutados en esta tarea:**

| Configuración | Valor/delta requerido |
| --- | --- |
| `OPERATOR_DAILY_LIMITS` existente | `INT-03=5,INT-02=20,CONT-09=1,RED-01=10,RED-02=20,RED-04=10` como techos; rampa reduce RED-02 inicialmente a 5. |
| `OPERATOR_WEEKLY_LIMITS` existente | `INT-03=25,INT-02=100,CONT-09=7,RED-01=50,RED-02=100,RED-04=40`; rampa reduce RED-02 inicialmente a 20. |
| `OPERATOR_TIMEZONE`, `OPERATOR_WINDOW`, `OPERATOR_MIN_SPACING_SECONDS` existentes | `America/Bogota`, `07:00-21:00`, `1200`. Añadir `OPERATOR_MAX_SPACING_SECONDS=2400`; nunca aceptar max < min ni ventanas ilimitadas para este ritmo. |
| Nuevos OPERATOR_* de agenda | `OPERATOR_WEEKLY_ACTIVITY_TARGET=100`, `OPERATOR_ACTIVITY_RAMP_TARGETS=50,75,100`, `OPERATOR_WEEKEND_FACTOR=0.5`. Invitaciones laborables y techo 20/100 se validan también en código, aunque el env pida más. |
| Nuevos OPERATOR_* de rampa | `OPERATOR_INVITE_RAMP_ENABLED=true`, `OPERATOR_INVITE_RAMP_STAGES=5/20,10/50,20/100`, `OPERATOR_INVITE_RAMP_MIN_DAYS=7`; estado/etapa en base, no reiniciable por env. |
| Nuevos OPERATOR_* de salud | `OPERATOR_INVITE_ACCEPTANCE_MIN=0.40`, `OPERATOR_INVITE_ACCEPTANCE_PAUSE=0.25`, `OPERATOR_INVITE_ACCEPTANCE_DROP_PP=10`, `OPERATOR_INVITE_SAMPLE_MIN=20`, `OPERATOR_INVITE_MATURITY_DAYS=7`, `OPERATOR_INVITE_COHORT_DAYS=28`. |
| Lecturas de perfiles | Nuevo `OPERATOR_PROFILE_READ_DAILY_LIMIT=80`, techo duro 100 aun con overrides; cuenta lecturas de investigación, preflight, conciliación y futuras visitas entre todos los conectores. `NETWORK_READ_CAPS=comments=60,search=20,profile=80,sync=4` sustituye profile=30, subordinado al contador global; reservar margen para conciliación. Lectura actual no equivale a visita notificada. |
| Autopiloto y guardas existentes | Verificar `OPERATOR_AUTOPILOT=true`, `NETWORK_ENABLED=true` y modos de `OPERATOR_AUTONOMY` efectivos; auto para participación autorizada, sin saltar verificador/líder/veto ni `OPERATOR_PAUSED`. No levantar pausas o restricciones de cuenta al desplegar. Mantener cooldown por autor y espera de invitación salvo nueva decisión explícita. |
| Tipo de cuenta y notas, nuevos | `LINKEDIN_ACCOUNT_TIER=free` y `LINKEDIN_INVITE_NOTE_MONTHLY_LIMIT=3`, tope prudente de producto, no cuota garantizada por LinkedIn. [BAR-16](#bar-16) define reservas, límites efectivos y fallback. Un upgrade no sube los techos generales ni salta la rampa. |
| Gasto | `EDITORIAL_DAILY_LLM_USD=2` y cap total de pieza ARQ-05; referentes 5 USD/mes y Perfil 10 USD por ciclo en registro. `OPERATOR_DAILY_LLM_USD=1` y `NETWORK_DAILY_LLM_USD=0.3` siguen como defaults de comentarios/clasificación, sin subirlos para forzar 100 acciones. |

Inventariar únicamente estas claves permitidas del env real sin copiar secretos, reconciliar overrides antiguos con los nuevos techos y actualizar los dos `.env.example` durante implementación. Mostrar efectivos, rampa y discrepancias antes de activar. No basta cambiar DEFAULT_LIMITS si siguen overrides 3/12, 15/60 o 5/20; tampoco se aplica el techo 20/100 saltando el estado inicial 5/20.

- **Criterios de aceptación:**
  1. **Dado** una cuenta sana en etapa estable con candidatos/recursos suficientes, **cuando** planifica la semana, **entonces** programa actividad útil todos los días y objetivo ≥100 entre tipos, con comentario diario pertinente, fin de semana más ligero y RED-02 solo laborable. Sin material de calidad, datos o presupuesto muestra el déficit y motivo, no genera relleno ni lecturas artificiales.
  2. **Dado** activación desde 5/20, **cuando** aplica los nuevos defaults/env, **entonces** RED-02 permanece en 5/20 hasta cumplir etapa/salud; después 10/50 y 20/100. Sin muestra madura mantiene etapa; rechazo/error/degradación aplica reducción o pausa y notifica sin intervención de Gustavo.
  3. **Dado** config 30/día o 200/semana y dos workers concurrentes, **cuando** reservan/envían, **entonces** el mínimo entre rampa, 20/100, env válido, reservas y límites del proveedor impide excesos. Un fin de semana bloquea RED-02 aunque haya aprobación previa.
  4. **Dado** cohortes de 20 maduras con 10 aceptadas y otras 15 recién enviadas, **cuando** calcula salud, **entonces** muestra 50 % sobre 20 y las 15 inmaduras aparte, sin contar perfiles repetidos. Una caída válida de 10 puntos o bajo 40 % reduce; no inventa tasa si falta conciliación.
  5. **Dado** 422 `cannot_resend_yet`, **cuando** lo registra, **entonces** bloquea al destinatario, frena la rampa y aplica la regla de repetición/alcance anterior; un 429 de cuenta activa la pausa correspondiente. No reenvía por otro conector ni presenta un fallo como interacción realizada.
  6. **Dado** agenda de varios tipos y jobs simultáneos, **cuando** ejecuta, **entonces** todos comparten reserva horaria, huecos aleatorios y ventana colombiana; no hay ráfagas, repetición diaria de patrón ni recuperación acelerada de atrasos. La espera se mantiene al reanudar y una pausa prevalece sobre cualquier meta.
  7. **Dado** 79 lecturas de perfil consumidas y dos operaciones listas, **cuando** reservan con cap 80, **entonces** solo una sale. Clasificación, preflight y conciliación comparten contador por request; no se salta con otra cuenta/conector ni se contabiliza dos veces una llamada. Si no cabe una comprobación requerida, la escritura espera.
  8. **Dado** el corte semanal, **cuando** informa, **entonces** desglosa social/investigación, acciones confirmadas, personas únicas, aceptación/cohortes, cupos, gasto, déficits y causas. No llama visitas públicas a `get_profile`, seguidores a conexiones ni ventas a invitaciones.
  9. **Dado** servidor con overrides antiguos o rampa ausente, **cuando** se valida el despliegue, **entonces** muestra la diferencia con la tabla y no declara aplicado este ritmo hasta resolver configuración/estado, manteniendo pausas/gates. El proceso no registra claves de proveedor ni el contenido completo del env.
  10. **Dado** una salida pública propuesta por el plan, **cuando** pasa la verificación, **entonces** comentarios, posts, artículos, texto de imágenes y perfil están en **inglés**; contenido pendiente en otro idioma se corrige antes de publicar. Nombres propios/fuentes no se falsifican y la interfaz interna puede seguir en español.
- **Brechas código/docs:** nueva orquestación de ritmo y observabilidad; no están implementados los OPERATOR_* nuevos ni el contador global de lecturas. Los caps/tablas de BAR-08 describen hoy, esta ficha describe su evolución. Se respetan las fuentes/datos disponibles y no se verifica aquí la capacidad actual de Unipile/LinkedIn por red.
- **Cobertura QA:** pendiente

### BAR-16 · Cuenta gratuita y notas de invitación reservadas por encaje <a id="bar-16"></a>

- **Dónde:** PWA · app · backend
- **Estado:** no implementado
- **Qué hace para Gustavo:** usa su cuenta gratuita principalmente con invitaciones sin nota y reserva las pocas notas personalizadas para las personas de mayor encaje, explicando el motivo.
- **Responsable:** `relaciones_comunidad` selecciona y justifica; investigador/clasificador aporta evidencia; verificador y líder/Jev revisan el texto; `operador_cuenta` es el único escritor. Código controla tier, saldo, reservas, fallback y auditoría.
- **Cadencia:** plan diario de lunes a viernes dentro de BAR-15; saldo de notas mensual por cuenta, revisado antes de cada envío y al cambiar tier o recibir restricciones. Las notas no aumentan la frecuencia de invitaciones.
- **Tu turno:** no se pide aprobar cada invitación bajo la autonomía ya autorizada. En modo aprobación se muestra texto exacto, razón de gastar nota y alternativa sin nota; Gustavo conserva veto. Avisos por discrepancia de tier o límites incluyen estado y acción necesaria, sin proponer comprar Premium automáticamente.
- **Datos necesarios y disponibilidad:** Gustavo confirma **free**, sin Premium ni Sales Navigator; clasificación/razón/confianza, propuestas e invitaciones existen. El conector y la validación hoy solo aceptan `user_id`, sin nota. Faltan tier configurable, texto opcional validado, saldo/reservas y error tipado de cuota de notas. Los comentarios del conector documentan «unas pocas al mes»; no existe lectura integrada de cuota restante ni una cifra universal verificada. La API oficial conectada no aporta aquí esa capacidad.
- **Código:** evolución futura de `operador.validate_payload`, gates/ejecución, `connectors.UnipileConnector.send_invitation`, conector simulado y `red.invites_blocked`. [BAR-05](#bar-05) y [BAR-09](#bar-09) describen el comportamiento actual; esta ficha amplía el contrato, sin cambiarlo en esta tarea.
- **Configuración y política:** `LINKEDIN_ACCOUNT_TIER=free|premium|sales_navigator`, default **free**; valor desconocido falla validación. No inferir upgrade por volumen de actividad. `LINKEDIN_INVITE_NOTE_MONTHLY_LIMIT=3` es un default conservador de producto por mes natural America/Bogota, configurable y válido también como 0 para deshabilitar notas; **no afirma que LinkedIn conceda tres**. El límite efectivo es el menor entre configuración y disponibilidad/restricciones verificadas del proveedor. Si no se conoce su saldo, mostrar «Desconocido» y permitir solo intentos reservados dentro del cap local, nunca anunciar tres notas disponibles. Agotamiento confirmado cierra notas hasta el reinicio acreditado por el proveedor; cambiar el mes local o reiniciar un job no borra ese bloqueo. En Premium/Sales Navigator se adapta la validación de notas (longitud/cupo) a capacidades verificadas del tier, manteniendo el cap local anterior hasta configurar uno sustentado; nunca asumir notas ilimitadas ni alterar la distribución del curso, la rampa o el techo general 20/100.
- **Riesgo y exclusividad:** **no lemlist ni otra herramienta de automatización de outreach junto a 0ff1ce**, tampoco tras un upgrade. Duplicaría invitaciones/acciones y la actividad automática sobre la cuenta, fuera de sus reservas y auditoría. Registrar esta condición al activar/cambiar cuenta; si se conoce una automatización paralela activa, pausar el outreach de 0ff1ce y avisar hasta que esté desactivada. No se instala ni conecta ninguna herramienta alternativa.
- **Criterios de aceptación:**
  1. **Dado** la cuenta gratuita actual y una invitación ordinaria, **cuando** Relaciones la planifica, **entonces** propone la invitación sin nota por defecto. No añade un saludo genérico para consumir saldo ni interpreta free como imposibilidad de invitar sin nota.
  2. **Dado** candidatos de alto encaje y saldo local reservable, **cuando** selecciona una excepción con nota, **entonces** prioriza los de mayor encaje sustentado en clasificación/evidencia vigente y explica por qué merece gastar ese cupo frente a invitar sin nota. Cita `NETWORK_UNITS`, especialmente `LI-03-M006-K01` (conexión sin pitch); la nota es breve, pertinente, en inglés y sin hechos inventados. Conserva el reparto por papeles de BIB-08 y no consume cupo para cumplir una cuota de notas.
  3. **Dado** varias propuestas con nota y workers concurrentes, **cuando** reservan, **entonces** deduplican por cuenta/destinatario/propósito y restan consumidas, reservadas y envíos inciertos del saldo local; con cap 3, la cuarta usa la alternativa sin nota. El ledger diferencia intento rechazado, envío confirmado y resultado incierto, con fuente del límite, periodo, tier y motivo de selección; no afirma consumo del proveedor sin evidencia.
  4. **Dado** un rechazo inequívoco **solo por cuota de notas** y confirmación de que no se creó invitación, **cuando** el operador procesa el error, **entonces** bloquea nuevas notas, registra motivo y programa esa misma invitación **sin nota**, bajo los mismos gates, veto, ventana, espaciado, preflight y límites RED-02. Vincula ambos intentos a una sola intención; solo el envío real cuenta como invitación realizada. La aprobación de la variante con nota incluye esta alternativa explícita; no exige otra decisión por quitarla.
  5. **Dado** timeout, respuesta ambigua, invitación ya pendiente o error de límite general/429/422 `cannot_resend_yet`, **cuando** considera el fallback, **entonces** no reenvía automáticamente sin nota. Concilia primero una posible escritura; si no puede descartarla, conserva la reserva y espera. Límites generales y destinatario bloqueado siguen BAR-15; un error genérico que contiene «quota» no basta para clasificarlo como cuota de notas ni eludir una pausa.
  6. **Dado** un upgrade o downgrade confirmado, **cuando** cambia `LINKEDIN_ACCOUNT_TIER`, **entonces** audita valor anterior/nuevo, actor, fecha y evidencia de capacidades, adapta política/validación y recalcula propuestas pendientes antes de enviarlas. Mantiene reservas, consumos, restricciones y rampas; un tier de pago no aumenta por sí solo volumen, gasto o longitud de notas. Si el proveedor contradice la configuración, usa la capacidad más restrictiva y avisa.
  7. **Dado** agotamiento de notas sin restricción general de invitaciones, **cuando** sigue el plan, **entonces** continúa con invitaciones sin nota elegibles y registra el fallback en actividad/auditoría. No aplica la pausa general BAR-09 a un error específico de notas ya clasificado; nunca evita una pausa de cuenta vigente.
  8. **Dado** despliegue o evidencia de outreach externo concurrente, **cuando** se valida la cuenta, **entonces** la configuración visible muestra tier efectivo, cupo local/observado, política sin nota y operador único. El riesgo conocido de lemlist/otra automatización activa bloquea la activación o pausa el outreach, con aviso; no se declara comprobada su ausencia mediante una API que no permite verla.
- **Brechas código/docs:** tier, notas excepcionales, reservas y distinción de errores no existen. Verificar códigos/campos reales con contrato del proveedor durante implementación y usar fixtures de rechazo inequívoco/ambiguo; no inventar hoy un código específico ni una cuota oficial. Actualizar ejemplos de env y overrides permitidos junto con BAR-15, sin leer ni modificar secretos en esta tarea.
- **Cobertura QA:** pendiente

## Retiradas

Ninguna.
