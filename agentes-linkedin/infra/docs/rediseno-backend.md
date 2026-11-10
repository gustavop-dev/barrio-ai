# Backend del rediseño: sin aprobaciones, Gustavo orienta

Este backend acompaña el [plan de rediseño de la oficina](../../../oficina/PLAN-REDISENO.md). Los agentes deciden y actúan solos. Gustavo deja de aprobar acciones y pasa a orientar a partir de los resultados. Solo le llega lo que nadie más puede resolver.

Lo implementa este bloque:
- el agente líder;
- las preguntas del equipo y «Lo que el equipo sabe de ti»;
- la orientación;
- las oportunidades;
- Tu turno, Actividad y Ajustes.

Las métricas y Resultados van aparte, en [metricas-resultados.md](metricas-resultados.md).

## Agente líder (`lider.py`)

Sustituye la aprobación humana de cada acción. Se activa con `LEAD_ENABLED=true` para las capacidades de `LEAD_CAPABILITIES` (por defecto `INT-03,CONT-09,RED-01,RED-02,RED-04`) cuando están en modo `auto`.

1. **Reglas fijas primero.** `autopiloto.content_issues` y `red.network_issues` cubren pitch, enlaces, longitud, filtraciones privadas, experiencias inventadas y la persona que ya no está en curso. Cualquier problema descarta la acción.
2. **Jev juzga la propuesta exacta.** Jev es el modelo System One de TypeSafe: le hace preguntas sí/no muy acotadas y devuelve probabilidades calibradas.

   | Capacidad | Preguntas y umbral |
   | --- | --- |
   | Comentario (INT-03) | `aporta` ≥ 0,7, `pitch` ≤ 0,2, `inventa` ≤ 0,2, `respeto` ≥ 0,8, `idioma` ≥ 0,7 |
   | Publicación (CONT-09), además del verificador con Opus | `clara` ≥ 0,6, `pitch` ≤ 0,2, `inventa` ≤ 0,2 |
   | Seguir (RED-01) | `riesgo` ≤ 0,3 |
   | Invitar (RED-02) | `riesgo` ≤ 0,2 |
   | Aceptar (RED-04) | `riesgo` ≤ 0,3 |

   Si hay orientación, se añade `orientacion` ≥ 0,4 (que no la contradiga).

   En la red, Jev no vuelve a juzgar si la persona encaja: lo decide una sola vez el clasificador de la red, y `red.network_issues` descarta antes cualquier RED-* sin ese veredicto (auditoría, R2). Ver [red-barrio.md](red-barrio.md).
3. **Decide el código.** Si todo pasa con claridad, aprueba. Si no, descarta y registra qué falló. **No escala nada a Gustavo.** Lo dudoso no se hace y el equipo prepara otra cosa.

Cada juicio queda en `ActionProposal.review` con las probabilidades, los umbrales, el modelo, el coste y la fecha. La nota de la decisión dice «Aprobada por el líder (jev-1.14.0)» o «Descartada por el líder». Actividad muestra lo descartado con `?descartadas=1`.

**Si Jev no responde**, la acción queda pendiente y se reintenta cada `LEAD_RETRY_MINUTES` (10). Caduca con su TTL; nunca se aprueba sin juicio.

**Tope por ciclo.** El líder revisa como máximo `LEAD_MAX_REVIEWS_PER_TICK` (5) propuestas en cada ciclo del autopiloto, de la más antigua a la más reciente. El resto espera a los ciclos siguientes, así que un `plan_network` con unas 25 propuestas ya no bloquea el ciclo varios minutos. No esperan a ese tope:
- los descartes por reglas fijas;
- las capacidades en modo `approval`;
- la caducidad.

Si Jev no responde a una revisión, el ciclo deja de llamarlo hasta el siguiente en lugar de esperar 60 s por cada propuesta.

**Alerta si no aprueba nada.** El líder solo puede descartar, así que su forma de fallar es no hacer nada sin avisar. Cada `LEAD_SILENCE_CHECK_MINUTES` (60), el autopiloto revisa cada capacidad que el líder juzga en modo `auto`. Si en los últimos 7 días revisó al menos `LEAD_SILENCE_MIN_REVIEWS` (5) propuestas y no aprobó ninguna, llega la Notificación `lead_silent` (capa sistema, con push). Dice cuántas revisó y qué preguntas fallan más, y enlaza a lo que no salió en la Lista del calendario. Llega una sola vez por capacidad y semana.

**Prefiltro de comentarios.** Antes de pagar a Opus por un borrador, Jev mira el post del referente (`lider.comment_worthy`, llamado desde `autopiloto._propose`). Con el umbral `COMMENT_PREFILTER_THRESHOLD` (u = 0,5) pasa si:
- `sustancia` ≥ u: desarrolla una idea, una experiencia o una opinión a la que se puede aportar;
- `tema` ≥ u: trata un tema del barrio (o lo que pide la orientación, si la hay);
- `vacante`, `promocion` e `hito` ≤ 1 − u: no es un anuncio de vacantes, una promoción pura ni un hito personal, donde comentar sería ruido.

