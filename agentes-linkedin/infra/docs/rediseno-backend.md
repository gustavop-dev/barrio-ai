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
   | Seguir (RED-01) | `encaja` ≥ 0,6, `riesgo` ≤ 0,3 |
   | Invitar (RED-02) | `encaja` ≥ 0,7, `riesgo` ≤ 0,2 |
   | Aceptar (RED-04) | `encaja` ≥ 0,5, `riesgo` ≤ 0,3 |

   Si hay orientación, se añade `orientacion` ≥ 0,4 (que no la contradiga).
3. **Decide el código.** Si todo pasa con claridad, aprueba. Si no, descarta y registra qué falló. **No escala nada a Gustavo.** Lo dudoso no se hace y el equipo prepara otra cosa.

Cada juicio queda en `ActionProposal.review` con las probabilidades, los umbrales, el modelo, el coste y la fecha. La nota de la decisión dice «Aprobada por el líder (jev-1.14.0)» o «Descartada por el líder». Actividad muestra lo descartado con `?descartadas=1`.

**Si Jev no responde**, la acción queda pendiente y se reintenta cada `LEAD_RETRY_MINUTES` (10). Caduca con su TTL; nunca se aprueba sin juicio.

**Coste.** Cada llamada pasa por `knowledge.providers.typesafe`: proveedor `typesafe`, propósito `lead-review`, con reserva y liquidación en el ledger y techo `TYPESAFE_LIMIT_USD`. A 0,042 USD por millón de tokens de entrada (la salida es gratis), un juicio de unas 600 tokens cuesta 0,00003 USD.

**Contrato de TypeSafe** (consultado el 2026-11-07): `POST https://api.typesafe.ai/v1/systemone` con `{model, state, questions}` y la clave en `Authorization: Bearer`. Devuelve `answers[id] = {type:'noul', noul:p}` y `usage.input_tokens`. Se probó con un caso inventado en español: un comentario genérico con venta dio `aporta`=0,04, `pitch`=0,99 e `idioma`=0,99.

Los umbrales empiezan conservadores. Se ajustarán con los resultados reales: los descartes y los rendimientos de lo que sí salió.

## Preguntas del equipo (`preguntas.py`)

`TeamQuestion` guarda:
- quién pregunta (el agente);
- qué necesita saber y para qué (`purpose`);
- la clave de memoria;
- si sugiere uso público;
- el estado (abierta, respondida, no quiere compartirlo o retirada);
- la respuesta.

De dónde salen las preguntas:
- **Agentes.**
  - El director editorial puede pedir hasta 2 hechos por pieza, cuando una experiencia real de Gustavo haría la pieza claramente mejor. Van en el campo `questions_for_gustavo` del brief.
  - `preguntas.ask()` no repite una clave abierta, rechazada, retirada ni ya conocida.
  - Cada pregunta nueva llega por push.
- **Memoria pendiente.** Cada hecho propuesto y aún no confirmado se convierte en una pregunta de confirmación, que se sincroniza al abrir Tu turno.

Cómo se responden:
- **Responder** (`POST /api/v1/preguntas/<id>/responder`, con `{text?, public_use?, accept?}`) guarda la respuesta como memoria confirmada `{texto, uso_publico}` con `memory.set_fact`. `accept=true` confirma tal cual el dato propuesto de una pregunta de confirmación. Solo los hechos con `uso_publico=true` pueden contarse con la voz de Gustavo en público.
- **«No quiero compartir esto»** (`POST /api/v1/preguntas/<id>/no-compartir`) cierra esa clave para siempre.
- Las dos acciones requieren sesión humana y el permiso `confirm_memory`.

**«Lo que el equipo sabe de ti»** está en `GET /api/v1/memoria/hechos`, que devuelve `[{key, text, public_use, version, updated_at}]`.
- `POST …/<key>/corregir` (`{text, public_use}`) confirma una versión nueva.
- `POST …/<key>/retirar` (`{reason?}`) confirma una lápida `{retirado: true}`. Los agentes dejan de usar ese dato y su historial se conserva.

