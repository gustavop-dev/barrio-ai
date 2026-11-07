# Plan de rediseño de la oficina

Acordado con Gustavo el 2026-11-06. Base para el diseño visual. El inventario de lo que existe hoy está en [`VISTAS.md`](VISTAS.md).

## Principio

Los agentes deciden y actúan solos. La app deja de ser un panel de control de la máquina y pasa a responder tres preguntas:

1. **¿Qué tengo que hacer yo?** Solo lo que nadie más puede hacer, y entregado completo.
2. **¿Vamos bien?** Resultados reales en LinkedIn.
3. **¿Con quién estamos hablando?** Personas y conversaciones.

Lo que hizo el equipo, por qué lo hizo y cuánto costó queda como consulta secundaria. No hay aprobaciones; el veto y la parada total quedan como salidas de emergencia.

## Navegación

| Vista | Ruta | Para qué |
|---|---|---|
| **Oficina** (inicio) | `/` | La escena del equipo trabajando. Se queda como inicio. |
| **Tu turno** | `/tu-turno` | Lo que depende de ti: preguntas del equipo, tareas y avisos. Lleva un contador en la navegación. |
| **Resultados** | `/resultados` | Dashboard para saber si vamos bien. |
| **Personas** | `/personas` | Prospectos, red y conversaciones, cada uno con su siguiente paso. |
| **Actividad** | `/actividad` | Lo que hizo y hará el equipo. Solo lectura, con veto opcional en lo programado. |
| **Ajustes** | `/ajustes` | Conexiones, notificaciones, parada total, autonomía, gasto de IA y referentes. |

- **Escritorio:** las 6 vistas en la barra lateral.
- **Móvil:** barra inferior con 5 (Oficina, Tu turno, Resultados, Personas y Actividad); Ajustes va en un icono de la barra superior.
- El banner de pausa sigue visible en todas las vistas.

## 1. Oficina (inicio)

- Se queda la escena tal como está: personajes con su estado real, luz de mañana o de tarde, ambiente, panel de equipo y panel de rol.
- Lo único nuevo es un acceso a Tu turno desde la escena, por ejemplo «3 cosas dependen de ti», cuando haya algo pendiente.

## 2. Tu turno

Regla: algo solo entra si **nadie más que Gustavo** puede resolverlo, y llega **completo**: contexto, lo que hay que hacer, el texto listo y un botón para cerrarlo. Tiene tres secciones.

### Preguntas del equipo

El espacio para responder lo que los agentes necesitan saber de ti.

- Cada pregunta muestra:
  - quién la hace;
  - qué necesita saber;
  - para qué lo necesita (por ejemplo, «para contar una experiencia real en el post del jueves»);
  - el campo de respuesta.
- Al responder, el dato pasa a la memoria confirmada. Esa memoria es la que alimenta los hechos públicos que usan los posts y los comentarios: hoy está vacía, así que la voz no puede contar experiencias propias.
- Se puede responder «No quiero compartir esto», y la pregunta no vuelve.
- Debajo, **«Lo que el equipo sabe de ti»**: las respuestas ya dadas, para corregirlas o retirarlas.

### Tareas

- **Tareas de perfil.** Por ejemplo, «Cambia tu titular»:
  - el texto exacto para copiar;
  - dónde se cambia en LinkedIn;
  - por qué, en dos líneas;
  - los botones *Hecho* y *No lo haré (con motivo)*.
  - Lo mismo para Acerca de, experiencia y destacados.
- **Conversaciones que te tocan.** Alguien que encaja te escribió, respondió a tu comentario o aceptó tu invitación. La tarjeta trae:
  - quién es y por qué importa;
  - un resumen del hilo y un borrador de respuesta;
  - *Abrir en LinkedIn*, *Hecho* e *Ignorar*.

### Avisos

Lo que se rompe sin ti:

- LinkedIn caduca en pocos días: *Reconectar*.
- Una acción quedó incierta: *¿Salió o no?*
- La máquina se detuvo, o LinkedIn limitó las invitaciones.

**Estado vacío:** «Nada depende de ti hoy», con un resumen de lo que hizo el equipo.

La pieza del día **no** entra: sale sola. Aparece en Actividad con «Vetar» hasta su hora y llega por push.

## 3. Resultados

