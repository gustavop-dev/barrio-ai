# Personas y oportunidades (`PRS`)

El barrio de Gustavo (las personas que el equipo descubre, sigue, invita y conecta), la ficha de cada persona, sus oportunidades de negocio y los referentes que el equipo observa. Lo que hace el equipo por detrás está en [red.md](red.md), [inbox.md](inbox.md) y [comentarios-y-lider.md](comentarios-y-lider.md).

- **Código:** backend `red_views.py` (`Contacts`, `ContactDetail`, `ContactDiscard`, `ContactNotes`, `Summary`), `serializers.ContactOutput`, `rediseno_views.Opportunities`, `OpportunityDetail`, `oportunidades.py`, `operador_views.Referents`, `ReferentDetail`; PWA `oficina/src/pages/Personas.tsx`, `Persona.tsx`, `pages/personas/*`; app `movil/src/personas/*`, `movil/src/app/(app)/personas/[id].tsx`; común `compartido/src/api/personas.ts`, `compartido/src/logic/personas.ts`, `barrio.ts`, `journey.ts`.
- **Documentación:** secciones «Red» y «Personas» de [`CONTRATO-API.md`](../../oficina/CONTRATO-API.md), [`rediseno-backend.md`](../../agentes-linkedin/infra/docs/rediseno-backend.md).

## Resumen