## Orientación (`orientacion.py`)

`GET` y `PUT /api/v1/orientacion` (`{text}`, máximo 4000 caracteres, con sesión humana). Es la dirección de alto nivel que Gustavo le da al equipo, por ejemplo:
- «más founders técnicos de EE. UU., menos marketers»;
- «empujar IA aplicada a operaciones»;
- «esta semana nada de invitaciones».

La leen:
- el redactor de comentarios;
- el director, los redactores, la selección y el verificador del circuito editorial;
- el clasificador de la red;
- el agente líder.

Es orientación privada: entra en `guardas.blocks()`, así que las comprobaciones de filtración también la protegen.

## Oportunidades (`oportunidades.py`)

`Opportunity` guarda:
- persona opcional;
- título;
- modalidad: `personal_startups` o `projectapp`;
- etapa: conversación → necesidad → cualificada → reunión → propuesta → acuerdo, o perdida;
- origen: `inbound`, `outbound`, `referido` u `otro`;
- notas e historial.

Endpoints:
- `GET /api/v1/oportunidades?stage=&modality=&contact=`;
- `POST /api/v1/oportunidades`;
- `GET` y `PATCH /api/v1/oportunidades/<id>`.

Las escrituras requieren sesión humana y `approve_actions`. Por ahora Gustavo las registra a mano desde Personas; el analista las propondrá cuando exista la lectura del inbox.

## Tu turno, Actividad y Ajustes

- **`GET /api/v1/tu-turno`** devuelve `{count, questions, tasks:{perfil:[], conversaciones:[]}, alerts, summary}`.
  - Avisos, cada uno con su acción:
    - LinkedIn caduca o caducó (Reconectar);
    - acciones inciertas («¿Salió o no?», con el endpoint para resolverlas);
    - máquina detenida;
    - cuenta en pausa;
    - invitaciones limitadas por LinkedIn;
    - presupuesto de IA al 80 % o más.
  - `summary` trae lo hecho hoy y la próxima pieza, para el estado vacío.
  - Las tareas de perfil y de conversaciones llegan en fases posteriores del plan.
- **`GET /api/v1/actividad?tipo=&limit=&descartadas=1`** es una sola línea de tiempo:
  - `upcoming.pieces`: piezas programadas, con `vetoable`;
  - `upcoming.queued`: acciones aprobadas esperando su turno;
  - `done`: lo confirmado, con texto, objetivo, enlace, justificación y quién decidió (`gustavo`, `lider` o `politica`);
  - `discarded`: opcional.
  - `tipo` admite comentarios, reacciones, publicaciones, seguimientos, invitaciones y aceptaciones.
- **`GET /api/v1/ajustes`** devuelve:
  - el modo de cada capacidad;
  - el estado del líder;
  - topes y ventana;
  - el gasto de Anthropic del mes, el acumulado y el techo;
  - la orientación.

## Configuración

```
OPERATOR_AUTONOMY=INT-03=auto,INT-02=auto,CONT-09=auto,RED-01=auto,RED-02=auto,RED-04=auto
LEAD_ENABLED=true
LEAD_CAPABILITIES=INT-03,CONT-09,RED-01,RED-02,RED-04
LEAD_RETRY_MINUTES=10
TYPESAFE_API_KEY=…            # privada; nunca en el repositorio
TYPESAFE_MODEL=jev-1.14.0
TYPESAFE_LIMIT_USD=2
```

Las salvaguardas no cambian:
- parada total y pausa por cuenta;
- ventana horaria, espaciado y topes diarios y semanales;
- una sola ejecución, con conciliación sin repetir;
- verificador de publicaciones;
- pausa de 7 días de las invitaciones si LinkedIn las limita.

Vetar sigue disponible en las piezas programadas.