El orden sigue `agentes-linkedin/infra/docs/datos-y-resultados-del-equipo.md`: lo principal son las oportunidades y lo demás es apoyo. Todo se compara con el periodo anterior (semana contra semana, o las últimas 4 semanas), y «sin dato» nunca se muestra como 0.

**1. ¿Genera negocio?**
- Conversaciones pertinentes abiertas esta semana.
- Embudo de oportunidades: conversación → necesidad → cualificada → reunión → propuesta → acuerdo.
- Todo separado entre **Startups (personal)** y **ProjectApp** (objetivo 60/40).
- Inbound: personas que encajan y te escriben o te invitan sin que las busques.

**2. ¿Llegamos a la gente correcta?**
- Crecimiento neto semanal de seguidores y conexiones.
- Conexiones nuevas que encajan, por rol del barrio (comprador, par, recomendador, divulgador, líder y aliado).
- Tasa de aceptación de invitaciones.
- Visitas al perfil.
- Personas que vuelven a interactuar.

**3. ¿El contenido aporta?**
- Impresiones por post a las 24 h y a los 7 días, frente a la mediana de las últimas 4 semanas.
- Interacción = (reacciones + comentarios + republicaciones) / impresiones, con la fórmula visible.
- Comentarios con sustancia y de quién vienen (rol del barrio).
- Mejor post del mes, por pilar.
- Constancia: días publicados frente a días previstos.

**4. ¿El equipo trabaja bien?** (pequeño, abajo del todo)
- Comentarios en posts de referentes y cuántos recibieron respuesta.
- Seguidos, invitados y aceptados en la semana.
- Gasto de IA del mes frente al presupuesto.

### Datos disponibles hoy

| Dato | Estado |
|---|---|
| Impresiones de cada post propio | Se guardan **una sola vez, segundos después de publicar** (`operador._record_metrics`), así que casi siempre valen ~0. Hacen falta cortes a las 24 h, 72 h y 7 días. |
| Reacciones y comentarios por post | El conector ya los lee (`connectors._post`), pero no se guardan. |
| Embudo de la red por etapa y por rol | Disponible: `/api/v1/red/summary` y `/api/v1/red/contacts`. |
| Seguidores, conexiones y visitas al perfil | No se capturan. Hay que comprobar qué da Unipile, o pedir a LinkedIn el permiso `r_member_profileAnalytics`, que requiere una revisión de la app. |
| Inbox y conversaciones | No está implementado. Unipile documenta los chats y sus webhooks. |
| Oportunidades y sus etapas | No existen todavía. |

## 4. Personas

Nace de la vista Red y absorbe Referentes.

- **Lista de personas con filtros:**
  - Etapa: descubierta, encaja, seguida, invitada, conectada, en conversación y oportunidad.
  - Rol del barrio y modalidad.
  - Referentes, como un tipo más.
- **Ficha de cada persona:**
  - quién es, por qué encaja y de dónde salió;
  - historial completo y última interacción;
  - **siguiente paso**, y de quién depende: del equipo o tuyo.
- **Oportunidades:** Gustavo marca a una persona como oportunidad y mueve su etapa a mano. Cuando exista la lectura del inbox, el analista podrá proponerlo.
- **Acciones:** *Descartar*, que ya existe. Para referentes: añadir, desactivar y quitar.

## 5. Actividad

Junta Acciones, el calendario de Contenido y el feed de Máquina en una sola línea de tiempo.

- **Próximo:** la pieza programada, con su hora y «Vetar».
- **Hecho:** posts, comentarios, reacciones, seguimientos, invitaciones y aceptaciones.
  - Cada elemento lleva el texto, a quién iba, el enlace a LinkedIn y, cuando aplique, «por qué» (justificación).
  - Se puede filtrar por tipo.
- **Detalle de una pieza:** la página actual de Pieza, aligerada. Arriba quedan el texto final y el resultado; el brief, las variantes, el panel de lectores y el verificador pasan a secciones plegadas, bajo «Cómo se escribió».
- **Inciertas:** no se resuelven aquí, sino desde Tu turno.

## 6. Ajustes

- LinkedIn oficial: estado, caducidad y Conectar o Reconectar.
- Notificaciones push.
- **Parada total** y reanudar.
- **Autonomía:** el modo de cada capacidad (auto, aprobación o apagado), en solo lectura mientras se configure en el servidor.
- Gasto de IA, en una línea: «este mes, X de Y».
- Topes y ventana horaria, plegados.
- Sesión y Acerca de.

