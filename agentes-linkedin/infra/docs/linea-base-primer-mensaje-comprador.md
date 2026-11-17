# Línea base del primer mensaje al comprador que acepta (BIB-09-primer-mensaje-comprador)

Medición del estado actual **antes** de cambiar nada, en el mismo orden que las otras metodologías
([primer mensaje](linea-base-primer-mensaje.md), [comentario de calentamiento](linea-base-comentario-calentamiento.md)):
evaluación primero, medir, procedimiento y compuertas. Caso hermano de `BIB-09-primer-mensaje` con la misma metodología
activada (`primer_mensaje`, clase 09): el origen ya no es una conversación en un post de Gustavo sino el recorrido del
comprador (fase 3 de `docs/plan-outbound.md`).

- **Fecha:** 16/11/2026. Rama `feat/outbound-comprador`, código en `b3130b7` (fase 2 y el volumen del 17/11).
- **Entorno:** PostgreSQL desechable propia con pgvector (no el runtime ni producción), Python 3.12,
  `LIVE_PROVIDERS=false`. Claude y Jev simulados; conector de LinkedIn simulado; unidades sintéticas.
- **Caso:** `evaluaciones.COURSE_CASES['primer_mensaje_comprador']` (`metodologia: primer_mensaje`). **Pruebas:**
  `src/team_backend/tests/test_primer_mensaje_comprador.py`, con el arnés `FirstMessagePathBase`
  (`tests/test_comprador_e2e.py`): elegido y seguido (`discover_network`, `classify_contacts` con la etapa en la web,
  RED-01), su post leído (`observe`) y comentado por el autopiloto (`autopiloto._propose`, `propose_comment`, líder,
  `operador.execute`), su respuesta (`collect_outcomes`) o un segundo comentario, la invitación aprobada por Gustavo, la
  aceptación (`sync_network`), el paso de borradores del autopiloto (`autopiloto._buyer_drafts`; hoy no existe y el paso
  no hace nada) y Tu turno (`GET /api/v1/tu-turno`, leído dos horas después de aceptar).
- **Cómo se midió:** las mismas pruebas sin los marcadores de fallo esperado:
  `manage.py test team_backend.tests.test_primer_mensaje_comprador -v 2` (en serie: el corredor paralelo no puede
  serializar las trazas de los fallos). Resultado: 11 pruebas, 3 pasan y 8 fallan.
- **Ajustes del arnés solo para medir (no son topes de producción):** `OPERATOR_DAILY_PROPOSALS=20` (el valor del
  17/11; OperatorBase deja 6 para las otras suites) y la lectura de invitaciones (`red.READ_CAPS['sync']`) a 20 por día,
  porque una prueba acepta a varias personas en el mismo día.

## Qué existe hoy

El único primer mensaje es el de RSP-07: cuando el equipo cierra un segundo turno de respuesta en un post de Gustavo
con alguien que ya es conexión, el líder juzga el `dm_opener` y Tu turno muestra «Mensaje sugerido». Un comprador del
recorrido que acepta la invitación queda en el paso «aceptó» y nadie le prepara nada: no hay borrador, ni toque después
de aceptar (la lectura y los comentarios del calentamiento solo miran el paso «calentando»), ni motivo registrado.

## Resultado por variante

| Variante | Qué pasa | Esperado | Observado | Por qué |
| --- | --- | --- | --- | --- |
| M1 | Respondió un comentario del equipo, invitada, aceptó | Borrador en el mismo ciclo, tarjeta (no el mismo minuto) que cita esa respuesta | **Falla:** ni borrador ni tarjeta | No hay paso que prepare el mensaje al aceptar. |
| M2 | Dos comentarios sin respuesta, invitada, aceptó | Nada antes de tiempo; un comentario más; borrador a los 7 días | **Falla:** nada antes (pasa), pero ni toque ni borrador | `calentamiento.warming`/`to_read` solo miran «calentando». |
| M3 | Sin posts ni señales, invitada a los 14 días, aceptó | Sin mensaje, motivo «hecho», sin llamada pagada | **Falla:** sin mensaje ni llamada (pasa) pero sin motivo | Nadie lo evalúa. |
| M4 | Borrador con enlace y «15 minutes» | Lo paran las reglas tras la reescritura | **Falla:** no hay borrador que parar | — |
| M5 | Borrador genérico («great to be connected») | Lo para el líder | **Falla:** no hay borrador que parar | — |
| M6 | Conversó en su post (RSP-07), comprador invitado que aceptó | Una sola tarjeta, la de la conversación | **Pasa** | Hoy solo existe esa tarjeta. |
| Interruptor apagado | M1 y M6 sin `BUYER_FIRST_MESSAGE_ENABLED` | Nada nuevo; RSP-07 intacto | **Pasa** | — |

