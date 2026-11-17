# Línea base de la nota de invitación (BIB-09-nota-invitacion)

Medición del estado actual **antes** de cambiar nada. Tercera metodología de outbound (clase 09): la nota de
invitación, que desde el 17/11/2026 se reserva a compradores calentados con un hecho concreto y se redacta al invitar
(fase 3 de `docs/plan-outbound.md`). También reproduce el error que la fase corrige.

- **Fecha:** 16/11/2026. Rama `feat/outbound-comprador`, código en `b3130b7`.
- **Entorno:** PostgreSQL desechable propia con pgvector, Python 3.12, `LIVE_PROVIDERS=false`. Claude y Jev simulados;
  conector de LinkedIn simulado; unidades sintéticas. Las tres unidades de la clase 09 (`LI-09-M002-K06`,
  `LI-09-V008-K04`, `LI-09-M002-K01`) quedan listadas en el caso, sin activar ni sembrar.
- **Caso:** `evaluaciones.COURSE_CASES['nota_invitacion']`. **Pruebas:** `src/team_backend/tests/test_nota_invitacion.py`
  con el arnés `FirstMessagePathBase`: elegido y seguido, un comentario del autopiloto en su post y su respuesta (se
  calienta y queda lista para invitar), el paso de borradores del autopiloto (hoy no existe), `red.plan`, la compuerta
  autónoma de RED-02 (`autopiloto.policy_review` con el líder, `OPERATOR_AUTONOMY=RED-02=auto`) y `operador.execute`.
  Las variantes que no se envían se miden en la propuesta y Gustavo las veta, para dejar cupo en la rampa del día (8).
- **Cómo se midió:** sin los marcadores de fallo esperado, `manage.py test team_backend.tests.test_nota_invitacion -v 2`
  (en serie). Resultado: 13 pruebas, 1 pasa y 12 fallan.
- **Ajustes del arnés solo para medir:** `BUYER_POSTS_READ_DAILY_LIMIT=20` (diez compradores leídos el mismo día; el
  tope de producción sigue en 8), los de la línea base del primer mensaje y la nota del clasificador en G.

## Qué existe hoy

La única nota sale del clasificador (`red.classify` escribe `invitation_note` y `note_reason`); `red.plan` la usa para
quien tiene confianza ≥ 0,9 (0,8 si conversó en su post) y cita LI-03-M006-K01, hasta `note_room()` (3 al mes). Nadie
redacta una nota al invitar ni con el calentamiento como contexto; no hay reglas propias de la nota (el líder pregunta
pitch, inventa, «en inglés» y si se justifica el cupo).

**El error:** `red.execution_issues` exige `review.note_approved`. Esa marca solo la pone `lider._review`. Si Gustavo
confirmó a la persona (`confirmed_by_gustavo`) o el líder está apagado (`LEAD_ENABLED=false`), `policy_review` aprueba sin
pasar por el líder, y la ejecución queda bloqueada con «Nota pendiente de verificador/líder» en cada intento hasta que la
propuesta caduca (48 h). Reproducido en `ConfirmedNoteBugTests` (las dos pruebas fallan hoy).

## Resultado por variante

| Variante | Nota (resumen) | Esperado | Observado |
| --- | --- | --- | --- |
| Flujo / N1 | «Ana, your post on moving a paid pilot off a spreadsheet stayed with me. Connecting…» (103) | Redactada al invitar, sale con la invitación | **Falla:** nadie la redacta; sale sin nota |
| N2 | «…be part of my network.» | Reglas; sale sin nota | **Falla:** sin nota (pasa) pero sin motivo |
| N3 | «I love what you write. Let us connect!» | Reglas | **Falla:** sin motivo |
| N4 | «I help companies like yours…» | Reglas | **Falla:** sin motivo |
| N5 | La de N1 alargada a 203 caracteres | Reglas | **Falla:** sin motivo |
| N6 | En español a una persona que escribe en inglés | Reglas | **Falla:** sin motivo |
| N7 | Hecho concreto + «exactly the kind of problem my team solves» | Líder | **Falla:** sin motivo |
| N8 | Sin calentamiento ni hecho (ruta sin posts, 14 días) | No se redacta («hecho») | **Falla:** sin motivo |
| N9 | Sin cupo de notas este mes | Sale sin nota («cupo») | **Falla:** sin motivo |
| G | Gustavo la confirmó; el clasificador puso nota | Invitada | **Falla:** aprobada y bloqueada (el error) |
| Regresión | Nota del clasificador que el líder aprueba | Sale con nota | **Pasa** |

## Calificación del caso completo

```
passed: False
errors: Citas no recuperadas; Falta fundamento del caso;
        Conducta incorrecta: redactada_al_invitar, nota_con_metodologia, N1_con_nota, N2…N9_stopped_by, G_invitada,
                             invitaciones_sin_salir
result: N1…N9_con_nota=False, G_invitada=False, invitaciones_sin_salir=1, course_citations=[]
```

`course_case_context('nota_invitacion')` no carga ninguna de las tres unidades (`course_missing` = las tres): es la
conducta correcta antes de activar la metodología. El recorrido genérico de `test_fase2_curso` salta este caso hasta
entonces.

## Cómo quedan marcadas las pruebas

Las doce que fallan llevan `@expectedFailure` con su motivo. Se quitan cuando su motivo desaparece: la corrección del
error (G y `ConfirmedNoteBugTests`), la activación de `nota_invitacion` (fuentes y carga de unidades), la redacción al
invitar con sus reglas fijas y las preguntas del líder (N1–N9) detrás de `BUYER_FIRST_MESSAGE_ENABLED`.
