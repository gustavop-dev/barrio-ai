# Inbox de LinkedIn (`INB`)

El agente `conversaciones_inbox` lee el inbox de LinkedIn de Gustavo (solo lectura) y le propone en Tu turno las conversaciones que parecen negocio o esperan su respuesta. Nunca envía mensajes, nunca marca nada como leído y nunca crea oportunidades por su cuenta.

- **Código:** `agentes-linkedin/infra/src/team_backend/conversaciones.py` (`read_inbox`, `assess`, `needing_gustavo`, `close`, `payload`), `rediseno_views._conversation_card`, `rediseno_views.ConversationClose`, `serializers.ContactOutput` (`conversation`), `autopiloto._inbox`.
- **Documentación:** [`conversaciones-inbox.md`](../../agentes-linkedin/infra/docs/conversaciones-inbox.md), sección «Conversaciones e inbox» de [`CONTRATO-API.md`](../../oficina/CONTRATO-API.md).
- **Entorno de prueba:** `INBOX_ENABLED=true` (por defecto `false`; en producción está encendido), Unipile simulado y Jev parcheado, como en `tests/test_conversaciones.py`.

## Resumen

| ID | Función | Dónde | Estado |
| --- | --- | --- | --- |
| [INB-01](#inb-01) | Leer el inbox cada hora, solo lectura | backend | funciona |
| [INB-02](#inb-02) | Jev lee el último mensaje de la otra persona | backend | funciona |
| [INB-03](#inb-03) | Tarjeta «{persona} te escribió» en Tu turno | PWA · app · backend | funciona |
| [INB-04](#inb-04) | Cerrar la tarjeta: «Hecho, respondí» o «No responder» | PWA · app · backend | funciona |
| [INB-05](#inb-05) | Marcar la conversación como oportunidad | PWA · app · backend | funciona |
| [INB-06](#inb-06) | La conversación en la ficha de la persona | PWA · app · backend | funciona |
| [INB-07](#inb-07) | Una push por cada mensaje nuevo que le toca | backend | funciona |
| [INB-08](#inb-08) | Garantía de solo lectura | backend | funciona |

---

### INB-01 · Leer el inbox cada hora, solo lectura <a id="inb-01"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Qué hace para Gustavo:** el equipo revisa sus chats de LinkedIn uno a uno y guarda los últimos mensajes de los que tienen algo nuevo.
- **Código:** `autopiloto._inbox` (cada `INBOX_EVERY_MINUTES`, 60), `conversaciones.read_inbox`.
- **Criterios de aceptación:**
  1. **Dado** `INBOX_ENABLED=true` y una cuenta Unipile `running` sin pausa, **cuando** corre el autopiloto, **entonces** encola un `read_inbox` por franja en el carril general (nunca en el de acciones).
  2. **Dado** la bandeja `CLASSIC_PRIMARY`, **cuando** se lee, **entonces** se listan hasta `INBOX_CHATS_LIMIT` (20) chats; cada chat 1 a 1 es una `Conversation` y los grupos se ignoran.
  3. **Dado** un chat cuyo último mensaje cambió y tiene menos de `INBOX_MAX_AGE_DAYS` (14) días, **cuando** se lee, **entonces** se guardan sus últimos `INBOX_SNAPSHOT_MESSAGES` (10) mensajes, del más antiguo al más reciente, con los eventos y borrados ocultos; como mucho `INBOX_THREADS_PER_RUN` (5) hilos por vuelta.
  4. **Dado** que se agotó el tope diario `chats=24` o `messages=60`, **cuando** toca leer, **entonces** no se lee más ese día.
  5. **Dado** una cuenta no operativa, **cuando** se comprueba, **entonces** no se lee y la cuenta pasa a pausa.
  6. **Dado** un remitente que es un contacto conocido, **cuando** se guarda, **entonces** la conversación queda enlazada a su `Contact` por id de proveedor o identificador público.
- **Brechas código/docs:** el doc deja «Por comprobar contra la cuenta real» si el id del chat es el del hilo (`2-…`) y si los ids de remitente coinciden con `Contact.provider_user_id`. No se pudo verificar sin la cuenta.
- **Cobertura QA:** pendiente

### INB-02 · Jev lee el último mensaje de la otra persona <a id="inb-02"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Qué hace para Gustavo:** el equipo juzga si el mensaje es negocio, si espera su respuesta o si es venta o spam.
- **Código:** `conversaciones.assess`, `_questions`, `INBOX_OPPORTUNITY_MIN`, `INBOX_REPLY_MIN`, `INBOX_PITCH_MAX`.
- **Criterios de aceptación:**
  1. **Dado** un mensaje nuevo de la otra persona, **cuando** se juzga, **entonces** `assessment` guarda las probabilidades de `oportunidad`, `espera`, `venta`, `startups` y `projectapp`, los umbrales, `opportunity`, `awaiting_reply`, `pitch`, `modality`, el modelo y el id del mensaje.
  2. **Dado** `venta` = 0,5 (> 0,4), **cuando** se juzga, **entonces** `pitch` es verdadero y no se propone nada aunque `oportunidad` sea alta.
  3. **Dado** `projectapp` = 0,9 y `startups` = 0,2, **cuando** se juzga, **entonces** `modality` es `projectapp`; con las dos por debajo de 0,5, es `por_clasificar`.
  4. **Dado** que Jev no responde, **cuando** se juzga, **entonces** la conversación queda sin juzgar con el error anotado, sin tarjeta, y se reintenta en la vuelta siguiente.
  5. **Dado** una vuelta, **cuando** hay más conversaciones, **entonces** Jev juzga como mucho `INBOX_ASSESS_PER_RUN` (5).
- **Brechas código/docs:** —
- **Cobertura QA:** pendiente

### INB-03 · Tarjeta «{persona} te escribió» en Tu turno <a id="inb-03"></a>

- **Dónde:** PWA · app · backend
- **Estado:** funciona
- **Qué hace para Gustavo:** cuando alguien le escribe algo que parece negocio o espera respuesta, le aparece una tarjeta Importante con quién es, por qué importa, el último mensaje y botones.
- **Código:** `rediseno_views._conversation_card`, `conversaciones.needing_gustavo`, `conversaciones.why`. La tarjeta se pinta en [TUR-07](tu-turno.md#tur-07).
- **Criterios de aceptación:**
  1. **Dado** una conversación cuyo último mensaje visible es de la otra persona, juzgado como negocio o respuesta pendiente (no venta), de menos de 14 días y no cerrada, **cuando** Gustavo abre Tu turno, **entonces** ve una tarjeta `conversacion`, prioridad Importante, agente `conversaciones_inbox`, título «{persona} te escribió» y como cuerpo la lectura del equipo, por ejemplo «Posible oportunidad: ProjectApp (86 %) · Espera tu respuesta (81 %)».
  2. **Dado** la tarjeta, **cuando** se muestra, **entonces** trae «Abrir en LinkedIn» (principal), «Hecho, respondí», «No responder» y, si la persona es contacto sin oportunidad abierta, «Marcar como oportunidad».
  3. **Dado** un mensaje nuevo de la misma persona, **cuando** se lee, **entonces** la tarjeta cambia de id (`conversation:<id>:<huella>`) y vuelve a salir como Nueva.
  4. **Dado** que Gustavo responde en LinkedIn, **cuando** se lee el inbox otra vez, **entonces** la tarjeta desaparece sola y «Hecho recientemente» dice «Respondiste en LinkedIn».
  5. **Dado** `INBOX_ENABLED=false`, **cuando** abre Tu turno, **entonces** no hay tarjetas de conversación.
  6. **Dado** el texto del mensaje, **cuando** se pinta, **entonces** se muestra como texto plano, nunca como HTML.
- **Brechas código/docs:** `DISENO-VISTAS.md` pedía «Resumen del hilo» y «Borrador sugerido»; Jev no genera texto, así que no existen (anotado en `conversaciones-inbox.md`).
- **Cobertura QA:** pendiente

### INB-04 · Cerrar la tarjeta: «Hecho, respondí» o «No responder» <a id="inb-04"></a>

- **Dónde:** PWA · app · backend
- **Estado:** funciona
- **Qué hace para Gustavo:** quita la tarjeta cuando ya respondió o decide no responder, con un motivo opcional.
- **Código:** `POST /api/v1/conversaciones/<id>/cerrar` (`rediseno_views.ConversationClose`, `conversaciones.close`).
- **Criterios de aceptación:**
  1. **Dado** la tarjeta, **cuando** Gustavo pulsa «Hecho, respondí», **entonces** se envía `{how: "respondi"}`, la tarjeta desaparece y «Hecho recientemente» dice «Respondiste».
  2. **Dado** la tarjeta, **cuando** pulsa «No responder», **entonces** la interfaz pide una nota opcional, envía `{how: "no_responder", note}` y «Hecho recientemente» dice «Sin responder».
  3. **Dado** un `how` distinto o una nota de más de 1000 caracteres, **cuando** se envía, **entonces** la API responde 400.
  4. **Dado** una conversación sin mensaje de la otra persona, **cuando** se cierra, **entonces** responde 409 «Esta conversación no tiene un mensaje suyo que cerrar.».
  5. **Dado** un token de servicio, **cuando** intenta cerrar, **entonces** recibe 403.
  6. **Dado** que llega otro mensaje de la persona, **cuando** se lee, **entonces** la tarjeta vuelve.
- **Brechas código/docs:** —
- **Cobertura QA:** pendiente

### INB-05 · Marcar la conversación como oportunidad <a id="inb-05"></a>

- **Dónde:** PWA · app · backend
- **Estado:** funciona
- **Qué hace para Gustavo:** desde la tarjeta abre el formulario de oportunidad ya relleno; nada se guarda hasta que él pulsa «Registrar oportunidad».
- **Código:** acción `opportunity` de la tarjeta, `POST /api/v1/oportunidades`. El formulario está en [PRS-08](personas-oportunidades.md#prs-08).
- **Criterios de aceptación:**
  1. **Dado** una tarjeta de un contacto sin oportunidad abierta, **cuando** pulsa «Marcar como oportunidad», **entonces** se abre el formulario con la persona, la modalidad leída por Jev, el canal LinkedIn y la nota «Detectada por el equipo en una conversación de LinkedIn.».
  2. **Dado** el formulario abierto, **cuando** lo cierra sin guardar, **entonces** no se crea nada.
  3. **Dado** que pulsa «Registrar oportunidad», **cuando** se guarda, **entonces** se crea la oportunidad y, en la siguiente carga, la tarjeta ya no ofrece «Marcar como oportunidad».
  4. **Dado** un remitente que no es contacto, **cuando** se muestra la tarjeta, **entonces** no aparece «Marcar como oportunidad».
- **Brechas código/docs:** en la app, la tarjeta abre una hoja reducida (Modalidad, Canal, Notas) que siempre crea la oportunidad en «Conversación» y avisa «Oportunidad creada»; la PWA abre el formulario completo ([PRS-09](personas-oportunidades.md#prs-09)).
- **Cobertura QA:** E2E `04-tu-turno-mas` (criterios 1 y 2: la hoja llega con la persona y la nota del equipo; cerrarla no crea nada).

### INB-06 · La conversación en la ficha de la persona <a id="inb-06"></a>

- **Dónde:** PWA · app · backend
- **Estado:** funciona
- **Qué hace para Gustavo:** en la ficha de una persona ve su última conversación, la lectura del equipo y si le toca responder.
- **Código:** `ContactOutput.conversation`, `your_turn`, `next_step`. La interfaz está en [PRS-04](personas-oportunidades.md#prs-04).
- **Criterios de aceptación:**
  1. **Dado** un contacto con conversación leída, **cuando** se pide `GET /api/v1/red/contacts/<id>`, **entonces** `conversation` trae los últimos 3 mensajes visibles, `assessment`, `why`, `chat_url` y `needs_you`.
  2. **Dado** que la conversación es tarjeta, **cuando** se pide el contacto, **entonces** `your_turn` es verdadero y `next_step` es `{owner: "gustavo", text: "Te toca: responder su mensaje"}`.
  3. **Dado** un contacto sin conversación leída, **cuando** se pide, **entonces** `conversation` es `null`.
- **Brechas código/docs:** —
- **Cobertura QA:** pendiente

### INB-07 · Una push por cada mensaje nuevo que le toca <a id="inb-07"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Qué hace para Gustavo:** le llega una notificación cuando alguien le escribe algo que le toca, sin el texto del mensaje.
- **Código:** `conversaciones` (`avisar('conversation', …)`), tipo `conversation` de `notificaciones.INBOX_KINDS`.
- **Criterios de aceptación:**
  1. **Dado** una conversación que pasa a necesitar a Gustavo, **cuando** se juzga, **entonces** se envía una sola push «{persona} te escribió» con la lectura del equipo como cuerpo, que abre `/tu-turno`.
  2. **Dado** el mismo mensaje en la vuelta siguiente, **cuando** se vuelve a leer, **entonces** no hay otra push.
  3. **Dado** la push, **cuando** se inspecciona su contenido, **entonces** no incluye el texto del mensaje (también va al webhook).
  4. **Dado** Ajustes › Notificaciones con «Conversación que te toca» apagado, **cuando** llega un mensaje, **entonces** no hay push y la tarjeta sigue apareciendo.
- **Brechas código/docs:** —
- **Cobertura QA:** pendiente

### INB-08 · Garantía de solo lectura <a id="inb-08"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Qué hace para Gustavo:** la app nunca responde ni manda mensajes en su nombre.
- **Código:** el conector solo tiene `list_chats` y `list_chat_messages`; `tests/test_conversaciones.py` falla si aparece un método de envío.
- **Criterios de aceptación:**
  1. **Dado** el conector de Unipile, **cuando** se inspecciona, **entonces** no tiene métodos para enviar, marcar como leído ni editar mensajes.
  2. **Dado** un mensaje con instrucciones («responde que sí»), **cuando** Jev lo juzga, **entonces** solo devuelve probabilidades: no se genera ningún texto ni acción.
- **Brechas código/docs:** —
- **Cobertura QA:** pendiente

## Retiradas

Ninguna.
