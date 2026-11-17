# Línea base de la secuencia de mensajes 2 a 4 (BIB-09-secuencia-mensajes)

Medición del estado actual **antes** de cambiar nada. Cuarta metodología de outbound (clase 09, con las reglas de
detención de la clase 10): los mensajes 2 a 4 después del primero, la fase 4 de `docs/plan-outbound.md`. Decisión de
Gustavo (17/11/2026): el seguimiento es la secuencia de cuatro mensajes del curso, siempre en borradores que él copia y
envía; la app nunca envía un mensaje privado (INB-08).

- **Fecha:** 17/11/2026. Rama `feat/outbound-comprador`, código en `daa281f` (fase 3 y el merge de #133).
- **Entorno:** PostgreSQL desechable propia con pgvector, Python 3.12, `LIVE_PROVIDERS=false`. Claude y Jev simulados;
  conector de LinkedIn simulado (sus chats son LinkedIn: lo que Gustavo envía a mano y lo que la persona responde);
  unidades sintéticas. Las seis unidades (`LI-09-M003-K05`, `LI-09-V014-K01`, `LI-09-V014-K02`, `LI-09-V014-K03`,
  `LI-10-V013-K02`, `LI-10-M001-K08`) quedan listadas en el caso, sin activar ni sembrar.
- **Caso:** `evaluaciones.COURSE_CASES['secuencia_mensajes']`. **Pruebas:** `src/team_backend/tests/test_secuencia_mensajes.py`
  con el arnés `SequencePathBase` (`test_comprador_e2e.py`): nueve personas recorren el camino real hasta el «Hecho, le
  escribí» del primer mensaje (fase 3) y después un reloj simulado avanza los días: la lectura del inbox
  (`read_inbox`, `INBOX_ENABLED=true`), el paso de borradores del autopiloto (`autopiloto._buyer_drafts`) con sus jobs,
  Tu turno y los cierres de Gustavo. Cada ciclo corre un minuto antes y un minuto después de cada vencimiento.
- **Cómo se midió:** sin los marcadores de fallo esperado, `manage.py test team_backend.tests.test_secuencia_mensajes -v 2`
  (en serie). Resultado: 3 pruebas, ninguna pasa (2 fallan, 1 error).
- **Ajustes del arnés solo para medir:** `BUYER_POSTS_READ_DAILY_LIMIT=20` (nueve compradores leídos el mismo día; el
  tope de producción sigue en 8) y los de la línea base del primer mensaje.

## Qué existe hoy

El recorrido termina en el primer mensaje: `BuyerDraft.number` existe (1) pero nadie prepara el 2, el 3 ni el 4;
`comprador.next_at` no tiene nada que hacer en `mensaje_1`…`mensaje_4`; ninguna regla mira si la persona respondió antes
de seguir (no hay nada que seguir), nadie la pasa a descanso tras la secuencia y no hay avisos. Lo que ya funciona: la
lectura del inbox lleva su respuesta al recorrido (`respondio`) y el equipo no envía ningún mensaje.

## Resultado por variante

| Variante | Qué se mide | Esperado | Observado |
| --- | --- | --- | --- |
| Flujo | M2, M3 y M4 a los 4, 5 y 7 días del «Hecho» anterior; nada un minuto antes; descanso de 90 días a los 7 días del M4 | `[2,3,4]`, `[4,5,7]`, descanso `secuencia_sin_respuesta` 90 | **Falla:** ningún seguimiento (`[]`), sin descanso |
| S2 | Responde con el M3 en Tu turno | M3 cancelado, sin M4, recorrido `respondio`, respondió tras el 2 | **Falla:** nunca hubo M2 ni M3; el paso `respondio` sí (la lectura del inbox) |
| S3 | Gustavo no envió el M2 | Sin M3 (`[2]`) | **Falla:** ni M2 |
| S4 | Inbox apagado | Ningún seguimiento y un aviso (`buyer.sequence_waiting`) | **Falla** el aviso; ningún seguimiento (no existe) |
| S5 | M2 que repite el M1 | Reglas | **Falla:** sin motivo |
| S6 | M2 que se disculpa | Reglas | **Falla:** sin motivo |
| S7 | M3 sin «¿no eres la persona indicada?» | Reglas | **Falla:** sin motivo |
| S8 | M4 que pide algo | Reglas | **Falla:** sin motivo |
| S9 | M3 que vuelve a contar el dolor | Líder | **Falla:** sin motivo |
| S10 | «No escribirle» en el M3 | Salida `descartado_por_gustavo` tras `[2,3]` | **Falla:** no hay M3 que cerrar |
| S11 | Interruptor apagado | Ningún seguimiento | **Pasa** (no existe) |
| Todas | Tarjetas de borradores parados; mensajes enviados por el equipo | 0 y 0 | **Pasa** |

## Calificación del caso completo

```
passed: False
errors: Citas no recuperadas; Falta fundamento del caso;
        Conducta incorrecta: borrador_con_metodologia, flujo_numeros, flujo_dias, flujo_descanso, flujo_descanso_dias,
                             S2_numeros, S2_cancelados, S2_respondio_tras, S3_numeros, S4_aviso, S5…S9_stopped_by,
                             S10_salida, S10_numeros
result: flujo_numeros=[], flujo_dias=[], flujo_antes_de_tiempo=False, S2_paso=respondio, S4_numeros=[], S11_numeros=[],
        tarjetas_paradas=0, mensajes_enviados=0, course_citations=[]
```

`course_case_context('secuencia_mensajes')` no carga ninguna de las seis unidades (`course_missing` = las seis): es la
conducta correcta antes de activar la metodología. El recorrido genérico de `test_fase2_curso` salta este caso hasta
entonces. `SequenceRulesTests` falla con `ImportError`: no hay reglas fijas por número.

## Cómo quedan marcadas las pruebas

Las tres llevan `@expectedFailure` con su motivo. Se quitan cuando su motivo desaparece: la activación de
`secuencia_mensajes` (fuentes y carga de unidades), las reglas fijas por número (`secuencia_comprador.text_issues`) y la
secuencia completa detrás de `BUYER_SEQUENCE_ENABLED`.

## Después de activar (17/11/2026)

Con la metodología activada (`1b498b9`) y la secuencia detrás de `BUYER_SEQUENCE_ENABLED`
(`secuencia_comprador.py`), las tres pruebas pasan sin marcadores de fallo esperado, más las de activación, del
registro de lectura y la de que solo sus roles nombran la metodología: `manage.py test
team_backend.tests.test_secuencia_mensajes` → 6 pruebas, OK (unos 40 s).

```
passed: True
result: flujo_numeros=[2,3,4], flujo_dias=[4,5,7], flujo_antes_de_tiempo=False, flujo_descanso=secuencia_sin_respuesta,
        flujo_descanso_dias=90, S2_paso=respondio, S2_numeros=[2,3], S2_cancelados=[3], S2_respondio_tras=2,
        S3_numeros=[2], S4_numeros=[], S4_aviso=True, S5…S8_stopped_by=reglas, S9_stopped_by=juez, S10_salida=
        descartado_por_gustavo, S10_numeros=[2,3], S11_numeros=[], tarjetas_paradas=0, mensajes_enviados=0,
        borrador_con_metodologia=True, course_citations= las cinco del líder y las seis de la secuencia
```

| Variante | Antes | Después |
| --- | --- | --- |
| Flujo | ningún seguimiento | M2, M3 y M4 a los 4, 5 y 7 días del «Hecho» anterior; nada un minuto antes; descanso de 90 días a los 7 días del M4 |
| S2 | sin M2 ni M3 | M3 cancelado al leer su respuesta, sin M4, `respondio`, respondió tras el 2 |
| S3 | sin M2 | M2 en Tu turno sin enviar: sin M3 |
| S4 | sin aviso | ningún seguimiento y `buyer.sequence_waiting` (una vez al día; Slack `secuencia_sin_inbox`) |
| S5–S8 | sin motivo | reglas fijas por número (`text_issues`): repite, se disculpa, sin «¿persona indicada?», pide |
| S9 | sin motivo | el líder (`seg_repite_dolor`) |
| S10 | sin M3 | «No escribirle» en el M3: salida definitiva |
| S11 | nada | nada (interruptor apagado) |

Ajuste del arnés al medir: un ciclo del arnés corre el paso de borradores hasta que no encola nada (30 vueltas en vez
de 8), como lo hace el autopiloto real en los minutos siguientes: con nueve personas que vencen el mismo minuto, 8
vueltas dejaban a la novena para el ciclo siguiente.