Si no pasa, el equipo prueba con el siguiente post candidato. Cada veredicto queda en un `AuditEvent` (`operator.comment_prefilter`) con las probabilidades, y el mismo post no se vuelve a preguntar. Se hacen como máximo 3 preguntas por ciclo. Si Jev no responde, se redacta como antes del prefiltro y queda un aviso `comment_prefilter_unavailable` en el log del autopiloto. Funciona cuando `LEAD_ENABLED=true` y se apaga con `COMMENT_PREFILTER=false`. Nunca usa un modelo de lenguaje.

**Coste.** Cada llamada pasa por `knowledge.providers.typesafe`: proveedor `typesafe`, propósito `lead-review` (`comment-prefilter` en el prefiltro), con reserva y liquidación en el ledger, dentro del presupuesto de IA del equipo (`AI_MONTHLY_LIMIT_USD`) y del techo opcional `TYPESAFE_LIMIT_USD` si se fija. A 0,042 USD por millón de tokens de entrada (la salida es gratis), un juicio de unas 600 tokens cuesta 0,00003 USD.

**Contrato de TypeSafe** (consultado el 2026-11-07): `POST https://api.typesafe.ai/v1/systemone` con `{model, state, questions}` y la clave en `Authorization: Bearer`. Devuelve `answers[id] = {type:'noul', noul:p}` y `usage.input_tokens`. Se probó con un caso inventado en español: un comentario genérico con venta dio `aporta`=0,04, `pitch`=0,99 e `idioma`=0,99.

Los umbrales empiezan conservadores. Se ajustarán con los resultados reales: los descartes y los rendimientos de lo que sí salió.

## Preguntas del equipo (`preguntas.py`)

`TeamQuestion` guarda:
- quién pregunta y qué necesita saber;
- para qué lo necesita (`purpose`);
- el tipo de respuesta: texto, sí o no con detalle, una opción, número o fecha;
- las opciones, la visibilidad sugerida y el plazo (`deadline`, por ejemplo la hora de la pieza para la que se pregunta);
- el aplazamiento, el estado y la respuesta.

De dónde salen las preguntas:
- **El director editorial** puede pedir hasta 2 hechos por pieza (`questions_for_gustavo` en el brief), con la hora de la pieza como plazo.
- **La memoria propuesta pendiente** llega como preguntas de confirmación.
- `preguntas.ask()` no repite una clave abierta, rechazada, retirada ni ya conocida. Cada pregunta nueva llega por push: «{Rol} te pregunta: …».

Cómo se resuelven:
- **Responder.** La respuesta se guarda como memoria confirmada `{texto, uso_publico}`. En las respuestas cortas (sí o no, opción, número, fecha), `texto` incluye la pregunta para que el dato se entienda solo.
- **Deshacer.** Dentro de los 15 minutos siguientes, devuelve la memoria a su versión anterior (o la retira si no había) y reabre la pregunta.
- **Más tarde.** La pospone 3 días.
- **No quiero compartir esto.** Cierra la clave para siempre.
- **Vencidas.** Una pregunta cuyo plazo ya pasó sigue visible, pero no cuenta como pendiente.

**«Lo que el equipo sabe de ti».** Cada dato confirmado muestra:
- su tema (la pregunta o el tema escrito por Gustavo);
- de dónde vino: respondió a un agente, lo añadió él o venía de la memoria;
- la visibilidad;
- cuántas veces se editó.

Gustavo puede añadir un dato a mano, que se confirma directamente; corregirlo, con una versión nueva; o retirarlo, con una lápida confirmada que conserva el historial.

## Orientación (`orientacion.py`)

`GET` y `PUT /api/v1/orientacion` (máximo 4000 caracteres, con sesión humana). Es la dirección de alto nivel de Gustavo. La leen:
- el redactor de comentarios;
- el circuito editorial;
- el clasificador de la red;
- el agente líder.

Las comprobaciones de filtración la protegen como orientación privada (`guardas.blocks()`).

## Oportunidades (`oportunidades.py`)

Siguen el formulario de Personas:
- persona del barrio, o nombre y empresa de alguien fuera de la red;
- modalidad: Startups (personal), ProjectApp o Por clasificar;
- canal: LinkedIn, email, llamada, evento u otro;
- etapa: conversación → necesidad identificada → cualificada → reunión → propuesta → acuerdo, o cerrada sin acuerdo;
- cómo llegó: citó un post o el perfil, lo dijo la persona, se infiere o se desconoce;
- necesidad, presupuesto o compensación, y dedicación;
- siguiente acción con su fecha, que aparece en el calendario;
- notas, historial y días en la etapa.

Las escrituras requieren sesión humana y `approve_actions`.

## Tu turno, Calendario, Personas y Ajustes