En ninguna variante se envía un mensaje privado (`mensajes_enviados=0`).

## Calificación del caso completo

`grade_course_case('primer_mensaje_comprador', …)` con todas las variantes:

```
passed: False
errors: Citas no recuperadas; Falta fundamento del caso;
        Conducta incorrecta: borrador_con_metodologia, M1_mismo_ciclo, M1_tarjeta, M1_cita, M2_toque, M2_tarjeta,
                             M3_stopped_by, M4_stopped_by, M5_stopped_by
result: M2_antes_de_tiempo=False, M3_tarjeta=False, M3_pagado=False, M4_tarjeta=False, M5_tarjeta=False,
        M6_tarjetas=1, M6_origen=conversacion, mensajes_enviados=0, course_citations=[]
```

`course_case_context('primer_mensaje_comprador')` carga las siete unidades de `FIRST_MESSAGE_UNITS` con la metodología
`primer_mensaje` (ya activada): la prueba de fuentes pasa desde la línea base.

## Cómo quedan marcadas las pruebas

En el commit de la evaluación, las ocho pruebas que fallan llevan `@expectedFailure` con su motivo. Se quitan cuando
su motivo desaparece: con el paso de borradores (`autopiloto._buyer_drafts`, `mensajes_comprador.prepare`), el toque
después de aceptar (calentamiento 2), las reglas, el líder y la tarjeta de Tu turno, todo detrás de
`BUYER_FIRST_MESSAGE_ENABLED`.

## Después de activar (16/11/2026)

Mismo caso, mismas pruebas y mismo juez simulado, ya sin marcadores, con `BUYER_FIRST_MESSAGE_ENABLED=true` y el líder
encendido: `manage.py test team_backend.tests.test_primer_mensaje_comprador` (en serie). Resultado: las 11 pruebas
pasan, y `grade_course_case` aprueba el caso completo (`passed: True`, sin errores) con las citas de `LEAD_UNITS` más las
siete de `FIRST_MESSAGE_UNITS`.

```
passed: True
result: borrador_con_metodologia=True, M1_mismo_ciclo=True, M1_tarjeta=True, M1_cita=respondio_comentario,
        M2_antes_de_tiempo=False, M2_toque=True, M2_tarjeta=True, M3_tarjeta=False, M3_stopped_by=hecho, M3_pagado=False,
        M4_tarjeta=False, M4_stopped_by=reglas, M5_tarjeta=False, M5_stopped_by=juez, M6_tarjetas=1,
        M6_origen=conversacion, mensajes_enviados=0
```

| Variante | Antes | Ahora | Qué lo cambió |
| --- | --- | --- | --- |
| M1 | Ni borrador ni tarjeta | Borrador en el ciclo que ve la aceptación; tarjeta una hora después que cita su respuesta | `autopiloto._buyer_drafts`, `mensajes_comprador.prepare` (`message_at`, `anchors`, `SHOW_AFTER`) |
| M2 | Ni toque ni borrador | Un comentario más en un post nuevo suyo y el borrador a los 7 días | `calentamiento.second_touch` en `to_read` y `buyer_posts`; `BUYER_FIRST_MESSAGE_AFTER_DAYS` |
| M3 | Sin motivo | Sin mensaje ni llamada pagada, motivo `hecho` | `anchors` vacío → `stop(..., hecho)` antes de pagar |
| M4 | Sin borrador | Lo paran las reglas tras la reescritura | `message_text_issues` (las de RSP-07 más el hecho declarado) |
| M5 | Sin borrador | Lo para el líder | `lider.review_buyer_draft` (`BUYER_MESSAGE_CHECKS`) |
| M6 | Una tarjeta | Una tarjeta, la de la conversación | `mensajes_comprador.cards` y `_messages` respetan `respuestas._dm_rows` |
| Interruptor apagado | Nada nuevo | Nada nuevo; RSP-07 intacto | `mensajes_comprador.enabled()` |

El camino completo y las variantes 1–10 del encargo están además en `test_comprador_e2e.py`
(`FirstMessageBuyerPathTests`, `FirstMessageSwitchOffPathTests`).
