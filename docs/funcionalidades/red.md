# Red del barrio (`BAR`)

El equipo descubre personas que encajan con Gustavo, las clasifica, las sigue, las invita sin nota y acepta las invitaciones que encajan. Gustavo puede descartar a cualquiera. La interfaz de Personas que muestra a estas personas está en [personas-oportunidades.md](personas-oportunidades.md).

- **Código:** `agentes-linkedin/infra/src/team_backend/red.py`, `red_views.py`, `autopiloto._network`, `operador.execute` (capacidades `RED-01`, `RED-02`, `RED-04`).
- **Documentación:** [`red-barrio.md`](../../agentes-linkedin/infra/docs/red-barrio.md), sección «Red» de [`CONTRATO-API.md`](../../oficina/CONTRATO-API.md).
- **Entorno de prueba:** `NETWORK_ENABLED=true` (por defecto `false`), cuenta `fake` con `OPERATOR_ALLOW_FAKE=true` y el clasificador parcheado, como en `tests/test_red.py`.

## Resumen

| ID | Función | Dónde | Estado |
| Organizaciones, fase 6 (18/11/2026, [ORG-28 a ORG-33](organizaciones.md#org-28)): con dos o más miembros activos el barrio
es de la organización. Una persona es una ficha (`registro.py`): se descubre y se clasifica una vez, la atiende quien la
toca primero (seguir, invitar, aceptar, comentar su post, responderle) y el otro miembro no la toca; dos o tres por empresa,
nunca dos del mismo cargo; los referentes se leen una vez y cada post lo comenta un solo miembro; los candidatos sin dueño se
reparten (afinidad, preferencia de rol opcional, hash estable); los perfiles de los colegas nunca son prospectos. Con un solo
miembro todo lo de esta página sigue igual.

--- | --- | --- | --- |
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
| [BAR-14](#bar-14) | Procedencia de referentes para Relaciones y el analista | backend | funciona |
| [BAR-15](#bar-15) | Ritmo diario, rampa semanal y configuración del operador | PWA · app · backend | no implementado |
| [BAR-16](#bar-16) | Cuenta gratuita y notas de invitación reservadas por encaje | PWA · app · backend | no implementado |

| [BAR-15](#bar-15) | Ritmo, rampa, salud y reservas compartidas | backend | funciona |
| [BAR-16](#bar-16) | Tier y notas excepcionales con alternativa sin nota | backend | funciona |
| [BAR-17](#bar-17) | Barrio en EE. UU.: más invitaciones, compradores con ronda semilla y dudas del líder para Gustavo | app · backend | funciona |
| [BAR-18](#bar-18) | Recorrido del comprador y embudo mínimo (outbound, fase 1) | backend | funciona |
| [BAR-19](#bar-19) | Calentamiento del comprador: leer, comentar dos veces e invitar (outbound, fase 2) | backend | implementado, apagado |
| [BAR-20](#bar-20) | Primer mensaje al aceptar y nota de invitación para calentados (outbound, fase 3) | backend · Tu turno | implementado, apagado |
| [BAR-21](#bar-21) | Secuencia de mensajes 2 a 4 para el comprador que no respondió (outbound, fase 4) | backend · Tu turno | implementado, apagado |
| [BAR-22](#bar-22) | La ruta del comprador que no publica: el puente por su empresa y los reintentos (outbound, fase 5) | backend | implementado, apagado |
| [BAR-23](#bar-23) | Su respuesta, el enlace de agenda (Cal.com), la entrega del lead y la lectura semanal del embudo (outbound, fase 6) | backend · Tu turno | implementado, apagado |
| [BAR-24](#bar-24) | Compradores por niveles y con puntaje, Latinoamérica después de EE. UU. y cupos blandos por papel | backend · API | funciona |
| [BAR-25](#bar-25) | El comprador de ProjectApp, el partner y la prueba de tres meses por segmento | backend · API · PWA | implementado, apagado |

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
  4. **Dado** que se agotó el presupuesto de IA del equipo (`AI_MONTHLY_LIMIT_USD` o el tope de seguridad diario `AI_DAILY_FUSE_USD`), **cuando** toca clasificar, **entonces** falla con «Presupuesto de IA agotado (AI_MONTHLY_LIMIT_USD o AI_DAILY_FUSE_USD).» y el autopiloto no encola la clasificación.
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
  1. **Dado** un contacto `followed` hace 49 h, **cuando** corre `plan_network`, **entonces** se propone RED-02 con `{user_id}` por defecto; las notas excepcionales siguen BAR-16 y el calendario/rampa BAR-15.
  2. **Dado** un contacto `followed` hace 47 h, **cuando** corre, **entonces** no se propone.
  3. **Dado** una propuesta RED-02 con nota, **cuando** la revisa la compuerta, **entonces** exige el contrato BAR-16: razón, alternativa sin nota, validación de texto y revisión del líder; campos desconocidos se rechazan.
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
  5. **Dado** que la ejecución no escribió, **cuando** se calculan topes, **entonces** no consume cupo de escritura; la espera aleatoria ya reservada se conserva para evitar ráfagas de reintentos.
  6. **Dado** un resultado incierto, **cuando** se concilia, **entonces** se relee el perfil y nunca se repite la escritura.
- **Brechas código/docs:** —
- **Cobertura QA:** pendiente

### BAR-08 · Topes de lectura, de escritura y de gasto <a id="bar-08"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Qué hace para Gustavo:** la red trabaja dentro de límites conservadores para no arriesgar su cuenta.
- **Código:** `red.read_caps`, `red._read`, `operador.limits`, `operador.capacity_left`, `operador.spacing_ok`. Desde la
  fase 2 de organizaciones todos son **de cada miembro** ([ORG-10](organizaciones.md#org-10)): sus cuentas comparten sus
  topes, su espaciado y su contador de lecturas de perfil; otro miembro tiene los suyos. El gasto de IA sigue siendo de
  toda la organización.
- **Criterios de aceptación:**
  1. **Dado** los topes por defecto, **cuando** se consulta `GET /api/v1/red/summary`, **entonces** `capacity` muestra RED-01 20/día y 100/semana, RED-02 según etapa (inicialmente 16 y 80, [BAR-17](#bar-17)), RED-04 10 y 40, y `read_caps` muestra `comments` 60, `search` 20, `profile` 80, `sync` 4. Fin de semana y reservas compartidas siguen BAR-15.
  2. **Dado** que se agotó el cupo de lecturas de perfil, **cuando** toca clasificar, **entonces** se detiene y lo dice en su error; el preflight usa además el contador global compartido y, si este se agota, la escritura espera sin saltarse la comprobación.
  3. **Dado** una escritura de red, un comentario y una publicación del mismo miembro, **cuando** se programan, **entonces** comparten su espaciado mínimo; las de otro miembro no lo esperan.
  4. **Dado** el cupo de 80 con 0,4 y la investigación con sus 32 gastadas a media mañana, **cuando** toca seguir o invitar antes de las 17:00, **entonces** la comprobación y la relectura salen de las 48 de las acciones. Las acciones nunca prestan a la investigación antes del corte. Después del corte, lo que sobró de una parte es de la otra, y el total sigue en 80 (18/11/2026).
  5. **Dado** que las acciones se quedaron sin lecturas antes de las 17:00, **cuando** corre el vigilante de Slack, **entonces** avisa una vez ese día con las dos partes y cómo ajustarlas.
- **Partes del cupo de lecturas de perfil (18/11/2026):**
  - **Qué pasó:** el 18/11/2026 el cupo de 80 se agotó a las 13:04: investigación 41, ejecución 17, preflight 16, conciliación 5, métricas 1. Después no salió ningún follow ni invitación: 3 y 2 ese día, contra 9 y 15 el anterior.
  - **Cómo queda (`operador.reserve_profile_read`, `operador.profile_read_pools`):**
    - Las lecturas que protegen o confirman una escritura tienen su parte: `preflight`, `execution` y `reconciliation` (`operador.ACTION_READS`).
    - Todas las demás (investigación de candidatos, referentes, métricas, posts de compradores, respuestas, comunidad…) tienen `OPERATOR_PROFILE_READ_RESEARCH_SHARE` del cupo del miembro. Con 80 y 0,4: 32 para investigar y 48 para las acciones.
    - Antes de `OPERATOR_PROFILE_READ_POOL_CUTOFF` (17:00, hora local) ninguna parte toma la otra. Desde esa hora, lo que una dejó es de la otra. `00:00` vuelve a un solo total.
    - El total no sube. Cada miembro tiene sus partes: la parte se fija por miembro (`manage.py operador ajustes`, de 0,1 a 0,9; un valor malo del `.env` vale 0,4 y nunca detiene las lecturas).
    - Cada lectura guarda su parte (`pool`) y, si es de una ejecución, su paso (`step`: `confirmacion` o `conciliacion`). El mensaje de espera nombra la parte agotada y la hora del corte.
  - **Por qué 0,4:** una acción escrita gasta 2 lecturas (la comprobación antes de escribir y la relectura que confirma). La que no escribe (ya lo sigues, invitación pendiente, fuera de alcance) gasta 1. Para 16–20 invitaciones y unos 10 follows al día hacen falta unas 52–60 lecturas en el peor caso y 35–45 en un día normal, más la conciliación. 48 cubren el día normal, y lo que la investigación deja pasa a las 17:00. Con 32 la investigación clasifica unas 30 personas al día (el 18/11 usó 41).
  - **Por qué cada acción leía tanto (16 + 17 lecturas para 5 acciones):**
    - Son dos lecturas por diseño: la comprobación antes de escribir y la relectura que confirma. Una lectura de horas antes no sirve como comprobación: no dice si ahora hay una invitación pendiente, si ya es conexión o si el perfil está restringido. No se reutiliza.
    - Cada ejecución que no escribe gasta su comprobación, y cada reintento diferido (`operador._defer`) gasta otra.
    - Una escritura que LinkedIn aún no muestra (`sent`) se releía cada hora durante 24 h: hasta 24 lecturas de «ejecución» cada una.
  - **Ahorros aplicados:**
    - **Conciliación con espera creciente (`autopiloto.reconcile_due`):** se relee a los 10 min y después cuando lleva esperando al menos lo mismo (1 h, 1,5 h, 3 h, 6 h, 12 h). Son 6 lecturas en 24 h en vez de 24.
    - **La comprobación no leída se devuelve (`operador.release_unread_preflight`):** si la ejecución no llegó a leer (cuenta detenida, el proveedor difirió antes, una compuerta paró una aceptación), la reserva queda como `operator.profile_read_unused` y no cuenta.
    - **Prefiltro por titular (`red.headline_settles`):** un reclutador, estudiante, pasante o quien busca empleo, sin un titular de founder o dueño, se clasifica por el titular sin gastar la lectura de señales.
    - Revisado y sin cambio: nadie ya clasificado se relee (la cola es `classification={}`), la clasificación compartida entre miembros no lee, y la sincronización solo relee a quien salió de la lista de invitaciones enviadas.
  - **Aviso:** `alertas_slack.acciones_sin_lecturas` avisa una vez al día si las acciones se quedaron sin lecturas antes del corte. El resumen diario trae las dos partes.
- **Brechas código/docs:** cuánto ahorra cada cambio en producción solo se ve con los eventos del día (consultas en `agentes-linkedin/infra/tasks/active_context.md`).
- **Cobertura QA:** `tests/test_fase2_curso.py` (`ProfileReadPoolTests`, la conciliación con espera creciente), `tests/test_red.py` (prefiltro por titular), `tests/test_alertas_slack.py` (`ProfileReadPartsAlertTests`). Corridas en local con conectores falsos y reloj fijo; la regresión completa corre en CI.

### BAR-09 · Pausa de invitaciones si LinkedIn las limita <a id="bar-09"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Qué hace para Gustavo:** si LinkedIn rechaza una invitación por límite, el equipo deja de invitar siete días y se lo dice.
- **Código:** `red.invites_blocked`, `red.network_issues`, `GET /api/v1/red/summary` (`invites_blocked`). Desde la fase 2
  de organizaciones el bloqueo es **del miembro** a quien LinkedIn frenó ([ORG-11](organizaciones.md#org-11)); a la persona
  rechazada no la vuelve a invitar nadie de la organización.
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
- **Qué hace para Gustavo:** ve cuántas personas hay en cada etapa, cuántas conexiones tiene por etiqueta, cuánto cupo queda hoy y si algo está frenado.
- **Código:** `GET /api/v1/red/summary` (`red.summary`, `red_views.Summary`). La interfaz está en [PRS-01](personas-oportunidades.md#prs-01).
- **Criterios de aceptación:**
  1. **Dado** contactos en varias etapas, **cuando** se pide el resumen, **entonces** `stages` trae el recuento de `candidate`, `fit`, `discarded`, `followed`, `invited`, `connected`, `closed` e `incoming`, más `opportunity` (personas con una oportunidad abierta) y `conversation: null`.
  2. **Dado** conexiones con y sin rol del barrio, **cuando** se pide el resumen, **entonces** `connections` trae `{ total, roles }`, con `roles` por `classification.role` y `sin_etiqueta` para quien no tiene: son los chips de Personas › Conexiones ([PRS-01](personas-oportunidades.md#prs-01)).
  3. **Dado** `NETWORK_ENABLED=false`, **cuando** se pide, **entonces** `enabled` vale `false` y el resto de datos guardados sigue llegando.
  4. **Dado** lecturas de hoy, **cuando** se pide, **entonces** `reads_today` las suma por tipo, con `execution` sin tope.
  5. **Dado** gasto del clasificador, **cuando** se pide, **entonces** `llm` trae `spent_today` y `daily` como números JSON; `daily` es el tope de seguridad diario de todo el equipo (`AI_DAILY_FUSE_USD`), no uno propio de la red.
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
- **Estado:** funciona
- **Qué hace para Gustavo:** el equipo puede explicar en qué conversación de un referente encontró a una persona y qué relación tiene con la participación y el aprendizaje del barrio.
- **Responsable:** `relaciones_comunidad` usa la procedencia; `investigador_referentes` descubre/clasifica; `analista_barrio_resultados` mide.
- **Cadencia:** en cada descubrimiento, nueva evidencia y planificación de relaciones; corte semanal/mensual para el analista.
- **Tu turno:** ninguna aprobación nueva de lecturas o clasificación. Las acciones conservan su autonomía/aprobación actual, y altas/bajas de referentes siempre van por TUR-20.
- **Datos necesarios y disponibilidad:** BAR-01 alimenta `PersonEvidence` antes de filtrar candidatos a invitación. Conserva personas ya conocidas, comentarios repetidos con ids diferentes y varios referentes; no reemplaza `Contact.evidence`. `FitClassification` conserva criterio/fecha/umbral/suficiencia, y `experiment_id` permite enlazar evidencia y decisiones futuras. Reactores y seguidores identificados automáticamente siguen ausentes ([matriz](observatorio-referentes.md#datos-conectores)).
- **Código:** `evidencia.referent_comments/relationship/contact_context/consult`; `red.discover/classify/_propose/sync/on_confirmed`; `operador.run_job`, `operador_views.ReferentDetail`; migración `0023_shared_evidence`. El grafo declara el servicio y su arista desde Relaciones. Las propuestas conservan los ids/fechas/fuentes y posibles ids de experimento en `review.case_evidence.provenance`.
- **Criterios de aceptación:**
  1. **Dado** un contacto descubierto en el post de un referente, **cuando** Relaciones prepara su siguiente paso, **entonces** dispone del referente/post, fuente, fecha, evidencia concreta y encaje del contacto, y conserva esa procedencia en la decisión; la audiencia de un referente no equivale a su lista completa de seguidores.
  2. **Dado** una persona ya conocida que aparece en otro referente o vuelve a comentar, **cuando** se observa, **entonces** añade la evidencia al mismo contacto, sin duplicarlo ni sustituir su procedencia anterior; el analista puede reconstruir asociaciones compartidas según OBS-03.
  3. **Dado** un experimento de foco aprobado, **cuando** Relaciones planifica, **entonces** relaciona la evidencia y acciones con el experimento y mantiene clasificación, reglas, topes, pausas y veto existentes. No sigue/invita a alguien solo porque pertenece a esa audiencia ni inicia mensajes privados.
  4. **Dado** un referente dado de baja, **cuando** se revisa su audiencia, **entonces** conserva la evidencia histórica y los contactos, pero no inicia nuevos barridos de ese referente; su baja no descarta automáticamente personas que ya encajan.
  5. **Dado** identidad ambigua, comentario inaccesible o solo contador de reacciones, **cuando** se registra, **entonces** conserva la limitación y no crea una identidad ni un vínculo causal. Si en el futuro se conecta lectura de reactores, registra esa fuente separadamente tras validarla.
- **Límites conservados:** añadir evidencia no cambia clasificación operativa, reglas, caps, gates ni veto. Quitar un referente archiva (`active=false`, `archived_at`), oculta su ficha y conserva posts/personas/evidencia; una alta explícita restaura el mismo id. No se recuperan procedencias perdidas antes de fase 4 ni se unen personas por nombres/prefijos. Los experimentos aprobados y sus planes se implementan en fase 5; este servicio conserva su referencia. Criterios de biblioteca: [BIB-03](biblioteca-equipos.md#bib-03).
- **Cobertura QA:** `test_evidencia.py`, regresiones de red/métricas/resumen/grafo y caso del harness `OBS-03-BAR-14-evidencia`. Claude ejecuta CI y sesión QA en vivo: `[qa: 03 08-resultados 09-personas 11 13-referentes 17-mapa-equipo]`; no se ejecutaron suites locales.

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
| Lecturas de perfiles | Nuevo `OPERATOR_PROFILE_READ_DAILY_LIMIT=80`, techo duro 100 aun con overrides; cuenta lecturas de investigación, preflight, conciliación y futuras visitas entre todos los conectores. `NETWORK_READ_CAPS=comments=60,search=20,profile=80,sync=4` sustituye profile=30, subordinado al contador global; reservar margen para conciliación. Lectura actual no equivale a visita notificada. Desde el 18/11/2026 el cupo se parte entre acciones e investigación ([BAR-08](#bar-08)). |
| Autopiloto y guardas existentes | Verificar `OPERATOR_AUTOPILOT=true`, `NETWORK_ENABLED=true` y modos de `OPERATOR_AUTONOMY` efectivos; auto para participación autorizada, sin saltar verificador/líder/veto ni `OPERATOR_PAUSED`. No levantar pausas o restricciones de cuenta al desplegar. Mantener cooldown por autor y espera de invitación salvo nueva decisión explícita. |
| Tipo de cuenta y notas, nuevos | `LINKEDIN_ACCOUNT_TIER=free` y `LINKEDIN_INVITE_NOTE_MONTHLY_LIMIT=3`, tope prudente de producto, no cuota garantizada por LinkedIn. [BAR-16](#bar-16) define reservas, límites efectivos y fallback. Un upgrade no sube los techos generales ni salta la rampa. |
| Gasto | Desde el 10/11/2026, un solo presupuesto de IA para todo el equipo (`AI_MONTHLY_LIMIT_USD=100` y el tope de seguridad diario `AI_DAILY_FUSE_USD=15`, `knowledge/presupuesto.py`), sin topes diarios por área. Caps del registro ARQ-05: pieza 8 USD por ciclo, referentes 5 USD/mes y Perfil 10 USD por ciclo. No subirlos para forzar 100 acciones. |

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
- **Brechas código/docs:** nueva orquestación de ritmo y observabilidad; no están implementados los OPERATOR_* nuevos ni el contador global de lecturas. Los caps/tablas de BAR-08 describen hoy, esta ficha describe su evolución. Se respetan las fuentes/datos disponibles y no se verifica aquí la capacidad actual de LinkedIn directo por red.
- **Cobertura QA:** pendiente

### BAR-16 · Cuenta gratuita y notas de invitación reservadas por encaje <a id="bar-16"></a>

- **Dónde:** PWA · app · backend
- **Estado:** no implementado
- **Qué hace para Gustavo:** usa su cuenta gratuita principalmente con invitaciones sin nota y reserva las pocas notas personalizadas para las personas de mayor encaje, explicando el motivo.
- **Responsable:** `relaciones_comunidad` selecciona y justifica; investigador/clasificador aporta evidencia; verificador y líder/Jev revisan el texto; `operador_cuenta` es el único escritor. Código controla tier, saldo, reservas, fallback y auditoría.
- **Cadencia:** plan diario de lunes a viernes dentro de BAR-15; saldo de notas mensual por cuenta, revisado antes de cada envío y al cambiar tier o recibir restricciones. Las notas no aumentan la frecuencia de invitaciones.
- **Tu turno:** no se pide aprobar cada invitación bajo la autonomía ya autorizada. En modo aprobación se muestra texto exacto, razón de gastar nota y alternativa sin nota; Gustavo conserva veto. Avisos por discrepancia de tier o límites incluyen estado y acción necesaria, sin proponer comprar Premium automáticamente.
- **Datos necesarios y disponibilidad:** Gustavo confirma **free**, sin Premium ni Sales Navigator; clasificación/razón/confianza, propuestas e invitaciones existen. El conector y la validación hoy solo aceptan `user_id`, sin nota. Faltan tier configurable, texto opcional validado, saldo/reservas y error tipado de cuota de notas. Los comentarios del conector documentan «unas pocas al mes»; no existe lectura integrada de cuota restante ni una cifra universal verificada. La API oficial conectada no aporta aquí esa capacidad.
- **Código:** evolución futura de `operador.validate_payload`, gates/ejecución, `linkedin_directo/cliente.py` (`send_invitation`, que ya acepta una nota de hasta 300 caracteres), conector simulado y `red.invites_blocked`. [BAR-05](#bar-05) y [BAR-09](#bar-09) describen el comportamiento actual; esta ficha amplía el contrato, sin cambiarlo en esta tarea.
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

## Participación: fase 2

Implementación en archivos; CI pendiente. Se conservan los criterios copiados de la especificación como contrato de revisión. El alcance de esta rama es backend.

Desde la fase 2 de organizaciones (17/11/2026) el ritmo de BAR-15 (topes, espaciado, agenda del día, rampa y su salud,
lecturas de perfil, bloqueos del proveedor) y el tier y las notas de BAR-16 son **de cada miembro**: el primer miembro
conserva el estado de antes (`target='member'`) y otro empieza el suyo (`target='member:<id>'`). Cada miembro puede tener
sus propios valores de `OPERATOR_DAILY_LIMITS`, `OPERATOR_WEEKLY_LIMITS`, `OPERATOR_INVITE_RAMP_STAGES`, el nuevo
`OPERATOR_INVITE_RAMP_START`, `OPERATOR_PROFILE_READ_DAILY_LIMIT`, `LINKEDIN_ACCOUNT_TIER`,
`LINKEDIN_INVITE_NOTE_MONTHLY_LIMIT`, `OPERATOR_AUTONOMY` y `EDITORIAL_POST_TIME` (`manage.py operador ajustes`); sin
ellos vale el `.env`. Ver [ORG-10 a ORG-12](organizaciones.md#org-10).

### BAR-15 · Ritmo diario, rampa semanal y configuración del operador <a id="bar-15"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Qué hace para Gustavo:** el barrio recibe participación útil todos los días, con objetivo semanal de al menos unas 100 interacciones de distintos tipos tras una rampa gradual, sin ráfagas ni comentarios de relleno.
- **Responsable:** Relaciones prepara el plan; backend calcula agenda, reservas, salud y contadores; Operación es el único escritor. Investigador y analista aportan perfiles/evidencia; verificador/líder conservan reglas del curso.
- **Cadencia:** plan semanal en America/Bogota, agenda distinta por día, ejecución solo en OPERATOR_WINDOW, revisión diaria de salud y conciliación; fines de semana más ligeros, sin invitaciones salientes.
- **Tu turno:** ninguna aprobación adicional para acciones cuya autonomía sea auto; conserva veto/modos actuales. Avisos de límite, aceptación baja, meta no alcanzada y presupuesto agotado; no pide incrementar topes para completar una cuota.
- **Datos de partida de la especificación:** propuestas/ejecuciones, lecturas auditadas, invitaciones/conexiones y fechas existen parcialmente. Faltan contadores unificados, cohortes de aceptación, rampa persistida, agenda aleatoria y reservas conjuntas de lecturas. No se inspeccionó el env privado del servidor; Gustavo informa que tiene overrides.
- **Código:** `operador.py`, `red.py`, `lider.py`, `metricas.py`, `resumen_semanal.py`; extensión mínima de notas y error tipado en `connectors.py`. Estado persistente en AuditEvent y exclusión transaccional mediante OperatorControl; sin migración.

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

**Despliegue:** [nota de fase 2](../despliegue-fase2-curso.md), con nombres de claves y validaciones pendientes; no se leyó el env privado.

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
- **Validación pendiente:** CI debe ejecutar los fakes y comprobar el contrato real de notas con una fixture redactada del proveedor. Solo el rechazo explícito de nota, con certeza de no creación, habilita fallback. UI y capacidades de perfil/imagen de otras fases no se amplían aquí.
- **Cobertura QA:** `test_fase2_curso.py` y regresiones de red/operador; ejecución pendiente de CI, no ejecutada localmente.

### BAR-16 · Cuenta gratuita y notas de invitación reservadas por encaje <a id="bar-16"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Qué hace para Gustavo:** usa su cuenta gratuita principalmente con invitaciones sin nota y reserva las pocas notas personalizadas para las personas de mayor encaje, explicando el motivo.
- **Responsable:** `relaciones_comunidad` selecciona y justifica; investigador/clasificador aporta evidencia; verificador y líder/Jev revisan el texto; `operador_cuenta` es el único escritor. Código controla tier, saldo, reservas, fallback y auditoría.
- **Cadencia:** plan diario de lunes a viernes dentro de BAR-15; saldo de notas mensual por cuenta, revisado antes de cada envío y al cambiar tier o recibir restricciones. Las notas no aumentan la frecuencia de invitaciones.
- **Tu turno:** no se pide aprobar cada invitación bajo la autonomía ya autorizada. En modo aprobación se muestra texto exacto, razón de gastar nota y alternativa sin nota; Gustavo conserva veto. Avisos por discrepancia de tier o límites incluyen estado y acción necesaria, sin proponer comprar Premium automáticamente.
- **Datos de partida de la especificación:** Gustavo confirma **free**, sin Premium ni Sales Navigator; clasificación/razón/confianza, propuestas e invitaciones existen. El conector y la validación hoy solo aceptan `user_id`, sin nota. Faltan tier configurable, texto opcional validado, saldo/reservas y error tipado de cuota de notas. Los comentarios del conector documentan «unas pocas al mes»; no existe lectura integrada de cuota restante ni una cifra universal verificada. La API oficial conectada no aporta aquí esa capacidad.
- **Código:** `operador.py`, `red.py`, `lider.py`, `metricas.py`, `resumen_semanal.py`; extensión mínima de notas y error tipado en `connectors.py`. Estado persistente en AuditEvent y exclusión transaccional mediante OperatorControl; sin migración.
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
- **Validación pendiente:** CI debe ejecutar los fakes y comprobar el contrato real de notas con una fixture redactada del proveedor. Solo el rechazo explícito de nota, con certeza de no creación, habilita fallback. UI y capacidades de perfil/imagen de otras fases no se amplían aquí.
- **Cobertura QA:** `test_fase2_curso.py` y regresiones de red/operador; ejecución pendiente de CI, no ejecutada localmente.

## Barrio en EE. UU. (12/11/2026)

### BAR-17 · Más invitaciones, compradores con ronda semilla y dudas del líder para Gustavo <a id="bar-17"></a>

- **Dónde:** app · backend
- **Estado:** funciona
- **Qué hace para Gustavo:** el equipo invita a más personas de la comunidad, primero en EE. UU.; a un comprador solo lo busca si está en EE. UU. y la web muestra que su startup tiene ronda semilla o posterior, o clientes que pagan. Cuando el líder frena a alguien que el clasificador dio por afín, se lo pregunta a Gustavo en vez de volver a intentarlo cada hora.
- **Decisiones de Gustavo (12/11/2026):** «al menos unas 15 por día porque necesitamos data»; «USA para todos porque la idea es que linkedin nos mande a posicionarnos allá»; «Semilla por delante … los agentes deberían poder validar esto»; la comunidad no son solo compradores («preferiblemente comunidad USA»). El calentamiento con comentarios antes de invitar y el outbound quedan para otro PR.
- **Código:** `red.py` (`plan`, `diverse_candidates`, `prioritized`, `outbound_rules`, `check_stages`, `_lead_resting`, `confirm_fit`, `on_lead_discard`, `search_location`), `ubicacion.py`, `operador.py` (`network_batches`, `batch_issue`, `spacing_range`, `capacity_left`), `autopiloto.py` (`policy_review`, `_execute`, `_network`), `research.py` (cupo `etapa:`), `referentes.py`/`referentes_research.py` (`extraordinary`), `connectors.py` (`_signals`, `search_people`, `search_parameters`), migración `0031_red_senales_rampa`, `movil/src/personas/PersonaScreen.tsx`.
- **Ritmo:**
  - Rampa RED-02 **8/40 → 16/80 → 20/100**, arranca en **16/80**; la primera etapa es solo el paso atrás tras una aceptación débil. La salud no cambia: sube tras siete días con ≥40 % sobre ≥20 invitaciones maduras, baja con <40 % o caída de 10 puntos, pausa bajo 25 %. La migración reubica la etapa vigente: primera o segunda → 16/80, tercera → 20/100.
  - RED-01 (seguir) **20/día y 100/semana**.
  - `NETWORK_BATCHES=09:00-11:00,15:00-17:00`: las acciones de red salen en dos tandas, con 3–8 minutos entre escrituras (`NETWORK_BATCH_SPACING_SECONDS`, nunca menos de dos); la primera tanda envía como máximo la mitad de las invitaciones del día; durante una tanda los comentarios esperan; fuera de ellas la red espera. Sin la variable rige el espaciado común de 20–40 minutos.
- **A quién invita y en qué orden:** todos los papeles salvo los líderes (que se siguen y se comentan), incluidos aliados y pares de búsqueda. El cupo del día se llena así: compradores en EE. UU., resto de la comunidad en EE. UU., comunidad en Latinoamérica, resto; dentro de cada grupo, mayor confianza primero. Las invitaciones se revisan antes que los follows. Desde el 17/11/2026 los cupos blandos por papel deciden a quién le toca y, dentro de los compradores, el puntaje ([BAR-24](#bar-24)).
- **Ubicación (`ubicacion.region`):** EE. UU. por país, estado o gran área metropolitana; Latinoamérica por país o gran ciudad; ubicación vacía no se adivina. `NETWORK_BUYER_REGION=us` (vacío apaga la regla): un comprador fuera de EE. UU. no encaja; una invitación recibida conserva el veredicto simple. Los compradores clasificados antes de la regla se barren una vez en el plan. **Cambiado el 17/11/2026 ([BAR-24](#bar-24)):** la región ya no saca a nadie, solo ordena (EE. UU. primero, después Latinoamérica).
- **Etapa del comprador (`NETWORK_STAGE_CHECK=true`):** un comprador afín en EE. UU. espera (`stage_check: pending`) hasta que una búsqueda web con citas muestre ronda semilla o posterior, o clientes que pagan; Sonnet decide solo con esos hallazgos (`semilla_o_mas`, `presemilla`, `sin_evidencia`). Sin hallazgos reintenta al día siguiente, hasta tres intentos. Presemilla o sin evidencia lo saca del barrio con la regla visible (**cambiado el 17/11/2026, [BAR-24](#bar-24):** cuatro niveles, solo la evidencia en contra saca, y la espera ya no frena el follow ni la invitación). Cupo propio `NETWORK_STAGE_CHECKS_PER_DAY=6` (claves `etapa:`), aparte de la investigación editorial; la pregunta pública solo lleva nombre y titular saneados. Desde el 19/11/2026 una verificación que se corta (por ejemplo el ciclo se detiene por `cost_cap` dentro de ella) queda `interrupted` y no `running`: si no llegó a reservar la llamada no consume cupo y se repite; las que dejó un proceso muerto se cierran tras `WEB_RESEARCH_STALE_MINUTES` (antes se quedaban `running` y ocupaban el cupo del día). `manage.py investigacion_web` las lista.
- **Señales de perfil (`Contact.signals`):** seguidores, conexiones y bio, leídas por LinkedIn directo al leer el perfil y su tarjeta. El conector directo no lee el idioma ni las marcas de creador, contratando, abierto a trabajo, premium o influencer: ya no llegan. El clasificador las recibe con la región; no hay mínimo de seguidores (Gustavo: «lo veremos con la data»).
- **Búsqueda:** `NETWORK_SEARCH_LOCATION=United States` (id leído una vez con `search_parameters`, el autocompletado de ubicación de LinkedIn, y guardado); `NETWORK_SEARCHES_PER_RUN=2`; una consulta que termina en `[es]` busca perfiles en español.
- **Dudas del líder:** un descarte del líder deja descansar a esa persona `NETWORK_LEAD_REST_DAYS=30` días para esa acción y crea el aviso `network_doubt` («El líder frenó a una persona que encaja», con enlace a la persona). En la ficha, «Sí, encaja» (`POST /api/v1/red/contacts/<id>/encaja`) guarda `confirmed_by_gustavo`: el líder deja de revisar las acciones de esa persona y el descanso termina.
- **Referentes:** las búsquedas mensuales piden voces con audiencia en EE. UU., incluidos creadores medianos con comunidad activa. `manage.py operador --usuario <u> referentes-extraordinaria --cuenta <id>` encola una revisión fuera de calendario (una por mes): plazo de siete días y cada propuesta requiere su decisión explícita, aunque se pida el día 1 (entonces no hay recordatorio del día 4 ni se aplica nada por silencio; `test_referentes_mensuales.test_an_extraordinary_review_on_day_one_is_never_applied_by_silence`).
- **Criterios de aceptación:**
  1. **Dado** una rampa nueva, **cuando** se consulta el cupo de RED-02, **entonces** es 16/día y 80/semana; un override solo baja etapas.
  2. **Dado** tandas configuradas, **cuando** se intenta una invitación fuera de ellas, **entonces** espera; dentro de la primera, el cupo es la mitad del día.
  3. ~~**Dado** un comprador afín en Medellín y otro en Austin, **cuando** se clasifican, **entonces** el primero queda descartado con la regla de ubicación y el segundo espera la verificación web antes de cualquier acción.~~ Reemplazado por [BAR-24](#bar-24), criterio 3.
  4. ~~**Dado** un comprador sin ronda visible tras tres días, **cuando** termina el último intento, **entonces** queda descartado con `sin_evidencia` y no se propone.~~ Reemplazado por [BAR-24](#bar-24), criterio 2.
  5. **Dado** un descarte del líder, **cuando** vuelve a correr el plan, **entonces** no se propone a esa persona por 30 días; tras «Sí, encaja», se propone y se aprueba sin el líder.
  6. **Dado** compradores, aliados, pares y un líder en EE. UU. y Latinoamérica, **cuando** se planifica, **entonces** las invitaciones siguen el orden de arriba y el líder solo se sigue.
- **Cobertura QA:** `tests/test_red_eeuu.py`, `test_fase2_curso.py`, `PersonaScreen.test.tsx`; ejecución en CI, no local.

## El sistema del comprador, fase 1 (16/11/2026)

### BAR-18 · Recorrido del comprador y embudo mínimo <a id="bar-18"></a>

- **Dónde:** backend
- **Estado:** funciona. Solo registra y lee: el equipo hace lo mismo que antes (mismos envíos, topes, rampa y prioridades) y ninguna compuerta lee estas tablas.
- **Qué hace para Gustavo:** cada comprador elegido tiene su recorrido: en qué paso va (elegido, calentando, invitado, aceptó, mensaje 1 a 4, respondió, interesado, reunión, en descanso o salió), por qué ruta, cuándo le toca lo siguiente, y un registro de cada toque del equipo y de cada señal de la persona, con su fuente y su fecha. De ahí sale el embudo por semana. Todavía no hay pantalla: es la línea base de las fases 2 a 6 de [plan-outbound.md](../plan-outbound.md#orden-propuesto).
- **Decisiones de Gustavo (17/11/2026):** las señales de la persona (respondió un comentario, comentó su post, lo invitó, aceptó, le escribió) se guardan aparte de lo que hace el equipo, con fecha y fuente. Salir no es borrar: el descanso lleva motivo, fecha de vuelta, número de intento y el ángulo de cada intento, y es distinto de la salida definitiva (pidió no ser contactado, no le interesa, descartado por Gustavo).
- **Código:** `comprador.py`; modelos `BuyerJourney` y `BuyerTouch` (migración `0048_recorrido_comprador`); ganchos pasivos en `red.py` (`_classify_batch`, `check_stages`, `outbound_rules`, `sync`, `on_rejected`, `discard`, `confirm_fit`), `operador._finish`, `respuestas._store` y `close_dm`, `conversaciones._from_messages`, `oportunidades.create`/`update` y `desenlaces_captura._comment`; `resultados_views.EmbudoComprador`; `manage.py comprador reconstruir|embudo`.
- **Quién entra:** un contacto clasificado `comprador` que encaja y cuya verificación web no encontró evidencia en contra (`stage_check` distinto de `failed`; desde el 17/11/2026 también mientras espera, [BAR-24](#bar-24)), o con «Sí, encaja». El recorrido guarda el nivel y el puntaje con que el equipo fue por la persona (`entry_level`, `entry_score`, `entry_score_version`): siguen a su nivel mientras solo está elegida y se fijan con el primer follow o la primera invitación. También un comprador al que el equipo ya siguió o invitó con un criterio anterior: entra y sale por regla si hoy no encaja. `Contact.stage` no cambia.
- **El registro (`BuyerTouch`):** solo se añade; editar o borrar una fila da error. Tres direcciones:
  - `saliente`, lo que hizo el equipo o Gustavo: seguir, comentar un post suyo, reaccionar, responderle en el hilo de un post de Gustavo, invitar (con o sin nota), aceptar su invitación, «Hecho, le escribí» y un mensaje de Gustavo leído en el inbox.
  - `entrante`, las señales de la persona: respondió a un comentario del equipo (el desenlace a 72 h), comentó un post de Gustavo, lo invitó, aceptó, le escribió primero o respondió un mensaje. «Reaccionó» y «nos siguió» tienen tipo, pero hoy ninguna lectura automática los trae.
  - `estado`: elegido, ruta, ángulo, descanso, reintento, salida, reabierto, ya conectados, no escribirle y oportunidad.
  - Cada toque guarda su `key` de origen y apunta a la propuesta, la ejecución, el post, el comentario, la conversación, la oportunidad o el desenlace de donde salió.
- **Cómo se llena:** `comprador.update(contact)` lee lo que Barrio ya guarda de la persona, añade lo que falta y recalcula el recorrido. Los ganchos y la reconstrucción usan esa misma función, así que dos pasadas dan lo mismo. Cada gancho corre en su propio savepoint: si falla, deja `AuditEvent buyer.record_failed` y la acción sigue. `BUYER_RECORD_ENABLED=false` apaga los ganchos sin tocar la reconstrucción. Una fecha del contacto (seguido, invitado, conectado) o su historial cuentan mientras no aparezca la fila propia de ese hecho; cuando aparece, la reemplaza (`comprador.current`).
- **Salidas y descanso:** las salidas definitivas no se reabren. Las de una regla de hoy (`fuera_de_criterio`, `invitacion_cerrada`, `perfil_restringido`) se reabren si la persona acepta o escribe, o si vuelve a cumplir el criterio. Una regla no saca a nadie de un descanso; una salida definitiva, sí. `rest`, `retry` y `leave` validan cada paso. En esta fase nadie entra en descanso: las fases 2 a 6 lo harán.
- **Embudo:** `GET /api/v1/resultados/embudo-comprador?semanas=1..26` (por defecto 8; permiso `operate_linkedin`). Trae el acumulado y cada semana (cohorte de elegidos y actividad), el paso de cada etapa a la siguiente, las comparaciones (ruta, calentados frente a no calentados, con nota frente a sin nota, con señal antes de invitar frente a sin señal, saliente frente a entrante) y los borradores pendientes frente a enviados. Con menos de 30 invitaciones avisa «muestra chica». Forma completa en «Embudo del comprador» de [`metricas-resultados.md`](../../agentes-linkedin/infra/docs/metricas-resultados.md).
- **Para las fases 2 a 6:** escriben con `record`, `rest`, `retry`, `leave`, `set_route` y `set_angle`, y leen con `journey`, `current`, `temperature` (las señales de una persona con su edad, sin pesos), `due`, `drafts` y `funnel`. Las pruebas de punta a punta (`test_comprador_e2e.BuyerPathBase`) se amplían con un método por paso nuevo.
- **Criterios de aceptación:**
  1. **Dado** un comprador en Austin con ronda semilla verificada en la web, **cuando** se clasifica, **entonces** tiene recorrido en `elegido`. Desde [BAR-24](#bar-24), si la web aún no respondió entra `por_confirmar`, y uno de Latinoamérica también entra, después de los de EE. UU.
  2. **Dado** que el equipo lo sigue, comenta un post suyo, él responde ese comentario, se le invita sin nota y acepta, **cuando** corre cada paso con las funciones de producción, **entonces** el recorrido pasa por calentando, invitado y aceptó, con un toque por paso y su referencia. La respuesta cuenta como señal antes de invitar.
  3. **Dado** un fallo del registro, aunque sea un error de base de datos dentro de la transacción de la acción (el descarte de Gustavo), **cuando** se ejecuta una acción, se clasifica o se descarta, **entonces** la acción termina y se guarda igual, y queda `buyer.record_failed`.
  4. **Dado** el historial sin recorridos, **cuando** corre `manage.py comprador reconstruir`, **entonces** crea los toques que habrían dejado los ganchos; una segunda corrida no añade nada y `--seco` no guarda.
  5. **Dado** un recorrido en descanso, **cuando** se reintenta antes de la fecha o sin ángulo, **entonces** se rechaza; después abre el intento 2 con su ángulo. Una salida definitiva no admite descanso ni reapertura, ni siquiera ante una respuesta.
  6. **Dado** menos de 30 invitaciones, **cuando** se lee el embudo, **entonces** cada bloque trae `muestra_chica: true` y el aviso.
- **Brechas:**
  - Con el inbox apagado (`INBOX_ENABLED=false`, su valor por defecto) no hay «respondió» ni «le escribió» desde el inbox; el mensaje enviado solo llega por «Hecho, le escribí».
  - El inbox guarda los últimos mensajes de cada conversación: el registro conserva lo que un gancho ya vio, pero la reconstrucción no recupera mensajes que salieron de esa ventana.
  - El historial de un contacto guarda 30 eventos; una invitación recibida antigua puede quedar solo como «llegó por invitación».
  - La ruta casi siempre queda `sin_definir` hasta la fase 2 (se marca `comentarios` cuando hay un post suyo observado o un comentario del equipo).
  - Interesado y reunión quedan en 0 hasta la fase 6: una oportunidad registrada es un toque de estado, no una etapa.
  - Volver a la cola de clasificación (`red.requeue`) no tiene gancho: se recoge en la siguiente clasificación.
- **Cobertura QA:** `tests/test_comprador.py` (33) y `tests/test_comprador_e2e.py` (4), con conector y proveedores falsos; regresión completa del backend en una PostgreSQL desechable.

## El sistema del comprador, fase 2 (16/11/2026)

### BAR-19 · Calentamiento del comprador <a id="bar-19"></a>

- **Dónde:** backend
- **Estado:** implementado detrás de `BUYER_WARMUP_ENABLED` (por defecto `false`), sin desplegar. Apagado, el equipo hace exactamente lo de antes: lee solo referentes, comenta solo sus posts, invita 48 h después de seguir y el recorrido dice lo mismo.
- **Qué hace para Gustavo:** a cada comprador elegido y seguido el equipo le lee los posts, le deja dos comentarios con aporte y pregunta en 7 a 14 días y lo invita después del segundo, antes si la persona responde, a los 14 días como máximo. Quien no acepta en 21 días descansa y vuelve con otro ángulo. Nunca hay mensajes privados automáticos ni se tocan topes o rampa.
- **Código:** `calentamiento.py` (`read_posts`, `quotas`/`rooms`, `buyer_posts`, `invite_at`/`invitable`, `heat`/`heats`, `buying_signals_from`, `sweep`, `old_invitations`); `operador.observe` (lectura), `autopiloto._observe`, `_propose_groups`, `_lead_redraft`, `comment_text_issues`/`warmup_text_issues`, `comment_author_issues`; `red.plan` (`sweep` e `invitable`), `red.prioritized`, `red._judge_stage` (señales de compra); `comprador.next_at`, `retry(signal=)`, `temperature(weigh=)`; `red_views.OldInvitations`.
- **A. Leer:** `operador.observe` (y el job `observe` con `solo_compradores` cuando solo ellos tocan) lee los posts recientes de quien está en `calentando` y de quien está `elegido` con su RED-01 abierto, el más caliente primero. Cada persona como mucho cada `BUYER_POSTS_REREAD_HOURS` (72) h y solo hasta tener sus comentarios. Tope propio de `BUYER_POSTS_READ_DAILY_LIMIT` (8) lecturas al día (`AuditEvent buyer.read`); con un id público (no `ACo…`) también gasta una lectura del cupo de perfil compartido (`OPERATOR_PROFILE_READ_DAILY_LIMIT`, 80). Los posts se guardan como `ObservedPost` sin referente; un post de un comprador nunca es señal editorial.
- **B. Comentar:** `_propose_groups` reparte el tope de INT-03 del día (15 por defecto desde el 17/11/2026, 7 el fin de semana) entre compradores, comunidad y referentes por `BUYER_COMMENT_SHARE` (8/2/5; 4/1/2 el fin de semana). Con el interruptor apagado, los 15 van a referentes, como hoy. Un grupo sin nada que comentar cede sus cupos al siguiente que tenga (compradores → comunidad → referentes, y vuelta); «comunidad» no tiene fuente de posts todavía, así que sus 2 cupos pasan a referentes, o a compradores si no hay posts de referentes. El presupuesto, los 20 borradores al día (`OPERATOR_DAILY_PROPOSALS`, antes 6) y un borrador a la vez rigen igual. Con la separación de 20 a 40 minutos caben unas 20 escrituras que no son de red al día: 15 comentarios solo con pocas respuestas ([plan-outbound.md](../plan-outbound.md), «Capacidad del día»). Posts de compradores de hasta `BUYER_POST_MAX_AGE_HOURS` (168) h; los de referentes siguen en 72 h. La espera de 48 h es por autor del post (`author_provider_id`), así que nunca hay dos comentarios a la misma persona el mismo día. El prefiltro del líder lee que un founder hable de su empresa como el tema, y solo descarta un anuncio sin nada que preguntar. Un comentario que el líder descartó tiene su reescritura también en el post de un comprador.
- **C. El comentario:** la metodología `comentario_calentamiento` ([BIB-11](biblioteca-equipos.md#bib-11), [COM-13](comentarios-y-lider.md#com-13)).
- **D. Invitar:** con el interruptor, un comprador con recorrido se invita cuando `calentamiento.invite_at` llega: el segundo comentario del intento (`BUYER_WARMUP_COMMENTS`), una señal que acelera o `BUYER_WARMUP_MAX_DAYS` (14) días después de seguirlo, lo que ocurra antes. Quien comentó un post de Gustavo (fuente `own_post`) se invita enseguida, como hoy. El resto de los roles (par, recomendador…) y quien no tiene recorrido siguen la regla de hoy. `next_at` del recorrido dice esa fecha (`comprador.due`).
- **E. Reciprocidad:** `comprador.temperature` pesa las señales (`WEIGHTS`: invitó o agendó 5; respondió un comentario, comentó su post, le escribió o respondió un mensaje 3; nos siguió, reaccionó o aceptó 1) y la mitad si tienen más de 30 días. Ordena a quién leer y comentar primero y, en `red.prioritized`, EE. UU. → comprador → puntaje + temperatura → confianza (fórmula en [BAR-24](#bar-24)). Aceleran la invitación (`ACCELERATORS`): respondió un comentario del equipo, comentó un post de Gustavo, lo invitó o le escribió, en el último mes. Si la persona lo invita, sigue el flujo de RED-04 de siempre.
- **F. Sin posts:** tras `BUYER_NO_POSTS_READS` (2) lecturas en 10 días sin un post comentable, el recorrido toma la ruta `sin_posts` (`comprador.set_route`): ya no se lee ni se comenta, y se invita a los 14 días por la regla del máximo. La fase 5 construye el resto de esa ruta.
- **G. Descanso:** `calentamiento.sweep` corre en cada `plan_network`. Quien tiene sus dos comentarios, fue invitado y no aceptó en `BUYER_REST_AFTER_DAYS` (21) días pasa a descanso `invitacion_no_aceptada` por `BUYER_REST_DAYS` (60) días (un año desde el tercer intento). En descanso no se lee ni se comenta. Una señal suya durante el descanso lo despierta con ese ángulo (`retry(signal=True)`, «Señal en el descanso: …»); al terminar el descanso empieza otro intento («otro post y otro tema»). La invitación pendiente nunca se reenvía ni se retira (no se toca `linkedin_directo/permitidas.py`): `GET /api/v1/red/invitaciones-pendientes?dias=21` le da a Gustavo la lista para retirarlas a mano si quiere.
- **H. Señales de compra (clase 08):** con el interruptor, la misma llamada de la verificación web de la etapa (`red._judge_stage`, `purpose network-stage`) devuelve también las señales que los hallazgos citan (`ronda`, `contratacion`, `expansion`, con fecha y URL). Se guardan en `classification.stage_check.senales` solo si citan una URL recibida; sin fuente no cuentan. Pesan 2 cada una (1 sin fecha o de más de 30 días) en la temperatura. No hay llamadas nuevas.
- **I. Encendido:** ver «Orden de encendido» abajo. Con el interruptor apagado, una prueba recorre el camino de hoy (`WarmupSwitchOffTests`).
- **Para las fases 3 a 6:** `calentamiento.invite_at(state, contact)`, `invite_ready`, `heat`/`heats` y `level`, `buying_signals(contact)`, `warming(account)`, `to_read`, `old_invitations(dias)` y `sweep`; `comprador.temperature(persona, weigh=True)` y `comprador.retry(journey, angulo, signal=True)`. El embudo ya separa `calentados`, `calentados_2` y con o sin señal de compra.
- **Orden de encendido:** 1) desplegar con el interruptor apagado (sin migraciones nuevas) y cargar las clases 07 y 10 en la base (`knowledge ingest`; sin las seis unidades no se redacta ningún comentario a un comprador); 2) `manage.py comprador reconstruir --seco` y sin `--seco` si aún no se hizo (fase 1); 3) comprobar con `manage.py test team_backend.tests.test_comentario_calentamiento` o el caso `BIB-09-comentario-calentamiento` en la evaluación; 4) `BUYER_WARMUP_ENABLED=true` y reiniciar el worker y el autopiloto; 5) mirar al día siguiente `buyer.read`, el embudo (`calentados_2`) y las propuestas INT-03 con autor sin referente. Para apagar, `false`: lo leído queda guardado y nada más cambia.
- **Criterios de aceptación:**
  1. **Dado** un comprador elegido y seguido con un post reciente, **cuando** corre `observe`, **entonces** su post queda como `ObservedPost` sin referente y se cuenta una lectura de compradores.
  2. **Dado** su post leído, **cuando** corre el autopiloto, **entonces** se propone ese post antes que el de un referente, el borrador carga las seis unidades, pasa las reglas del calentamiento y las preguntas `cal_*` del líder y se publica; un segundo post suyo no se comenta antes de 48 h.
  3. **Dado** un solo comentario, **cuando** corre `plan_network` 49 h después de seguirlo, **entonces** no se le invita; tras el segundo comentario, sí, y el embudo lo cuenta en `calentados_2`.
  4. **Dado** que responde el primer comentario, **cuando** corre el plan, **entonces** se le invita sin el segundo.
  5. **Dado** dos lecturas sin posts, **cuando** corre la lectura, **entonces** toma la ruta `sin_posts`, no se vuelve a leer y se invita a los 14 días.
  6. **Dado** dos comentarios y una invitación sin aceptar en 21 días, **cuando** corre el plan, **entonces** pasa a descanso; en descanso no se lee ni se comenta; una señal lo despierta sin otra invitación.
  7. **Dado** el interruptor apagado, **cuando** corre todo el camino, **entonces** es el de hoy: sin lecturas de compradores, sin reglas del calentamiento e invitación a las 48 h.
  8. **Dado** el interruptor encendido, **cuando** se consultan los topes, **entonces** INT-03 y la rampa de RED-02 son los mismos y los cupos por grupo suman el tope del día.
- **Brechas:**
  - No hay acción permitida para responder en el hilo del comprador cuando contesta nuestro comentario: su respuesta solo adelanta la invitación.
  - El grupo «comunidad» no tiene fuente de posts: sus cupos siempre pasan a otro grupo.
  - Una señal de compra no despierta un descanso: la verificación web corre una vez por persona. Con la fase 5 ([BAR-22](#bar-22)) hay una reverificación al terminar cada descanso; durante el descanso, ninguna.
  - Quien no publica o fue invitado con un solo comentario no entra en descanso por esta regla. Resuelto en la fase 5 ([BAR-22](#bar-22)), con su interruptor.
  - Resuelto el 17/11/2026: `OPERATOR_DAILY_PROPOSALS` pasa de 6 a 20 y el tope de INT-03 por defecto a 15/75. Lo que limita ahora es la separación entre escrituras (unas 20 al día fuera de las rondas de red).
- **Cobertura QA:** `tests/test_comprador_e2e.py` (`WarmupBuyerPathTests`, `WarmupSwitchOffTests`), `tests/test_calentamiento.py` y `tests/test_comentario_calentamiento.py`, con conector y proveedores falsos, en una PostgreSQL desechable.

## El sistema del comprador, fase 3 (16/11/2026)

### BAR-20 · Primer mensaje al aceptar y nota de invitación para calentados <a id="bar-20"></a>

- **Dónde:** backend · Tu turno (PWA y app: solo dos etiquetas de la tarjeta)
- **Estado:** implementado detrás de `BUYER_FIRST_MESSAGE_ENABLED` (por defecto `false`), sin desplegar. Necesita el líder encendido (`LEAD_ENABLED`): sin él no se prepara nada. Apagado, todo es como antes: el único primer mensaje es el de RSP-07 y la nota sale del clasificador; `FirstMessageSwitchOffPathTests` y `FirstMessageSwitchOffTests` lo comprueban.
- **Qué hace para Gustavo:** cuando un comprador del recorrido acepta su invitación, el equipo le deja en Tu turno un primer mensaje de tres líneas que cita algo real que pasó entre ellos; él lo copia y lo envía desde LinkedIn. Las 3 notas del mes van a los compradores ya calentados, redactadas al invitarlos, para que acepten. La app nunca envía un mensaje privado (INB-08; `linkedin_directo/permitidas.py` sin tocar).
- **Código:** `mensajes_comprador.py` (nuevo: `message_at`, `awaiting_touch`, `anchors`, `note_text_issues`/`message_text_issues`, `prepare`, `step`, `note_hold`/`ready_notes`/`use_note`/`approved_note`/`note_outcome`, `cards`, `close`, `recently_resolved`); modelo `BuyerDraft` y el toque `borrador` (migración 0049); `autopiloto._buyer_drafts` (job `prepare_buyer_draft`, antes de `_network`); `lider.review_buyer_draft` (`BUYER_MESSAGE_CHECKS`, `NOTE_CHECKS`, `note_questions`, `dm_questions('recorrido')`); `red.plan` (notas del comprador), `red.note_approved` y `send_invitation` (`_note_outcome`); `calentamiento.second_touch` (en `to_read`, `buyer_posts` y la reescritura del líder); `comprador.next_at` (paso «aceptó»), `_draft_facts`, `drafts`; `rediseno_views.TuTurno` y `SuggestedMessageClose`.
- **A. Cuándo (LI-09-M002-K05):** si la persona interactuó con el equipo en los últimos 30 días (respondió un comentario, comentó un post de Gustavo, lo invitó o le escribió), el borrador se prepara en el ciclo del autopiloto que ve la aceptación y la tarjeta aparece una hora después de aceptar (`SHOW_AFTER`), nunca el mismo minuto. Si no, antes un toque más (calentamiento 2: un comentario en un post nuevo suyo con las reglas, el líder y los topes del calentamiento) y el borrador `BUYER_FIRST_MESSAGE_AFTER_DAYS` (7; entre 1 y 21) días después de aceptar y después de ese toque; a los 21 días se prepara igual. La ruta sin posts no espera un toque. `next_at` del recorrido en «aceptó» dice esa fecha.
- **B. El mensaje:** la metodología `primer_mensaje` ya activada ([BIB-10](biblioteca-equipos.md#bib-10)), redactada por Relaciones con los hechos de la persona (`anchors`: la respuesta a un comentario del equipo con su post, lo que comentó en un post de Gustavo, lo que escribió al invitarlo, un post suyo que el equipo comentó con ese comentario, una señal de compra con su fuente). La primera línea cita uno de ellos (`anchor`). Sin nada real no hay mensaje ni llamada pagada, y queda el motivo (`hecho`). Reglas fijas: las de RSP-07 (`respuestas.dm_text_issues`) más «declara un hecho suyo»; una reescritura; después el líder con las seis preguntas `dm_*` sobre esos hechos y `inventa`. Lo que fallan las reglas o el líder se descarta, se audita (`buyer.draft_stopped`) y nunca se muestra. En el idioma de la persona.
- **C. La tarjeta:** «Mensaje sugerido» en Tu turno (`dm:<borrador>`), con «Abrir su perfil», «Hecho, le escribí» y «No escribirle», el mismo endpoint de RSP-07 (`POST /api/v1/respuestas/<id>/mensaje`). Una tarjeta por persona: si conversó con Gustavo en su post, gana la de RSP-07 y el recorrido no prepara otra (ni después de que él la cierre). «Hecho, le escribí» registra el mensaje (paso `mensaje_1`); «No escribirle» es una salida definitiva (`descartado_por_gustavo`). La push `dm_ready` sale una vez. Las etiquetas de la tarjeta dicen qué cita (`comment_label`, `reply_label`: «Su post», «Lo que comentó el equipo»…): es el único cambio de la PWA y la app.
- **D. La nota:** las notas del mes (`note_room`, 3) van a compradores calentados (un comentario del equipo o una interacción) con un hecho concreto, los más calientes primero. Se redactan cuando la persona queda lista para invitar, con los comentarios del calentamiento y las señales como contexto: metodología `nota_invitacion` ([BIB-12](biblioteca-equipos.md#bib-12)). Reglas fijas (menos de 200 caracteres, sin vender ni insinuarlo, sin «ser parte de mi red» ni las otras fórmulas, sin elogio genérico, el hecho nombrado, su idioma), una reescritura y el líder con cinco preguntas `nota_*`. `red.plan` espera hasta 6 h (`NOTE_HOLD`) a que se decida la nota de un calentado; una nota parada (reglas, líder, sin hecho, sin cupo) nunca frena la invitación: sale sin nota. Con el interruptor encendido el clasificador ya no pone notas. Una nota lista sin usar caduca a los 7 días.
- **E. El error corregido** (commit `78cadb5`, vale también apagado): una invitación con nota a una persona que Gustavo confirmó, o con el líder apagado, quedaba bloqueada hasta caducar; ahora sale sin la nota no revisada. La nota del comprador cuenta como aprobada por su propia revisión del líder (`approved_note`), así que sale con ella aunque Gustavo haya confirmado a la persona.
- **F. El recorrido y el embudo:** cada decisión es un toque `borrador` (tipo, resultado, quién lo paró) y «Hecho, le escribí» o «No escribirle» del recorrido son `mensaje` o `no_escribirle` con `fuente: recorrido`; el recorrido queda aceptó → (comentario) → borrador → mensaje. El embudo cuenta «recibieron mensaje» y `borradores` separa pendientes frente a enviados de las dos fuentes, más `recorrido` (preparados, pendientes, enviados, no enviados, parados por motivo) y `notas` (preparadas, con invitación, enviadas, paradas); la comparación con nota frente a sin nota ya existía.
- **Para las fases 4 a 6:** `BuyerDraft` (`number` 2–4 para la secuencia, `attempt`, estados y `stopped_by`), `mensajes_comprador.anchors(contact)`, `message_text_issues`/`note_text_issues`, `prepare` con `kind` y `number`, `cards`, `close` y `decision(contact, kind, attempt, number)`; `lider.review_buyer_draft`; `comprador.drafts()`.
- **Costo con el interruptor encendido (estimado, no medido):** una llamada a Claude Opus 5.5 por borrador (dos si hay reescritura) con las unidades enteras en caché (unos 10–20 mil tokens de entrada y 600 de salida: entre 0,06 y 0,12 USD) más la revisión de Jev (menos de 0,001 USD). Sin nada real que citar no se paga. Con la rampa en la etapa 1 (20 invitaciones a la semana) y un 30–40 % de aceptación, unos 25–35 mensajes y 3 notas al mes: 2 a 8 USD; en la etapa 3 (100 a la semana), 10 a 35 USD, dentro de `AI_MONTHLY_LIMIT_USD`. El toque después de aceptar es un comentario más dentro de los topes de INT-03.
- **Orden de encendido:** 1) desplegar con el interruptor apagado (migración 0049) y cargar la clase 09 en la base si no está (`knowledge ingest`); 2) comprobar con `manage.py test team_backend.tests.test_primer_mensaje_comprador team_backend.tests.test_nota_invitacion` o los casos en la evaluación; 3) con el líder encendido, `BUYER_FIRST_MESSAGE_ENABLED=true` (conviene después de `BUYER_WARMUP_ENABLED`, aunque no lo exige) y reiniciar el worker y el autopiloto; 4) mirar `buyer.drafted`, `buyer.draft_stopped`, `buyer.draft_ready`, las tarjetas y `borradores` del embudo. Para apagar, `false`: los borradores listos dejan de mostrarse y nada más cambia.
- **Criterios de aceptación:**
  1. **Dado** un comprador que respondió un comentario del equipo, invitado con su nota, **cuando** acepta, **entonces** el siguiente ciclo prepara el borrador con `FIRST_MESSAGE_UNITS`, el líder lo aprueba y la tarjeta aparece una hora después, citando esa respuesta; «Hecho, le escribí» lo deja en `mensaje_1` y el embudo en «recibieron mensaje».
  2. **Dado** un comprador que aceptó sin interactuar, **cuando** corre el autopiloto, **entonces** no hay borrador; se lee y se comenta un post nuevo suyo, y el borrador sale a los 7 días.
  3. **Dado** que no hay nada real que citar, **cuando** le toca, **entonces** no hay mensaje ni llamada pagada y queda el motivo `hecho`.
  4. **Dado** un borrador que incumple las reglas después de la reescritura o que el líder rechaza, **cuando** se decide, **entonces** se descarta, se audita y no aparece tarjeta.
  5. **Dado** «No escribirle», **cuando** Gustavo la cierra, **entonces** la persona sale del recorrido (`descartado_por_gustavo`) y no se prepara nada más.
  6. **Dado** que no quedan notas este mes, **cuando** se invita a un calentado, **entonces** sale sin nota y queda el motivo `cupo`.
  7. **Dado** que Gustavo confirmó a la persona, **cuando** sale la invitación, **entonces** sale con la nota que el líder revisó (o sin nota si nadie la revisó), nunca bloqueada.
  8. **Dado** el interruptor apagado, **cuando** corre todo el camino, **entonces** es el de hoy y RSP-07 queda intacto.
  9. **Dado** que conversó con Gustavo en su post y además es un comprador que aceptó, **cuando** se mira Tu turno, **entonces** hay una sola tarjeta, la de RSP-07, y ningún segundo mensaje.
  10. **Dado** pares y recomendadores, **cuando** corre el plan, **entonces** siguen la regla de hoy, sin nota ni espera.
- **Brechas:**
  - La prueba A/B de notas del curso (20 con nota A, 20 con B, 20 sin nota) no está: con 3 notas al mes no hay volumen. Queda la comparación con nota frente a sin nota del embudo.
  - El toque después de aceptar es solo un comentario: no hay reacción en el recorrido (INT-02 no se usa para compradores).
  - Quien invitó a Gustavo (RED-04) o ya era su conexión también queda en «aceptó» y recibe el mismo borrador si tiene hechos; solo una conversación que el inbox ya vio lo evita (`conversacion`). Con el inbox apagado (`INBOX_ENABLED=false`) esa conversación no se ve.
  - Con el interruptor encendido y el líder apagado no hay notas ni mensajes: nada sin revisión.
- **Cobertura QA:** `tests/test_comprador_e2e.py` (`FirstMessageBuyerPathTests`, `FirstMessageSwitchOffPathTests`), `tests/test_primer_mensaje_comprador.py` y `tests/test_nota_invitacion.py`, con conector y proveedores falsos, en una PostgreSQL desechable; `oficina/src/pages/TuTurno.test.tsx` y `movil/src/turno/TuTurnoScreen.test.tsx` para las etiquetas.

## El sistema del comprador, fase 4 (17/11/2026)

### BAR-21 · Secuencia de mensajes 2 a 4 para el comprador que no respondió <a id="bar-21"></a>

- **Dónde:** backend · Tu turno (PWA y app: solo la etiqueta del mensaje de la tarjeta)
- **Estado:** implementado detrás de `BUYER_SEQUENCE_ENABLED` (por defecto `false`), sin desplegar. Necesita la fase 3 (`BUYER_FIRST_MESSAGE_ENABLED`), el líder (`LEAD_ENABLED`) y el inbox (`INBOX_ENABLED`). Apagado, todo es como en la fase 3: el recorrido termina en el primer mensaje; `test_6_with_the_switch_off_the_journey_ends_at_the_first_message` lo comprueba.
- **Qué hace para Gustavo:** a un comprador que no respondió a su primer mensaje el equipo le deja en Tu turno el mensaje 2, el 3 y el 4 del curso, cada uno a su tiempo y con su trabajo, en la misma tarjeta del primer mensaje con la etiqueta «Seguimiento n de 4». Él lo copia y lo envía desde LinkedIn y marca «Hecho, le escribí». Si ella responde, no hay más mensajes y Slack se lo dice. Decisión de Gustavo del 17/11/2026: siempre borradores, nunca envío (INB-08; `linkedin_directo/permitidas.py` sin tocar).
- **Código:** `secuencia_comprador.py` (nuevo: `due`, `replied_at`, `inbox_ready`, `ready`, `text_issues`, `inputs`, `step`, `_stop`, `_rest`, `_wake`, `prioritize`, `cards`, `referral_asked`, `link_referral`, `due_today`, `funnel`); `mensajes_comprador.prepare`, `_draft`, `_judge`, `decision`, `tries` y `close` con `number`; `lider.review_buyer_draft` (`SEQUENCE_CHECKS`, `SEQUENCE_COMMON`, `sequence_questions`); `autopiloto._buyer_drafts` (el mismo job `prepare_buyer_draft` con `number`); `conversaciones.read_inbox` (`prioritize`); `calentamiento.wake` (antes interna de `sweep`); `comprador._Fold` (`sent`, `replied_at`), `next_at`, `drafts` (`por_numero`), `funnel` (`secuencia`), `FALLBACK_RANK` (`lista:`); `alertas_slack.seguimiento_vence_hoy`, `comprador_respondio`, `secuencia_sin_inbox`, `buyer_lines`; `rediseno_views.TuTurno`; modelo: `BuyerDraft.State.CANCELLED`, `BuyerTouch.Kind.REFERRED`, `BuyerJourney.referred_by` (migración 0050).
- **A. Cuándo y qué:** el mensaje n vence `BUYER_SEQUENCE_DAYS` (`4,5,7`) días después del «Hecho, le escribí» del mensaje n−1, nunca desde el borrador (los +4/+5/+7 de la diapositiva LI-09-M003-K05). Si el n−1 no se envió, el n no se prepara (`ready`). Se redacta en el idioma de la persona, de lunes a viernes y dentro de `READ_WINDOW` (LI-10-M001-K08), con la metodología `secuencia_mensajes` ([BIB-13](biblioteca-equipos.md#bib-13)) y lo que ya se le envió (`seguimiento.anteriores`). Reglas fijas por número (`text_issues`): el M2 cuenta el mismo dolor de otra forma, sin repetir el primero ni disculparse; el M3 pregunta si es la persona indicada o quién se encarga; el M4 cierra con elegancia, sin preguntar, pedir ni rogar; además las del primer mensaje. Una reescritura; después el líder con las preguntas `seg_*` de su número. Lo que fallan las reglas o el líder se descarta, se audita (`buyer.draft_stopped`) y nunca se muestra. La tarjeta es la del primer mensaje («Abrir su perfil», «Hecho, le escribí», «No escribirle», `POST /api/v1/respuestas/<id>/mensaje`), con `text_label` «Seguimiento n de 4» y el último mensaje que él envió («Tu mensaje n (hace X días)»).
- **B. Si responde, se detiene todo:** antes de preparar un seguimiento y antes de mostrar su tarjeta se busca su respuesta en lo que leyó el inbox: un mensaje suyo después del primero de Gustavo en la conversación leída, o la lista de chats con su mensaje al final (aunque el hilo no se haya leído aún; ese toque `lista:` cede ante el del hilo). Si responde, se cancelan los seguimientos pendientes (estado `cancelado`, `buyer.draft_cancelled`; cerrar uno cancelado da 409), el recorrido pasa a `respondio` (por el toque de su mensaje), se audita `buyer.sequence_replied` (tras qué mensaje) y se llama a `REPLY_HANDLERS` (fase 6) una vez por intento. Sin el inbox encendido y leído en las últimas `BUYER_SEQUENCE_INBOX_FRESH_HOURS` (3) no se prepara nada (nunca se supone «no respondió»), se audita `buyer.sequence_waiting` una vez al día y Slack avisa; una tarjeta solo se muestra si el inbox se leyó en las últimas 24 h. `read_inbox` lee primero los hilos de estos compradores (`prioritize`), dentro de sus topes.
- **C. Después del M4:** `BUYER_SEQUENCE_REST_AFTER_DAYS` (7) días sin respuesta tras el «Hecho» del M4, descansa `BUYER_SEQUENCE_REST_DAYS` (90; un año desde el tercer intento) con motivo `secuencia_sin_respuesta` (`buyer.sequence_rested`). Sigue siendo conexión. Una señal suya durante el descanso la despierta con ese ángulo (`calentamiento.wake`, la regla del calentamiento) y ese intento empieza por un primer mensaje nuevo (fase 3). También descansa si un seguimiento lo paran las reglas o el líder (a los 7 días del último «Hecho») o si vence hace más de `BUYER_SEQUENCE_MAX_LATE_DAYS` (14; un primer mensaje enviado mucho antes de encender). «No escribirle» en cualquier número es una salida definitiva (`descartado_por_gustavo`).
- **D. El referido del M3 (para la fase 6):** `referral_asked(journey)` dice si se le envió el M3 en este intento; `link_referral(journey, referrer, at, note)` une a la persona nueva con quien la refirió (`BuyerJourney.referred_by`, toque `referido`, `buyer.referral_linked`); falla si quien refiere no recibió el M3.
- **E. Metodología:** `secuencia_mensajes`, seis unidades de las clases 09 y 10 con su evaluación `BIB-09-secuencia-mensajes`, su línea base y su registro de lectura ([BIB-13](biblioteca-equipos.md#bib-13)).
- **F. Slack:** «seguimiento que vence hoy» (`comprador:seguimientos_hoy`, una vez al día dentro de la ventana: quiénes y qué número); «un comprador respondió» (`comprador:respondio:<evento>`, una vez por respuesta, quién y tras qué mensaje, nunca su texto; en la siguiente vuelta del vigilante, hasta 5 minutos); «secuencia detenida porque el inbox está apagado» (`comprador:secuencia_sin_inbox`, una vez al día, con el motivo y cuántos esperan); el resumen diario cuenta los mensajes del recorrido (primeros y seguimientos pendientes y enviados hoy, y los cancelados porque respondió) cuando la fase 3 o la 4 están encendidas.
- **G. Embudo:** `secuencia` en `GET /api/v1/resultados/embudo-comprador`: `recibieron` (M1 a M4), `respondieron_tras` (tras qué mensaje), `comprobacion` (el «la mayoría responde al 2.º o 3.º» del curso, medido con `tras_2_o_3_pct` y `muestra_chica`), `descansan` y `activa`; `borradores.por_numero` (preparados, pendientes, enviados, no enviados, cancelados, parados de cada número).
- **Para las fases 5 y 6:** `secuencia_comprador.REPLY_HANDLERS` (`handler(journey, at, after)`, cada uno en su punto de guardado; un fallo se audita y no frena la secuencia), `referral_asked`, `link_referral`, `replied_at`, `due`, `sent`/`previous` (lo que se le envió), `BuyerDraft` con `number` 2–4 y el estado `cancelado`.
- **Costo con el interruptor encendido (estimado, no medido):** una llamada a Claude Opus 5.5 por seguimiento (dos si hay reescritura), entre 0,06 y 0,12 USD, más Jev (menos de 0,001 USD). Hasta tres por persona que no responde: con 25–35 primeros mensajes al mes en la etapa 1, a lo sumo 75–105 seguimientos (5 a 13 USD); en la etapa 3, de 3 a 4 veces eso, dentro de `AI_MONTHLY_LIMIT_USD`. El inbox encendido lee la lista de chats cada hora dentro de la ventana (unas 14 lecturas de lista al día) y hasta `INBOX_THREADS_PER_RUN` (5) hilos por lectura, dentro de los 60 al día de su tope; la secuencia no añade lecturas, solo cambia el orden de los hilos.
- **Orden de encendido:** 1) desplegar con el interruptor apagado (migración 0050); 2) comprobar con `manage.py test team_backend.tests.test_secuencia_mensajes` o los casos de la evaluación; 3) con el inbox, el líder y la fase 3 encendidos y el inbox leyendo, `BUYER_SEQUENCE_ENABLED=true` y reiniciar el worker y el autopiloto; 4) mirar `buyer.drafted`, `buyer.draft_stopped`, `buyer.sequence_replied`, `buyer.sequence_waiting`, `buyer.sequence_rested`, las tarjetas y `secuencia` del embudo. Para apagar, `false`: los seguimientos listos dejan de mostrarse y nada más cambia.
- **Criterios de aceptación:**
  1. **Dado** un comprador con el primer mensaje enviado que no responde, **cuando** pasan 4 días desde el «Hecho», **entonces** aparece «Seguimiento 2 de 4» (nada un minuto antes); igual el 3 a los 5 días del «Hecho» del 2 y el 4 a los 7 del 3; a los 7 días del 4, descansa 90 días con `secuencia_sin_respuesta`.
  2. **Dado** que responde después del M2, **cuando** corre el autopiloto, **entonces** no se prepara el M3, el recorrido queda en `respondio`, se llama al manejador de la fase 6 y Slack avisa una vez.
  3. **Dado** un M3 en Tu turno y su respuesta, **cuando** el inbox la ve, **entonces** el M3 se cancela, su tarjeta desaparece y cerrarlo da 409.
  4. **Dado** que Gustavo no marcó «Hecho» del M2, **cuando** pasan los días, **entonces** no hay M3.
  5. **Dado** el inbox apagado o sin leer, **cuando** vence un seguimiento, **entonces** no se prepara nada y Slack avisa una vez al día.
  6. **Dado** un seguimiento que incumple las reglas tras la reescritura o que el líder rechaza, **cuando** se decide, **entonces** no hay tarjeta y queda auditado.
  7. **Dado** «No escribirle» en el M3, **cuando** la cierra, **entonces** sale del recorrido y no hay M4.
  8. **Dado** el interruptor apagado, **cuando** corre todo el camino, **entonces** el recorrido termina en el primer mensaje, como en la fase 3.
  9. **Dado** una señal suya durante el descanso, **cuando** corre el calentamiento, **entonces** despierta con un intento nuevo y un primer mensaje nuevo.
  10. **Dado** un sábado, **cuando** vence un seguimiento, **entonces** se redacta el lunes.
- **Brechas:**
  - Sin email ni teléfono: después del M4 no hay otro canal; descansa.
  - El curso dice «retira la invitación de quien no acepta» y «detén la secuencia si hace clic o agenda»: no aplica (se retiran nunca las invitaciones; clic y reunión son de la fase 6).
  - El aviso «respondió» llega en la siguiente vuelta del vigilante (hasta 5 minutos), no en el mismo instante.
  - Un M2 listo que Gustavo no envía no caduca: la tarjeta sigue hasta que la cierre.
  - Con el inbox leyendo por la lista de chats, una respuesta que llega y se borra antes de la lectura no se ve.
- **Cobertura QA:** `tests/test_comprador_e2e.py` (`SequenceBuyerPathTests`: el flujo completo y las variantes 1 a 8, fin de semana, respuesta vista en la lista, seguimiento vencido, referido), `tests/test_secuencia_mensajes.py` (caso completo con funciones de producción, reglas, activación, registro), `tests/test_alertas_slack.py` (`BuyerSequenceAlertTests`), con conector y proveedores falsos y el reloj simulado, en una PostgreSQL desechable; `oficina/src/pages/TuTurno.test.tsx` y `movil/src/turno/TuTurnoScreen.test.tsx` para la etiqueta.

## El sistema del comprador, fase 5 (17/11/2026)

### BAR-22 · La ruta del comprador que no publica: el puente por su empresa y los reintentos <a id="bar-22"></a>

- **Dónde:** backend (PWA y app: solo la etiqueta del papel «Puente» en Personas).
- **Estado:** implementado detrás de `BUYER_NO_POSTS_ROUTE_ENABLED` (por defecto `false`), sin desplegar. Necesita el calentamiento (`BUYER_WARMUP_ENABLED`: la ruta `sin_posts` solo existe ahí); la nota y el primer mensaje, además, la fase 3 (`BUYER_FIRST_MESSAGE_ENABLED`) y el líder. Apagado, todo es como en las fases 2 a 4: `NoPostsSwitchOffTests.test_8_with_the_switch_off_the_path_is_the_one_of_phases_2_to_4` lo comprueba.
- **Qué hace para Gustavo:** a un comprador que no publica (dos lecturas sin posts, fase 2) el equipo no puede calentarlo con comentarios. Si tiene una señal de compra con fuente, la usa para la nota y el primer mensaje; si no tiene nada real que citar, busca a alguien de su empresa que sí publique (el puente), lo calienta con comentarios y lo invita. Lo que haga el puente (aceptar, responder) cuenta como señal del comprador y le da algo real que citar. Quien no acepta descansa y vuelve con otro ángulo, hasta tres intentos.
- **Diseño:** la ruta es de Gustavo (plan del 17/11/2026: «apruebo entrar por el cofounder»), no del curso, que no trata al comprador que no publica. La sustentan, sin que ningún agente las cargue (sus reglas son código): LI-07-M005-K01 («busca la llave»: seguir y comentar antes de conectar; a alguien de 3.er grado se entra por alguien de su red), LI-07-M005-K02 (tarjeta 04: quien comenta donde comenta tu cliente), LI-08-M004-K04 (2 a 3 personas por empresa, nunca dos con el mismo cargo o que hacen lo mismo, por flancos distintos), LI-08-M004-K05 (decide, influye, usa) y LI-10-V008-K01 (calentar: visitar, reaccionar, comentar, seguir, volver a visitar). Leídas completas de la biblioteca local con SELECT el 17/11/2026.
- **Código:** `sin_posts.py` (nuevo: `company_of`, `same_company`, `cargo_of`, `people_at`, `status`, `request`, `early`, `hold_rest`, `search`, `_pick`, `_create`, `read`, `reading_due`, `warming`, `invite_ready`, `repeat_issues`, `draft_inputs`, `relayed`, `fact`, `strong_signal`, `note_by_route`, `warmed_waiting`, `next_angle`, `retry`, `recheck_waiting`, `rechecks_due`, `recheck_done`, `funnel`); `calentamiento.sweep` (descanso con menos comentarios, el puente antes del descanso, el pedido del puente), `wake` (ángulo y reverificación), `buyer_posts`, `buyer_ids`, `warmup_post`, `draft_inputs`, `invitable`, `WEIGHTS`; `comprador.facts` (señales del puente), `update` (un puente actualiza a su comprador), `retry(kind, detail)`, `rebuild`, `funnel` (`ruta_sin_posts`), `_project` (la señal del puente no cuenta como «señal antes de invitar»); `mensajes_comprador.anchors` (el ancla `puente`), `talk_issues`, `_notes` (nota por señal), `note_hold`; `red.check_stages` (`_recheck_signals`), `stage_pending`, `ROLE_LABELS`, el plan de seguimientos; `operador.observe` (la búsqueda y la lectura de puentes); `autopiloto.comment_text_issues`, `_observe`, `_lead_redraft`; `lider.ROLE_MEANING`; modelo: `Contact.bridge_for`, `BuyerTouch.Kind` `puente`, `reverificacion` y `senal_puente` (migración 0051).
- **1. Seguir y visitar dos veces en 10 días:** seguir sí (RED-01 del plan, como hoy). La visita **no se construye**: el conector no registra una visita visible (`get_profile` lee el perfil sin que la visita se compruebe; [BAR-15](#bar-15): «no se simula una visita pública»), y gastar lecturas del tope compartido de 80 en una visita que quizá nadie ve no sirve. El embudo lo dice (`visitas.disponible: false`).
- **2. Comentar donde él comenta:** **no se construye**. El conector no lee la actividad de comentarios de una persona (lee sus posts y los comentarios de un post). No se inventa; el embudo lo dice (`donde_comenta.disponible: false`).
- **3. El puente:**
  - **Cuándo se pide** (toque `puente`, estado `pedido`): en cuanto toma la ruta sin nada real que citar (sin señal de compra con fuente ni interacción: `sin_ancla`); antes de su descanso (`ruta_sin_resultado`, punto 6b); o como ángulo de un reintento (`reintento`). Uno por intento.
  - **La búsqueda** (job `observe`, dentro de `READ_WINDOW`): la empresa sale de su titular («… at Acme», «CTO @ Acme», «Fundador de Acme»). Sin empresa, `sin_puente` con `sin_empresa`. Si ya hay dos personas de esa empresa en curso (compradores o puentes), `empresa_completa` sin buscar. Si no, una búsqueda de personas por el nombre de la empresa (`search_people`), dentro del tope «search» (20 al día) y de `BUYER_BRIDGE_SEARCHES_PER_DAY` (2). Cada resultado: no conocido, una persona, de la misma empresa (la empresa de su titular empieza por ese nombre: «Acme Inc» sí, «Globex Acme Partners» no), con un cargo legible y distinto del suyo (CEO, CTO, COO, CFO, CMO, CPO, CRO, fundador, VP, dirección, ingeniería, ventas, marketing, producto). La página real de búsqueda no trae titular: una lectura de perfil por resultado (tope compartido de 80, propósito `buyer_bridge`), como mucho `BUYER_BRIDGE_PROFILES_PER_SEARCH` (3). A quien pasa, una lectura de posts del tope de compradores (8), hasta 2 por búsqueda: el primero con un post comentable es el puente. Sin nadie, `sin_puente` con el motivo (`no_publica`, `sin_lectura`, `mismo_cargo`, `sin_cargo`, `otra_empresa`, `conocido`, `sin_resultados`). Con un tope agotado el pedido espera al día siguiente. No hay llamadas pagadas.
  - **El puente es su propio contacto:** papel `puente`, etapa `fit`, `bridge_for` → el recorrido del comprador, clasificación por regla (`classification.puente` con comprador, empresa y cargo). No tiene recorrido ni es un segundo comprador.
  - **Se calienta como un comprador:** el plan lo sigue (RED-01); `observe` lee sus posts (tope de compradores, cada 72 h); el autopiloto los comenta con la metodología `comentario_calentamiento`, sus reglas, el líder, la espera de 48 h por autor y la parte de compradores del día, con su propio `para_que` («colega de un posible cliente… nunca le vendas ni menciones a su colega») y lo que se le escribió al comprador como `no_repitas`; se invita con la regla del calentamiento (2.º comentario, una señal que acelera o 14 días), sin nota. Si su comprador sale del recorrido, el puente deja de leerse, comentarse e invitarse.
  - **Nunca lo mismo a la segunda persona:** una regla fija de `autopiloto.comment_text_issues` para cualquier comentario a uno de los dos que repita lo que el equipo le escribió al otro (comentarios, notas y mensajes; la misma comparación de la secuencia).
  - **Lo que hace el puente cuenta para el comprador** (toque `senal_puente`, entrante): aceptó (una vez), respondió un comentario del equipo, comentó un post de Gustavo, lo invitó o le escribió. Pesa 1 en su temperatura, actualiza su recorrido al momento y le da un ancla `puente` para la nota y el primer mensaje. No cuenta como «señal antes de invitar» del comprador.
  - **«Hablé con X de tu equipo» solo tras una interacción real:** regla fija en la nota y el mensaje (`talk_issues`); si el puente solo aceptó, el texto puede decir que conectó con él, nunca que hablaron. El sistema del redactor lo explica cuando hay un hecho `puente`.
- **4. Invitar a los 14 días:** la regla de la fase 2 (`invite_at`), sin cambios. **La nota por señal:** un comprador de esta ruta con una señal de compra con fuente y fecha de los últimos `BUYER_SIGNAL_RECENT_DAYS` (30) días, o una señal de su puente, es candidato a una de las 3 notas del mes, después de los calentados con comentarios: ellos van primero en la cola y las notas que quedan se reservan para los calentados que esperan (`warmed_waiting`); si no queda, la invitación sale sin nota con el motivo `cupo`. Misma metodología, reglas y líder que la nota de la fase 3.
- **5. Primer mensaje:** el ancla es la señal de compra con su fuente o el puente (uno por puente, la interacción primero). «Algo verificable en común» **no se construye**: no hay de dónde sacarlo con fuente. Sin ancla no hay mensaje ni llamada (`hecho`). Esta ruta no espera un toque después de aceptar (fase 3).
- **6. Reintentos:**
  - **a.** Invitado con menos de dos comentarios (o ninguno) y sin aceptar en `BUYER_REST_AFTER_DAYS` (21) días → descanso de `BUYER_REST_DAYS` (60), `invitacion_no_aceptada`. Los 21 días cuentan desde lo último entre la invitación, el último comentario del intento, la última señal del puente del intento y el inicio del intento (si la invitación es de uno anterior, sigue pendiente y nunca se reenvía).
  - **b.** En la ruta sin posts, antes del descanso se intenta el puente (`hold_rest`): se pide y el descanso espera mientras se busca o mientras el puente está en curso, hasta `BUYER_BRIDGE_WAIT_DAYS` (21) días. Sin empresa, sin nadie, o ya buscado en un intento anterior, descansa. El plan cuenta `puente_antes_del_descanso`.
  - **c.** Cada reintento cambia de ángulo y lo guarda (`comprador.retry(..., kind, detail)`, detalle `tipo`): `senal_en_descanso` (una señal suya lo despertó), `senal_nueva` (una señal de compra con fuente que ningún intento ni texto citó, la más nueva; guarda `senal`), `puente` (esta ruta, sin puente aún y con lugar en la empresa: pide el puente del intento) u `otro_tema` (numerado desde el segundo). Tres intentos y después un año, en todas las rutas.
  - **d.** Al terminar un descanso, una reverificación web de sus señales de compra (si su etapa ya se verificó con `ok` y `NETWORK_STAGE_CHECK` está encendido): el reintento espera hasta 2 días a que el job `check_buyer_stages` (`red.check_stages`, desde el 18/11/2026 en su propia corrida) la corra dentro del mismo cupo diario de verificaciones (`NETWORK_STAGE_CHECKS_PER_DAY`, 6; clave `etapa:<persona>:reverificacion:<intento>:<día>`). Suma solo señales con una fuente nueva; nunca cambia el veredicto ni el encaje. Una por descanso: si no corre a tiempo queda `vencida` y el reintento sigue sin ella (toque `reverificacion`, `buyer.signals_rechecked`).
- **7. Embudo:** `ruta_sin_posts` en `GET /api/v1/resultados/embudo-comprador`, solo con el interruptor: `comparacion` (con y sin puente, el bloque de etapas de siempre), `puentes` (pedidos, búsquedas, encontrados, `sin_puente` por motivo, seguidos, invitados, aceptaron, compradores con señal del puente y con interacción del puente), `donde_comenta` y `visitas` (`disponible: false` con el motivo), `reintentos.por_angulo` y `reverificaciones` (pedidas, hechas, con señal nueva, vencidas).
- **8. Metodología:** no se activa ninguna nueva: ningún agente redacta algo distinto (el comentario al puente es `comentario_calentamiento`, la nota `nota_invitacion` y el mensaje `primer_mensaje`, ya activadas) y la búsqueda, los topes y los reintentos son reglas de código. El registro de lectura de `comentario_calentamiento` anota que también comenta al puente y que la ruta es diseño de Gustavo.
- **Para la fase 6:** `sin_posts.status(journey)` y `bridge_of_journey(journey)` (su puente), `relayed(journey)` y `fact(touch)` (lo que hizo el puente, como señal y como ancla), `strong_signal(contact)`, `next_angle(journey)`, `counterpart(cuenta, id)` (la otra persona de la empresa), `funnel`; los toques `puente`, `senal_puente` y `reverificacion`; `comprador.retry(journey, angulo, kind=, detail=)`.
- **Lecturas al día con el interruptor encendido:** hasta `BUYER_BRIDGE_SEARCHES_PER_DAY` (2) búsquedas dentro del tope «search» (20); hasta 3 lecturas de perfil por búsqueda dentro del tope compartido de 80; hasta 2 lecturas de posts por búsqueda y la relectura de los puentes que se calientan (cada 72 h), dentro de las 8 de compradores; el seguimiento y la invitación de un puente gastan lo de cualquier RED-01 y RED-02. Las reverificaciones van dentro de las 6 verificaciones de etapa del día: cada una es una búsqueda web y una llamada a Claude, la misma de la verificación de etapa (unos centavos de USD). Los comentarios al puente están dentro del tope de INT-03; sus invitaciones, de la rampa de RED-02.
- **Orden de encendido:** 1) desplegar con el interruptor apagado (migración 0051); 2) comprobar con `manage.py test team_backend.tests.test_comprador_e2e.NoPostsBuyerPathTests`; 3) con `BUYER_WARMUP_ENABLED=true` (y la fase 3 para la nota y el mensaje), `BUYER_NO_POSTS_ROUTE_ENABLED=true` y reiniciar el worker y el autopiloto; 4) mirar `buyer.bridge_search`, `buyer.bridge_found`, `buyer.bridge_none` (motivo), `buyer.signals_rechecked`, los contactos con papel «Puente» y `ruta_sin_posts` del embudo. Para apagar, `false`: los puentes quedan como contactos, dejan de leerse, comentarse e invitarse, y nada más cambia.
- **Criterios de aceptación:**
  1. **Dado** un comprador que no publica con una señal de compra con fuente, **cuando** pasan 14 días, **entonces** se le invita con una nota que cita la señal (si quedan notas); al aceptar, el primer mensaje la cita; no se pide puente ni se comenta nada.
  2. **Dado** uno sin señal ni interacción, **cuando** corre el plan, **entonces** se pide su puente; la búsqueda descarta el mismo cargo y otra empresa y encuentra a un colega que publica; se le sigue, se le comenta dos veces y se le invita; al aceptar, sube la temperatura del comprador; tras una interacción real, su mensaje puede decir que habló con él.
  3. **Dado** dos personas de una empresa en curso, **cuando** se pide un puente, **entonces** no se busca a una tercera; nunca dos con el mismo cargo.
  4. **Dado** que no hay nada real que citar ni puente, **cuando** acepta, **entonces** no hay mensaje ni llamada pagada.
  5. **Dado** un invitado con un comentario que no acepta en 21 días, **cuando** corre el plan, **entonces** descansa 60 días.
  6. **Dado** un reintento, **cuando** termina el descanso, **entonces** el ángulo es otro y queda guardado; tras el tercer intento descansa un año.
  7. **Dado** el fin de un descanso, **cuando** hay cupo de verificaciones, **entonces** se reverifican sus señales una sola vez y el reintento usa la señal nueva.
  8. **Dado** el interruptor apagado, **cuando** corre todo el camino, **entonces** es el de las fases 2 a 4.
  9. **Dado** los topes de lectura, **cuando** se buscan puentes, **entonces** la búsqueda, las lecturas de perfil y de posts quedan dentro de sus topes y nunca se simula una visita.
- **Brechas:**
  - La visita al perfil y «comentar donde él comenta» no están (el conector no puede); tampoco «algo verificable en común».
  - La empresa y el cargo salen del titular: un titular sin «at/@/de Empresa» no da empresa (`sin_empresa`) y un cargo poco común no se lee (`sin_cargo`). Las comparaciones de empresa son por nombre, sin la página de la empresa.
  - Un puente que se encuentra pero nunca acepta no cuenta para el comprador; tras `BUYER_BRIDGE_WAIT_DAYS` el comprador descansa igual.
  - La reverificación es al terminar el descanso; una señal de compra nueva durante el descanso no lo despierta.
  - La aceptación del puente no aparece en las etapas del embudo del comprador: va aparte, en `ruta_sin_posts.puentes`.
- **Cobertura QA:** `tests/test_comprador_e2e.py` (`NoPostsBuyerPathTests`: escenarios 1 a 7 y 9, y la nota por señal detrás de los calentados; `NoPostsSwitchOffTests`: escenario 8), con conector y proveedores falsos y el reloj simulado, en una PostgreSQL desechable; `compartido/src/logic/conexiones.test.ts` para la etiqueta.

## El sistema del comprador, fase 6 (17/11/2026)

### BAR-23 · Su respuesta, el enlace de agenda, la entrega del lead y la lectura semanal <a id="bar-23"></a>

- **Dónde:** backend · Tu turno (PWA y app sin cambios: las tarjetas usan los tipos y las acciones de siempre).
- **Estado:** implementado detrás de `BUYER_REPLY_ENABLED` (por defecto `false`), sin desplegar. Necesita la fase 4 (`BUYER_SEQUENCE_ENABLED`, con la fase 3, el líder y el inbox). Apagado, todo es como en las fases 1 a 5: su respuesta detiene la secuencia y el recorrido queda en `respondio`; el webhook responde 202 sin guardar nada y no hay tarjetas, entregas ni lectura. `ReplyBuyerPathTests.test_9_with_the_switch_off_everything_is_as_in_phases_1_to_5` lo comprueba.
- **Qué hace para Gustavo:** cuando un comprador responde, el equipo lee toda la conversación, dice qué tipo de respuesta es y le deja en Tu turno la contestación para que él la copie y la envíe. Al interesado (y a quien pide información) la contestación le lleva su enlace de Cal.com; cuando reserva, la reunión se registra sola, el recorrido pasa a `reunion` y el lead queda entregado, sin calificar, listo para que Gustavo cree la oportunidad con un toque. Ahí termina la máquina de LinkedIn (decisión de Gustavo del 17/11/2026). Cada lunes, Slack le dice dónde se rompe primero el embudo y el único cambio de la semana.
- **Código:** `respuesta_comprador.py` (nuevo: `enabled`, `active`, `booking_ref`, `link_for`, `conversation`, `pending_message`, `said_date`, `rest_until`, `profile_in`, `decide`, `classify`, `apply`, `text_issues`, `link_issues`, `draft`, `prepare`, `on_reply`, `step`, `_wake`, `resolve_referrals`, `set_referral`, `cards`, `covered`, `close`, `pending_counts`, `funnel`); `agenda_calcom.py` (nuevo: `signed`, `_fields`, `receive`, `match`, `booked`, `_book`, `_cancel`, `note_date`, `manual`, `associate`, `cards`); `entrega_lead.py` (nuevo: `data`, `build`, `cancelled`, `confirm`, `on_opportunity`, `payload`, `listing`, `cards`); `lectura_embudo.py` (nuevo: `TABLE`, `_checks`, `read`, `text`); `comprador_views.py` (nuevo) y `urls.py`; `comprador._Fold` (`_meeting`, `_cancelled`, `meeting_date`, `reply_type`), `_project`, `rest` (varios descansos en un intento), `drafts` y `funnel` (`respuestas`); `mensajes_comprador.prepare` (el tipo `respuesta`), `tries`, `anchors` (`lo_que_dijo`, `referido`), `warmed`, `RETURN_RULES`, `REFERRAL_RULES`; `secuencia_comprador.link_referral` (`reply`), `prioritize`; `lider.review_buyer_draft` (`REPLY_CHECKS`, `REPLY_COMMON`, `reply_questions`); `autopiloto._buyer_drafts` (`respuesta_comprador.step`); `calentamiento.sweep` (no despierta un «no es el momento»); `apps.ready` (`REPLY_HANDLERS`); `oportunidades.create` (`entrega_lead.on_opportunity`); `rediseno_views.TuTurno` y `SuggestedMessageClose`; `alertas_slack` (`comprador_interesado`, `reunion_agendada`, `reserva_sin_emparejar`, `falta_enlace_agenda`, `lectura_semanal_embudo`, `buyer_lines`); `resumen_semanal.week_stats` (`comprador`); modelo: `BuyerJourney.reply_type`, `booking_ref`, `meeting_date`, `BuyerTouch.Kind` `respuesta_clasificada`, `reunion_cancelada` y `respuesta_enviada`, `BuyerDraft.Kind.REPLY` (`respuesta`), `StoppedBy.LINK` (`agenda`), `Contact.Source.REFERRAL` (`referido`), `MeetingBooking` y `LeadHandoff` (migración 0052).
- **A. Clasificar su respuesta** (LI-11-M006-K01): su mensaje más nuevo después del primer «Hecho» del intento, leído en el inbox, abre una decisión (`BuyerDraft` de tipo `respuesta`, job `prepare_buyer_draft`). Jev lee **toda** la conversación (lo que leyó el inbox más lo que Gustavo envió por el recorrido) con la metodología cargada y da una probabilidad para cada tipo: `interesado`, `pide_informacion`, `no_es_el_momento`, `no_le_interesa`, `otra_persona`. El código elige el tipo solo si llega a `BUYER_REPLY_MIN` (0,7) y le saca `BUYER_REPLY_MARGIN` (0,2) al siguiente; si no, `otro`. Propósito propio en el registro de gasto (`buyer-reply-classify`) y el presupuesto se mira antes de pagar. El tipo queda en el recorrido (`reply_type`, toque `respuesta_clasificada`, `buyer.reply_classified`). Más de 5 clasificaciones pagadas en un intento: las siguientes salen como tarjeta sin llamada. Tras 3 intentos fallidos del job, tarjeta sin borrador.
- **B. Qué cambia y la contestación por tipo** (siempre un borrador que Gustavo copia y envía, [INB-08](inbox.md#inb-08); `linkedin_directo/permitidas.py` sin tocar):
  - Reglas comunes (`text_issues`, en código antes del líder): su idioma; tres líneas y 500 caracteres; sin enlace, correo, teléfono ni hashtag propios; sin vender ni ofrecer servicios, sin precios, sin prometer resultados o plazos, sin presionar ni insistir («reconsider», «última oportunidad»…); sin las fórmulas que matan un mensaje; solo `interesado` y `pide_informacion` pueden proponer una llamada. Una reescritura; luego el líder (`lead-review-reply`: `resp_responde` ≥ 0,7, `resp_pitch`, `resp_presiona` y `resp_inventa` ≤ 0,2, más `resp_paso_facil` ≥ 0,6 en los dos tipos con enlace, `resp_insiste` ≤ 0,2 y `resp_agradece` ≥ 0,6 en el «no» y el «ahora no», `resp_agradece` en la redirección). Un borrador que no pasa no tiene tarjeta y queda auditado (`buyer.draft_stopped`).
  - **El único enlace** es el de su agenda y solo en `interesado` y `pide_informacion`: el redactor nunca lo escribe; el código agrega al final `CALCOM_BOOKING_URL?metadata[barrio]=<su identificador>` (`link_for`, `link_issues`). Nunca en el M1–M4 ni en la nota.
  - `interesado`: el recorrido pasa a `interesado`. Dos o tres líneas con un hecho real suyo (si no hay ninguno, el borrador no lo inventa y la tarjeta lo dice) y el enlace, con un paso siguiente fácil (LI-12-M001-K04: «propón algo concreto y fácil de aceptar»).
  - `pide_informacion`: responde solo con hechos confirmados; lo que no se sabe (precio, plazos) va a la tarjeta («Falta confirmar antes de enviar») para que Gustavo lo complete, y ofrece la llamada con el enlace. Sigue en `respondio` hasta que muestre interés o agende.
  - `no_es_el_momento` (LI-11-M006-K03, LI-08-M003-K05): agradece sin insistir; descansa hasta la fecha que dijo, a las 9:00 locales (`said_date`: «after January», «en marzo», «next quarter», «in 6 weeks», Q2, fechas ISO o dd/mm/aaaa; una fecha pasada o a más de un año no cuenta) o 90 días. Al terminar, un intento nuevo cuyo ángulo es lo que dijo (`reintento` de tipo `lo_que_dijo`) y un primer mensaje nuevo (fase 3) que lo retoma. Si ella escribe durante el descanso, despierta y su mensaje se clasifica. El calentamiento ya no despierta este descanso por sus reglas.
  - `no_le_interesa`: agradece y cierra; salida definitiva (`no_le_interesa`), nunca más se le escribe aunque vuelva a escribir.
  - `otra_persona` (LI-11-M006-K02): agradece. Si su mensaje trae el perfil (`linkedin.com/in/…`), el equipo lo lee (una lectura de perfil, propósito `buyer_referral`, dentro del tope compartido) y crea el contacto (origen `referido`, etapa `fit`) con su propio recorrido, enlazado a quien la refirió (`referred_by`, toque `referido`). Si no, la tarjeta pide «Pegar su perfil». La persona nueva cuenta como calentada y su primera nota o mensaje puede nombrar a quien la refirió (el hecho `referido`). Regla de 2 por empresa: un referido puede ser la tercera persona de su empresa (es un pedido explícito, no una campaña), nunca la cuarta.
  - `otro`: tarjeta «necesita tu respuesta» con la conversación y sin borrador ni llamada pagada.
  - Sin `CALCOM_BOOKING_URL`: ningún borrador de los dos tipos con enlace; la tarjeta lo dice, se audita `buyer.reply_no_link` y Slack avisa una vez al día.
  - **Tu turno:** una tarjeta por respuesta, con su título y su etiqueta («Respuesta sugerida · con tu agenda», «· sin insistir», «· cierre», «· agradece»), lo que ella escribió y lo que falta; «Abrir la conversación», «Hecho, le escribí», «No escribirle» (`POST /api/v1/respuestas/<id>/mensaje`; «no» nunca la saca del recorrido) y, en los dos tipos con enlace, «Agendó». Su tarjeta de conversación del inbox no sale dos veces. «Hecho» deja el toque `respuesta_enviada`.
- **C. Cal.com:** `POST /api/v1/comprador/calcom/webhook`, anónimo, con `BOOKING_CREATED`, `BOOKING_RESCHEDULED` y `BOOKING_CANCELLED`. Firma `X-Cal-Signature-256` = HMAC-SHA256(`CALCOM_WEBHOOK_SECRET`, cuerpo crudo) en hex, comparada en tiempo constante (fuente: `packages/features/webhooks/lib/sendPayload.ts` de Cal.com y cal.com/docs/developing/guides/automation/webhooks). Sin secreto: 403 a todo; firma mala: 403; más de 64 KB: 413; con el interruptor apagado: 202 sin guardar. Cada entrega se procesa una vez (sha256 del cuerpo, bajo un candado); una reserva es una fila por `uid`. Del cuerpo solo se usa lo que sirve para emparejar, validado: el identificador de su enlace (`payload.metadata.barrio`: Cal.com guarda los parámetros `metadata[clave]` del enlace de reserva y los devuelve en el webhook, docs «Webhooks» y «Prefill booking form»), la reserva que reprograma (`rescheduleUid`), el correo del asistente si ella lo escribió en la conversación y su nombre exacto si hay un solo candidato. Sin emparejar: tarjeta en Tu turno con los candidatos y «No es de un comprador», y aviso en Slack. Emparejada: recorrido en `reunion` con su fecha (`meeting_date`), sus borradores pendientes cancelados y la entrega lista. Cancelada: vuelve a `interesado` y la entrega se cancela; reprogramada: cambia la fecha. «Agendó» a mano en la tarjeta de su respuesta, con la fecha si Gustavo la escribe («20/11/2026 10:30»).
- **D. La entrega del lead** (`LeadHandoff`, `GET /api/v1/comprador/entregas`, de solo lectura y neutra a la fuente; [CONTRATO-API](../../oficina/CONTRATO-API.md)): quién es y su empresa, `fuente` (`linkedin`), el recorrido (señal de entrada, toques, mensajes enviados, a cuál respondió, su respuesta, puente y quién la refirió), la conversación en tres líneas, la reunión y lo que el equipo sabe del negocio con su fuente. **Sin calificación** (es de la máquina de ventas). Tarjeta «Reunión agendada con …» con «Crear la oportunidad» (o «Vincular su oportunidad» si ya tiene una abierta): un toque de Gustavo la crea en `reunion`, canal LinkedIn, con la reunión como siguiente acción ([PRS-09](personas-oportunidades.md#prs-09)); la entrega enlaza oportunidad, conversación y recorrido. Una oportunidad creada a mano desde Personas también la enlaza.
- **E. Metodología:** `respuesta_comprador`, seis unidades de las clases 08, 11 y 12 con su evaluación `BIB-11-respuesta-comprador`, su línea base y su registro de lectura ([BIB-14](biblioteca-equipos.md#bib-14)).
- **F. La lectura semanal del embudo** (`lectura_embudo`, `GET /api/v1/comprador/lectura-semanal`, determinista): la tabla de LI-12-M001-K04 en el orden del embudo, la primera etapa que se rompe, su causa más probable y UN cambio («Arregla una etapa a la vez»), esta semana frente a la anterior y los borradores pendientes frente a enviados. Con menos de 30 invitaciones dice «muestra chica» y no juzga. Umbrales: la aceptación bajo 20 % es del curso (el docente: «20 % o 10 % sería trágico»); el resto son del equipo y lo dicen (inventario parado, fuga entre aceptar y escribir, respuesta bajo 10 %, reunión bajo 20 % con 5 respuestas). Los lunes, dentro de la ventana de lectura, cinco líneas como mucho en el canal de resúmenes; también en el resumen semanal (`semana.comprador`, [SEM-02](resumen-semanal.md#sem-02)).
- **G. Slack:** «un comprador está interesado» (`comprador:interesado:<evento>`, una vez, quién y nunca su texto); «reunión agendada» o «reprogramada» (`comprador:reunion:<evento>`, quién y cuándo); «reserva sin emparejar» (`comprador:reserva:<reserva>`); «falta tu enlace de agenda» (una vez al día); la lectura semanal (lunes); el resumen diario cuenta las respuestas que esperan en Tu turno (con y sin borrador).
- **H. Embudo:** `interesados` y `reunion` con datos reales (una reunión cancelada sin otra deja de contar); `respuestas` en `GET /api/v1/resultados/embudo-comprador`: `clasificadas`, `por_tipo`, los borradores de respuesta y `horas_respuesta_a_reunion` (mediana y personas); `borradores.respuestas`.
- **Costo con el interruptor encendido (estimado, no medido):** por respuesta, una clasificación de Jev (menos de 0,001 USD) y, salvo `otro`, una llamada a Claude Opus 5.5 (0,06 a 0,12 USD; dos con reescritura) más el líder (Jev). Con 25–35 primeros mensajes al mes y una respuesta de cada 10 a 20, son 3 a 10 respuestas: menos de 1,5 USD al mes, dentro de `AI_MONTHLY_LIMIT_USD`. Un referido con perfil gasta una lectura de perfil del tope compartido. El webhook y la lectura semanal no llaman a ningún modelo.
- **Orden de encendido:** 1) desplegar con el interruptor apagado (migración 0052) y las clases 08, 11 y 12 en la base; 2) en Cal.com, el webhook a `https://<dominio>/api/v1/comprador/calcom/webhook` con los tres eventos y un secreto; ese secreto en `CALCOM_WEBHOOK_SECRET` y la página de reserva en `CALCOM_BOOKING_URL`; reiniciar la API; el «Ping» de Cal.com debería recibir 202 (firma buena, fase apagada; sin verificar que el «Ping» venga firmado, si no la prueba es la reserva del paso 4); 3) comprobar con `manage.py test team_backend.tests.test_respuesta_comprador`; 4) con las fases 3 y 4, el líder y el inbox encendidos, `BUYER_REPLY_ENABLED=true` y reiniciar el worker, el autopiloto y la API; una reserva de prueba de Gustavo en su propia página debe quedar «sin emparejar» en Tu turno y descartarse con «No es de un comprador»; 5) mirar `buyer.reply_classified`, `buyer.drafted`, `buyer.draft_stopped`, `buyer.reply_no_link`, `calcom.event`, `calcom.unmatched`, `calcom.rejected`, `buyer.meeting_booked`, `lead.handoff_ready` y `respuestas` del embudo. Para apagar, `false`: las tarjetas y el webhook dejan de actuar (202) y nada más cambia. El orden de las seis fases está en [plan-outbound](../plan-outbound.md#orden-de-encendido).
- **Criterios de aceptación:**
  1. **Dado** el camino completo, **cuando** ella responde con interés, **entonces** el recorrido pasa a `interesado`, hay un borrador con su enlace, «Hecho» lo registra, el webhook firmado lo pasa a `reunion` con su fecha, la entrega trae todos los campos sin calificación, un toque crea la oportunidad enlazada y el embudo tiene cada etapa en 1.
  2. **Dado** que pide información, **cuando** se prepara, **entonces** lleva el enlace y la tarjeta dice qué falta confirmar.
  3. **Dado** «no es el momento» con fecha, **cuando** se clasifica, **entonces** descansa hasta esa fecha y vuelve con lo que dijo; sin fecha, 90 días.
  4. **Dado** «no le interesa», **cuando** se clasifica, **entonces** sale de forma definitiva y nada más se le prepara.
  5. **Dado** «lo ve otra persona» con su perfil, **cuando** corre el paso, **entonces** esa persona es un contacto con su recorrido enlazado; sin perfil, Gustavo lo pega.
  6. **Dado** poca confianza, **cuando** se clasifica, **entonces** es `otro`: tarjeta y ningún borrador.
  7. **Dado** `CALCOM_BOOKING_URL` vacío, **cuando** responde con interés, **entonces** no hay borrador y hay aviso.
  8. **Dado** el webhook, **cuando** llega con firma mala o sin secreto, repetido, sin emparejar, cancelado o reprogramado, **entonces** se rechaza, se procesa una vez, espera a Gustavo, vuelve a `interesado` o cambia la fecha.
  9. **Dado** «Agendó», **cuando** Gustavo lo marca, **entonces** pasa a `reunion` como con el webhook.
  10. **Dado** el interruptor apagado, **cuando** corre todo, **entonces** es como en las fases 1 a 5; y el enlace nunca va en el M1–M4.
  11. **Dado** la lectura semanal, **cuando** se rompe la aceptación o la respuesta, o hay menos de 30 invitaciones, **entonces** nombra la primera rota y un solo cambio, o «muestra chica».
- **Brechas:**
  - Sin verificar contra Cal.com real (no se llamó): que un enlace de reserva simple conserve `metadata[barrio]` en la versión actual, que una reprogramación conserve la metadata y el nombre exacto del campo de la reserva anterior (`rescheduleUid` o `fromReschedule`; se aceptan los dos). Si la metadata no llega, empareja el correo o el nombre, o Gustavo desde Tu turno.
  - `get_profile(<slug>)` del conector directo para el referido no se probó contra LinkedIn; con error queda `sin_perfil` y la tarjeta lo dice.
  - La lectura semanal no ve clics en el enlace (Cal.com no los avisa): «responden pero no hay reuniones» se mide con reservas.
  - No hay respuesta automática ni recordatorio de la reunión; lo que pasa después es de la máquina de ventas.
- **Cobertura QA:** `tests/test_comprador_e2e.py` (`ReplyBuyerPathTests`: el camino completo y las variantes 1 a 11), `tests/test_respuesta_comprador.py` (caso completo con funciones de producción, reglas fijas, decisión, fechas, firma y recepción del webhook, el pliegue con reuniones, la lectura semanal y su aviso, activación y registro), con conector y proveedores falsos y el reloj simulado, en una PostgreSQL desechable.

## Compradores menos rígidos (17/11/2026)

### BAR-24 · Compradores por niveles y con puntaje, Latinoamérica después de EE. UU. y cupos blandos por papel <a id="bar-24"></a>

- **Dónde:** backend · API
- **Estado:** funciona, con las variables de [BAR-17](#bar-17) (`NETWORK_BUYER_REGION`, `NETWORK_STAGE_CHECK`) y una nueva (`NETWORK_ROLE_SHARE`). No usa interruptores del outbound: con todos los `BUYER_*_ENABLED` apagados funciona igual.
- **Qué hace para Gustavo:** deja de sacar del barrio a un comprador porque la web no sabe nada de su empresa. Cada comprador tiene un perfil, un nivel de evidencia y un puntaje explicable de 0 a 100. Solo la evidencia en contra lo saca. Los compradores de Latinoamérica entran después de los de EE. UU., y las invitaciones de la semana se reparten por papel sin que ningún papel se coma el cupo.
- **Decisiones de Gustavo (17/11/2026):**
  - «Siento que puede ser demasiado estricto, o que el verificador hace una pregunta demasiado rígida y no deja pasar a nadie».
  - Compradores de Latinoamérica: «podríamos prospectarlos al inicio; queremos ir hacia USA pero no los descartamos de una».
  - Reparto de papeles: «debería ser construido», pero «estamos cortando con una misma tijera a todos; podríamos cambiar las preguntas dependiendo del perfil, pero no ser tan rígidos».
  - El objetivo no cambia: ronda semilla o posterior, o clientes que pagan («Semilla por delante», `posicionamiento.MODALITIES`).
- **Dónde se perdía cada comprador (línea base, [`linea-base-compradores.md`](../../agentes-linkedin/infra/docs/linea-base-compradores.md)):**
  - `red.CLASSIFY_SYSTEM` pedía `fit=false` «cuando falte información». Con eso, `red._classify_batch` sacaba a founders en stealth y a perfiles «Founder @X»: 45 de 53 compradores en 14 días, casi siempre «sin evidencia», no evidencia en contra.
  - La regla de región descartaba a todo comprador fuera de EE. UU. Estaba en `red._classify_batch` y se repetía en `outbound_rules`, `outbound_target` y `network_issues`.
  - `red.check_stages` hacía la misma pregunta genérica a todos. El juez tenía «Ante la duda, sin_evidencia», y tres intentos sin hallazgos terminaban en `failed`, es decir, descartado.
  - `red.stage_waiting` frenaba el follow y la invitación mientras la verificación estaba en `pending`.
  - Los reintentos caían justo después de medianoche, fuera de las horas de lectura.
  - `red.diverse_candidates` no tenía reparto por papel. Las invitaciones salían así: par 53 %, aliado 26 %, comprador 9 %.
- **Código:**
  - `nivel_comprador.py` (nuevo): perfiles, niveles, preguntas, puntaje, entrada y reevaluación.
  - `reparto.py` (nuevo): cupos blandos por papel.
  - `red.py`:
    - Clasificador: `CLASSIFY_SCHEMA` y `CLASSIFY_SYSTEM` (`buyer_profile`, `buyer_level`, `us_market`) y `_classify_batch`.
    - Verificación web: `STAGE_SYSTEM`, `_judge_stage`, `check_stages`, `_settle_stage`, `_recheck_signals` y `_raise_level`.
    - Plan y orden: `stage_waiting`, `outbound_rules`, `outbound_target`, `network_issues`, `plan`, `prioritized` y `buyer_score`.
  - `comprador.py`: `chosen`, `_project` (entrada) y `funnel` (`entrada_comprador`).
  - `BuyerJourney.entry_level`, `entry_score` y `entry_score_version` (migración `0053_entrada_nivel_comprador`).
  - `lider.py` (`ROLE_MEANING` y el nivel en el estado), `serializers.ContactOutput.buyer`, `posicionamiento.LOCATION` y `compartido/src/api/types.ts` (`ContactBuyer`).
  - `manage.py operador reevaluar-compradores`.
- **Perfiles (`buyer_profile`), cada uno con su pregunta a la web y al juez:**
  - `startup_financiada`: ronda, inversores y fecha.
  - `bootstrapped`: clientes que pagan, precios, ingresos, empleados y años operando.
  - `stealth`: salida previa, trayectoria, equipo, contrataciones y respaldo. Que la web no sepa nada es `por_confirmar`, nunca `no_encaja`.
  - `ejecutivo`: si decide o influye en contratar desarrollo, y el tamaño de la empresa.
  - Es la misma llamada de investigación con las mismas búsquedas. No hay llamadas pagadas nuevas ni cupos más altos.
- **Niveles (`buyer_level`):**
  - `confirmado`: ronda semilla o posterior, o clientes que pagan, con fuente.
  - `probable`: señales indirectas, por ejemplo inversores sin ronda publicada, precios publicados, una salida previa o contrataciones.
  - `por_confirmar`: no hay datos públicos todavía.
  - `no_encaja`: evidencia en contra, por ejemplo presemilla declarada sin ingresos, alguien que vende para otros o alguien que pidió no ser contactado.
  - **Cómo se combinan:** la evidencia en contra gana. Si no la hay, gana el nivel más fuerte entre el del perfil y el de la web. Un veredicto sin fuente recibida queda `por_confirmar`.
  - **Cuándo se sale:** solo `no_encaja` saca del barrio, con la regla «La verificación encontró evidencia en contra: no es comprador».
  - **Sin hallazgos:** tres intentos sin hallazgos dejan `por_confirmar` con `stage_check: ok`.
  - **Mientras la web no termina:** el comprador se sigue y se invita igual.
  - **Pregunta que no se puede hacer:** si la pregunta no pasa `research.safe_question`, queda `por_confirmar` y no frena la cola.
- **Puntaje (`buyer_score_v1`, 0–100):** es la suma de componentes visibles, y el desglose siempre suma el total.
  - **Evidencia:** confirmado 50, probable 33, por confirmar 16, no encaja 0.
  - **Mercado:** objetivo 20; negocio en EE. UU. desde otra región 14; sin ubicación 12; Latinoamérica 8; otra región 4.
  - **Papel:** decide 12; sin dato 9; influye 6.
  - **Servicios:** construye software, producto o IA 12; sin dato 9; no coincide 6.
  - **Confianza del clasificador:** hasta 6.
  - **Perfil escueto:** cuando el titular tiene cuatro palabras o menos y no hay bio, solo se agrega el aviso «perfil con poca información». Cada dato que falta toma el valor del medio de su componente, nunca el piso.
  - **Para qué sirve:** ordena dentro del cupo del comprador y nunca excluye a nadie.
- **Prioridad con el outbound (`nivel_comprador.priority`):** `prioridad = puntaje + 5 × min(peso de temperatura, 8)`.
  - El puntaje dice quién es la persona y la temperatura (`calentamiento.heats`), qué hizo de vuelta.
  - Una señal Alta (+15) vale casi un nivel (17 puntos). El peso cuenta hasta 8 (+40).
  - La temperatura solo cuenta con `BUYER_WARMUP_ENABLED=true`.
  - Orden de `red.prioritized`:
    1. Región: EE. UU., después Latinoamérica, después el resto.
    2. Comprador antes que el resto de la comunidad.
    3. Dentro de la región, primero quien vende en EE. UU.
    4. Prioridad.
    5. Confianza.
- **Orden del cupo:**
  1. Compradores de EE. UU. `confirmado` y `probable`.
  2. Compradores de EE. UU. `por_confirmar`.
  3. Compradores de Latinoamérica, primero los que tienen negocio o clientes en EE. UU. (`us_market`).
  4. El resto.
  - `NETWORK_BUYER_REGION=us` ya no saca a nadie, solo ordena. Con `''` el orden por región se apaga.
- **Cupos blandos por papel (`NETWORK_ROLE_SHARE`, por defecto `comprador=20,recomendador+aliado=15,divulgador=20,par=25`, de la tabla del barrio LI-03-V021-K03):**
  - El cupo decide a quién le toca, nunca cuántas invitaciones salen. La rampa, los topes y la ventana no cambian.
  - Meta semanal de cada papel = su parte del total × min(tope semanal de RED-02, lo que la rampa permite esta semana).
  - Cada turno va al papel con candidatos que esté más por debajo de su parte. Si hay empate, va el comprador.
  - Un papel sin candidatos cede su turno, y nadie espera para cumplir un porcentaje.
  - Dentro de cada papel se mantiene el orden de `red.plan`.
  - `''` apaga los cupos. Un valor malo (líder, papel desconocido o repetido, parte ≤ 0) es un error de configuración, no un valor por defecto silencioso.
  - El resumen del plan guarda el reparto con lo planeado.
  - **Regla de `aliado`:** comparte el turno de los recomendadores. La tabla busca recomendadores entre «clientes, aliados y socios», y un aliado (alguien que vende servicios a founders) es quien recomienda a Gustavo.
- **Verificación en la ventana:** `check_stages` corre solo dentro de `READ_WINDOW`. Un reintento queda para el inicio de la ventana siguiente, no 24 horas después.
- **Verificación en su propia corrida (18/11/2026):**
  - **Qué pasaba:** cada mañana llegaba «Ciclo detenido: red. Se alcanzó el presupuesto del ciclo» y ese día no se verificaba a nadie (el 18/11: 0 verificaciones y 6 compradores `pending`). `red.classify` llamaba a `check_stages` dentro de la misma corrida de `classify_contacts`. Esa corrida tiene un solo presupuesto (`cost_cap_usd: 1` del ciclo `red`). La clasificación gastaba ~0,22 USD (`network-classify`). Después, la investigación web reservaba su peor caso antes de buscar, ~0,85–0,89 USD (`web-research-tool`). 0,22 + 0,87 > 1: `orquestacion.provider_metadata` paraba la corrida con `cost_cap` antes de la primera búsqueda.
  - **Cómo queda:**
    - `classify_contacts` solo clasifica (`red.classify` → `_classify_batch`).
    - La verificación y la reverificación al terminar un descanso (`_recheck_signals`) corren en su propio job, `check_buyer_stages` (`red.check_buyer_stages` → `check_stages`): su propia corrida del ciclo `red`, con su propio presupuesto.
    - Una verificación por corrida (`red.STAGE_CHECKS_PER_RUN=1`). Peor caso de una corrida: ~0,89 (investigación) + ~0,04 (juez `network-stage`) ≈ 0,93 USD, dentro de 1 USD. Dos no caben.
  - **Cuándo se encola:** el autopiloto (`autopiloto._network`) la encola cada `NETWORK_STAGE_CHECK_EVERY_MINUTES` (20 por defecto), con el mismo patrón de reloj que los demás jobs de la red. Solo se encola si se cumplen todas estas condiciones:
    - estamos dentro de `READ_WINDOW`;
    - hay presupuesto del equipo (`budget_left`);
    - hay una verificación o reverificación vencida y cupo del día (`red.stage_pending`: `NETWORK_STAGE_CHECK`, `NETWORK_STAGE_CHECKS_PER_DAY=6`);
    - no hay otro `check_buyer_stages` pendiente.
  - **Ritmo:** las 6 del día caben en unas 2 horas de la ventana. Ningún comprador se queda sin verificar porque la clasificación se coma el presupuesto.
  - **Grafo `6.17-verificacion-etapa-propia`:**
    - El paso `verificar_etapa` (relaciones_comunidad → clasificador_red, propósitos `web-research-tool` y `network-stage`, una llamada por corrida, 300 s).
    - `clasificar` solo con `network-classify`.
    - El esquema `stage_result`.
    - En `code_bindings`: `network_edges`, `job_roles` (investigador_referentes) y `autopilot_direct_kinds`.
  - **Permisos:** `check_buyer_stages` está en `jobs.OPERATION_PERMISSIONS` y `PAID_OPERATIONS`.
  - **La alerta no cambia:** una corrida que de verdad pasa su presupuesto se detiene con `cost_cap`, deja la tarjeta «Ciclo detenido: red» en Tu turno y avisa por push y Slack (`OPERATOR_ALERT_WEBHOOK`).
  - **La reserva de la investigación web (`knowledge/providers.py`, `_claude` con `WebTools`):**
    - Se reserva antes de llamar, por el peor caso, sin cambiarla en este arreglo.
    - Entrada reservada = (I + 256 + búsquedas × `WEB_SEARCH_RESERVED_TOKENS` + lecturas × `WEB_FETCH_MAX_CONTENT_TOKENS`) × (1 + búsquedas + lecturas).
    - Esa entrada se cobra a precio de escritura de caché (×1,25). A eso se suma `WEB_RESEARCH_MAX_TOKENS` de salida y `WEB_SEARCH_USD_PER_REQUEST` por búsqueda.
    - Con los valores de hoy (2 búsquedas, 2 lecturas, 25 000, 4 000, 4 000 de salida, Sonnet a 2/10 USD por millón, 0,01 por búsqueda) queda ≈ (I + 58 256) × 1,25e-5 + 0,06 USD. Con I ≈ 5 000–8 000 tokens contados da 0,85–0,89 USD.
    - Lo real observado es 0,03–0,07 USD por investigación.
    - No hay error de cálculo. Es un peor caso deliberado: cada búsqueda o lectura puede volver a enviar todo lo anterior (×5) y una búsqueda puede traer hasta 25 000 tokens.
    - **Propuesta, no aplicada:** si se quiere margen sin perder el peor caso, bajar `WEB_SEARCH_RESERVED_TOKENS` a ~12 000 según lo que midan las búsquedas reales (la reserva queda en ~0,53–0,56 USD) o `WEB_FETCH_MAX_USES` a 1 (~0,65–0,68 USD). Hoy no hace falta: la corrida propia tiene ~7 % de holgura.
- **El nivel decide el encaje (18/11/2026):**
  - **Qué pasaba:** el 18/11/2026 se clasificaron 16 compradores tras BAR-24/BAR-25. 10 salieron del barrio con nivel `por_confirmar` (9) o `probable` (1), 3 con `no_encaja` (bien) y 2 entraron. Un ejemplo (anonimizado): `probable`, puntaje 68, «Fundador y CEO de una empresa en Florida…; tamaño no consta», `fit: false`.
  - **Causa:** `red._classify_batch` tomaba el encaje de `result['fit']` y de la confianza mínima, y el nivel solo iba al bloque del comprador. El modelo respondía `fit=false` junto a un nivel que lo deja dentro («es una hipótesis», «no consta») y con confianza baja. `evaluaciones.run_classifier` copiaba el mismo corte. La verificación web ya derivaba el encaje del nivel (`_settle_stage`), y el líder no saca a nadie (solo deja descansar la acción), así que ninguno tenía este defecto. Los demás papeles no tienen nivel: siguen con `fit` y la confianza mínima, sin cambio.
  - **Cómo queda (`nivel_comprador.decide`, `red.classifier_fit`):**
    - Solo `no_encaja` saca a un comprador; `confirmado`, `probable` y `por_confirmar` entran. Su confianza ordena, nunca lo saca.
    - Si el modelo dice `fit=false` con otro nivel, gana el nivel y queda auditado (`AuditEvent network.buyer_fit_overridden`, con lo que dijo el modelo, lo que quedó y la corrección).
    - `no_encaja` exige un motivo de la lista cerrada (`buyer_against` en el clasificador, `en_contra` en el juez). Sin motivo baja a `por_confirmar`. El motivo queda en `buyer.against`.
    - Un comprador sin nivel queda `por_confirmar`, o `no_encaja` si dio un motivo válido. `no_contactar` siempre saca.
  - **Motivos válidos de `no_encaja` (`nivel_comprador.AGAINST`):**
    - `no_decide`: no es dueño, founder ni decide; vende, recluta o ejecuta para otros.
    - `vende_servicios`: vive de vender sus servicios (consultor, freelance, coach, agencia) en vez de dirigir una empresa con producto u operación propia.
    - `competidor_software`: su empresa vende desarrollo de software.
    - `demasiado_grande`: más de 1000 personas (línea ProjectApp; también lo pone el código con `projectapp.too_big`).
    - `idea_sin_empresa`: idea sin empresa, estudiante o presemilla declarada sin ingresos.
    - `empresa_cerrada`: la empresa cerró o ya no opera.
    - `no_contactar`: pide no ser contactado (solo el clasificador: lo dice el perfil, no la web).
    - No son motivos: «tamaño no consta», «sin datos públicos», «es una hipótesis».
  - **Contador:** `nivel_comprador.corrections_count(desde, hasta, cuentas)` devuelve el total, el desglose por corrección (`fit_del_modelo`, `no_encaja_sin_motivo`, `sin_nivel`, `motivo_sin_no_encaja`, `no_contactar`) y cuántos entraron pese a `fit=false` del modelo. `reevaluar-compradores` lo imprime para los últimos 7 días. El resumen de `network.classified` trae `buyer_fit_corrected`.
  - **Prompts:** `red.classify`, `red.stage` y sus versiones de ProjectApp cambiaron: hay una `criterion_version` nueva en las dos líneas. Un experimento que cruce el cambio cierra «inconcluso» (`experimentos`, versiones de criterio distintas).
  - **Aviso:** `alertas_slack.compradores_descartados_con_nivel` avisa una vez al día si un comprador salió hoy con un nivel que no es `no_encaja` (cuenta, sin nombres, y dice cómo rescatarlo).
- **Entrada y embudo:**
  - El recorrido guarda el nivel, el puntaje y la versión con que el equipo fue por la persona (`comprador._project`). Mientras solo está elegida siguen a su nivel, porque la verificación web suele responder el mismo día. El primer follow o la primera invitación los fijan, y una subida de nivel posterior cambia el puntaje actual, no la entrada.
  - `GET /api/v1/resultados/embudo-comprador` trae `entrada_comprador`, de solo lectura:
    - `por_nivel`: confirmado, probable, por confirmar, no encaja y sin nivel.
    - `por_puntaje`: tramos 80-100, 60-79, 40-59 y 0-39, más sin puntaje.
    - Cada grupo cuenta elegidos, seguidos, calentados, invitados, aceptaron y respondieron.
  - `GET /api/v1/red/contacts/<id>` trae `buyer`: nivel, perfil, `us_market`, puntaje, desglose, versión, avisos, evidencia, fuentes y la entrada.
- **Con el outbound ([BAR-18](#bar-18) a [BAR-23](#bar-23)):**
  - Un comprador `por_confirmar` o de Latinoamérica es elegido y tiene recorrido, así que pasa por el calentamiento, las notas y los mensajes igual que uno de EE. UU. cuando esos interruptores se encienden.
  - Las señales de compra (`senales`) siguen saliendo en la misma llamada del juez.
  - La reverificación de un comprador en descanso (`_recheck_signals`) además sube su nivel si encuentra más evidencia con fuente. Nunca lo baja ni saca a nadie a mitad del recorrido: la evidencia en contra queda en la nota `stage_rechecked`.
- **Reevaluación de quien salió con las reglas viejas:** `manage.py operador --usuario <u> reevaluar-compradores --cuenta <id>` lista sin cambiar nada; `--confirmar` aplica.
  - **Grupos:**
    - `fuera_de_eeuu`: se restaura en su lugar, `por_confirmar`.
    - `sin_evidencia_web`: se restaura `por_confirmar` con `stage_check: ok`, sin búsqueda nueva.
    - `sin_evidencia_clasificador`: vuelve a la cola y lo juzga la clasificación normal con el prompt nuevo, en sus lotes y su presupuesto.
    - `sin_nivel`: se completan el nivel y el puntaje, y nada más cambia.
    - `descartado_con_nivel` (18/11/2026): salió con un nivel que lo deja dentro (`nivel_comprador.left_by_model_fit`). Se restaura con su nivel, línea, segmento, evidencia y puntaje, sin pagar otra clasificación; con la verificación web encendida queda `pending`. Va antes de `sin_evidencia_clasificador`, para que su «no consta» no lo mande de nuevo al clasificador.
    - Un comprador con `no_encaja` guardado ya no vuelve al clasificador aunque su motivo diga «no consta» (hasta el 18/11 un `no_encaja` con `fit=false` no llevaba regla).
  - **A quién no toca:** a nadie a quien Gustavo o LinkedIn le dijeron que no, a quien Gustavo confirmó, ni a quien está invitado, conectado o cerrado. Tampoco restaura a quien salió por una regla del código (sin cita del curso, tamaño, colega) ni a quien atiende otro miembro en el registro compartido (`registro.gate`).
  - **Registro y repetición:** cada fila deja `AuditEvent network.buyer_reevaluated`. Una segunda corrida no encuentra a nadie.
  - **Qué imprime:** filas por puntaje («`61* por_confirmar reclasificar Nombre · grupo · motivo`»; el `*` marca un puntaje provisional).
- **Criterios de aceptación:**
  1. **Dado** un founder en stealth en Nueva York sin datos públicos, **cuando** se clasifica y la web no encuentra nada en tres días, **entonces** sigue en el barrio `por_confirmar`, se sigue y se invita.
  2. **Dado** un comprador sin ronda visible, **cuando** termina el último intento, **entonces** queda `por_confirmar` (`ok`), no descartado. Solo la evidencia en contra con fuente (`no_encaja`) lo saca.
  3. **Dado** un comprador afín en Bogotá y otro en Austin, **cuando** se clasifican y se planifica, **entonces** los dos encajan y el de Austin va primero.
  4. **Dado** compradores de EE. UU. confirmado, probable y por confirmar, y de Latinoamérica con y sin negocio en EE. UU., **cuando** se planifica, **entonces** se invitan en ese orden y todos se invitan.
  5. **Dado** el calentamiento encendido y un comprador `por_confirmar` con señales recientes, **cuando** se ordena, **entonces** puede pasar a uno confirmado frío de su misma región, nunca a uno de una región anterior.
  6. **Dado** cupos por papel y pocos compradores, **cuando** se planifica, **entonces** sus turnos pasan a otros papeles y nadie espera.
  7. **Dado** una corrida de `reevaluar-compradores` sin `--confirmar`, **cuando** termina, **entonces** nada cambió; con `--confirmar` cada uno queda una vez y una segunda corrida no encuentra a nadie.
  8. **Dado** todos los `BUYER_*_ENABLED` apagados, **cuando** corre el caso `BAR-24-compradores`, **entonces** el resultado es el mismo y no se escribe ningún recorrido.
  9. **Dado** un lote de 10 por clasificar y compradores esperando su verificación, **cuando** corre `classify_contacts`, **entonces** solo clasifica y no se detiene por presupuesto. **Cuando** corre `check_buyer_stages`, verifica a uno, dentro de su propio presupuesto, y deja `ok` con nivel, fuentes y señales. La suma del peor caso de cada corrida del ciclo `red` no pasa su `cost_cap_usd` (18/11/2026).
  10. **Dado** un comprador que el modelo devuelve con `fit=false` y nivel `por_confirmar` o `probable` («es una hipótesis», confianza 0,5), **cuando** se clasifica, **entonces** entra con su nivel y su puntaje, se sigue y se invita, y queda un `network.buyer_fit_overridden` (18/11/2026).
  11. **Dado** un `no_encaja` sin motivo de la lista («tamaño no consta»), **cuando** se clasifica o lo juzga la web, **entonces** queda `por_confirmar`. Con motivo (`no_decide`, `idea_sin_empresa`…) sale, y el motivo queda en `buyer.against`.
  12. **Dado** compradores descartados con nivel `probable` o `por_confirmar`, **cuando** corre `reevaluar-compradores` sin `--confirmar`, **entonces** los lista en `descartado_con_nivel` sin cambiar nada ni pagar. Con `--confirmar` vuelven con su nivel y puntaje, una sola vez; nunca vuelven los vetados, los restringidos, los sacados por una regla ni los que atiende otro miembro.
- **Brechas:**
  - Cómo responde el modelo real con el prompt nuevo solo se mide con una corrida pagada. Las pruebas miden qué hace el código con cada respuesta. Desde el 18/11/2026 los dobles incluyen la forma real (`real` en `BUYERS_CASE` y `PROJECTAPP_CASE`): respuestas incoherentes como las de producción.
  - La reevaluación no se corrió contra ninguna base real: la aplica Gustavo en producción.
  - Entrarán más compradores con poca certeza (`por_confirmar`): el 18/11 habrían sido 12 de 16 en vez de 2. Ordenan por puntaje y nadie se descarta por eso; el riesgo es gastar invitaciones en gente que no compra, y se mide con la aceptación y las respuestas por nivel (`entrada_comprador.por_nivel`).
  - El puntaje usa el titular y la bio. Sin perfil leído, los componentes toman el valor del medio.
- **Cobertura QA:**
  - `tests/test_compradores_niveles.py`: el caso, niveles, puntaje, cupos y reevaluación. Desde el 18/11/2026 también el caso con la forma real (`RealShapeTests`), la tabla de `decide` (`DecideTests`), el juez sin motivo y el rescate `descartado_con_nivel` (`LeftByFitTests`).
  - `tests/test_red_eeuu.py`, `tests/test_red.py` y `tests/test_comprador.py`.
  - `tests/test_comprador_e2e.py`: el recorrido `por_confirmar`, el de Latinoamérica con y sin calentamiento, y la reverificación que sube el nivel. `RealShapeBuyerPathTests` (18/11/2026): `fit=false` con `por_confirmar` entra, se sigue y se invita; `no_encaja` con motivo sale y sin motivo se queda.
  - `tests/test_verificacion_etapa.py` (18/11/2026): con el cliente de Anthropic falso y los precios y reservas reales, cubre:
    - la clasificación sola;
    - la verificación en su corrida;
    - una por corrida y seis al día;
    - la cola del autopiloto (interruptor, ventana, cupo, presupuesto, sin duplicados);
    - el peor caso de cada corrida contra su `cost_cap_usd`;
    - la parada real que sigue avisando.
  - Se corrieron en local con proveedores falsos en una PostgreSQL desechable. La regresión completa corre en CI.

## El comprador de ProjectApp y el partner (17/11/2026)

### BAR-25 · El comprador de ProjectApp, el partner y la prueba de tres meses por segmento <a id="bar-25"></a>

- **Dónde:** backend · API · PWA (etiqueta «Partner»)
- **Estado:** implementado, apagado. `NETWORK_PROJECTAPP_BUYER_ENABLED=false` por defecto: apagado, prompts, esquemas, criterios, puntaje (v1), reparto, búsquedas, embudo y lectura son los de [BAR-24](#bar-24) (la prueba fija sus hashes de `origin/main`).
- **Qué hace para Gustavo:** además del comprador startup de antes, el barrio busca, juzga, ordena y mide al comprador de ProjectApp (empresas tradicionales de 20 a 200 personas en EE. UU.) y a los partners (agencias que subcontratan desarrollo), y solo cita los casos reales a un comprador de su mismo segmento con lo que Gustavo confirmó.
- **Decisiones de Gustavo (17/11/2026):** no se verticaliza el contenido; se verticaliza a quién se le escribe y con qué prueba. Comprador de ProjectApp: dueño o CEO, o líder de tecnología (suave 60 % líderes, 40 % dueños). Partner ≠ aliado. Oferta: equipo dedicado desde unos 20 millones de pesos al mes (unos 5.000 USD) o proyecto por requerimientos desde unos 20 millones; nearshore, buena calidad a menor costo. Casos: dos plataformas grandes a la medida (educación en línea y retail), nada más confirmado. Prueba del 17/11/2026 al 17/02/2027 con `educacion_en_linea`, `retail_ecommerce`, `duenos_latinos_eeuu` y `otro`. Señales de la clase 08 con fuente y fecha (contratar desarrolladores primero). 80 invitaciones por semana: ProjectApp 28, startup 12, partner 12, recomendador y aliado 8, par 10, divulgador 10. Sin post semanal de negocio: preguntas sobre los casos.
- **Dónde se perdía cada persona (línea base, [`linea-base-comprador-projectapp.md`](../../agentes-linkedin/infra/docs/linea-base-comprador-projectapp.md), 2/8):** el clasificador solo conocía compradores de startup (sin línea, segmento ni papel); el puntaje v1 no miraba el tamaño (la plomería de 5 personas empataba con la academia de 30); nada sacaba a una multinacional de 20.000 empleados (se invitaba segunda); la agencia de marketing que subcontrata desarrollo salía como aliado `fit=false`; el vecindario de `projectapp` era vago. Después: 8/8, orden P1, P2, P3.
- **Código:**
  - `projectapp.py` (nuevo): interruptor, líneas, papeles, segmentos, tamaño, búsquedas por audiencia, lectura de posts de partners, casos (`case_for`, `case_issues`, `ask_case_questions`, `case_facts`) y progreso de la prueba (`test_week`, `test_progress`).
  - `posicionamiento.py`: `PROJECTAPP_BUYER`, `PARTNER`, `OFFER`, `CASES`; `MODALITIES['projectapp']` refinado; `network_criteria(projectapp_buyer)` y `lead_criteria(projectapp_buyer)` (sin el argumento, el texto de antes).
  - `red.py`: `CLASSIFY_SYSTEM_PROJECTAPP`, `CLASSIFY_SCHEMA_PROJECTAPP`, `classify_system`, `classify_schema`, `classify_units`, `roles`, `_classify_batch` (línea, segmento, tamaño, `SIZE_RULE`), `STAGE_SYSTEM_PROJECTAPP`, `STAGE_SCHEMA_PROJECTAPP`, `_judge_stage`, `_settle_stage` (tamaño de la web y señales con fecha), `discover` (rotación por audiencia), `ROLE_LABELS['partner']`.
  - `nivel_comprador.py`: perfiles `dueno_empresa_tradicional` y `lider_tecnologia` con sus preguntas, `papel_of`, `score_v2` y la reevaluación (`_projectapp_group`, `actions`).
  - `reparto.py`: `PROJECTAPP_SHARE`, `keys_of`, `_mix` (60/40) y el déficit por grupo.
  - `calentamiento.py` (`group_of`, `used`: «comunidad» son los partners), `autopiloto._observe` y `_propose_groups`, `operador.observe`.
  - `lider.py`: `criteria_del_barrio()`, `ROLE_MEANING['partner']`, `BUYER_MEANING_PROJECTAPP`, `PARTNER_CHECK` (`competidor`) y `CASE_CHECK` (`caso_inventa`).
  - `mensajes_comprador.py`, `secuencia_comprador.py` (mensaje 2) y `respuesta_comprador.py` (interesado y pide información): el caso del segmento y `CASE_RULES`.
  - `comprador.py` (`_project`: línea y segmento; `funnel`: `por_linea`, `por_segmento`, `prueba_projectapp`), `lectura_embudo.py` (la línea de la prueba en Slack), `resultados.py` (`red.roles()`).
  - `BuyerJourney.line` y `segment` (migración `0054_linea_segmento_comprador`).
  - `manage.py operador reevaluar-compradores` (grupos nuevos) y `manage.py operador preguntas-casos-projectapp`.
  - Metodología `con_quien` de la clase 08 (`knowledge.clases.METODOLOGIAS_ACTIVAS`, `operador.WHO_UNITS`, grafo 6.16, registro `agentes-linkedin/equipos/observatorio/registro-lectura-con-quien.json`, caso `BIB-08-con-quien`).
  - PWA: `compartido/src/logic/format.ts`, `conexiones.ts`, `piece.ts`, `resultados.ts`.
- **Clasificación (una llamada, la misma de antes):** papeles par, recomendador, líder, comprador, divulgador, aliado y **partner**. El comprador lleva `buyer_profile` (que decide la línea), `buyer_level`, `buyer_segment`, `company_size` y `us_market`. El código completa `buyer.line`, `papel`, `segment`, `also_segments` y `company_size` (`projectapp.complete`). Más de 1000 personas es `no_encaja` con `SIZE_RULE`, diga lo que diga el modelo. El clasificador carga NETWORK_UNITS más las 9 unidades de `con_quien`.
- **Segmento (`projectapp.segments`):** la industria gana (`educacion_en_linea`, `retail_ecommerce`); `duenos_latinos_eeuu` es un dueño en EE. UU. que declara español (nunca por nombre o foto): su segmento si la industria es otra, una coincidencia adicional (`also_segments`) si no. El resto, `otro`.
- **Verificación web de ProjectApp:** la misma llamada pregunta el tamaño (`tamano`, solo con fuente) y las señales de la clase 08 (`contrata_desarrolladores`, `lanzamiento_digital`, `sistema_legado`, `crecimiento`), cada una con su fuente y su fecha; sin fecha no cuenta. La línea startup sigue con la pregunta de antes.
- **Puntaje v2 (`buyer_score_v2`):** ProjectApp: evidencia 32/21/10/0, tamaño 26 (20 a 200) / 13 sin dato / 8 (201 a 1000) / 2 (menos de 20) / 0, señal 10 contrata desarrolladores / 8 reciente (≤ 90 días) / 6 antigua / 5 sin dato, mercado 14/10/8 sin dato/4/2, papel 12 decide / 8 sin dato / 4 otro, confianza hasta 6. El dato que falta vale el punto medio de su componente. La línea startup conserva los componentes y puntos de v1. Ejemplos del caso: CTO de retail de 80 personas que contrata, `confirmado`: 32+26+10+14+12+5 = 99; dueña de una academia de 30 personas sin señal, `por_confirmar`: 10+26+5+14+12+5 = 72; plomería de 5 personas: 10+2+5+14+12+5 = 48.
- **Búsquedas (`projectapp.next_search`):** rotan por audiencia en proporción 28/12/12 (`NETWORK_SEARCH_AUDIENCE_SHARE`) dentro de `NETWORK_SEARCHES_PER_RUN` y del tope diario de búsquedas (20). Cada audiencia rota sus consultas: `NETWORK_SEARCH_QUERIES_PROJECTAPP`, `NETWORK_SEARCH_QUERIES` (startup, sin cambios) y `NETWORK_SEARCH_QUERIES_PARTNER`. `network.searched` guarda la audiencia. El conector solo filtra por palabras clave, ubicación e idioma: tamaño, industria, cargo y contratación no son filtros de LinkedIn (son de Sales Navigator).
- **Partner:** se sigue, sus posts se leen dentro del tope de lecturas de compradores (un cuarto, `projectapp.read_share`), se comenta en el cupo «comunidad» del día (2 de 15) hasta 2 veces en 30 días, y se invita en su cupo. No tiene recorrido de comprador ni mensajes. El líder pregunta `competidor` (una agencia de desarrollo es par).
- **Reparto:** sin `NETWORK_ROLE_SHARE` en el `.env`, el valor por defecto con el interruptor es `comprador_projectapp=28,comprador_startup=12,partner=12,recomendador+aliado=8,par=10,divulgador=10`. Si el `.env` lo fija (como `deploy/.env.example`, que trae el de BAR-24), hay que poner este valor a mano; vacío apaga los cupos. Los papeles `partner` y `comprador_*` solo valen con el interruptor: apagarlo con ellos en la variable es un error de configuración (`ValueError`), así que se revierten juntos. Dentro de ProjectApp, 60/40 suave entre líderes de tecnología y dueños (sin papel, turno de dueños). Un grupo sin candidatos cede su turno. El reporte del plan trae por grupo meta, invitados, déficit, listos y planeados, y el desglose por papel.
- **Prueba con casos:** el caso del segmento de la persona (`case_for`) entra en el mensaje 2 de la secuencia y en las respuestas a interesado y pide información, con `CASE_RULES`. `case_issues` (regla fija) rechaza un caso de otro segmento y una cifra que no esté en los hechos confirmados ni en la oferta; el líder pregunta `caso_inventa` (máx. 0,2). Los hechos salen solo de las respuestas de Gustavo con uso público a `preguntas-casos-projectapp` (cinco por caso; idempotente); un «no» a nombrar al cliente lo deja sin nombre.
- **El nivel decide (18/11/2026, [BAR-24](#bar-24)):** con el prompt de ProjectApp el modelo también respondía `fit=false` junto a `por_confirmar` o `probable` («tamaño no consta»). Ahora el nivel decide en las dos líneas, `demasiado_grande` es uno de los motivos de `no_encaja` (y lo pone el código si el perfil o la web dicen más de 1000 personas), y el caso `BAR-25-comprador-projectapp` pasa 8/8 también con la forma real de las respuestas (`real`).
- **Reevaluación (`reevaluar-compradores`, con el interruptor):** además de los grupos de BAR-24, `linea` (comprador en curso sin línea: completar en su lugar), `otra_linea` (encaja y nadie lo tocó: vuelve al clasificador) y `posible_partner` (agencia descartada como aliado, recomendador o divulgador: vuelve al clasificador). Nunca a quien dijo que no ni dos veces a la misma persona. En seco sin `--confirmar`.
- **Medición:** `GET /api/v1/resultados/embudo-comprador` trae `por_linea`, `por_segmento` (cada uno con la regla de muestra de 30) y `prueba_projectapp` (semana N de 13, invitaciones, aceptaciones, respuestas y reuniones por segmento, partners invitados, `muestra`). La lectura del lunes suma una línea: semana, invitaciones por segmento y partners, si alguno tiene muestra y la revisión del 17/02/2027.
- **Criterios de aceptación:**
  1. **Dado** el interruptor apagado, **cuando** corre el caso `BAR-25-comprador-projectapp`, **entonces** da la línea base (2/8) y los prompts tienen el hash de `origin/main`.
  2. **Dado** el interruptor encendido, **cuando** corre el caso, **entonces** 8/8: P1, P2 y P3 compradores de ProjectApp con su segmento y papel, P4 fuera por tamaño, P5 partner invitado sin recorrido, P7 en la línea startup; orden P1, P2, P3.
  3. **Dado** un comprador sin tamaño, sin señal, sin ubicación y sin cargo, **cuando** se puntúa, **entonces** cada componente toma su punto medio y el desglose suma el puntaje.
  4. **Dado** un partner seguido que publica, **cuando** el autopiloto comenta, **entonces** el comentario cuenta en «comunidad», se le invita y no tiene recorrido ni mensajes.
  5. **Dado** un texto que cita el caso de retail a una compradora de educación, o una cifra no confirmada, **cuando** se revisa, **entonces** la regla fija lo marca; el precio de la oferta no.
  6. **Dado** `reevaluar-compradores` sin `--confirmar`, **cuando** termina, **entonces** nada cambió; con `--confirmar` cada persona se mueve una vez y una segunda corrida no encuentra a nadie.
- **Brechas:**
  - Cómo responde el modelo real al prompt nuevo solo se mide en producción (o con una corrida pagada).
  - La reevaluación y las preguntas de los casos no se corrieron contra ninguna base real: las corre Gustavo.
  - Que la web devuelva el tamaño y la fecha de una vacante depende de lo que publique cada empresa.
  - La PWA solo muestra la etiqueta «Partner»; el embudo por segmento se lee en la API y en Slack.
- **Cobertura QA:**
  - `tests/test_comprador_projectapp.py`: el caso antes y después, el apagado, línea y segmento, perfiles, puntaje v2, reparto, búsquedas, casos, preguntas, reevaluación, embudo y lectura, activación y registro de `con_quien`.
  - `tests/test_comprador_e2e.py` (`ProjectAppPathTests`): el comprador de ProjectApp de la búsqueda a la aceptación y el partner de la búsqueda a la invitación.
  - `compartido/src/logic/conexiones.test.ts`: «Partner» y «Partners».
  - En local (17/11/2026), solo los archivos tocados y los que cubren el cambio, en una PostgreSQL desechable: `test_comprador_projectapp` (32), `test_comprador_e2e` (70), los módulos de niveles, calentamiento, comprador, red y red EE. UU. (133), respuesta, primer mensaje, secuencia, nota y comentario (81), grafo, biblioteca, evaluaciones, fase 2, auditorías y ProjectApp (170), `test_operador` (22); jest de conexiones y resultados (24). Seis mutaciones (regla de tamaño, punto medio del tamaño, caso de otro segmento, 60/40, reenvío doble, interruptor siempre encendido), todas detectadas. La regresión completa, en CI.
