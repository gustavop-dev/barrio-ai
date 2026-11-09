# Tu turno (`TUR`)

Lo que solo Gustavo puede resolver: avisos que rompen algo sin él, preguntas del equipo, conversaciones que le tocan y la orientación que propone el analista. Incluye la pestaña «Lo que el equipo sabe de ti».

- **Código:** backend `rediseno_views.TuTurno`, `alerts`, `_question_card`, `_conversation_card`, `_summary_card`, `TuTurnoSeen`, `preguntas.py`; PWA `oficina/src/pages/TuTurno.tsx`, `pages/turno/*`; app `movil/src/app/(app)/(tabs)/tu-turno.tsx`, `movil/src/turno/*`; lógica común `compartido/src/logic/turno.ts`.
- **Documentación:** secciones «Tu turno» y «Notificaciones y prioridades de Tu turno (rev 18)» de [`CONTRATO-API.md`](../../oficina/CONTRATO-API.md), [`rediseno-backend.md`](../../agentes-linkedin/infra/docs/rediseno-backend.md).

## Resumen

| ID | Función | Dónde | Estado |
| --- | --- | --- | --- |
| [TUR-01](#tur-01) | Ver lo que depende de él, por prioridad | PWA · app · backend | funciona |
| [TUR-02](#tur-02) | Contador en la navegación | PWA · app · backend | funciona |
| [TUR-03](#tur-03) | Una tarjeta pasa de Nueva a Vista | PWA · app · backend | funciona |
| [TUR-04](#tur-04) | Aviso «¿Salió o no?» de una acción incierta | PWA · app · backend | funciona |
| [TUR-05](#tur-05) | Aviso de LinkedIn caducado o a punto de caducar | PWA · app · backend | funciona |
| [TUR-06](#tur-06) | Reanudar la máquina o la cuenta desde Tu turno | PWA · app · backend | funciona |
| [TUR-07](#tur-07) | Tarjeta de conversación que le toca | PWA · app · backend | funciona |
| [TUR-08](#tur-08) | Tarjeta de la orientación propuesta por el analista | PWA · app · backend | parcial |
| [TUR-09](#tur-09) | Responder una pregunta del equipo | PWA · app · backend | parcial |
| [TUR-10](#tur-10) | Responder una pregunta con audio | PWA · app · backend | funciona |
| [TUR-11](#tur-11) | «Más tarde» y las pospuestas | PWA · app · backend | funciona |
| [TUR-12](#tur-12) | «No quiero compartir esto» | PWA · app · backend | funciona |
| [TUR-13](#tur-13) | Preguntas cuyo plazo pasó | PWA · app · backend | funciona |
| [TUR-14](#tur-14) | Hecho recientemente | PWA · app · backend | funciona |
| [TUR-15](#tur-15) | Ver lo que el equipo sabe de él | PWA · app · backend | funciona |
| [TUR-16](#tur-16) | Añadir algo que quiere que sepan | PWA · app · backend | funciona |
| [TUR-17](#tur-17) | Editar o retirar un dato | PWA · app · backend | funciona |
| [TUR-18](#tur-18) | Tareas de perfil | PWA · app · backend | funciona |
| [TUR-19](#tur-19) | Deslizar una tarjeta | app | funciona |
| [TUR-20](#tur-20) | Decidir altas, bajas y sustituciones de referentes | PWA · app · backend | funciona |
| [TUR-21](#tur-21) | Decidir un experimento de participación | PWA · app · backend | funciona |

---

### TUR-01 · Ver lo que depende de él, por prioridad <a id="tur-01"></a>

- **Dónde:** PWA · app · backend
- **Estado:** funciona
- **Qué hace para Gustavo:** abre Tu turno y ve, ordenado de lo más urgente a lo que puede esperar, todo lo que solo él puede resolver; si no hay nada, ve qué hizo el equipo hoy.
- **Código:** `GET /api/v1/tu-turno` (`rediseno_views.TuTurno`, `_ordered`); PWA `pages/turno/Pendiente.tsx`; app `movil/src/turno/TuTurnoScreen.tsx`.
- **Criterios de aceptación:**
  1. **Dado** un aviso urgente, uno importante y dos preguntas sin prisa, **cuando** abre Tu turno, **entonces** ve los grupos «Urgente · 1», «Importante · 1» y «Cuando puedas · 2», en ese orden, y el subtítulo «1 urgente · 1 importante · 2 cuando puedas» (PWA).
  2. **Dado** dos tarjetas de la misma prioridad, una con plazo y otra sin él, **cuando** se ordenan, **entonces** va primero la de plazo más cercano y después la más reciente.
  3. **Dado** que la máquina detenida desde la app, una acción incierta o LinkedIn caducado existen, **cuando** se calcula la prioridad, **entonces** son Urgente; LinkedIn que caduca en 3 días o menos, una cuenta en pausa, una pregunta con plazo en menos de 48 h, una conversación y una acción que espera su aprobación ([BAR-13](red.md#bar-13)) son Importante; el resto de preguntas y la orientación propuesta son Cuando puedas.
  4. **Dado** que no hay nada pendiente (aunque haya tarjetas caducadas, que siguen debajo en «Ya no es urgente»), **cuando** abre Tu turno, **entonces** ve «Nada depende de ti hoy», el resumen del día («Hoy el equipo publicó 1 post, comentó en 6…» o «Hoy el equipo aún no ha publicado ni interactuado.»), la hora de la próxima pieza si la hay y un enlace al Calendario.
  5. **Dado** que la carga está en curso, **cuando** abre la vista, **entonces** ve un esqueleto «Cargando lo que depende de ti…».
  6. **Dado** un error en la primera carga, **cuando** falla, **entonces** ve «No se pudo completar» con el detalle y «Reintentar»; si ya había datos, ve «No se pudo actualizar» y las tarjetas siguen visibles.
  7. **Dado** un aviso informativo (invitaciones limitadas, pieza bloqueada, presupuesto agotado), **cuando** abre Tu turno, **entonces** no aparece: está en Personas, Calendario o Ajustes.
  8. **Dado** el enlace `/tu-turno#turno-<id>`, **cuando** carga, **entonces** la vista baja hasta esa tarjeta.
  9. **Dado** que la máquina se detuvo desde el servidor (`OPERATOR_PAUSED`), **cuando** abre Tu turno, **entonces** no hay tarjeta: aparece en Notificaciones › Próximo ([NOT-03](notificaciones.md#not-03)).
- **Brechas código/docs:** el contrato documenta `top` «para la tarjeta de la Oficina»; ninguna interfaz lo usa (el diseño rev 18 quitó lo que había sobre la escena).
- **Cobertura QA:** E2E `04-tu-turno` (criterios 1, 3 y 9: grupos, orden y contador con las 8 tarjetas del mundo de QA) y `04-tu-turno-estados` (4 vacío y 6 «No se pudo actualizar» con el interruptor de fallos). El 2 (orden por plazo) y el 7 son del backend; el 5 (esqueleto) y el 8 (ancla), de Jest.

### TUR-02 · Contador en la navegación <a id="tur-02"></a>

- **Dónde:** PWA · app · backend
- **Estado:** funciona
- **Qué hace para Gustavo:** en la barra ve cuántas cosas dependen de él, en rojo si alguna es urgente.
- **Código:** `count`, `critical`, `urgent_count` de `GET /api/v1/tu-turno`; PWA `components/Layout.tsx`; app `components/shell/useTurnCount.ts`, `BottomBar.tsx` / `TopBar.tsx`.
- **Criterios de aceptación:**
  1. **Dado** tres tarjetas en estado Nueva o Vista y una pospuesta, **cuando** carga cualquier vista, **entonces** el contador muestra 3 (lo pospuesto y lo caducado no cuentan).
  2. **Dado** al menos una tarjeta urgente, **cuando** se pinta, **entonces** el contador es rojo; si no, es neutro.
  3. **Dado** 0 pendientes, **cuando** se pinta, **entonces** el contador no aparece.
  4. **Dado** más de 99 pendientes, **cuando** se pinta, **entonces** muestra «99+».
  5. **Dado** que `GET /api/v1/tu-turno` falla, **cuando** se pinta la barra, **entonces** el contador desaparece sin mensaje (comportamiento actual; la vista Tu turno sí muestra el error).
- **Brechas código/docs:** —
- **Cobertura QA:** E2E `04-tu-turno`, `04-tu-turno-aprobar` y `04-tu-turno-mas` (criterios 1 y 2: «Tu turno, 8 pendientes, 1 urgente», baja al resolver, «2 urgentes» con la máquina detenida). El 3 (sin contador) en `04-tu-turno-estados`; el 4 y el 5, Jest.

### TUR-03 · Una tarjeta pasa de Nueva a Vista <a id="tur-03"></a>

- **Dónde:** PWA · app · backend
- **Estado:** funciona
- **Qué hace para Gustavo:** lo que ya vio deja de marcarse como Nuevo la próxima vez.
- **Código:** `POST /api/v1/tu-turno/vistos` (`TuTurnoSeen`, modelo `InboxSeen`); PWA `pages/turno/useSeenCards.ts`; app `movil/src/turno/useSeenCards.ts`.
- **Criterios de aceptación:**
  1. **Dado** una tarjeta Nueva, **cuando** al menos la mitad (o 160 px) queda en pantalla, **entonces** se envía su id en `POST /api/v1/tu-turno/vistos` (en lotes) y en la siguiente carga llega con `state: "vista"`.
  2. **Dado** la misma visita, **cuando** ya se marcó, **entonces** la etiqueta «Nueva» sigue visible hasta salir de la vista.
  3. **Dado** una lista de ids que no es lista, con ids vacíos o de más de 120 caracteres, o con más de 200 ids, **cuando** se envía, **entonces** la API responde 400.
  4. **Dado** que el envío falla, **cuando** pasa, **entonces** no se avisa y se reintenta la próxima vez que la tarjeta aparece.
- **Brechas código/docs:** el contrato dice que la respuesta es `{seen}`; el tipo de `compartido/src/api/tuTurno.ts` espera `{count}`. No tiene efecto porque no se usa.
- **Cobertura QA:** E2E `04-tu-turno` (criterio 2: la etiqueta «Nueva» de la tarjeta urgente). El envío por lotes y los 400, backend.

### TUR-04 · Aviso «¿Salió o no?» de una acción incierta <a id="tur-04"></a>

- **Dónde:** PWA · app · backend
- **Estado:** funciona
- **Qué hace para Gustavo:** cuando LinkedIn no confirmó si una acción salió, comprueba en LinkedIn y dice si se aplicó o no, con una nota.
- **Código:** tarjeta `uncertain:<id>` de `rediseno_views.alerts`; `POST /api/v1/operador/actions/<id>/resolve`; PWA `pages/turno/TurnoCardView.tsx`; app `movil/src/turno/TurnoCard.tsx`, `actions.ts`.
- **Criterios de aceptación:**
  1. **Dado** una acción en `uncertain`, **cuando** abre Tu turno, **entonces** ve una tarjeta Urgente con un título según la capacidad (por ejemplo «Comprueba si salió tu comentario» o «Comprueba si salió tu publicación»), lo que se intentó (tipo, destino, hora, texto citado) y «Ver en LinkedIn».
  2. **Dado** la tarjeta, **cuando** pulsa «Sí, se aplicó», **entonces** se abre «Confirmar que se aplicó» con la nota obligatoria «Qué comprobaste»; sin nota no se envía.
  3. **Dado** una nota, **cuando** confirma, **entonces** se envía `{outcome: "confirmed", note}`, la acción queda `confirmed`, la tarjeta desaparece, aparece «Anotado: se aplicó» y «Hecho recientemente» dice «Confirmaste que se aplicó».
  4. **Dado** «No se aplicó», **cuando** confirma con nota, **entonces** se envía `{outcome: "failed", note}` y aparece «Anotado: no se aplicó».
  5. **Dado** que la acción ya no está en `sent` ni `uncertain`, **cuando** envía, **entonces** el error «Solo se resuelven acciones enviadas o inciertas.» se ve dentro del diálogo y la tarjeta sigue.
- **Brechas código/docs:** —
- **Cobertura QA:** E2E `04-tu-turno` (criterios 1 a 3: la tarjeta, deslizar abre «Confirmar que se aplicó» con la nota y la tarjeta se va; «Hecho recientemente» dice «Confirmaste que se aplicó»). El 4 y el 5, backend y Jest.

### TUR-05 · Aviso de LinkedIn caducado o a punto de caducar <a id="tur-05"></a>

- **Dónde:** PWA · app · backend
- **Estado:** funciona
- **Qué hace para Gustavo:** antes de que caduque el permiso de publicar, y cuando ya caducó, le aparece «Reconecta LinkedIn» con un botón.
- **Código:** tarjetas `linkedin_expiring` y `linkedin_expired` de `rediseno_views.alerts`; acción `href: /api/v1/linkedin/oauth/start`. Con el token caducado, la tarjeta de cuenta en pausa por ese motivo no se muestra (reanudar no serviría).
- **Criterios de aceptación:**
  1. **Dado** un token que caduca en 5 días, **cuando** abre Tu turno, **entonces** ve «Reconecta LinkedIn», Cuando puedas, con «El permiso para publicar caduca el <fecha> (quedan 5 días). LinkedIn no deja renovarlo solo.».
  2. **Dado** un token que caduca en 2 días, **cuando** abre Tu turno, **entonces** la misma tarjeta es Importante.
  3. **Dado** un token caducado, **cuando** abre Tu turno, **entonces** ve «Reconecta LinkedIn», Urgente, con «El acceso caducó y la publicación diaria está en pausa.».
  4. **Dado** la tarjeta en la PWA, **cuando** pulsa «Reconectar LinkedIn», **entonces** el navegador navega (no `fetch`) a `/api/v1/linkedin/oauth/start`.
  5. **Dado** la tarjeta en la app, **cuando** pulsa «Reconectar LinkedIn», **entonces** se abre `/ajustes#linkedin` de la PWA en el navegador externo para conectar (el OAuth necesita la cookie de la PWA; ver [AJU-07](ajustes.md#aju-07)); al volver, la app no refresca el estado hasta la siguiente consulta.
  6. **Dado** que reconectó, **cuando** vuelve a Tu turno, **entonces** la tarjeta ya no está y «Hecho recientemente» dice «Reconectado».
- **Brechas código/docs:** —
- **Cobertura QA:** Sin E2E: seed_qa no puede sembrar una credencial de LinkedIn (su guarda se niega a correr si existe una, para proteger una oficina real). El criterio 3 lo cubre `LinkedInExpiredTests` en el backend.

### TUR-06 · Reanudar la máquina o la cuenta desde Tu turno <a id="tur-06"></a>

- **Dónde:** PWA · app · backend
- **Estado:** funciona
- **Qué hace para Gustavo:** si detuvo la máquina o una cuenta quedó en pausa, la reanuda desde la tarjeta.
- **Código:** tarjetas `machine_paused` y `account_paused:<id>`; `POST /api/v1/operador/control {paused: false}`, `POST /api/v1/operador/accounts/<id>/pause {paused: false}`.
- **Criterios de aceptación:**
  1. **Dado** la máquina detenida desde la app, **cuando** abre Tu turno, **entonces** ve «Reanuda la máquina», Urgente, con el motivo y «Detenida por <usuario> · <fecha>».
  2. **Dado** esa tarjeta, **cuando** pulsa «Reanudar», **entonces** se abre «Reanudar la máquina» con motivo opcional, que se envía como `reason`; al confirmar aparece «Máquina reanudada» y la tarjeta desaparece.
  3. **Dado** una cuenta en pausa, **cuando** abre Tu turno, **entonces** ve «Reanuda la cuenta de LinkedIn», Importante, con «<cuenta>: <motivo>»; «Reanudar la cuenta» la reanuda y aparece «Cuenta reanudada».
  4. **Dado** la parada fijada en el servidor, **cuando** abre Tu turno, **entonces** no hay tarjeta de máquina.
- **Brechas código/docs:** —
- **Cobertura QA:** E2E `04-tu-turno-mas` (criterios 1 y 2: detener la máquina desde Ajustes, la tarjeta urgente «Reanuda la máquina» con «Detenida por qa», reanudar con motivo). El 3 y el 4, backend.

### TUR-07 · Tarjeta de conversación que le toca <a id="tur-07"></a>

- **Dónde:** PWA · app · backend
- **Estado:** funciona
- **Qué hace para Gustavo:** ve quién le escribió, por qué importa y el último mensaje, y abre el hilo en LinkedIn para responder él.
- **Código:** tarjeta `conversacion` (ver [INB-03](inbox.md#inb-03)); PWA `TurnoCardView.tsx`; app `TurnoCard.tsx`.
- **Criterios de aceptación:**
  1. **Dado** una tarjeta de conversación, **cuando** se pinta, **entonces** muestra el avatar y el nombre (enlazado a `/personas/<id>` si es contacto), el titular, los chips de rol y modalidad, «Por qué importa» con la lectura del equipo, «Último mensaje · <cuándo>» con el texto citado y «La app nunca envía mensajes: respondes tú en LinkedIn.».
  2. **Dado** «Abrir en LinkedIn», **cuando** lo pulsa, **entonces** se abre `chat_url` fuera de la app.
  3. **Dado** «No responder», **cuando** lo pulsa, **entonces** se pide un motivo opcional con «La tarjeta sale de Tu turno hasta que te vuelva a escribir. Nadie le responde por ti.» y después aparece «Anotado: no responderás».
  4. **Dado** «Hecho, respondí», **cuando** lo pulsa, **entonces** aparece «Anotado: respondiste» y la tarjeta desaparece.
  5. **Dado** «Marcar como oportunidad», **cuando** lo pulsa, **entonces** se abre el formulario de oportunidad relleno ([INB-05](inbox.md#inb-05)).
- **Brechas código/docs:** —
- **Cobertura QA:** E2E `04-tu-turno` (criterios 1 y 4: la tarjeta y «Hecho, respondí» deslizando) y `04-tu-turno-mas` (3 «No responder» con su motivo, 5 «Marcar como oportunidad»). El 2 abre LinkedIn: no se automatiza.

### TUR-08 · Tarjeta de la orientación propuesta por el analista <a id="tur-08"></a>

- **Dónde:** PWA · app · backend
- **Estado:** parcial
- **Qué hace para Gustavo:** si el resumen semanal propone una orientación sin decidir, lo ve en Tu turno y puede abrir el resumen o descartarla.
- **Código:** tarjeta `resumen` (`rediseno_views._summary_card`); ver [SEM-08](resumen-semanal.md#sem-08).
- **Criterios de aceptación:**
  1. **Dado** una orientación propuesta sin decidir, **cuando** abre Tu turno, **entonces** ve «El analista propone una orientación», Cuando puedas, con el texto propuesto.
  2. **Dado** la tarjeta, **cuando** se pinta, **entonces** muestra también la semana y el titular del resumen (`summary.label`, `summary.titular`). **Hoy falla en la PWA:** solo muestra el cuerpo. En la app no se comprobó.
  3. **Dado** «Ver el resumen», **cuando** lo pulsa, **entonces** navega dentro de la app a Resultados, al bloque `#resumen`, sin recargar.
  4. **Dado** «Descartar», **cuando** lo pulsa, **entonces** el resumen queda `descartado`, aparece «Resumen descartado» y la tarjeta desaparece.
- **Brechas código/docs:** la API envía `summary: {id, week_start, label, titular}` y la PWA no lo pinta.
- **Cobertura QA:** E2E `04-tu-turno` (criterio 1) y `04-tu-turno-mas` (4 «Descartar»). El 3 (navegar a Resultados) lo cubre `06-notificaciones-destinos` por la notificación del resumen.

### TUR-09 · Responder una pregunta del equipo <a id="tur-09"></a>

- **Dónde:** PWA · app · backend
- **Estado:** parcial
- **Qué hace para Gustavo:** un agente le pregunta algo («¿Has liderado una migración a microservicios?»), él responde y elige si es público o privado; la respuesta pasa a la memoria confirmada.
- **Código:** `POST /api/v1/preguntas/<id>/responder` y `…/deshacer` (`preguntas.answer`, `preguntas.undo`); PWA `pages/turno/QuestionForm.tsx`, `VisibilityField.tsx`; app `movil/src/turno/QuestionForm.tsx`.
- **Criterios de aceptación:**
  1. **Dado** una pregunta `text`, **cuando** responde y pulsa «Responder», **entonces** se envía `{text, public_use}`, aparece «Guardado. El equipo ya puede usarlo» con «Deshacer» y el dato aparece en «Lo que el equipo sabe de ti».
  2. **Dado** una pregunta `yes_no`, `choice`, `number` o `date`, **cuando** responde, **entonces** se envía `value` (`si`/`no`, una de las opciones, un número o `AAAA-MM-DD`) y el texto guardado incluye la pregunta para entenderse solo.
  3. **Dado** un valor inválido (por ejemplo una opción que no existe), **cuando** se envía, **entonces** la API responde 400 («Elige una de las opciones», «Escribe un número»…) y el error se ve bajo el formulario.
  4. **Dado** una pregunta `confirm`, **cuando** pulsa «Sí, es correcto», **entonces** se envía `{accept: true}`; si escribe una corrección, «Guardar corrección» envía `text`.
  5. **Dado** el selector «Quién puede verlo», **cuando** se abre la pregunta, **entonces** viene preseleccionado según `suggested_public` (o `proposed_value.uso_publico` en `confirm`), con Público «El equipo puede mencionarlo en posts y comentarios.» y Privado «Solo orienta decisiones; nunca aparece en un texto público.».
  6. **Dado** que la pregunta ya no está abierta, **cuando** responde, **entonces** ve «No se puede ahora» con «La pregunta ya no está abierta.».
  7. **Dado** «Deshacer» en el aviso de 5 s, **cuando** lo pulsa, **entonces** la memoria vuelve a su versión anterior, la pregunta se reabre y aparece «Respuesta deshecha. La pregunta vuelve a estar abierta».
  8. **Dado** que pasaron menos de 15 minutos desde la respuesta, **cuando** Gustavo quiere deshacerla, **entonces** tiene dónde hacerlo. **Hoy falla:** la interfaz solo ofrece «Deshacer» en el aviso de 5 s, aunque la API lo permite 15 minutos.
  9. **Dado** que pasaron más de 15 minutos, **cuando** se pide deshacer, **entonces** la API responde 409 y la PWA muestra «Ya no se puede deshacer: pasaron más de 15 minutos».
- **Brechas código/docs:** ventana de deshacer de 15 minutos en la API frente a 5 s en la interfaz. El botón de enviar queda desactivado sin explicar por qué mientras el valor no es válido (PWA).
- **Cobertura QA:** E2E `04-tu-turno` (criterio 1: respuesta escrita y su dato en «Lo que el equipo sabe de ti») y `04-tu-turno-mas` (2 con una opción y 7 «Deshacer»). El 3, 5, 6, 8 y 9, backend y Jest.

### TUR-10 · Responder una pregunta con audio <a id="tur-10"></a>

- **Dónde:** PWA · app · backend
- **Estado:** funciona
- **Qué hace para Gustavo:** en vez de escribir, responde con una nota de voz que el equipo transcribe.
- **Código:** «Responder con audio» abre la captura con contexto `pregunta` ([CAP-07](captura.md#cap-07)).
- **Criterios de aceptación:**
  1. **Dado** una pregunta abierta, **cuando** pulsa «Responder con audio», **entonces** se abre la hoja de captura con el chip «Responde a <agente>» y la pregunta.
  2. **Dado** el envío con texto o audio, **cuando** el equipo lo procesa, **entonces** la pregunta queda respondida con la visibilidad elegida (o la sugerida) y la captura termina en `dato_guardado` con «Está en Lo que el equipo sabe de ti · Público/Privado».
  3. **Dado** que la pregunta se cerró antes de enviar, **cuando** se envía, **entonces** la API responde 409 «Esa pregunta ya no está abierta.».
- **Brechas código/docs:** en la app, enviar con audio falla hoy ([CAP-04](captura.md#cap-04)).
- **Cobertura QA:** E2E `04-tu-turno-mas` (criterio 1: la hoja de captura con «Responde a …» y la pregunta) y `05-captura-contexto` (1 y el envío con audio que llega al backend). El 2 necesita el worker; el 3, backend.

### TUR-11 · «Más tarde» y las pospuestas <a id="tur-11"></a>

- **Dónde:** PWA · app · backend
- **Estado:** funciona
- **Qué hace para Gustavo:** aparta una pregunta tres días sin que cuente en el contador.
- **Código:** `POST /api/v1/preguntas/<id>/mas-tarde` (`preguntas.postpone`).
- **Criterios de aceptación:**
  1. **Dado** una pregunta abierta, **cuando** pulsa «Más tarde», **entonces** `postponed_until` es ahora + 3 días, aparece «Pospuesta. Vuelve el <fecha>» y el contador baja en 1.
  2. **Dado** una pregunta pospuesta, **cuando** abre Tu turno, **entonces** está en el pliegue «Pospuestas · N» con «Vuelve el <fecha> · no cuenta en el contador».
  3. **Dado** que pasan los 3 días, **cuando** abre Tu turno, **entonces** vuelve a la lista principal y cuenta.
  4. **Dado** una pregunta ya cerrada, **cuando** se pospone, **entonces** la API responde 409.
- **Brechas código/docs:** —
- **Cobertura QA:** E2E `04-tu-turno` (criterios 1 y 2: «Más tarde» deslizando y con su botón, «Pospuestas · 3» con las tres). El 3 y el 4, backend.

### TUR-12 · «No quiero compartir esto» <a id="tur-12"></a>

- **Dónde:** PWA · app · backend
- **Estado:** funciona
- **Qué hace para Gustavo:** cierra una pregunta para siempre; el equipo no la vuelve a hacer.
- **Código:** `POST /api/v1/preguntas/<id>/no-compartir` (`preguntas.decline`).
- **Criterios de aceptación:**
  1. **Dado** una pregunta, **cuando** pulsa «No quiero compartir esto», **entonces** se pide confirmación «No compartir esto» con «La pregunta se cierra y el equipo no volverá a hacerla. Tampoco podrá contar esto en público.».
  2. **Dado** que confirma, **cuando** se envía, **entonces** la pregunta queda `declined`, aparece «Hecho. El equipo no volverá a preguntarlo» y «Hecho recientemente» dice «No quisiste compartirla».
  3. **Dado** una clave rechazada, **cuando** un agente la pregunta otra vez, **entonces** no se crea la pregunta.
- **Brechas código/docs:** —
- **Cobertura QA:** E2E `04-tu-turno-mas` (criterios 1 y 2: la confirmación «No compartir esto» y «No quisiste compartirla» en «Hecho recientemente»). El 3, backend.

### TUR-13 · Preguntas cuyo plazo pasó <a id="tur-13"></a>

- **Dónde:** PWA · app · backend
- **Estado:** funciona
- **Qué hace para Gustavo:** una pregunta que ya llegó tarde sigue visible pero deja de contarle como pendiente.
- **Código:** `preguntas.is_pending`, `later` con `state: "caducada"`.
- **Criterios de aceptación:**
  1. **Dado** una pregunta abierta con plazo pasado, **cuando** abre Tu turno, **entonces** no cuenta en el contador y aparece en «Ya no es urgente · N» con la etiqueta «Caducada» y «Ya no es urgente, pero sigue siendo útil.».
  2. **Dado** esa pregunta, **cuando** la responde, **entonces** se guarda igual que una pendiente.
  3. **Dado** una pregunta con plazo en menos de 24 h, **cuando** se pinta, **entonces** la línea del plazo («Útil antes de las HH:MM») va en rojo.
- **Brechas código/docs:** —
- **Cobertura QA:** E2E `04-tu-turno` (criterio 1: «Ya no es urgente · 1», «Caducada» y su texto; no cuenta). El 2 y el 3, Jest y backend.

### TUR-14 · Hecho recientemente <a id="tur-14"></a>

- **Dónde:** PWA · app · backend
- **Estado:** funciona
- **Qué hace para Gustavo:** ve lo que resolvió en los últimos 7 días y cómo.
- **Código:** `recent` de `GET /api/v1/tu-turno` (`preguntas.recently_resolved`, `_resolved_alerts`, `conversaciones.recently_resolved`).
- **Criterios de aceptación:**
  1. **Dado** una pregunta respondida hace 2 días, **cuando** abre el pliegue «Hecho recientemente», **entonces** la ve con «Respondida» y «hace 2 días».
  2. **Dado** una acción incierta resuelta, LinkedIn reconectado, la máquina reanudada o una conversación cerrada, **cuando** abre el pliegue, **entonces** aparecen con «Confirmaste que se aplicó», «Reconectado», «Reanudada», «Respondiste» o «Sin responder».
  3. **Dado** algo resuelto hace 8 días, **cuando** abre el pliegue, **entonces** no aparece.
- **Brechas código/docs:** —
- **Cobertura QA:** E2E `04-tu-turno`, `04-tu-turno-aprobar` y `04-tu-turno-mas` (criterios 1 y 2: «Respondida», «Confirmaste que se aplicó», «Respondiste», «Aprobada», «Reanudada», «Sin responder», «No quisiste compartirla»). El 3, backend.

### TUR-15 · Ver lo que el equipo sabe de él <a id="tur-15"></a>

- **Dónde:** PWA · app · backend
- **Estado:** funciona
- **Qué hace para Gustavo:** ve cada dato que el equipo puede usar, si es público o privado, de dónde vino y cuántas veces lo editó.
- **Código:** `GET /api/v1/memoria/hechos` (`preguntas.facts`); PWA `pages/turno/Sabe.tsx` (`/tu-turno/sabe`); app `movil/src/turno/Sabe.tsx`.
- **Criterios de aceptación:**
  1. **Dado** datos confirmados, **cuando** abre la pestaña, **entonces** ve la introducción «Esto es lo único que el equipo puede contar de ti. Nadie inventará tus experiencias, clientes ni servicios.» y una tarjeta por dato con el tema, «Público»/«Privado», el texto, el origen («Lo añadiste tú», «Respondiste al <agente>», «Lo confirmaste en la memoria»), la fecha y `vN` si se editó.
  2. **Dado** más de 20 datos, **cuando** abre la pestaña, **entonces** aparece una búsqueda sin distinguir tildes, con «N de M» y «Nada coincide con «…».» si no hay resultados.
  3. **Dado** ningún dato, **cuando** abre la pestaña, **entonces** ve «Aún no hay nada confirmado» y «Nadie inventará tus experiencias, clientes ni servicios: responde las preguntas del equipo para que puedan usarlas.».
  4. **Dado** un error al cargar, **cuando** falla, **entonces** ve el error con «Reintentar».
  5. **Dado** el enlace `/memoria` (antiguo), **cuando** lo abre en la PWA, **entonces** llega a `/tu-turno/sabe`.
- **Brechas código/docs:** —
- **Cobertura QA:** E2E `04-tu-turno` y `04-tu-turno-sabe` (criterio 1: la introducción, tema, visibilidad, origen y `v2`) y `04-tu-turno-estados` (3 vacío y 4 error con «Reintentar»). El 2 (búsqueda desde 20 datos), Jest.

### TUR-16 · Añadir algo que quiere que sepan <a id="tur-16"></a>

- **Dónde:** PWA · app · backend
- **Estado:** funciona
- **Qué hace para Gustavo:** escribe un dato suyo, elige la visibilidad y queda confirmado al guardar.
- **Código:** `POST /api/v1/memoria/hechos` (`preguntas.add_fact`).
- **Criterios de aceptación:**
  1. **Dado** «Añadir algo que quieras que sepan», **cuando** escribe un texto, un tema opcional y deja Privado (por defecto), **entonces** al guardar la API responde 201 con la lista, aparece «Guardado. El equipo ya puede usarlo» y el dato sale con «Lo añadiste tú».
  2. **Dado** un texto vacío o de más de 4.000 caracteres, **cuando** guarda, **entonces** la API responde 400 «Escribe el dato (máximo 4000 caracteres)».
  3. **Dado** un dato público, **cuando** corre el circuito editorial, **entonces** aparece en `public_facts`; uno privado, en `private_guidance`.
- **Brechas código/docs:** —
- **Cobertura QA:** E2E `04-tu-turno-sabe` (criterio 1: Privado por defecto, «Lo añadiste tú»). El 2 y el 3, backend.

### TUR-17 · Editar o retirar un dato <a id="tur-17"></a>

- **Dónde:** PWA · app · backend
- **Estado:** funciona
- **Qué hace para Gustavo:** corrige un dato (queda una versión nueva) o lo retira para que el equipo deje de usarlo.
- **Código:** `POST /api/v1/memoria/hechos/<key>/corregir` y `…/retirar` (`preguntas.correct`, `preguntas.retire`).
- **Criterios de aceptación:**
  1. **Dado** un dato, **cuando** lo edita y guarda, **entonces** se crea una versión nueva, aparece «Guardado como vN» y el tema no cambia.
  2. **Dado** un dato, **cuando** pulsa «Retirar» y confirma (motivo opcional), **entonces** se guarda una lápida, aparece «Retirado. El equipo ya no lo usará» y el dato desaparece de la lista.
  3. **Dado** una clave que no está en la memoria confirmada, **cuando** se corrige o retira, **entonces** la API responde 409 «Ese dato no está en la memoria confirmada.».
  4. **Dado** una edición o una retirada, **cuando** se hace, **entonces** no hay «Deshacer» (comportamiento actual).
- **Brechas código/docs:** —
- **Cobertura QA:** E2E `04-tu-turno-sabe` (criterios 1 y 2: versión nueva `v2` y retirar). El 3 y el 4, backend.

### TUR-18 · Tareas de perfil <a id="tur-18"></a>

- **Dónde:** PWA · app · backend
- **Estado:** funciona
- **Qué hace para Gustavo:** recibe el Markdown de cambios, los assets y una checklist sincronizada por sección; revisa el copy listo para pegar y aplica él mismo lo que elige en LinkedIn.
- **Responsable:** `perfil` coordina las tareas, `posicionamiento` sustenta el mensaje y `editor_visual` prepara foto/mural; Gustavo decide y aplica.
- **Cadencia:** propuesta completa cada seis meses ([EST-01](estrategia-perfil.md#est-01)); mensual para destacados, artículos y actividad ([EST-02](estrategia-perfil.md#est-02)); bajo demanda desde captura ([EST-05](estrategia-perfil.md#est-05)). Una tarea por sección y versión, agrupada por propuesta.
- **Tu turno:** «Aceptar propuesta», «Pedir ajuste», «Más tarde» y «No lo haré»; foto exige «Elegir A» o «Elegir B» sin preselección. Banner muestra la nota de composición estilizada para decidirlo aparte. Aceptar no significa aplicar; después, «Hecho, lo apliqué» o «Lo cambié con otro texto». Gustavo puede aceptar/aplicar solo algunas secciones.
- **Datos necesarios y disponibilidad:** Paquete versionado, assets y checklist implementados. Relectura autorizada del titular; las demás secciones conservan «comprobación automática no disponible». No se promete una lectura completa del perfil.
- **Código:** `perfil_views.py`, `perfil.cards/markdown`, `rediseno_views.TuTurno`, `compartido/api/perfil.ts` y `ProfileProposal.tsx` en PWA/app; notificación `profile_task` habilitada en Ajustes.
- **Criterios de aceptación:**
  1. **Dado** una propuesta de perfil, **cuando** abre Tu turno, **entonces** descarga el Markdown y ve por sección texto actual con fuente/fecha o «No pudimos leer tu perfil actual», copy inglés con «Copiar», porqué, IDs del curso por recomendación, evidencia y pasos. El contador usa el límite de LinkedIn verificado al generar (la ficha previa citaba titular 220 y Acerca de 2.600); un límite no comprobado aparece pendiente. **A y B, cada una 800×800 PNG/JPG**, banner 1584×396 PNG y previews móvil/escritorio con cada retrato tienen descarga y comparación privada con referencias de Perfil; todos pertenecen a la versión del documento/checklist.
  2. **Dado** «Hecho, lo apliqué», **cuando** lo pulsa, **entonces** la sección pasa a «Aplicado por Gustavo, pendiente de comprobar». Solo una relectura autorizada que compare el contenido permite «Comprobado»; si la sección no es legible, queda «Aplicado por Gustavo; comprobación automática no disponible», con fecha y evidencia manual opcional. El clic no prueba una escritura en LinkedIn.
  3. **Dado** «Lo cambié con otro texto», **cuando** lo pulsa, **entonces** puede pegar lo que usó.
  4. **Dado** «No lo haré», **cuando** lo pulsa, **entonces** se pide un motivo obligatorio.
  5. **Dado** secciones aceptadas y otras pendientes, **cuando** vuelve a abrir, **entonces** conserva por sección propuesta, decisión, versión y estado de aplicación; puede copiar y aplicar de forma independiente. Todas las secciones EST-01, incluida URL personalizada, figuran aunque alguna indique «Falta información», «No aplica» o «Conservar»; falta de fotos no bloquea revisar copy.
  6. **Dado** una nueva versión o un cambio conocido del perfil actual, **cuando** intenta aceptar/aplicar desde una tarjeta antigua, **entonces** ve el cambio y debe revisar la versión vigente. Repetir una confirmación ya guardada no duplica tareas ni historial.
  7. **Dado** una tarea aceptada, **cuando** se registra o descarga su recurso, **entonces** ningún trabajo ni conector escribe el perfil de LinkedIn. «Abrir LinkedIn» y copiar/descargar solo ayudan a Gustavo a hacerlo.
  8. **Dado** error de guardado, recurso ausente o propuesta incompleta, **cuando** intenta decidir, **entonces** conserva los cambios locales y muestra el motivo/reintento; no marca la sección aceptada o aplicada hasta confirmar el guardado. Sin propuestas muestra el estado vacío existente.
  9. **Dado** A, B y banner propuestos, **cuando** revisa la checklist, **entonces** ve ocho puntos por opción (punto 3: A grises, B color natural sin aguamarina en piel/ropa), visión de identidad contra **03**, **sonrisa de 01 en los tres** y transitions claras como en 03, nunca gafas de sol; fallo/resultado incierto bloquea el asset. Preview aprobado no equivale a comprobación final en la app de LinkedIn.
  10. **Dado** A y B completas y válidas, **cuando** Gustavo pulsa «Elegir A» o «Elegir B», **entonces** registra opción/versión en documento y checklist y conserva ambas descargas. No hay elección automática ni aprobación de foto por aceptar otra sección; si falta una opción la entrega de foto sigue parcial. Elegir retrato no aprueba banner ni publica.
  11. **Dado** el banner con micrófono y ninguna charla confirmada en memoria, **cuando** lo revisa, **entonces** ve junto al copy y en el Markdown que es una composición de estilo, no evidencia de evento real; no aparece «speaker» ni prueba social inventada. Decide aceptar, ajustar o descartar esa propuesta de forma independiente.
  12. **Dado** un hecho imprescindible de perfil no encontrado en memoria ni fuentes legibles, **cuando** Perfil necesita aclararlo, **entonces** Tu turno muestra **una pregunta por hecho faltante** con la sección afectada; no vuelve a preguntar hechos acreditados ni repite el mismo en varias tarjetas. Sin respuesta queda pendiente solo lo dependiente y se omite prueba social sin evidencia. La frase del banner llega propuesta y citada por Perfil; el texto de prueba es solo fallback EST-04, no una pregunta abierta de copy para Gustavo.
- **Brechas código/docs:** CI/QA y activación pendientes de Claude; [guía de verificación](../arquitectura/fase8-verificacion.md). Los assets privados no están en el repo.
- **Cobertura QA:** `test_perfil.py`, Jest/Vitest y Maestro `18-perfil`; regresiones `04-*`, `10-galeria` y seed. Escrita, sin ejecución local.

### TUR-19 · Deslizar una tarjeta <a id="tur-19"></a>

- **Dónde:** app
- **Estado:** funciona
- **Qué hace para Gustavo:** en el teléfono resuelve una tarjeta deslizándola a la derecha, o pospone una pregunta deslizándola a la izquierda.
- **Código:** `movil/src/turno/SwipeableCard.tsx`, `swipe.ts`, `exits.ts`; tokens de `theme/motion.ts` (umbral del 33 % del ancho o 900 pt/s).
- **Criterios de aceptación:**
  1. **Dado** una tarjeta con una acción directa (por ejemplo «Hecho, respondí»), **cuando** la desliza a la derecha más de un tercio del ancho, **entonces** se ejecuta esa acción, vibra, el botón pasa a un check y la tarjeta se recoge.
  2. **Dado** que esa acción pide una nota, **cuando** la desliza, **entonces** la tarjeta vuelve a su sitio y se abre la hoja de la nota.
  3. **Dado** una pregunta abierta, **cuando** la desliza a la izquierda, **entonces** se pospone 3 días con «Pospuesta. Vuelve el <fecha>».
  4. **Dado** una tarjeta caducada, o una pregunta deslizada a la derecha, **cuando** intenta deslizar, **entonces** no pasa nada (como mucho se mueve 24 pt).
  5. **Dado** un lector de pantalla, **cuando** recorre la tarjeta, **entonces** las acciones de deslizar están disponibles como acciones accesibles.
  6. **Dado** que la API responde con un error, **cuando** vuelve, **entonces** la tarjeta vuelve y se ve el `detail` del error.
- **Brechas código/docs:** no se comprobó en un teléfono un caso posible: si tras un deslizamiento correcto la tarjeta sigue en la respuesta de la API, podría quedar fuera de la pantalla e invisible (`SwipeableCard.tsx:218-225`, `exits.ts:305-309`). Los errores de red salen en inglés ([APP-08](app-movil-instalacion.md#app-08)).
- **Cobertura QA:** E2E `04-tu-turno` (criterios 1 a 3: derecha con acción directa, derecha que pide nota y la hoja, izquierda «Más tarde») y `04-tu-turno-estados` (6: la API rechaza y la tarjeta vuelve con el motivo). El 4 y el 5, Jest.

### TUR-20 · Decidir altas, bajas y sustituciones de referentes <a id="tur-20"></a>

- **Dónde:** PWA · app · backend
- **Estado:** funciona
- **Qué hace para Gustavo:** revisa los diez lugares variables los días 1–5; los cinco main permanecen protegidos y ve qué se aplicará al cierre si no responde.
- **Responsable:** `investigador_lider` presenta; Gustavo aprueba/rechaza/edita; backend aplica el vencimiento autorizado OBS-02. El líder/Jev no suplanta la decisión humana ni puede tocar main.
- **Cadencia:** lote del día 1, recordatorios días 1 y 4 y cierre al terminar el día 5 en America/Bogota, con una tarjeta por decisión/versionado y eventos deduplicados. Gestión de protegidos solo bajo acción explícita de Gustavo, sin plazo automático.
- **Tu turno:** «Aprobar alta», «Aprobar baja», «Aprobar sustitución», «Rechazar», «Editar», «Guardar y aplicar cambios», «Pedir ajuste» y «Más tarde». La pareja muestra «sale X · entra Y». Se explica «Si no respondes, se aplicará al terminar el día 5»; responder para ajustar/posponer excluye esa tarjeta del automatismo.
- **Gestión propia de Gustavo:** acceso «Gestionar protegidos» en Tu turno y en Personas › Referentes. Mover/reemplazar/proteger/desproteger es una acción iniciada y guardada por él, con efecto antes/después y auditoría OBS-02; ningún agente la propone ni el cierre mensual la ejecuta. La etiqueta main muestra protección vigente y el historial de quién la cambió.
- **Datos necesarios y disponibilidad:** Lote/versiones, pares y evidencia, protección main, plazo Bogotá, respuestas y conflictos transaccionales disponibles.
- **Código:** `referentes_views.cards/ChangeDecision`, `ReferentDecision` en PWA/app, lógica compartida `logic/referentes.ts`.
- **Criterios de aceptación:**
  1. **Dado** el lote mensual, **cuando** abre Tu turno, **entonces** distingue cinco main protegidos de diez plazas variables y ve identidad/enlace, acción, objetivos, evidencia, muestra/límites, motivo, ocupación antes/después y plazo local. La evidencia de Top Voice tiene fuente o dice «No verificado»; main nunca ofrece una propuesta de baja.
  2. **Dado** un swap, **cuando** lo presenta, **entonces** muestra una sola pareja «sale X · entra Y», con ambos perfiles y efecto conjunto; aprobarla o aplicarla al plazo ejecuta ambas partes atómicamente. Altas y bajas solas tienen tarjeta propia, sin sustitución implícita.
  3. **Dado** rechazo, edición sin aplicar, petición de ajuste o aplazamiento, **cuando** llega el cierre, **entonces** no aplica esa versión por silencio. «Guardar y aplicar cambios» valida main/capacidad/evidencia y aplica exactamente la versión editada, conservando historial.
  4. **Dado** una propuesta elegible sin respuesta al final del día 5, **cuando** ejecuta el cierre OBS-02, **entonces** la aplica una sola vez y muestra «Aplicada por plazo autorizado», nunca «Aprobada por Gustavo». Registra aviso con cambios, evidencias y número de main/variables, sin afectar protegidos.
  5. **Dado** días 1 y 4 con pendientes, **cuando** recuerda, **entonces** avisa una vez por mes/día qué requiere revisión y qué significa no responder; la tarjeta muestra fecha/hora en America/Bogota. Recordatorio o push no sustituye el registro verificable de la propuesta.
  6. **Dado** decisión concurrente, tarjeta obsoleta, lote tardío, error de red o llamada sin autorización, **cuando** intenta aplicar, **entonces** cumple OBS-02: valida versión/estado/protección transaccionalmente, conserva pendientes o rechaza y no declara éxito sin guardado. Solo el job de cierre con las condiciones verificadas puede usar el mandato por plazo.
  7. **Dado** un main y Gustavo autenticado, **cuando** inicia desde Tu turno o Personas › Referentes un cambio explícito de posición, reemplazo o protección, **entonces** ve/guarda la decisión concreta con capacidad/versiones validadas y auditoría de actor, fecha, origen y valores anteriores/nuevos. La sustitución transfiere protección atómicamente y la desprotección respeta plazas OBS-02. La misma solicitud con identidad de agente/job falla; no existe propuesta del agente de desproteger ni aprobación por silencio.
- **Brechas código/docs:** implementación entregada en fase 5; ejecución de CI/QA delegada a Claude, sin pruebas locales. Conservar los límites observacionales de OBS-03.
- **Cobertura QA:** casos sintéticos en `test_referentes_mensuales.py`, Jest/Vitest y `19-referentes-mensual.yaml`; pendientes de ejecución por Claude. [Entrega y verificaciones](../../agentes-linkedin/infra/docs/referentes-mensuales.md).

### TUR-21 · Decidir un experimento de participación <a id="tur-21"></a>

- **Dónde:** PWA · app · backend
- **Estado:** funciona
- **Qué hace para Gustavo:** sabe qué va a probar el equipo, durante cuánto tiempo y qué resultado ayudaría a decidir sobre un referente.
- **Responsable:** `analista_barrio_resultados` presenta; Gustavo decide; `relaciones_comunidad` ejecuta el foco aprobado con las guardas actuales.
- **Cadencia:** al proponer/modificar un experimento OBS-04; seguimiento semanal informativo y resultado al cierre.
- **Tu turno:** «Aprobar experimento», «Pedir ajuste», «Descartar», «Más tarde» y «Detener» mientras esté activo. Aprobar no acepta futuras altas/bajas ni cambia la orientación.
- **Datos necesarios y disponibilidad:** Planes versionados, aprobación positiva, 14/28/7 días, dos comentarios por semana, umbrales congelados y resultados en Personas › Referentes.
- **Código:** `experimentos`, `referentes_views.ExperimentDecision` y `ReferentDecision` en PWA/app.
- **Criterios de aceptación:**
  1. **Dado** un experimento propuesto, **cuando** se muestra, **entonces** incluye hipótesis, referente activo, público, fechas de base/foco/seguimiento, participación máxima, comparación, métrica, umbral, muestra mínima, presupuesto dentro de topes y limitaciones de datos/atribución.
  2. **Dado** aprobación de la versión vigente, **cuando** empieza la fecha acordada, **entonces** activa solo ese plan; sin aprobación, con versión obsoleta o con otro foco activo, no inicia y explica el motivo. No se inicia retroactivamente una prueba cuyo periodo aprobado ya pasó.
  3. **Dado** «Detener» o una modificación de público/duración/criterio, **cuando** la registra, **entonces** detiene futuras acciones de foco o crea una revisión pendiente de aprobación, conserva lo ya ejecutado y marca su impacto en la comparación; no borra resultados anteriores.
  4. **Dado** un resultado al cierre, **cuando** recomienda una baja, alta u orientación, **entonces** abre la decisión correspondiente con enlace al experimento, sin aplicarla por la aprobación inicial. Un fallo al guardar la decisión deja el estado anterior y permite reintentar sin duplicar el plan.
- **Brechas código/docs:** implementación entregada en fase 5; ejecución de CI/QA delegada a Claude, sin pruebas locales. Conservar los límites observacionales de OBS-03.
- **Cobertura QA:** casos sintéticos en `test_referentes_mensuales.py`, Jest/Vitest y `19-referentes-mensual.yaml`; pendientes de ejecución por Claude. [Entrega y verificaciones](../../agentes-linkedin/infra/docs/referentes-mensuales.md).

## Retiradas

Ninguna.
