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
| [TUR-18](#tur-18) | Tareas de perfil | PWA · app · backend | no implementado |
| [TUR-19](#tur-19) | Deslizar una tarjeta | app | funciona |

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
- **Cobertura QA:** pendiente

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
- **Cobertura QA:** pendiente

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
- **Cobertura QA:** pendiente

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
- **Cobertura QA:** pendiente

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
- **Cobertura QA:** pendiente

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
- **Cobertura QA:** pendiente

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
- **Cobertura QA:** pendiente

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
- **Cobertura QA:** pendiente

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
- **Cobertura QA:** pendiente

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
- **Cobertura QA:** pendiente

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
- **Cobertura QA:** pendiente

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
- **Cobertura QA:** pendiente

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
- **Cobertura QA:** pendiente

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
- **Cobertura QA:** pendiente

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
- **Cobertura QA:** pendiente

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
- **Cobertura QA:** pendiente

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
- **Cobertura QA:** pendiente

### TUR-18 · Tareas de perfil <a id="tur-18"></a>

- **Dónde:** PWA · app · backend
- **Estado:** no implementado
- **Qué hace para Gustavo:** el equipo le propondría cambios en su perfil de LinkedIn (titular, Acerca de…) con el texto actual, el propuesto, el porqué y los pasos para aplicarlo él.
- **Código:** no existe. `tasks.perfil` llega siempre vacío; el tipo de push `profile_task` existe en el backend, pero Ajustes no ofrece su interruptor hasta que haya evento. Diseño en `DISENO-VISTAS.md` (rama `feat/rediseno-oficina`), sección 2.C1.
- **Criterios de aceptación:**
  1. **Dado** una propuesta de perfil, **cuando** abre Tu turno, **entonces** ve la sección, el texto actual (o «No pudimos leer tu perfil actual»), el propuesto con «Copiar» y el contador frente al límite de LinkedIn (titular 220, Acerca de 2.600), el porqué y los pasos.
  2. **Dado** «Hecho», **cuando** lo pulsa, **entonces** la tarea pasa a «Aplicado, pendiente de comprobar» y después a «Comprobado» cuando el equipo relee el perfil.
  3. **Dado** «Lo cambié con otro texto», **cuando** lo pulsa, **entonces** puede pegar lo que usó.
  4. **Dado** «No lo haré», **cuando** lo pulsa, **entonces** se pide un motivo obligatorio.
- **Brechas código/docs:** el ciclo de Perfil (PERF-*) está diseñado y sin implementar (`mapa-agentes-runtime.md`: perfil «Parcial (a mano)»).
- **Cobertura QA:** pendiente

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
- **Cobertura QA:** pendiente

## Retiradas

Ninguna.
