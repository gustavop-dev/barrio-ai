# Línea base del comentario de calentamiento (BIB-09-comentario-calentamiento)

Medición del estado actual **antes** de cambiar el procedimiento, en el mismo orden que el primer mensaje
([linea-base-primer-mensaje.md](linea-base-primer-mensaje.md)): evaluación primero, medir, procedimiento, lectura y
compuertas. Segunda metodología de outbound (clases 07 y 10): el comentario que el equipo deja en el post de un comprador
que se está calentando antes de invitarlo (fase 2 de `docs/plan-outbound.md`).

- **Fecha:** 16/11/2026. Rama `feat/outbound-comprador`, código en `38b41f5` (fase 1 del comprador).
- **Entorno:** PostgreSQL desechable propia con pgvector (no el runtime 55439 ni producción), Python 3.12,
  `LIVE_PROVIDERS=false`. Claude y Jev simulados; conector de LinkedIn simulado; unidades de las clases 07 y 10
  sintéticas (OperatorBase siembra `operador.WARMUP_COMMENT_UNITS`, nunca texto del curso).
- **Caso:** `evaluaciones.COURSE_CASES['comentario_calentamiento']`. **Pruebas:**
  `src/team_backend/tests/test_comentario_calentamiento.py`, con las funciones de producción: compradores elegidos y
  seguidos (`discover_network`, `classify_contacts` con la etapa en la web, `plan_network` y RED-01 aprobado), su post en el
  conector, la lectura (job `observe`), la propuesta del autopiloto (`autopiloto._propose`, con el prefiltro del líder), el
  borrador (job `propose_comment`), la compuerta con el líder (`autopiloto.policy_review` → `lider.review`) y la escritura
  (`operador.execute`).
- **Cómo se midió:** las mismas pruebas sin los marcadores de fallo esperado:
  `manage.py test team_backend.tests.test_comentario_calentamiento -v 2`. Resultado: 11 pruebas, 3 pasan y 8 fallan.
- **El juez simulado:** Jev contesta por rasgos del texto. «aporta» (la pregunta de hoy) dice sí con un aporte concreto
  **o** una pregunta concreta; `cal_aporte`, `cal_pregunta` y `cal_aplauso` (las del calentamiento) solo responden si se
  las hacen.

## Qué existe hoy

El equipo comenta solo posts de referentes activos (`ObservedPost.referent`): `operador.observe` lee a los referentes y
`autopiloto._propose` filtra `referent__active=True`. Un post de un comprador solo llega a la base si alguien lo guarda a
mano (`BuyerPathBase.their_post`), y entonces un comentario sobre él pasa las mismas reglas y preguntas que el de un
referente: 40–900 caracteres, sin pitch ni enlaces, y «aporta» (opinión con fundamento, matiz **o** pregunta concreta). Nada
pide 25–40 palabras, la pregunta final ni prohíbe el aplauso. Los agentes no pueden cargar unidades de las clases 07 ni 10
(`knowledge.clases.CLASES_AGENTES` = 01–06).

## Resultado por variante

| Variante | Comentario (resumen) | Esperado | Observado | Por qué |
| --- | --- | --- | --- | --- |
| Flujo | Post de un comprador que se calienta | Se lee y se propone | **Falla:** ni se lee ni se propone | `observe` solo lee referentes; `_propose` solo mira posts de referentes activos. |
| C1 | Mecanismo concreto (registrar las respuestas un mes) + «Which question do your best accounts answer differently?» (38 palabras) | Publicado | **Pasa:** publicado con el texto exacto | Nada lo revisa como calentamiento: pasa por las reglas generales. El borrador no carga las unidades 07/10 (**falla** esa prueba). |
| C2 | «Great post! 👏👏 … congrats … What is next for the team?» | Lo paran las reglas | **Falla:** lo para el juez | No hay regla de aplauso: se paga una revisión del líder y la descarta «aporta». |
| C3 | Aporte + «Our team builds exactly that… DM me» | Lo paran las reglas | **Pasa:** reglas | `autopiloto.PITCH` («dm me»). |
| C4 | Aporte + pregunta en 58 palabras | Lo paran las reglas | **Falla:** publicado | La longitud es 40–900 caracteres, no 25–40 palabras (LI-07-M001-K04). |
| C5 | Aporte sin pregunta (34 palabras) | Lo paran las reglas | **Falla:** publicado | Nada exige terminar en una pregunta (LI-07-M005-K05). |
| C6 | Repite la cifra del post + pregunta concreta, sin aporte propio (33 palabras) | Lo para el juez | **Falla:** publicado | «aporta» acepta una pregunta concreta como aporte. |
| R | El texto de C5 en el post de un referente | Publicado (la metodología no rige referentes) | **Pasa:** publicado | Sin cambios para referentes. |

En ninguna variante se envía un mensaje privado (`mensajes_enviados=0`).

## Calificación del caso completo

`grade_course_case('comentario_calentamiento', …)` con todas las variantes, sobre la revisión real del líder en C1:

```
passed: False
errors: Falta fundamento del caso;
        Conducta incorrecta: leido, propuesto, borrador_con_metodologia, C2_stopped_by, C4_publicado, C4_stopped_by,
                             C5_publicado, C5_stopped_by, C6_publicado, C6_stopped_by
course_citations: LI-03-V020-K02, LI-03-M006-K01, LI-03-M005-K06, LI-06-M001-K04, LI-06-M001-K07  (solo LEAD_UNITS)
```

`course_case_context('comentario_calentamiento')` no carga ninguna de las seis unidades (`course_missing` = las seis): es
la conducta correcta antes de activar la metodología.

## Cómo quedan marcadas las pruebas

En el commit de la evaluación, las ocho pruebas que fallan llevan `@expectedFailure` con su motivo, y el recorrido
genérico de `test_fase2_curso` salta `comentario_calentamiento` con un comentario. C1 (publicado), C3 y R no se marcan
porque pasan. Los marcadores se quitan cuando su motivo desaparece:

- Flujo: con la lectura de posts de compradores y la propuesta por grupos (detrás de `BUYER_WARMUP_ENABLED`).
- C2, C4, C5: con las reglas fijas del calentamiento (aplauso, 25–40 palabras, una pregunta al final).
- C6: con las preguntas del líder sobre el calentamiento (`cal_aporte`, `cal_pregunta`, `cal_aplauso`).
- Carga de unidades, caso completo y fuentes: con la activación de las seis unidades de las clases 07 y 10.
