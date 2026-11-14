# Comentarios y agente líder (`COM`)

El equipo observa los posts de los referentes de Gustavo, escribe comentarios en su voz y los publica solos. El agente líder (Jev, de TypeSafe) aprueba o descarta cada acción en lugar de Gustavo; nunca escala nada.

- **Código:** `agentes-linkedin/infra/src/team_backend/operador.py` (`observe`, `propose_comment`, `_draft_comment`, `execute`), `autopiloto.py` (`_observe`, `_lead_redraft`, `_propose`, `_prefilter`, `policy_review`, `content_issues`, `lead_silence`), `lider.py` (`review`, `comment_worthy`).
- **Documentación:** [`rediseno-backend.md`](../../agentes-linkedin/infra/docs/rediseno-backend.md), [`mapa-agentes-runtime.md`](../../agentes-linkedin/infra/docs/mapa-agentes-runtime.md), [`operador-linkedin.md`](../../agentes-linkedin/infra/docs/operador-linkedin.md).
- **Entorno de prueba:** cuenta `fake` (Unipile simulado), Claude y TypeSafe parcheados, como en `tests/test_operador.py` y `tests/test_auditoria_lider.py`.

## Resumen

| ID | Función | Dónde | Estado |
| --- | --- | --- | --- |
| [COM-01](#com-01) | Observar los posts de los referentes | backend | funciona |
| [COM-02](#com-02) | Prefiltro: ¿merece comentario este post? | backend | funciona |
| [COM-03](#com-03) | Redactar un comentario en la voz de Gustavo | backend | funciona |
| [COM-04](#com-04) | Reglas fijas del comentario y una reescritura | backend | funciona |
| [COM-05](#com-05) | El agente líder aprueba o descarta | backend | funciona |
| [COM-06](#com-06) | Publicar el comentario sin duplicarlo | backend | funciona |
| [COM-07](#com-07) | Aviso si el líder no aprueba nada en 7 días | backend | funciona |
| [COM-08](#com-08) | Reacciones (INT-02) | backend | parcial |
| [COM-09](#com-09) | Proponer un comentario a mano para un post | backend | parcial |
| [COM-10](#com-10) | Gestionar referentes | PWA · app · backend | funciona |
| [COM-11](#com-11) | Relaciones usa la evidencia de referentes y de su audiencia | backend | funciona |
| [COM-12](#com-12) | Un comentario que el líder descartó se reescribe una vez con sus razones | backend | implementado |

---

### COM-01 · Observar los posts de los referentes <a id="com-01"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Qué hace para Gustavo:** cada pocas horas el equipo lee los posts nuevos de sus referentes y le avisa si hay novedades.
- **Código:** `autopiloto._observe` (cada `OPERATOR_OBSERVE_EVERY_MINUTES`, 180), `operador.observe`.
- **Criterios de aceptación:**
  1. **Dado** referentes activos cuya última observación fue hace más de 180 min, **cuando** corre el autopiloto, **entonces** encola un trabajo `observe` (uno por franja).
  2. **Dado** posts nuevos, **cuando** termina la observación, **entonces** se guardan como `ObservedPost` y se registra la Notificación `observatory` «Observatorio encontró N posts nuevos de tus referentes» con enlace al calendario de hoy (sin push por defecto).
  3. **Dado** ningún referente activo, **cuando** corre el autopiloto, **entonces** no encola nada.
- **Brechas código/docs:** —
- **Cobertura QA:** pendiente

### COM-02 · Prefiltro: ¿merece comentario este post? <a id="com-02"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Qué hace para Gustavo:** antes de pagar un borrador, Jev descarta los posts donde comentar sería ruido (vacantes, promociones, hitos personales, temas ajenos).
- **Código:** `autopiloto._prefilter`, `lider.comment_worthy`, `PREFILTER_CHECKS`, `COMMENT_PREFILTER_THRESHOLD` (0,5).
- **Criterios de aceptación:**
  1. **Dado** `LEAD_ENABLED=true` y `COMMENT_PREFILTER=true`, **cuando** hay un post candidato sin veredicto, **entonces** Jev lo juzga y queda un `AuditEvent` `operator.comment_prefilter` con las probabilidades.
  2. **Dado** un post con `vacante` > 0,5, **cuando** se juzga, **entonces** se salta y el mismo post no se vuelve a preguntar.
  3. **Dado** un ciclo, **cuando** hay muchos candidatos, **entonces** se hacen como mucho 3 preguntas a Jev.
  4. **Dado** que Jev no responde, **cuando** se juzga, **entonces** el post pasa a borrador igual (como antes del prefiltro).
- **Brechas código/docs:** —
- **Cobertura QA:** pendiente

### COM-03 · Redactar un comentario en la voz de Gustavo <a id="com-03"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Qué hace para Gustavo:** el equipo escribe un comentario que aporta al post del referente, en su voz, con fundamento del curso.
- **Código:** `autopiloto._propose`, `operador.propose_comment`, `_draft_comment`, `COMMENT_SYSTEM`.
- **Criterios de aceptación:**
  1. **Dado** cupo de INT-03 libre tras los comentarios pendientes, presupuesto de IA del equipo sin agotar (`AI_MONTHLY_LIMIT_USD` y el tope de seguridad diario `AI_DAILY_FUSE_USD`) y menos de `OPERATOR_DAILY_PROPOSALS` (6) borradores hoy, **cuando** corre el autopiloto, **entonces** encola un `propose_comment` para el post candidato más reciente (de las últimas `OPERATOR_MAX_POST_AGE_HOURS`, 72 h).
  2. **Dado** un referente que ya tuvo un comentario en las últimas `OPERATOR_AUTHOR_COOLDOWN_HOURS` (48), **cuando** se buscan candidatos, **entonces** sus posts se saltan.
  3. **Dado** un borrador, **cuando** se guarda, **entonces** es una propuesta INT-03 con `payload.text`, `rationale`, `citations` y `risks`; si el redactor decide no comentar, queda descartada.
  4. **Dado** un `propose_comment` ya en cola, **cuando** corre el autopiloto, **entonces** no encola otro (un borrador pagado a la vez).
- **Brechas código/docs:** —
- **Cobertura QA:** pendiente

### COM-04 · Reglas fijas del comentario y una reescritura <a id="com-04"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Qué hace para Gustavo:** un comentario con pitch, enlaces, hashtags, datos de contacto o experiencias inventadas nunca sale; si se puede arreglar, se reescribe una vez.
- **Código:** `autopiloto.comment_text_issues`, `comment_author_issues`, `operador.propose_comment` (reescritura con `revision`).
- **Criterios de aceptación:**
  1. **Dado** un borrador de 30 caracteres, **cuando** se revisa, **entonces** aparece «Longitud fuera de 40–900 caracteres».
  2. **Dado** un borrador con un enlace, un correo, un teléfono, un hashtag o una petición de contacto, **cuando** se revisa, **entonces** aparece el motivo correspondiente.
  3. **Dado** un borrador que rompe una regla de texto, **cuando** se redacta, **entonces** se reescribe una sola vez con el borrador anterior y las reglas incumplidas.
  4. **Dado** que la reescritura sigue rompiendo reglas, **cuando** la revisa la política, **entonces** se descarta con «Descartada por política autonomia-v1».
- **Brechas código/docs:** —
- **Cobertura QA:** pendiente

### COM-05 · El agente líder aprueba o descarta <a id="com-05"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Qué hace para Gustavo:** Jev juzga cada comentario, pieza y acción de red con preguntas cerradas; si todo pasa con claridad, aprueba; si hay duda, descarta. Nada le llega a Gustavo para aprobar.
- **Código:** `autopiloto.policy_review`, `lider.review`, `lider.CHECKS`, `LEAD_ENABLED`, `LEAD_CAPABILITIES`, `LEAD_MAX_REVIEWS_PER_TICK`.
- **Criterios de aceptación:**
  1. **Dado** `LEAD_ENABLED=true` e INT-03 en `auto`, **cuando** un comentario pasa las reglas, **entonces** Jev responde `aporta`, `pitch`, `inventa`, `respeto` e `idioma`, y se aprueba solo si `aporta` ≥ 0,7, `pitch` ≤ 0,2, `inventa` ≤ 0,2, `respeto` ≥ 0,8 e `idioma` ≥ 0,7.
  2. **Dado** una orientación de Gustavo, **cuando** se revisa, **entonces** se añade `orientacion` ≥ 0,4.
  3. **Dado** cualquier umbral fallido, **cuando** se decide, **entonces** la acción pasa a `discarded` con «Descartada por el líder (…)» y `review` guarda respuestas, umbrales, modelo y coste. Un comentario así tiene una reescritura con esas razones ([COM-12](#com-12)).
  4. **Dado** que Jev no responde, **cuando** se revisa, **entonces** la acción queda en `proposed`, se reintenta tras `LEAD_RETRY_MINUTES` (10) y el resto del ciclo no vuelve a llamar a Jev.
  5. **Dado** más de 5 propuestas pendientes, **cuando** corre un ciclo, **entonces** el líder revisa como mucho `LEAD_MAX_REVIEWS_PER_TICK` (5), de la más antigua a la más reciente.
  6. **Dado** una acción de red, **cuando** la revisa el líder, **entonces** solo pregunta por riesgos concretos de la persona (perfil falso, cuenta de una organización, reclutador, prospector en frío; y, solo si el clasificador la marcó compradora, si vive de vender sus servicios), con el papel y la razón del clasificador a la vista: cada uno ≤ 0,6 para seguir y aceptar, ≤ 0,5 para invitar; el encaje no se vuelve a juzgar.
  7. **Dado** `LEAD_ENABLED=false`, **cuando** una acción pasa las reglas en `auto`, **entonces** se aprueba por política sin Jev.
- **Brechas código/docs:** —
- **Cobertura QA:** pendiente

### COM-06 · Publicar el comentario sin duplicarlo <a id="com-06"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Qué hace para Gustavo:** el comentario aprobado sale una sola vez, dentro del horario y los topes.
- **Código:** `operador.execute` (rama INT-03), `_find_own_comment`.
- **Criterios de aceptación:**
  1. **Dado** un comentario `approved`, dentro de `OPERATOR_WINDOW`, con espaciado y cupo, **cuando** se ejecuta, **entonces** se escribe una vez y, si al releer aparece, queda `confirmed`; si no aparece aún, queda `sent`.
  2. **Dado** que ya existe un comentario propio idéntico en ese post, **cuando** se ejecuta, **entonces** se confirma sin escribir («Ya existía un comentario propio idéntico; no se escribió otro.»).
  3. **Dado** fuera de la ventana horaria, **cuando** se intenta, **entonces** no se escribe y queda aprobado para después.
  4. **Dado** un resultado incierto, **cuando** termina, **entonces** queda `uncertain`, llega la push «¿Salió o no?» y aparece la tarjeta de Tu turno ([TUR-04](tu-turno.md#tur-04)).
- **Brechas código/docs:** —
- **Cobertura QA:** pendiente

### COM-07 · Aviso si el líder no aprueba nada en 7 días <a id="com-07"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Qué hace para Gustavo:** como el líder solo puede descartar, si en una semana no aprueba nada de una capacidad, Gustavo recibe un aviso para revisar umbrales u orientación.
- **Código:** `autopiloto.lead_silence` (cada `LEAD_SILENCE_CHECK_MINUTES`, 60).
- **Criterios de aceptación:**
  1. **Dado** `LEAD_ENABLED=true`, INT-03 en `auto` y al menos `LEAD_SILENCE_MIN_REVIEWS` (5) revisiones en 7 días sin ninguna aprobación, **cuando** corre la comprobación, **entonces** se guarda la Notificación `lead_silent` «El líder no aprobó nada de INT-03 en 7 días», con lo que más falla, push por defecto y enlace `/calendario?vista=lista&tipo=comentarios&no_salio=1`.
  2. **Dado** que ya se avisó esa capacidad esta semana ISO, **cuando** vuelve a correr, **entonces** no se repite.
  3. **Dado** una sola aprobación en los 7 días, **cuando** corre, **entonces** no hay aviso.
- **Brechas código/docs:** —
- **Cobertura QA:** pendiente

### COM-08 · Reacciones (INT-02) <a id="com-08"></a>

- **Dónde:** backend
- **Estado:** parcial
- **Qué hace para Gustavo:** el equipo podría reaccionar a los posts de sus referentes.
- **Código:** `operador.execute` ejecuta INT-02 (sin apilar una segunda reacción), y el calendario las cuenta. Ningún agente las propone y ninguna pantalla las crea: solo se pueden crear por la API del operador.
- **Criterios de aceptación:**
  1. **Dado** una propuesta INT-02 aprobada, **cuando** se ejecuta y el post no tenía reacción propia, **entonces** se añade la reacción y queda `confirmed` si al releer `user_reacted` es verdadero.
  2. **Dado** que el post ya tenía una reacción propia, **cuando** se ejecuta, **entonces** se confirma sin añadir otra.
  3. **Dado** posts observados que merecen reacción, **cuando** corre el autopiloto, **entonces** el equipo propone reacciones. **Hoy falla:** no hay código que las proponga.
- **Brechas código/docs:** `mapa-agentes-runtime.md` lo reconoce («No propone reacciones (INT-02 solo se crea a mano)»).
- **Cobertura QA:** pendiente

### COM-09 · Proponer un comentario a mano para un post <a id="com-09"></a>

- **Dónde:** backend
- **Estado:** parcial
- **Qué hace para Gustavo:** podría pedir al equipo un comentario para un post concreto.
- **Código:** `POST /api/v1/operador/posts/<id>/propose-comment` existe; ninguna pantalla de la PWA ni de la app lo usa.
- **Criterios de aceptación:**
  1. **Dado** un post observado, **cuando** se llama a la ruta con sesión humana y los permisos, **entonces** se encola la redacción y aparece una propuesta INT-03.
  2. **Dado** la PWA o la app, **cuando** Gustavo mira un post de un referente, **entonces** puede pedirlo desde ahí. **Hoy falla:** no hay botón.
- **Brechas código/docs:** la PWA anterior al rediseño tenía la pantalla `/acciones`; el rediseño la redirige a `/calendario`.
- **Cobertura QA:** pendiente

### COM-10 · Gestionar referentes <a id="com-10"></a>

- **Dónde:** PWA · app · backend
- **Estado:** funciona
- **Qué hace para Gustavo:** decide a quién observa el equipo: añade, desactiva, reactiva o quita referentes.
- **Código:** `GET|POST /api/v1/operador/referents`, `PATCH|DELETE /api/v1/operador/referents/<id>`. La interfaz está en [PRS-12](personas-oportunidades.md#prs-12).
- **Criterios de aceptación:**
  1. **Dado** una cuenta y un identificador de LinkedIn con motivo, **cuando** Gustavo añade un referente, **entonces** aparece en la lista y la siguiente observación lo incluye.
  2. **Dado** un referente, **cuando** lo desactiva con `PATCH {active: false, reason}`, **entonces** deja de observarse y sus posts dejan de ser candidatos a comentario.
  3. **Dado** un referente, **cuando** lo quita, **entonces** la API responde 204 y desaparece de la lista.
  4. **Dado** la lista, **cuando** se carga, **entonces** cada referente muestra `contacts_count` (personas del barrio salidas de sus posts).
- **Brechas código/docs:** ver [PRS-12](personas-oportunidades.md#prs-12) para lo que muestra cada interfaz. La evolución [OBS-02](observatorio-referentes.md#obs-02), **implementada en fase 5**, añade `protected`, gestión exclusiva de Gustavo desde Personas › Referentes o Tu turno y auditoría de sus cambios; el CRUD revalida protección, versión y capacidad en una transacción.
- **Cobertura QA:** pendiente

### COM-11 · Relaciones usa la evidencia de referentes y de su audiencia <a id="com-11"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Qué hace para Gustavo:** la participación en posts de referentes se apoya en la conversación y en lo aprendido de su audiencia, manteniendo el trabajo de Relaciones.
- **Responsable:** `relaciones_comunidad`; `investigador_referentes` aporta investigación y `analista_barrio_resultados` señales de participación.
- **Cadencia:** oportunidades de comentario **cada día**, según ritmo/caps y agenda [BAR-15](red.md#bar-15), con evidencia semanal y foco experimental si lo hay; calidad y cooldown por autor prevalecen.
- **Tu turno:** ninguna aprobación rutinaria adicional de comentarios; los cambios de referentes y experimentos siguen TUR-20/21 y las acciones conservan su política actual.
- **Datos necesarios y disponibilidad:** Dossier, evidencia agregada y foco aprobado entran a Relaciones por la arista `senales_referentes`; no se transfieren mensajes privados ni se inventan seguidores.
- **Código:** `experimentos.signals/eligible/execution_issues`, `operador.run_job/propose_comment/final_write_gate`, `autopiloto._propose`.
- **Criterios de aceptación:**
  1. **Dado** un post de referente activo, **cuando** Relaciones propone comentar, **entonces** recibe el texto y URL, comentarios accesibles, por qué interesa ese referente y señales pertinentes de OBS-03/04, y redacta una aportación situada sin inventar el hilo que no pudo leer.
  2. **Dado** participantes de ese referente presentes en el barrio, **cuando** usa su contexto, **entonces** toma procedencia/encaje de BAR-14 para entender problemas y argumentos, sin insertar datos privados, mencionar personas para atraerlas ni inferir que son seguidores de Gustavo.
  3. **Dado** falta de dossier o señales, **cuando** hay un post legible, **entonces** puede seguir el flujo actual con la evidencia disponible y explicitar el alcance; si no puede verificar el contenido base, no redacta un comentario que finja haberlo leído.
  4. **Dado** cualquier comentario o foco, **cuando** pasa a ejecución, **entonces** conserva guardas, líder, enfriamiento y Operación, con caps/agenda BAR-15; las reacciones pertenecen a ese ritmo y no autorizan envíos de inbox.
  5. **Dado** la actividad diaria, **cuando** redacta/verifica un comentario, **entonces** lo entrega en inglés, con aporte situado y fundamento del curso; no publica elogio vacío, pitch ni repetición para alcanzar 100 interacciones. La falta de aporte se informa y no se compensa con ráfagas.
- **Brechas código/docs:** implementación entregada en fase 5; ejecución de CI/QA delegada a Claude, sin pruebas locales. Conservar los límites observacionales de OBS-03.
- **Cobertura QA:** casos sintéticos en `test_referentes_mensuales.py`, Jest/Vitest y `19-referentes-mensual.yaml`; pendientes de ejecución por Claude. [Entrega y verificaciones](../../agentes-linkedin/infra/docs/referentes-mensuales.md).

### COM-12 · Un comentario que el líder descartó se reescribe una vez con sus razones <a id="com-12"></a>

- **Dónde:** backend
- **Estado:** implementado
- **Qué hace para Gustavo:** si Jev descarta un comentario («no aporta una idea concreta», «suena a venta»…), el equipo lo reescribe una vez sabiendo por qué, y Jev juzga el texto nuevo. Antes ese descarte era definitivo. Nunca hay una tercera vuelta.
- **Origen:** Gustavo, 14/11/2026: «si nos bloquea buscar una manera de reintentar… tampoco iteraciones infinitas» ([`compuertas.md`](../../agentes-linkedin/infra/docs/compuertas.md)).
- **Código:** `autopiloto._lead_redraft` (en cada tick, antes de `_propose`), `operador.propose_comment(redraft_of=…)`, `operador.run_job` (`params.redraft_of`), `COMMENT_SYSTEM` (`revision.lead_reasons`), `compuertas.lead_redraft`, `compuertas.LEAD_REDRAFT`.
- **Criterios de aceptación:**
  1. **Dado** `LEAD_ENABLED=true`, INT-03 en `auto`, `COMMENT_LEAD_REDRAFT=true` (por defecto) y un comentario del equipo que Jev descartó en las últimas 24 h, sobre un post de un referente activo de menos de `OPERATOR_MAX_POST_AGE_HOURS`, **cuando** corre el autopiloto con cupo de INT-03, presupuesto de IA, sitio en `OPERATOR_DAILY_PROPOSALS` y ningún `propose_comment` en cola, **entonces** encola un `propose_comment` con `{post, redraft_of}` (id determinista por descarte).
  2. **Dado** ese trabajo, **cuando** redacta, **entonces** el redactor recibe `revision: {previous_comment, lead_reasons}` y la propuesta nueva lleva el riesgo «Reescrito una vez con las razones del líder: …»; pasa por las reglas fijas y por Jev como cualquier comentario.
  3. **Dado** que la reescritura rompe una regla fija, **cuando** se redacta, **entonces** no tiene la reescritura por reglas de [COM-04](#com-04): la política la descarta.
  4. **Dado** un post que ya tiene dos borradores de comentario, **cuando** corre el autopiloto o se pide otra reescritura, **entonces** no se encola nada y `propose_comment` responde «Este comentario ya se reescribió una vez con las razones del líder…».
  5. **Dado** un descarte por las reglas (no por Jev), una decisión del redactor de no comentar o un descarte de hace más de 24 h, **cuando** corre el autopiloto, **entonces** no hay reescritura por el líder.
  6. **Dado** la auditoría de compuertas, **cuando** la reescritura se aprueba, **entonces** cuenta en «Líder (Jev) · INT-03» como «pasó tras reintento», y «Descartes sin reescritura» cuenta los descartes que no tuvieron otro borrador.
- **Brechas código/docs:** las respuestas INT-04 no tienen esta reescritura.
- **Cobertura QA:** `tests/test_compuertas.py` (`LeadRedraftTests`), escrito; CI pendiente.

## Retiradas

Ninguna.
