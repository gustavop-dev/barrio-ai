# Línea base del primer mensaje (BIB-09-primer-mensaje)

Medición del estado actual **antes** de cambiar el procedimiento, en el orden aprobado por Gustavo: evaluación primero,
medir, procedimiento, lectura y compuertas. Primera metodología de outbound (clase 09, «primer mensaje»); la nota de
invitación queda para la siguiente iteración.

- **Fecha:** 16/11/2026. Rama `feat/biblioteca-clases-07-12`, código en `ac49a3e` (tras unir `chore/quitar-unipile`).
- **Entorno:** PostgreSQL desechable propia con pgvector (no el runtime 55439 ni producción), Python 3.12,
  `LIVE_PROVIDERS=false`. Claude y Jev simulados; conector de LinkedIn simulado; unidades de la clase 09 sintéticas.
- **Caso:** `evaluaciones.COURSE_CASES['primer_mensaje']`. **Pruebas:** `src/team_backend/tests/test_primer_mensaje.py`, con
  las funciones de producción: lectura del hilo (`respuestas.read`), borrador (`respuestas.propose`), compuerta del
  autopiloto con el líder (`autopiloto.policy_review` → `lider.review`), escritura (`operador.execute`), conexión
  (`respuestas.on_connected`, `red.sync`) y Tu turno (`GET /api/v1/tu-turno`).
- **Cómo se midió:** las mismas pruebas sin los marcadores de fallo esperado, en una copia temporal no versionada:
  `manage.py test team_backend.tests.<copia> -v 2`. Resultado: 8 pruebas, 2 pasan y 6 fallan.

## Qué existe hoy

El único primer mensaje es el `dm_opener` que redacta Relaciones (`respuestas.propose`) en el segundo turno de una
conversación en un post de Gustavo cuando se permite el cierre. Se guarda como `plain(dm_opener)[:800]` (recorta sin avisar),
no pasa ninguna regla, el líder no lo mira (`lider.CHECKS['reply']` juzga solo la respuesta pública) y Tu turno lo muestra
como «Mensaje sugerido» en cuanto la persona es conexión. Los agentes no pueden cargar unidades de la clase 09
(`operador.AGENT_UNIT` solo admite 01–06).

## Resultado por variante

| Variante | Mensaje | Esperado | Observado | Por qué |
| --- | --- | --- | --- | --- |
| P1 | «Hi Ana — your point about rolling back the payments flow stuck with me; we left that thread half-open. Did you isolate it with a flag or a separate deploy?» | Tarjeta | **Pasa:** tarjeta con el texto exacto | No hay ninguna compuerta: pasa porque nada lo revisa, no porque se haya comprobado. |
| P2 | «Hi Ana — your point about rolling back the payments flow stuck with me. Do you have 15 minutes this week? https://cal.com/x» | Sin tarjeta; lo paran las reglas | **Falla:** tarjeta con el enlace y la petición de 15 minutos | No hay reglas sobre el mensaje privado; `reply_text_issues` solo mira la respuesta pública. |
| P3 | «Hope you're doing well! We are a leading partner fixing scaling, hiring and fundraising for startups like yours. Looking forward to hearing from you.» | Sin tarjeta; lo paran las reglas y también el juez | **Falla:** tarjeta | Sin reglas de fórmulas ni de venta en el mensaje privado. |
| P3 (solo el juez) | El mismo texto guardado, revisado por el líder | `dm_approved=False` | **Falla:** la revisión no tiene `dm_approved` | El líder no hace preguntas sobre el primer mensaje. La respuesta pública se aprueba. |
| P4 | «Thanks for the great chat on my post. How are you approaching engineering these days?» | Sin tarjeta; lo para el juez | **Falla:** tarjeta | Nadie juzga toque concreto, puente ni pregunta fácil. |
| P5 | Aceptación sin conversación previa | Sin tarjeta (momento) | **Pasa:** ni borrador, ni aviso, ni tarjeta | `_dm_rows` solo considera comentarios con segundo turno y cierre; una aceptación no redacta nada. |

En ninguna variante se envía un mensaje privado (`messages_sent=0`): el conector no tiene cómo hacerlo (INB-08).

## Calificación del caso completo

`grade_course_case('primer_mensaje', …)` con las cinco variantes, sobre la revisión real del líder en P1:

```
passed: False
errors: Falta fundamento del caso;
        Conducta incorrecta: P2_card, P2_stopped_by, P3_card, P3_stopped_by, P3_judge_rejects, P4_card, P4_stopped_by
course_citations: LI-03-V020-K02, LI-03-M006-K01, LI-03-M005-K06, LI-06-M001-K04, LI-06-M001-K07  (solo LEAD_UNITS)
```

`course_case_context('primer_mensaje')` no carga ninguna de las siete unidades (`course_missing` = las siete): el contexto
sale vacío porque `AGENT_UNIT` rechaza la clase 09. Es la conducta correcta antes de activar la metodología.

## Cómo quedan marcadas las pruebas

En el commit de la evaluación, las seis pruebas que fallan llevan `@expectedFailure` con su motivo, y el recorrido genérico
de `test_fase2_curso` salta `primer_mensaje` con un comentario. P1 y P5 no se marcan porque pasan. Los marcadores se quitan
cuando su motivo desaparece:

- P2, P3, P3 (solo el juez) y P4: con el procedimiento (reglas en código, preguntas del líder, `dm_approved`, tarjeta).
- Caso completo y carga de fuentes: con la lectura y la activación de las siete unidades de la clase 09. Sin ellas el
  fundamento del caso no puede cumplirse aunque la conducta ya sea la correcta.
