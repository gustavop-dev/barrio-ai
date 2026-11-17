# Línea base de la respuesta del comprador (BIB-11-respuesta-comprador)

Medición del estado actual **antes** de cambiar nada. Quinta metodología de outbound (clase 11, con la clase 08 y la
tabla de diagnóstico de la clase 12): la respuesta del comprador, la reunión agendada y la entrega del lead, la fase 6 de
`docs/plan-outbound.md`. Decisión de Gustavo (17/11/2026): la máquina de LinkedIn termina en la REUNIÓN AGENDADA, con
Cal.com; la calificación y lo que sigue son de una futura máquina de ventas; los mensajes siempre son borradores que él
copia y envía (INB-08).

- **Fecha:** 17/11/2026. Rama `feat/outbound-comprador`, código en `d94e455` (fases 1–5 y el merge de #134).
- **Entorno:** PostgreSQL desechable propia con pgvector, Python 3.12, `LIVE_PROVIDERS=false`. Claude y Jev simulados;
  conector de LinkedIn simulado (sus chats son LinkedIn: lo que Gustavo envía a mano y lo que la persona responde);
  unidades sintéticas; el webhook de Cal.com lo publica el cliente de pruebas, firmado con el secreto de prueba. Las seis
  unidades (`LI-11-M006-K01`, `LI-11-M006-K02`, `LI-11-M006-K03`, `LI-11-M006-K06`, `LI-08-M003-K05`, `LI-12-M001-K04`)
  quedan listadas en el caso, sin activar ni sembrar.
- **Caso:** `evaluaciones.COURSE_CASES['respuesta_comprador']`. **Pruebas:** `src/team_backend/tests/test_respuesta_comprador.py`
  con el arnés `ReplyPathBase` (`test_comprador_e2e.py`): ocho personas recorren el camino real hasta el «Hecho, le
  escribí» del primer mensaje (fase 3); después responden y un reloj simulado avanza con la lectura del inbox
  (`read_inbox`), el paso de borradores del autopiloto (`autopiloto._buyer_drafts`) con sus jobs, Tu turno, los cierres
  de Gustavo, el webhook de Cal.com y la lectura de la entrega.
- **Cómo se midió:** sin los marcadores de fallo esperado, `manage.py test <copia sin marcadores> -v 2` (en serie).
  Resultado: 3 pruebas, ninguna pasa (2 fallan, 1 error), 29,6 s.
- **Ajustes del arnés solo para medir:** `INBOX_THREADS_PER_RUN=20` e `INBOX_READ_CAPS=chats=200,messages=400` (ocho
  respuestas leídas en el mismo ciclo; los topes de producción siguen en 5 hilos por corrida y 24/60 al día) y los de las
  líneas base de las fases 3 y 4.

## Qué existe hoy

La fase 4 detiene la secuencia cuando ella responde: el recorrido pasa a `respondio`, se cancelan los seguimientos y se
llama a `secuencia_comprador.REPLY_HANDLERS`, que está vacío. Nadie clasifica la respuesta ni redacta qué contestar; el
recorrido nunca llega a `interesado` ni a `reunion` (el embudo los cuenta en cero); no hay enlace de agenda, ni webhook de
Cal.com, ni entrega del lead, ni lectura semanal del embudo. Lo que ya funciona: la lectura del inbox lleva su respuesta al
recorrido, la conversación aparece en Tu turno si Jev la marca, y el equipo no envía ningún mensaje.

## Resultado por variante

| Variante | Qué se mide | Esperado | Observado |
| --- | --- | --- | --- |
| Flujo | Interesado → borrador con su enlace → «Hecho» → reserva de Cal.com → `reunion` → entrega → oportunidad con un toque | tipo `interesado`, enlace con su identificador, `reunion`, entrega completa sin calificación, oportunidad en `reunion` | **Falla:** sin tipo; queda en `respondio`; sin borrador, sin enlace; el webhook no existe (404); sin entrega (404) ni oportunidad |
| P | Pide información | `pide_informacion`, enlace, la tarjeta dice qué falta | **Falla:** nada |
| N1 | «Escríbeme después de enero» | descanso `no_es_el_momento` hasta el 1 de febrero, sin enlace | **Falla:** sin descanso |
| N2 | «Ahora no», sin fecha | descanso de 90 días | **Falla:** sin descanso |
| X | No le interesa; vuelve a escribir | salida `no_le_interesa` y nada más preparado | **Falla:** sin salida |
| O | La redirige a otra persona con su perfil | contacto nuevo referido, con su recorrido | **Falla:** nadie la crea |
| B | Respuesta ambigua | `otro`, sin borrador, tarjeta «necesita tu respuesta» | **Falla:** sin tipo ni tarjeta propia |
| E | `CALCOM_BOOKING_URL` vacío | sin borrador con enlace y un aviso | **Falla** el aviso; sin borrador (no existe) |
| I | Interruptor apagado | nada clasificado | **Pasa** (no existe) |
| Todas | Mensajes enviados por el equipo; el enlace fuera de N1, X y O | 0; ninguno | **Pasa** |

## Calificación del caso completo

```
passed: False
errors: Citas no recuperadas; Falta fundamento del caso;
        Conducta incorrecta: clasificacion_con_metodologia, borrador_con_metodologia, flujo_tipo, flujo_paso, flujo_enlace,
                             flujo_reunion, flujo_entrega, flujo_oportunidad, P_tipo, P_enlace, P_faltan, N1_tipo,
                             N1_descanso, N1_hasta_lo_que_dijo, N2_tipo, N2_descanso_dias, X_tipo, X_salida, X_despues,
                             O_tipo, O_referido, B_tipo, B_tarjeta, E_aviso
result: I_clasificadas=0, flujo_paso=respondio, *_tipo=None, flujo_enlace=False, P_enlace=False, N1_enlace=False,
        X_enlace=False, O_enlace=False, B_borrador=False, E_borrador=False, flujo_reunion=False, flujo_entrega=False,
        flujo_oportunidad=None, X_despues=None, mensajes_enviados=0, course_citations=[]
```

`course_case_context('respuesta_comprador')` no carga ninguna de las seis unidades (`course_missing` = las seis): es la
conducta correcta antes de activar la metodología. El recorrido genérico de `test_fase2_curso` salta este caso hasta
entonces. `ReplyRulesTests` falla con `ImportError`: no hay reglas fijas de la respuesta.

## Cómo quedan marcadas las pruebas

Las tres llevaban `@expectedFailure` con su motivo. Se quitaron cuando su motivo desaparece: la activación de
`respuesta_comprador` (fuentes y carga de unidades), las reglas fijas de la respuesta (`respuesta_comprador.text_issues`)
y la fase 6 completa detrás de `BUYER_REPLY_ENABLED`.

## Después de activar (fase 6, 17/11/2026)

Misma rama, con `respuesta_comprador` activada (`637d93b`) y la fase 6 detrás de `BUYER_REPLY_ENABLED`. Mismo entorno y
mismos ajustes del arnés; el caso corre con `BUYER_REPLY_ENABLED=true`, `CALCOM_BOOKING_URL` y `CALCOM_WEBHOOK_SECRET` de
prueba (la variante I lo apaga y la E vacía el enlace). Sin marcadores de fallo esperado.

- **Caso completo:** pasa. Una corrida en serie, 30,9 s.
- **`test_respuesta_comprador.py`:** 26 pruebas, todas pasan (31,9 s con `--parallel 2`), entre ellas las reglas fijas,
  la decisión con umbral y margen, las fechas de «no es el momento», la firma y la recepción del webhook, el pliegue de la
  reunión y la lectura semanal.
- **Camino completo:** `test_comprador_e2e.ReplyBuyerPathTests`, 15 pruebas, todas pasan (73,5 s): el camino entero hasta
  la entrega y las variantes 1 a 11 de la fase.

| Variante | Antes | Después |
| --- | --- | --- |
| Flujo | sin tipo, `respondio`, sin enlace, 404 | `interesado`, borrador con su enlace e identificador, «Hecho», reserva por el webhook emparejada por el enlace, `reunion`, entrega completa sin calificación, oportunidad en `reunion` con un toque |
| P | nada | `pide_informacion`, con enlace, la tarjeta dice qué falta confirmar |
| N1 | sin descanso | `no_es_el_momento`, descanso hasta el 1 de febrero (lo que dijo), sin enlace |
| N2 | sin descanso | `no_es_el_momento`, 90 días |
| X | sin salida | `no_le_interesa`, salida definitiva; vuelve a escribir y no se prepara nada (0) |
| O | nadie la crea | `otra_persona`, Bruno entra como contacto referido con su propio recorrido |
| B | sin tipo | `otro`, sin borrador, tarjeta «necesita tu respuesta» |
| E | sin aviso | sin borrador y `buyer.reply_no_link` |
| I | pasa | pasa: con el interruptor apagado, 0 clasificadas |
| Todas | 0 enviados | 0 enviados por el equipo; el enlace solo en Flujo y P |

```
passed: True
errors: []
result: I_clasificadas=0, flujo_tipo=interesado, flujo_paso=interesado (antes de la reserva), flujo_enlace=True,
        flujo_reunion=True, flujo_entrega=True, flujo_oportunidad=reunion, P_tipo=pide_informacion, P_enlace=True,
        P_faltan=True, N1_tipo=no_es_el_momento, N1_descanso=no_es_el_momento, N1_hasta_lo_que_dijo=True,
        N1_enlace=False, N2_tipo=no_es_el_momento, N2_descanso_dias=90, X_tipo=no_le_interesa,
        X_salida=no_le_interesa, X_despues=0, X_enlace=False, O_tipo=otra_persona, O_referido=True, O_enlace=False,
        B_tipo=otro, B_borrador=False, B_tarjeta=True, E_borrador=False, E_aviso=True, mensajes_enviados=0,
        clasificacion_con_metodologia=True, borrador_con_metodologia=True,
        course_citations=[LI-03-V020-K02, LI-03-M006-K01, LI-03-M005-K06, LI-06-M001-K04, LI-06-M001-K07,
                          LI-11-M006-K01, LI-11-M006-K02, LI-11-M006-K03, LI-11-M006-K06, LI-08-M003-K05, LI-12-M001-K04]
```

Los tres marcadores de fallo esperado ya no están: las fuentes cargan desde `637d93b`, las reglas fijas existen
(`respuesta_comprador.text_issues`, `link_issues`) y la fase 6 está completa.