| ID | Función | Dónde | Estado |
| --- | --- | --- | --- |
| [PRS-01](#prs-01) | Barrio: la lista de personas y sus etapas | PWA · app · backend | funciona |
| [PRS-02](#prs-02) | Buscar y filtrar personas | PWA · app · backend | funciona |
| [PRS-03](#prs-03) | Ficha de una persona | PWA · app · backend | funciona |
| [PRS-04](#prs-04) | La conversación en la ficha | PWA · app · backend | funciona |
| [PRS-05](#prs-05) | Notas sobre una persona, escritas o de voz | PWA · app · backend | con fallo conocido |
| [PRS-06](#prs-06) | Descartar a una persona | PWA · app · backend | funciona |
| [PRS-07](#prs-07) | Tablero de oportunidades | PWA · app · backend | con fallo conocido |
| [PRS-08](#prs-08) | Registrar, editar y eliminar una oportunidad | PWA · app · backend | funciona |
| [PRS-09](#prs-09) | «Marcar como oportunidad» | PWA · app · backend | funciona |
| [PRS-10](#prs-10) | La oportunidad en la ficha y en el calendario | PWA · app · backend | funciona |
| [PRS-11](#prs-11) | Aviso de oportunidad nueva o que cambia de etapa | backend | funciona |
| [PRS-12](#prs-12) | Referentes | PWA · app · backend | funciona |

---

### PRS-01 · Barrio: la lista de personas y sus etapas <a id="prs-01"></a>

- **Dónde:** PWA · app · backend
- **Estado:** funciona
- **Qué hace para Gustavo:** ve a las personas de su barrio, en qué etapa está cada una y cuántas hay en cada etapa, con los avisos de la red.
- **Código:** `GET /api/v1/red/contacts`, `GET /api/v1/red/summary` ([BAR-11](red.md#bar-11)); PWA `personas/Barrio.tsx`; app `personas/Barrio.tsx`.
- **Criterios de aceptación:**
  1. **Dado** Personas, **cuando** lo abre, **entonces** ve las pestañas «Barrio», «Oportunidades» y «Referentes» (en la URL, `?pestana=`) y, en Barrio, los chips de etapa con su número: Todas, Por clasificar, Encaja, Seguido, Invitado, Conectado, En conversación, Oportunidad, Te invitó, Cerrado y Descartado.
  2. **Dado** cada persona, **cuando** se pinta, **entonces** muestra avatar, nombre (o «Sin nombre»), etapa, titular, chips de rol y modalidad (o «Sin clasificar todavía»), origen y última actividad, y «Te toca» si le toca a Gustavo.
  3. **Dado** un chip de etapa, **cuando** lo elige, **entonces** se filtra (`?etapa=`); «Oportunidad» muestra las personas con una oportunidad abierta.
  4. **Dado** `red/summary.enabled = false`, **cuando** abre Barrio, **entonces** ve «La red está apagada en el servidor» con «El equipo no descubre ni propone a nadie nuevo. Lo guardado sigue aquí.».
  5. **Dado** `invites_blocked.blocked = true`, **cuando** abre Barrio, **entonces** ve «Invitaciones en pausa: LinkedIn las limitó», el motivo y «El equipo sigue observando y siguiendo.».
  6. **Dado** el chip «En conversación» con número `null`, **cuando** se pinta, **entonces** aparece desactivado con «· aún no disponible».
  7. **Dado** ninguna persona, **cuando** abre Barrio, **entonces** ve «Aún no hay personas» con «El equipo empieza a descubrir cuando lee los comentarios de los referentes.».
  8. **Dado** la carga o un error, **cuando** abre Barrio, **entonces** ve «Cargando personas…» o el error con «Reintentar» («No se pudo actualizar la lista» si ya había datos).
  9. **Dado** más de una página, **cuando** pulsa «Cargar más», **entonces** carga la siguiente.
  10. **Dado** el enlace antiguo `/red` o `/referentes`, **cuando** lo abre, **entonces** llega a Personas (a la pestaña Referentes en el segundo caso).
- **Brechas código/docs:** si falla `red/summary`, los chips pierden sus números y los avisos desaparecen sin mensaje (las dos interfaces). «En conversación» sigue siempre sin datos aunque el inbox ya lee conversaciones ([BAR-11](red.md#bar-11)).
- **Cobertura QA:** pendiente

### PRS-02 · Buscar y filtrar personas <a id="prs-02"></a>

- **Dónde:** PWA · app · backend
- **Estado:** funciona
- **Qué hace para Gustavo:** busca por nombre o titular y filtra por rol del barrio, modalidad y origen.
- **Código:** parámetros `q`, `role`, `modality`, `source` de `GET /api/v1/red/contacts`.
- **Criterios de aceptación:**
  1. **Dado** «Buscar por nombre», **cuando** escribe «lucía», **entonces** a los 300 ms se filtra por nombre o titular (`?q=`).
  2. **Dado** «Más filtros», **cuando** elige «Rol del barrio», «Modalidad» u «Origen», **entonces** se filtra y el botón indica cuántos filtros hay activos.
  3. **Dado** filtros sin resultados, **cuando** se aplican, **entonces** ve «Nadie coincide con estos filtros» (o «Nadie en «<etapa>» ahora mismo» con solo la etapa) y «Quitar filtros».
- **Brechas código/docs:** —
- **Cobertura QA:** pendiente

### PRS-03 · Ficha de una persona <a id="prs-03"></a>

- **Dónde:** PWA · app · backend
- **Estado:** funciona
- **Qué hace para Gustavo:** abre a una persona y ve quién es, en qué punto del recorrido está, cuál es el siguiente paso y de quién depende, por qué encaja, de dónde salió y su historial.
- **Código:** `GET /api/v1/red/contacts/<id>` (`display_stage`, `next_step`, `your_turn`, `classification`, `evidence`, `history`); PWA `Persona.tsx` (al lado de la lista en escritorio); app `personas/PersonaScreen.tsx`, `Journey.tsx`.
- **Criterios de aceptación:**
  1. **Dado** una persona, **cuando** abre su ficha, **entonces** ve avatar, etapa, nombre enlazado a su perfil, titular, ubicación, grado («1.er grado», «2.º grado»…) y si la sigue, con «Abrir en LinkedIn».
  2. **Dado** el siguiente paso, **cuando** se pinta, **entonces** dice «Siguiente paso · Te toca» o «· Equipo», el texto (por ejemplo «El equipo la invitará cuando termine la espera»), la fecha y la acción abierta con su estado; con `your_turn`, «Ir a Tu turno».
  3. **Dado** el recorrido, **cuando** se pinta, **entonces** muestra Descubierto → (Te invitó | Seguido → Invitado) → Conectado → En conversación → Oportunidad, con la etapa alcanzada, o el final Descartado o Cerrado («Invitación ignorada o retirada»).
  4. **Dado** una clasificación, **cuando** se pinta «Por qué encaja», **entonces** ve rol, modalidad, afinidad, motivo, «Confianza N %» y la fecha; sin clasificar, «Sin clasificar todavía. El equipo la clasificará en el próximo ciclo.»; si no encaja, la etiqueta «No encaja».
  5. **Dado** el origen, **cuando** se pinta «De dónde salió», **entonces** ve «Comentó en un post de <referente>» con el comentario citado y «Ver el post», «Búsqueda: <consulta>», «Te invitó» con el mensaje, o «Añadido a mano».
  6. **Dado** «Historial completo», **cuando** lo abre, **entonces** ve los eventos (hasta 30) o «Sin eventos todavía.».
  7. **Dado** un id que no existe, **cuando** abre la ficha, **entonces** ve «No encontramos a esta persona» con «Puede que el enlace sea viejo.» y «Volver a Personas».
  8. **Dado** la carga o un error, **cuando** abre la ficha, **entonces** ve «Cargando la ficha…» o el error con «Reintentar».
  9. **Dado** la PWA en escritorio sin persona elegida, **cuando** abre Personas, **entonces** ve «Elige a alguien de la lista».
- **Brechas código/docs:** —
- **Cobertura QA:** pendiente

### PRS-04 · La conversación en la ficha <a id="prs-04"></a>

- **Dónde:** PWA · app · backend
- **Estado:** funciona
- **Qué hace para Gustavo:** en la ficha ve los últimos mensajes con esa persona y la lectura del equipo, y abre el hilo en LinkedIn.
- **Código:** `ContactOutput.conversation` ([INB-06](inbox.md#inb-06)); PWA y app `ConversationBlock.tsx`.
- **Criterios de aceptación:**
  1. **Dado** una conversación leída, **cuando** abre la ficha, **entonces** ve las etiquetas de la lectura («Posible oportunidad · <modalidad>», «Espera tu respuesta», «Parece venta o spam» o «Sin señales de negocio ni respuesta pendiente»), las probabilidades («Oportunidad 86 % · Espera respuesta 81 % · Venta o spam 4 %»), los últimos mensajes («Tú» o el nombre, y cuándo), «La app nunca envía mensajes: respondes tú en LinkedIn.» y «Abrir en LinkedIn».
  2. **Dado** que el equipo aún no juzgó el último mensaje, **cuando** se pinta, **entonces** ve «El equipo aún no ha leído su último mensaje.».
  3. **Dado** que no hay conversación, **cuando** se pinta, **entonces** ve «Aún no hay una conversación leída con esta persona» con «Cuando el equipo lea tu inbox de LinkedIn verás aquí sus últimos mensajes y su lectura. La app nunca envía mensajes.».
  4. **Dado** los mensajes, **cuando** se pintan, **entonces** son texto plano, nunca HTML.
- **Brechas código/docs:** —
- **Cobertura QA:** pendiente

### PRS-05 · Notas sobre una persona, escritas o de voz <a id="prs-05"></a>

- **Dónde:** PWA · app · backend
- **Estado:** con fallo conocido
- **Qué hace para Gustavo:** apunta lo que sabe de una persona, escribiendo o con una nota de voz.
- **Código:** `POST /api/v1/red/contacts/<id>/notas {text}`; «Nota de voz» abre la captura con contexto `persona` ([CAP-07](captura.md#cap-07)).
- **El fallo:** en la app, una nota de voz no llega ([CAP-04](captura.md#cap-04)). La nota escrita funciona.
- **Criterios de aceptación:**
  1. **Dado** «Añadir nota», **cuando** escribe y pulsa «Guardar nota», **entonces** la API responde 201, aparece «Nota guardada» y la nota sale como «Tu nota · <fecha>».
  2. **Dado** una nota vacía, **cuando** intenta guardar, **entonces** no se envía.
  3. **Dado** «Nota de voz», **cuando** graba y envía, **entonces** al procesarse aparece en las notas con la transcripción y `source: "captura"`. **Hoy falla en la app.**
  4. **Dado** ninguna nota, **cuando** abre la ficha, **entonces** ve «Aún no hay notas sobre esta persona.».
  5. **Dado** un usuario sin `approve_actions` o un token de servicio, **cuando** intenta añadir una nota, **entonces** recibe 403.
- **Brechas código/docs:** en la app, si la sesión se restaura sin usuario (ver [ACC-06](acceso.md#acc-06)), sus propias notas se etiquetan «Nota de <usuario>» en vez de «Tu nota».
- **Cobertura QA:** pendiente

### PRS-06 · Descartar a una persona <a id="prs-06"></a>

- **Dónde:** PWA · app · backend
- **Estado:** funciona
- **Qué hace para Gustavo:** descarta a alguien que no le interesa, con un motivo; el equipo no vuelve a proponerlo.
- **Código:** `POST /api/v1/red/contacts/<id>/discard {note}` ([BAR-10](red.md#bar-10)).
- **Criterios de aceptación:**
  1. **Dado** una persona en Por clasificar, Encaja, Seguido o Te invitó, **cuando** abre su ficha, **entonces** ve «Descartar»; en las demás etapas no aparece.
  2. **Dado** «Descartar», **cuando** lo pulsa, **entonces** ve «Descartar a <nombre>» con la nota obligatoria «Por qué la descartas» y «No volverá a proponerse: el equipo no la seguirá ni la invitará. Si tiene una acción abierta, se veta.».
  3. **Dado** que confirma, **cuando** termina, **entonces** aparece «Descartada: no volverá a proponerse», la etapa pasa a Descartado y su acción abierta queda vetada.
  4. **Dado** un 409 (ya invitada o con una acción ejecutándose), **cuando** vuelve, **entonces** el motivo se ve dentro de la confirmación.
  5. **Dado** el descarte, **cuando** termina, **entonces** no hay «Deshacer» (comportamiento actual).
- **Brechas código/docs:** —
- **Cobertura QA:** pendiente

### PRS-07 · Tablero de oportunidades <a id="prs-07"></a>

- **Dónde:** PWA · app · backend
- **Estado:** con fallo conocido
- **Qué hace para Gustavo:** ve sus oportunidades por etapa y las mueve arrastrando o eligiendo la etapa, con «Deshacer».
- **Código:** `GET /api/v1/oportunidades?page_size=100`, `PATCH /api/v1/oportunidades/<id> {stage}`; PWA `personas/Oportunidades.tsx`; app `personas/Oportunidades.tsx`, `drag.ts`.
- **El fallo:** el tablero pide una sola página de 100 y no pide más, así que con más de 100 oportunidades las demás no aparecen y no se avisa. Además, el evento del calendario de una oportunidad sin persona enlaza a `/personas?tab=oportunidades` y las dos interfaces solo entienden `?pestana=`, así que abre Barrio.
- **Criterios de aceptación:**
  1. **Dado** oportunidades, **cuando** abre la pestaña Oportunidades, **entonces** las ve agrupadas por etapa (Conversación, Necesidad identificada, Cualificada, Reunión, Propuesta, Acuerdo), cada una con nombre (enlazado si es un contacto), empresa, modalidad, «Siguiente acción», «N días en la etapa», un selector de etapa y «Editar»; las cerradas sin acuerdo van en un pliegue.
  2. **Dado** una oportunidad, **cuando** la arrastra a otra columna (o mantiene pulsado y la suelta en la app, o cambia el selector), **entonces** se mueve al momento, se envía el `PATCH`, aparece «Movida a «<etapa>»» con «Deshacer» y el historial guarda «<antes> → <después>».
  3. **Dado** que el `PATCH` falla, **cuando** vuelve el error, **entonces** la tarjeta vuelve a su etapa y se ve «No se pudo cambiar la etapa».
  4. **Dado** «Deshacer», **cuando** lo pulsa, **entonces** vuelve a la etapa anterior; si ese envío falla, se ve un error (hoy no se avisa: se corrige solo en la siguiente carga).
  5. **Dado** ninguna oportunidad, **cuando** abre la pestaña, **entonces** ve «Aún no hay oportunidades» con «Regístrala cuando una conversación tenga una necesidad real. Así Resultados empieza a medir el negocio.».
  6. **Dado** 120 oportunidades, **cuando** abre el tablero, **entonces** ve las 120. **Hoy falla:** ve 100.
  7. **Dado** el evento del calendario de una oportunidad sin persona, **cuando** lo abre, **entonces** llega a la pestaña Oportunidades. **Hoy falla.**
- **Brechas código/docs:** la notificación de la misma oportunidad enlaza a `/personas?pestana=oportunidades` (correcto) y el calendario a `?tab=` (`rediseno_views.Calendar`). En la app no se puede arrastrar a «Cerrada sin acuerdo» (sí con el selector).
- **Cobertura QA:** pendiente

### PRS-08 · Registrar, editar y eliminar una oportunidad <a id="prs-08"></a>

- **Dónde:** PWA · app · backend
- **Estado:** funciona
- **Qué hace para Gustavo:** registra una oportunidad con alguien del barrio o de fuera, con la modalidad, el canal, la etapa, cómo llegó, la necesidad y la siguiente acción; la edita o la elimina.
- **Código:** `POST /api/v1/oportunidades`, `PATCH|DELETE /api/v1/oportunidades/<id>` (`oportunidades.create`, `update`, `delete`); PWA y app `OportunidadForm.tsx`.
- **Criterios de aceptación:**
  1. **Dado** «Nueva oportunidad», **cuando** elige a una persona «De Personas» (búsqueda desde 2 letras) o escribe «Alguien fuera de la red», la modalidad y cómo llegó, **entonces** «Registrar oportunidad» la crea (201), aparece «Oportunidad registrada» y sale en el tablero.
  2. **Dado** que falta la persona, la modalidad o cómo llegó, **cuando** intenta guardar, **entonces** ve «Elige a alguien de Personas.», «Escribe el nombre de la persona.», «Elige la modalidad.» o «Elige cómo llegó.» y «Falta algo obligatorio: revisa los campos marcados.».
  3. **Dado** la API sin persona, **cuando** recibe el alta, **entonces** responde 400 «Elige una persona del barrio o escribe el nombre de alguien fuera de la red».
  4. **Dado** «Editar», **cuando** cambia campos y guarda, **entonces** aparece «Cambios guardados».
  5. **Dado** «Eliminar», **cuando** lo pulsa, **entonces** ve «Se borra la oportunidad con X y su historial. Deja de contar en Resultados. No se puede deshacer.»; al confirmar, la API responde 204 y aparece «Oportunidad eliminada».
  6. **Dado** la fecha de la siguiente acción, **cuando** la escribe en la app, **entonces** acepta `AAAA-MM-DD` (no hay selector de fecha) y avisa «Escribe la fecha como AAAA-MM-DD.» si no la entiende; la PWA usa un selector de fecha.
  7. **Dado** la siguiente acción con fecha, **cuando** se guarda, **entonces** aparece en la capa Tuyo del calendario ([PRS-10](#prs-10)).
- **Brechas código/docs:** —
- **Cobertura QA:** pendiente

### PRS-09 · «Marcar como oportunidad» <a id="prs-09"></a>

- **Dónde:** PWA · app · backend
- **Estado:** funciona
- **Qué hace para Gustavo:** desde la ficha de una persona, o desde una conversación en Tu turno, abre el formulario de oportunidad ya ligado a esa persona.
- **Código:** PWA `Persona.tsx`, `pages/turno/TurnoCardView.tsx` (formulario completo); app `PersonaScreen.tsx` (formulario completo) y `movil/src/turno/OpportunitySheet.tsx` (hoja reducida desde Tu turno).
- **Criterios de aceptación:**
  1. **Dado** una persona sin oportunidad, **cuando** abre su ficha, **entonces** ve «Marcar como oportunidad»; con una oportunidad, no.
  2. **Dado** el botón, **cuando** lo pulsa, **entonces** se abre el formulario con la persona ya elegida y nada se guarda hasta pulsar el botón de guardar.
  3. **Dado** «Marcar como oportunidad» en una tarjeta de conversación, **cuando** lo pulsa, **entonces** el formulario llega con la modalidad leída, canal LinkedIn y la nota «Detectada por el equipo en una conversación de LinkedIn.» ([INB-05](inbox.md#inb-05)).
- **Brechas código/docs:** desde Tu turno, la app abre una hoja reducida («Nueva oportunidad», Modalidad, Canal, Notas) que siempre crea la oportunidad en «Conversación» y avisa «Oportunidad creada»; la PWA abre el formulario completo.
- **Cobertura QA:** pendiente

### PRS-10 · La oportunidad en la ficha y en el calendario <a id="prs-10"></a>

- **Dónde:** PWA · app · backend
- **Estado:** funciona
- **Qué hace para Gustavo:** en la ficha ve la oportunidad abierta de esa persona, y en el calendario la fecha de su siguiente acción.
- **Código:** `ContactOutput.opportunity`, `GET /api/v1/oportunidades?contact=<id>`; eventos `meeting` y `opportunity_next` de la capa Tuyo, `opportunity` de la capa Conversaciones.
- **Criterios de aceptación:**
  1. **Dado** una persona con oportunidad abierta, **cuando** abre su ficha, **entonces** ve la sección Oportunidad con la etapa, «N días en la etapa», necesidad, canal, cómo llegó, presupuesto, dedicación, siguiente acción y «Editar oportunidad»; su etapa visible pasa a «Oportunidad».
  2. **Dado** una siguiente acción con fecha, **cuando** abre el calendario ese día, **entonces** aparece en Tuyo «<siguiente acción> · <persona>» (como reunión si la etapa es Reunión).
  3. **Dado** una oportunidad creada o que cambia de etapa, **cuando** abre el calendario ese día, **entonces** aparece en Conversaciones «Oportunidad con <persona>: …».
  4. **Dado** una oportunidad cerrada (acuerdo o sin acuerdo), **cuando** abre el calendario, **entonces** su siguiente acción ya no aparece.
- **Brechas código/docs:** —
- **Cobertura QA:** pendiente

### PRS-11 · Aviso de oportunidad nueva o que cambia de etapa <a id="prs-11"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Qué hace para Gustavo:** cada oportunidad nueva o que avanza queda en Notificaciones.
- **Código:** `oportunidades._notify`, tipo `opportunity`.
- **Criterios de aceptación:**
  1. **Dado** una oportunidad nueva, **cuando** se registra, **entonces** se guarda la Notificación «Oportunidad con <persona>: <etapa>» con la siguiente acción (o la modalidad) como detalle, enlazada a la persona (o a `/personas?pestana=oportunidades`), sin push por defecto.
  2. **Dado** un cambio de etapa, **cuando** se guarda, **entonces** hay otra Notificación; la misma etapa dos veces no duplica (`ref` `opportunity:<id>:<etapa>`).
- **Brechas código/docs:** —
- **Cobertura QA:** pendiente

### PRS-12 · Referentes <a id="prs-12"></a>

- **Dónde:** PWA · app · backend
- **Estado:** funciona
- **Qué hace para Gustavo:** decide qué voces observa el equipo: añade, pide observar ya, desactiva, reactiva o quita referentes.
- **Código:** `GET|POST /api/v1/operador/referents`, `POST /api/v1/operador/observe`, `PATCH|DELETE /api/v1/operador/referents/<id>`; PWA y app `personas/Referentes.tsx`. Lo que hace el equipo con ellos: [COM-10](comentarios-y-lider.md#com-10).
- **Criterios de aceptación:**
  1. **Dado** la pestaña Referentes, **cuando** la abre, **entonces** ve cada referente con su nombre (enlace externo), «Activo» o «Inactivo», el motivo, «Observado hace X» o «Aún sin observar» y «N personas del barrio salieron de sus posts», con «Desactivar»/«Reactivar» y «Quitar».
  2. **Dado** «Añadir referente», **cuando** pega una URL de perfil y un motivo, **entonces** aparece «Referente añadido»; una URL inválida da «Pega la URL de un perfil: https://www.linkedin.com/in/…» y sin motivo «El motivo es obligatorio.».
  3. **Dado** «Observar ahora», **cuando** lo pulsa, **entonces** se encola la observación y aparece «Observación encolada. Los posts nuevos aparecerán en unos minutos».
  4. **Dado** «Desactivar», **cuando** lo pulsa, **entonces** aparece «Referente desactivado» con «Deshacer».
  5. **Dado** «Quitar», **cuando** confirma «Quitar a X» («El equipo deja de leer sus posts. Las personas que ya salieron de ellos siguen en el barrio. Si solo quieres una pausa, desactívalo.»), **entonces** aparece «Referente quitado».
  6. **Dado** más de una cuenta, **cuando** abre la pestaña, **entonces** puede elegir la cuenta; sin cuentas, ve «No hay ninguna cuenta de LinkedIn» con «Conecta la cuenta en el servidor para elegir referentes.».
  7. **Dado** ningún referente, **cuando** abre la pestaña, **entonces** ve «Aún no hay referentes» con «Añade a alguien cuya conversación importe para tu barrio: el equipo empieza a descubrir personas en sus posts.».
- **Brechas código/docs:** la API permite cambiar el motivo de un referente (`PATCH {reason}`) y ninguna interfaz lo ofrece.
- **Cobertura QA:** pendiente

## Retiradas

Ninguna.