**Tu turno** (`GET /api/v1/tu-turno`) entrega tarjetas completas, cada una con:
- tipo y tono;
- el agente que la pide;
- título en imperativo;
- cuerpo y plazo;
- sus acciones con el endpoint y el cuerpo que hay que enviar.

Avisos, según el spec:
- LinkedIn caducado (crítico);
- LinkedIn caduca pronto;
- acción incierta (crítica), con lo que se intentó y los botones «Sí, se aplicó» y «No se aplicó», que piden nota;
- máquina detenida desde la app (crítica, con Reanudar);
- máquina detenida desde el servidor (crítica, sin acción);
- cuenta en pausa.

Lo informativo no entra: las invitaciones limitadas, las piezas bloqueadas y el presupuesto se ven en Personas, Calendario y Ajustes.

Además, la respuesta trae:
- el contador y si hay algo crítico;
- el elemento más urgente (`top`), para la Oficina;
- las preguntas pospuestas o vencidas aparte (`later`);
- lo resuelto en los últimos 7 días;
- el resumen del día para el estado vacío.

Las conversaciones que le tocan a Gustavo llegan como tareas (`tasks.conversaciones`, tipo `conversacion`, Importante) cuando el inbox está encendido; ver [conversaciones e inbox](conversaciones-inbox.md). Las tareas de perfil llegan con la fase del ciclo de Perfil.

**Calendario** (`GET /api/v1/calendario`) devuelve, por día local, los conteos menudos y los eventos importantes, en cinco capas:

| Capa | Eventos |
| --- | --- |
| Tuyo | Plazos de preguntas, siguientes acciones y reuniones de oportunidades, caducidad de LinkedIn y lo que Gustavo resolvió |
| Publicaciones | Cada pieza con su estado |
| Red | Conexiones nuevas que encajan (agrupadas), invitaciones recibidas y aceptadas, e invitaciones previstas al terminar la espera de 48 h (como estimación) |
| Conversaciones | Oportunidades nuevas o que cambian de etapa |
| Sistema | Paradas, reanudaciones, cuentas en pausa y acciones inciertas o fallidas |

La **vista Lista** (`GET /api/v1/actividad`) trae «Próximo» y todo lo hecho, con filtros y paginación:
- **Próximo:** la pieza con su estado, etapa, tesis, primeras líneas, pilar, modalidad y lector; y las acciones en cola, con la hora estimada de salida según la ventana y el espaciado.
- **Cada elemento:** texto, extracto del post original, reacción, persona con su rol, enlace, justificación, quién decidió y su estado traducido.

**Personas:**
- **Cada persona trae:**
  - su etapa visible, que es «Oportunidad» si tiene una abierta;
  - el siguiente paso y de quién depende;
  - sus notas;
  - su oportunidad abierta.
- **La lista** busca por nombre o titular y filtra por rol y modalidad.
- **Los referentes** se desactivan, se reactivan o se quitan, y muestran cuántas personas salieron de sus posts.

**Ajustes** reúne:
- el modo de cada capacidad y el estado del líder;
- la ventana (abierta o cerrada ahora) y el espaciado;
- topes;
- el gasto de IA de hoy de todo el equipo frente a su tope de seguridad diario (`AI_DAILY_FUSE_USD`) y el de cada área (general, editorial, imágenes y red) sin tope propio, más el mes frente a `AI_MONTHLY_LIMIT_USD`, el total y lo gastado en Jev;
- el número de datos confirmados;
- la orientación.

**Notificaciones push.** Las piezas llevan a `/calendario/pieza/<id>`. La alerta del líder (`lead_silent`) lleva a la Lista del calendario con lo que no salió. Las acciones inciertas, la cuenta en pausa, la caducidad de LinkedIn y las preguntas llevan a `/tu-turno`.

## Configuración

```
OPERATOR_AUTONOMY=INT-03=auto,INT-02=auto,CONT-09=auto,RED-01=auto,RED-02=auto,RED-04=auto
LEAD_ENABLED=true
LEAD_CAPABILITIES=INT-03,CONT-09,RED-01,RED-02,RED-04
LEAD_RETRY_MINUTES=10
LEAD_MAX_REVIEWS_PER_TICK=5
LEAD_SILENCE_MIN_REVIEWS=5
LEAD_SILENCE_CHECK_MINUTES=60
COMMENT_PREFILTER=true
COMMENT_PREFILTER_THRESHOLD=0.5
TYPESAFE_API_KEY=…            # privada; nunca en el repositorio
TYPESAFE_MODEL=jev-1.14.0
TYPESAFE_LIMIT_USD=             # opcional: techo mensual de Jev dentro del presupuesto de IA del equipo
```

Las salvaguardas no cambian:
- parada total y pausa por cuenta;
- ventana horaria, espaciado y topes diarios y semanales;
- una sola ejecución, con conciliación sin repetir;
- verificador de publicaciones;
- pausa de 7 días de las invitaciones si LinkedIn las limita.

Vetar sigue disponible en las piezas programadas.