## Qué pasa con cada vista actual

| Vista actual | Destino |
|---|---|
| Oficina | Se queda como inicio, con acceso a Tu turno. |
| Máquina | Se reparte: la parada total, el gasto, los topes y la ventana van a Ajustes; el feed va a Actividad. |
| Acciones | Pasa a Actividad. Las inciertas van a Tu turno. Sin aprobaciones. |
| Contenido | La pieza programada y el historial pasan a Actividad. |
| Pieza | Queda como detalle dentro de Actividad, aligerado. |
| Referentes | Se integra en Personas. |
| Red | Pasa a ser Personas. Los topes y lecturas de red van a Ajustes, plegados. |
| Conocimiento | **Desaparece de la interfaz.** Sigue en el backend como base de datos de los agentes. Las citas del curso se muestran como texto, sin enlace. |
| Memoria | Pasa a Tu turno: preguntas y «Lo que el equipo sabe de ti». |
| Ajustes | Se queda y crece con lo que viene de Máquina. |
| Login | Igual. |

## Autonomía: sin aprobaciones

- En el código, comentarios, reacciones y la publicación diaria (INT-03, INT-02 y CONT-09) ya están en `auto` por defecto.
- Seguir, invitar y aceptar en la red (RED-01, RED-02 y RED-04) pasan a `auto` con `OPERATOR_AUTONOMY`, y requieren `OPERATOR_AUTOPILOT=true`.
- Hay que revisar los valores del despliegue, porque el contrato habla de un modo de ensayo con todo en `approval`.
- Las salvaguardas no cambian: verificador, guardas de texto, topes diarios y semanales, ventana horaria, la comprobación previa a cada acción de red (`red.network_issues`) y la pausa de 7 días si LinkedIn limita las invitaciones.
- En la interfaz desaparecen «Aprobar» y «Pendiente de aprobación». Quedan «Vetar», que es opcional, y «Parada total».

## Trabajo de backend necesario

| Para | Qué hace falta |
|---|---|
| Preguntas del equipo | Un modelo de pregunta: agente, contexto, para qué, estado y respuesta. Los agentes la crean cuando les falta un dato, y la respuesta se guarda como memoria confirmada. |
| Métricas de contenido | Cortes por post a las 24 h, 72 h y 7 días, con impresiones, reacciones, comentarios y republicaciones. |
| Métricas de audiencia | Seguidores y conexiones a diario, y visitas al perfil si la fuente lo permite. |
| Conversaciones | Lectura del inbox vía Unipile (chats y webhooks) y detección de las que te tocan. |
| Oportunidades | Un modelo de oportunidad con etapas, modalidad y procedencia, y su registro manual desde Personas. |
| Tareas de perfil | Implementar el ciclo de Estrategia y Perfil (`agentes-linkedin/infra/docs/ciclo-estrategia-perfil.md`) para que entregue tareas completas. |
| Tu turno | Un endpoint que agregue preguntas, tareas y avisos con su contador. |

## Fases

1. **Solo frontend, con lo que ya existe:**
   - la nueva navegación;
   - la Oficina con acceso a Tu turno;
   - Tu turno con avisos, inciertas y memoria;
   - Actividad unificada;
   - Personas sobre la red y los referentes;
   - una primera versión de Resultados con el embudo de la red;
   - Ajustes con lo que viene de Máquina;
   - quitar Conocimiento.
2. **Preguntas del equipo y métricas:** el modelo de preguntas y los cortes por post y de audiencia; Resultados completo.
3. **Conversaciones y oportunidades:** el inbox y el modelo de oportunidad. Personas pasa a ser un CRM ligero.
4. **Tareas de perfil:** el ciclo de Estrategia y Perfil conectado a Tu turno.

## Decisiones

- La Oficina se queda como inicio. *(Gustavo)*
- Conocimiento sale de la interfaz y queda en el backend. *(Gustavo)*
- Las preguntas del equipo tienen su propio espacio para responderlas, dentro de Tu turno. *(Gustavo)*
- Sin aprobaciones: los agentes actúan solos, con veto opcional y parada total. *(Gustavo)*
- La red pasa a `auto` junto con lo demás. *(Por defecto, cambiable)*
- Al principio, Gustavo registra las oportunidades a mano; el analista las propondrá cuando exista el inbox. *(Por defecto, cambiable)*
