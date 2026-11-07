# Especificación de vistas para el diseño UI

Detalle de cada pantalla de la oficina rediseñada: bloques, campos de cada elemento, acciones, estados y comportamiento en móvil. El porqué y las fases están en [`PLAN-REDISENO.md`](PLAN-REDISENO.md); lo que existe hoy, en [`VISTAS.md`](VISTAS.md).

**Cómo leerla:**
- **Existe** quiere decir que el backend ya da ese dato o esa acción (se cita el endpoint de [`CONTRATO-API.md`](CONTRATO-API.md)).
- **Nuevo** quiere decir que hay que construirlo en el backend. Se diseña igual; en la fase 1 se muestra con el estado «aún no disponible» (ver [Componentes](#componentes-comunes)).
- Los textos entre comillas son propuestas de copy, no obligatorios.

---

## Índice

1. [Marco común](#marco-común)
2. [Oficina (inicio)](#1-oficina-inicio)
3. [Tu turno](#2-tu-turno)
4. [Calendario](#3-calendario)
5. [Resultados](#4-resultados)
6. [Personas](#5-personas)
7. [Ajustes](#6-ajustes)
8. [Login](#7-login)
9. [Notificaciones push](#notificaciones-push)
10. [Componentes comunes](#componentes-comunes)
11. [Vocabularios: estados, etiquetas y tonos](#vocabularios-estados-etiquetas-y-tonos)

---

## Marco común

### Navegación

| Orden | Vista | Ruta | Etiqueta corta (móvil) |
|---|---|---|---|
| 1 | Oficina | `/` | Oficina |
| 2 | Tu turno | `/tu-turno` | Tu turno |
| 3 | Calendario | `/calendario` | Calendario |
| 4 | Resultados | `/resultados` | Resultados |
| 5 | Personas | `/personas` | Personas |
| 6 | Ajustes | `/ajustes` | — (icono en la barra superior) |

- **Escritorio (≥ 900 px):**
  - Barra lateral fija con el logo «Barrio AI», las 6 vistas con icono y etiqueta, y abajo el crédito «Arte: LimeZu · Modern Interiors» con enlace.
  - La vista activa se resalta.
- **Móvil (< 900 px):**
  - Barra superior con el logo a la izquierda y el icono de Ajustes a la derecha.
  - Barra inferior fija con 5 entradas (Oficina, Tu turno, Calendario, Resultados y Personas), cada una con icono y etiqueta corta.
  - Respetar el área segura inferior del iPhone (PWA instalada).
- **Contador de Tu turno:** número de pendientes en la entrada de navegación (escritorio y móvil).
  - Rojo si hay algún aviso crítico; neutro si solo hay preguntas o tareas.
  - Oculto si es 0.
  - Cuenta los avisos, las preguntas y las tareas pendientes (no las pospuestas).

### Banner de pausa (global)

Aparece debajo de la barra superior, en todas las vistas, mientras la máquina está detenida. **Existe:** `overview.control`.

- **Contenido:** icono de pausa, «Máquina en pausa», el motivo y «· fijada en el entorno» si `source = env`.
- **Al tocarlo:** lleva a Ajustes → Máquina.
- **Variante cuenta en pausa:** «La cuenta de LinkedIn está en pausa» cuando la máquina está en marcha pero `account.paused` es verdadero. Lleva al aviso correspondiente de Tu turno.

### Comportamientos globales

- **Sesión caducada:** cualquier 401 o 403 lleva a Login con `?next=` y vuelve a la misma ruta después de entrar.
- **Sin conexión:** franja discreta «Sin conexión. Mostrando lo último que cargó». Los datos ya cargados siguen visibles.
- **Confirmaciones:** después de una acción, toast abajo («Guardado», «Vetada», «Marcada como hecha»). Las acciones reversibles muestran «Deshacer» durante 5 s.
- **Refresco automático:** escena cada 15 s; Tu turno, Calendario y Pieza cada 30 s; Personas y Resultados cada 60 s; LinkedIn cada 5 min. No hace falta mostrar un indicador de recarga; sí «actualizado hace X» donde se indique.
- **Enlaces externos** (LinkedIn): se abren en otra pestaña con el icono ↗. Solo se muestran si la URL es https.
- **Accesibilidad:** «Saltar al contenido» al inicio; foco visible; el contraste de los tonos debe cumplir AA; respetar `prefers-reduced-motion`.

---

## 1. Oficina (inicio)

**Objetivo:** ver al equipo trabajando. Es el inicio y la vista «bonita»; casi no cambia.

**Se llega desde:** el logo, la navegación y el inicio de la PWA.

**Datos:**
- **Existe:** actividad por rol en `GET /api/v1/oficina/actividad` (estado, detalle y desde cuándo, por rol).
- **Existe:** la definición de equipos y roles en el frontend (`scene/roles.ts`).
- **Nuevo:** el resumen de Tu turno (contador y primer elemento).

### Estructura

- **Escritorio (≥ 1100 px):** la escena a la izquierda, ocupando el ancho disponible, y el panel lateral de 340 px a la derecha, fijo al hacer scroll.
- **Móvil:** la escena a todo el ancho (con scroll horizontal si no cabe, o escalada), la tira de equipos con scroll horizontal y el panel debajo.

### Bloques

**A. Barra de la escena**
- Título «PLANTA ABIERTA / Barrio AI».
- Botón alternable de luz: «☀ Luz de mañana» o «☾ Tarde en el estudio». Por defecto es tarde entre las 18:00 y las 6:00.
- Botón alternable de ambiente: «Pausar ambiente» o «Activar ambiente». Arranca pausado si el sistema pide menos movimiento.

**B. Escena (canvas pixel-art)**
- 16 personajes en sus puestos, con 4 estados visuales:
  - **Trabajando:** animación de lectura, monitor encendido y luz verde.
  - **En espera:** animación idle; solo estos dan paseos ambientales.
  - **En diseño:** figura atenuada e inmóvil con la etiqueta «en diseño».
  - **Sin dato:** figura quieta. Nunca se simula trabajo.
- **Interacción:** tocar un personaje abre su rol en el panel; tocar una zona abre su equipo. El equipo seleccionado se resalta en la escena.

**C. Acceso a Tu turno** (nuevo; solo si hay pendientes)
- Tarjeta flotante sobre la escena (esquina superior derecha) o primera tarjeta del panel.
- **Contenido:**
  - el contador («3 cosas dependen de ti»);
  - el título del elemento más urgente, por ejemplo «Responde: ¿aceptas proyectos de 3 meses?»;
  - el retrato del agente que lo pide.
- **Acción:** «Ver» lleva a Tu turno.
- Si hay un aviso crítico, la tarjeta usa el tono de error.

**D. Pie de la escena**
- Leyenda: Trabajando, En espera y En diseño, con su punto de color.
- «Actividad real · hace X». Mientras carga, «Leyendo actividad…»; si falla, «Actividad no disponible».

**E. Tira de equipos**
- 7 chips con el icono y el nombre de cada equipo. El seleccionado se marca.

**F. Panel lateral, modo equipo** (por defecto, Operación)
- Icono, la etiqueta «ESPACIO DEL EQUIPO», el número de equipo (01–07) y el badge «Nuevo» si aplica.
- Nombre, propósito, «N INTEGRANTES · LUGAR» y el resumen: «2 trabajando · 1 en espera · 0 en diseño · 1 sin datos».
- **Lista de miembros:** retrato, nombre, el detalle de lo que hace ahora (o su propósito si no hay detalle) y el badge de estado. Tocar un miembro abre su rol.

**G. Panel lateral, modo rol**
- Retrato grande, «AGENTE · EQUIPO» o «SERVICIO · EQUIPO», nombre y badge de estado.
- Si es un servicio: «Es un servicio de software, no un agente de IA…».
- **Misión.**
- **Estado real:** estado, detalle y desde cuándo. Si no hay datos: «Sin datos de actividad…».
- Si está en diseño, la nota correspondiente.
- **Opcional (nuevo):** «Lo último que hizo», con 3 elementos importantes filtrados por ese rol y el enlace «Ver en el Calendario».
- Botón «Ver su equipo · {equipo}».

### Estados

- **Cargando:** la escena se pinta con los personajes quietos y «Leyendo actividad…».
- **Error:** nota de error con «Reintentar» y «Mientras tanto los personajes quedan quietos: la oficina no simula trabajo».
- **Sin pendientes:** el bloque C no aparece.

### Equipos y roles (para diseñar los paneles)

| Equipo | Lugar en la escena | Roles |
|---|---|---|
| Estrategia y perfil | Los escritorios compartidos | Posicionamiento, Perfil |
| Observatorio | Junto a los ventanales | Investigador de referentes, Analista del barrio y resultados |
| Mesa editorial | La mesa larga | Director editorial, Copywriter A, Copywriter B |
| El barrio | El sofá y la mesa de centro | Lector comprador, Lector recomendador, Lector divulgador, Lector líder de opinión, Lector par profesional |
| Revisión | El rincón tranquilo | Editor verificador |
| Relaciones | La mesa de la cocina | Relaciones con la comunidad, Conversaciones e inbox |
| Operación | Junto a la puerta | Operador de cuenta (servicio) |

---

## 2. Tu turno

**Objetivo:** todo lo que solo Gustavo puede resolver, cada cosa lista para hacerse en uno o dos toques.

**Se llega desde:** la navegación (con contador), la tarjeta de la Oficina y las notificaciones push.

**Regla de entrada:** un elemento solo aparece si nadie más que Gustavo puede resolverlo. Lo informativo (una pieza bloqueada, invitaciones en pausa por límite) va al Calendario o a Personas, no aquí.

### Estructura

- **Cabecera:** «Tu turno» y un resumen, por ejemplo «2 avisos · 3 preguntas · 1 tarea».
- **Pestañas:**
  - **Pendiente** (por defecto).
  - **Lo que el equipo sabe de ti** (`/tu-turno/sabe`).
- **Pendiente** apila las secciones en orden de urgencia: **Avisos → Preguntas → Tareas**. Al final, plegado, «Hecho recientemente» con los últimos 7 días.
- **Escritorio:** una columna centrada de unos 760 px. Las tarjetas de tarea de perfil pueden usar dos columnas internas (antes y después).
- **Móvil:** una columna; los botones principales ocupan todo el ancho.

### Anatomía común de una tarjeta

| Parte | Contenido |
|---|---|
| Tipo | Icono y etiqueta: Aviso, Pregunta, Perfil o Conversación. |
| Quién lo pide | Retrato pixel y nombre del rol que lo genera (por ejemplo, Perfil o Analista del barrio). Los avisos del sistema usan el retrato del Operador de cuenta. |
| Título | En imperativo y concreto: «Reconecta LinkedIn», «Responde…», «Cambia tu titular». |
| Plazo | Si aplica: «antes del jueves 09:00», «caduca en 3 días». En rojo si quedan menos de 24 h. |
| Cuerpo | Específico de cada tipo (ver abajo). |
| Acciones | Una principal y una o dos secundarias. |
| Pie | «Creada hace X». |

### A. Avisos

| Aviso | Cuándo aparece | Cuerpo | Acciones | Datos |
|---|---|---|---|---|
| **LinkedIn caduca pronto** | `expiring_soon` y no caducado | «El permiso para publicar caduca el {fecha} (quedan {n} días). LinkedIn no deja renovarlo solo.» | **Reconectar LinkedIn**: navegación completa a `/api/v1/linkedin/oauth/start` | Existe: `linkedin/status` |
| **LinkedIn caducado** (crítico) | `expired` | «El acceso caducó y la publicación diaria está en pausa.» | **Reconectar LinkedIn** | Existe |
| **Acción incierta** (crítico) | Hay acciones en estado `uncertain` (una tarjeta por acción) | Qué se intentó: tipo, texto (o reacción, o persona), destino (post de {autor} o perfil) y hora. «El proveedor no confirmó si se aplicó. Comprueba en LinkedIn.» Con el enlace «Ver en LinkedIn». | **Sí, se aplicó** / **No se aplicó**. Ambas abren un modal con la nota obligatoria «Qué comprobaste». | Existe: `actions?state=uncertain` y `POST …/resolve` |
| **Máquina detenida** (crítico) | `control.paused` y `source = db` | Motivo, quién la paró y cuándo. | **Reanudar**, con un modal de nota opcional | Existe: `POST /api/v1/operador/control` |
| **Máquina detenida desde el servidor** | `control.paused` y `source = env` | «La parada viene del servidor (`OPERATOR_PAUSED=true`). No se puede levantar desde la app.» | Ninguna (informativa, pero solo Gustavo puede cambiarla) | Existe |
| **Cuenta en pausa** | `account.paused` | Nombre de la cuenta y motivo. | **Reanudar la cuenta** | Existe: `POST /api/v1/operador/accounts/<id>/pause` |

### B. Preguntas del equipo (nuevo)

Aquí Gustavo responde lo que los agentes necesitan saber de él. Las respuestas se guardan como memoria confirmada, que es lo que permite a los posts y comentarios contar experiencias reales.

**Campos de una pregunta:**

| Campo | Ejemplo |
|---|---|
| Quién pregunta | Retrato y nombre del rol: «Director editorial». |
| Pregunta | «¿Has liderado la migración de un monolito a microservicios en una startup?» |
| Para qué | «Para el post del jueves sobre arquitectura. Sin un caso real, el post se queda en opinión.» |
| Tipo de respuesta | Texto libre, sí/no (con detalle opcional), una opción de una lista, número o fecha. |
| Visibilidad sugerida | «Se puede contar en público» o «Solo para orientar al equipo». |
| Plazo | Opcional: «Útil antes del jueves 09:00». |

**Interacción:**
- **Campo de respuesta** según el tipo. En texto libre, un área de 3 líneas que crece.
- **Selector de visibilidad**, con la sugerencia preseleccionada:
  - **Público:** el equipo puede mencionarlo en posts y comentarios.
  - **Privado:** solo orienta las decisiones y nunca aparece en un texto público.
- **Acciones:**
  - **Responder** (principal).
  - **Más tarde:** la pospone 3 días y sale del contador.
  - **No quiero compartir esto:** se cierra y la pregunta no vuelve.
- **Después de responder:** toast «Guardado. El equipo ya puede usarlo», con «Deshacer».
- **Pregunta caducada** (pasó la pieza para la que era): pasa a tono neutro con «Ya no es urgente, pero sigue siendo útil». No cuenta como pendiente.

### C. Tareas

**C1. Tarea de perfil (nuevo)**

| Campo | Contenido |
|---|---|
| Sección del perfil | Titular, Acerca de, Experiencia ({puesto}), Destacados, Foto, Banner o Habilidades. |
| Ahora | El texto actual, leído del perfil, con su fecha de lectura. Puede no estar disponible: «No pudimos leer tu perfil actual». |
| Propuesto | El texto nuevo completo, con el botón **Copiar**. |
| Límite | Contador de caracteres frente al límite de LinkedIn (titular 220, Acerca de 2.600). |
| Por qué | 2 líneas, más «Ver el razonamiento completo» (plegable: dirección de posicionamiento aceptada, lector al que apunta y evidencia). |
| Cómo hacerlo | Pasos numerados: «1. Abre tu perfil · 2. Toca el lápiz junto a tu nombre · 3. Pega el titular · 4. Guarda». Con el enlace «Abrir mi perfil en LinkedIn». |

- **Escritorio:** «Ahora» y «Propuesto» lado a lado. **Móvil:** uno debajo del otro, con «Propuesto» primero.
- **Acciones:**
  - **Hecho:** pasa a «Aplicado, pendiente de comprobar».
  - **Lo cambié con otro texto:** abre un campo para pegar lo que se usó realmente.
  - **No lo haré:** pide un motivo obligatorio.
- **Estados de la tarea:** Pendiente → Aplicado, pendiente de comprobar → Comprobado (el equipo releyó el perfil). También puede quedar Rechazada.

**C2. Conversación que te toca (nuevo; requiere leer el inbox)**

| Campo | Contenido |
|---|---|
| Persona | Iniciales o foto, nombre (enlace a su ficha en Personas), titular, rol del barrio y modalidad. |
| Qué pasó | «Te escribió», «Respondió a tu comentario en el post de {autor}», «Aceptó tu invitación» o «Te mencionó». |
| Resumen del hilo | 3 o 4 líneas del analista. |
| Último mensaje | Texto literal, con fecha. |
| Por qué importa | «Pregunta por disponibilidad para un proyecto de IA: posible oportunidad ProjectApp.» |
| Borrador sugerido | Texto editable, con **Copiar**. Gustavo responde él mismo en LinkedIn: la app nunca envía mensajes. |

- **Acciones:**
  - **Abrir en LinkedIn:** enlace directo al hilo (principal).
  - **Copiar borrador.**
  - **Hecho, respondí.**
  - **No responder:** motivo opcional.
  - **Marcar como oportunidad:** abre el formulario de oportunidad de Personas.

### D. Hecho recientemente (plegado)

- Lista de lo resuelto en los últimos 7 días: tipo, título, cuándo y cómo se cerró (Respondida, Hecho, Rechazada, Reconectado…).

### Pestaña «Lo que el equipo sabe de ti»

**Existe en parte:** `GET /api/v1/memory`, `POST /api/v1/memory/proposals` y `POST /api/v1/memory/<id>/confirm`. **Nuevo:** retirar un dato y la visibilidad pública o privada por dato.

- **Lista de datos confirmados.** Cada dato muestra:
  - el tema (la pregunta o la clave), la respuesta, el badge Público o Privado y la fecha;
  - de dónde vino: «Respondiste al Director editorial» o «Lo añadiste tú».
- **Acciones por dato:**
  - **Editar:** crea una versión nueva; se muestra «v2».
  - **Retirar:** con confirmación; el equipo deja de usarlo.
- **Botón «Añadir algo que quieras que sepan»:** un campo de texto libre, la visibilidad y Guardar. Se confirma directamente, porque lo escribe Gustavo.
- **Búsqueda simple** por texto, si hay más de 20 datos.
- **Vacío:** «Aún no hay nada confirmado. Nadie inventará tus experiencias, clientes ni servicios: responde las preguntas del equipo para que puedan usarlas».

### Estados de la vista

- **Nada pendiente:** ilustración (personaje idle) con «Nada depende de ti hoy», el resumen del día («Hoy el equipo publicó 1 post, comentó en 6 y siguió a 4 personas») y el enlace al Calendario.
- **Cargando:** esqueleto de 3 tarjetas.
- **Error en una sección:** solo esa sección muestra el error con «Reintentar»; las demás siguen funcionando.

---

## 3. Calendario

**Objetivo:** ver día a día las tareas y las acciones importantes: lo que hizo el equipo, lo que tiene programado y lo que te toca a ti. Desde aquí se puede vetar lo que aún no salió.

Sustituye a la vista Actividad. El calendario es la vista principal, cada día abre su detalle y el modo **Lista** muestra lo mismo como una línea de tiempo continua.

**Se llega desde:**
- la navegación;
- las notificaciones de piezas;
- la ficha de una persona (su acción abierta);
- Resultados (al tocar un post);
- el resumen del día en Tu turno;
- «Lo último que hizo» de un rol en la Oficina.

**Datos:**
- **Existe:**
  - `GET /api/v1/editorial/calendar?desde=&dias=`: piezas por día.
  - `GET /api/v1/operador/actions`: acciones; paginado y sin filtro de fechas.
  - `GET /api/v1/operador/feed`: eventos del operador, como pausas y reanudaciones.
  - `GET /api/v1/red/contacts`: fechas de seguir, invitar y conectar.
  - `GET /api/v1/linkedin/status`: `expires_at`.
- **Nuevo:**
  - un endpoint que devuelva, por día, los eventos importantes y los conteos (forma propuesta al final de esta sección);
  - los plazos de Tu turno;
  - las fechas de las oportunidades (reuniones y siguientes acciones).

### Qué aparece en el calendario

Cada evento pertenece a una **capa**, con su color, y cada capa se puede ocultar. En la cuadrícula solo se ven los eventos **importantes**. Lo menudo (comentarios, reacciones, seguimientos e invitaciones enviadas) aparece como conteo en el resumen del día y completo en «Ver todo lo del día».

| Capa | Color sugerido | Eventos importantes | Datos |
|---|---|---|---|
| **Tuyo** | Naranja (foco) | Plazos de preguntas y tareas de Tu turno. Reuniones y siguientes acciones de oportunidades. Día en que caduca LinkedIn. Tareas que marcaste como hechas. | Nuevo, salvo la caducidad de LinkedIn (existe) |
| **Publicaciones** | Verde | Pieza publicada (hora e impresiones), programada (hora), preparándose, día sin pieza, bloqueada, vetada, fallida o incierta. | Existe |
| **Red** | Azul | Conexiones nuevas que encajan (agrupadas: «3 conexiones nuevas»). Invitaciones recibidas y aceptadas. Invitaciones previstas: personas seguidas cuyo plazo de 48 h vence ese día, como estimación sujeta a los topes. | Existe (fechas de contactos); la previsión se calcula |
| **Conversaciones** | Latón | Conversación nueva con alguien que encaja. Oportunidad nueva o que cambia de etapa. | Nuevo |
| **Sistema** | Óxido | Parada total y reanudación. Cuenta en pausa. Acción incierta o fallida. LinkedIn caducado. | Existe |

**Prioridad**, cuando no caben todos en una celda: Tuyo > Sistema > Publicaciones > Conversaciones > Red.

### Estructura

- **Cabecera:**
  - el título «Calendario» y el rango visible («Noviembre 2026» o «3–9 nov 2026»);
  - la navegación «←», «Hoy» y «→»;
  - el selector de vista: **Mes · Semana · Lista**;
  - los chips de capa, alternables y con su color, todos activos por defecto.
- **URL:** `/calendario?vista=mes&fecha=2026-11-06&capas=tuyo,publicaciones`, para volver al mismo sitio.
- **Escritorio (≥ 1100 px):**
  - el calendario a la izquierda, ocupando el ancho disponible;
  - el **panel del día** a la derecha (unos 380 px), con el día seleccionado (hoy por defecto).
- **Móvil:**
  - **Semana compacta por defecto:** una tira de 7 días arriba, con un punto de color por cada capa que tenga eventos, y debajo el detalle del día seleccionado. Deslizar la tira cambia de semana.
  - **Mes:** una cuadrícula compacta con solo puntos, sin texto. Tocar un día lo abre.
  - **Lista:** días seguidos con scroll.
- **Zona horaria:** los días se calculan en la del calendario editorial (`America/Bogota`), no en la del dispositivo. Si el dispositivo está en otra zona, la cabecera dice «Horas de Bogotá».

### Vista Mes

- Cuadrícula de lunes a domingo, con 5 o 6 filas. Los días de otro mes van atenuados y hoy va resaltado.
- **Celda:**
  - el número del día;
  - hasta 3 eventos como chips: icono, hora si la tiene y texto corto. Por ejemplo, «09:00 Post: IA sin rehacer el producto», «Reunión con Ana» o «3 conexiones nuevas».
  - «+N más» si no caben;
  - un punto naranja si ese día hay algo tuyo pendiente;
  - en los días pasados sin publicación, una marca sutil «sin post».
- **Interacción:** tocar la celda selecciona el día y muestra su panel. Tocar un chip abre su destino directamente: la pieza, la persona o Tu turno.

### Vista Semana

- 7 columnas.
- **Franja «todo el día»** arriba, para lo que no tiene hora: plazos, conexiones agrupadas y conteos.
- **Eje horario** debajo, acotado a la ventana de actividad (por ejemplo, 07:00–21:00), con los eventos que tienen hora: la publicación, las acciones importantes ejecutadas y las reuniones.
- Una línea «ahora» en el día de hoy.

### Vista Lista

Es la antigua línea de tiempo de Actividad.

- **Arriba, el bloque «Próximo»:** la pieza programada y lo que espera su turno (ver más abajo).
- **Debajo, los días** del más reciente al más antiguo (Hoy, Ayer, «Martes 4 de noviembre»…), con **todo** lo que pasó, no solo lo importante.
- **Filtros por tipo:** Todo · Publicaciones · Comentarios · Reacciones · Red.
- **Interruptor** «Mostrar lo que no salió» (vetadas, descartadas, caducadas y sustituidas), apagado por defecto. Las fallidas y las inciertas se ven siempre.
- **Paginación:** «Cargar más» al final.

### Panel del día

Las secciones aparecen solo si tienen contenido:

1. **Cabecera:** «Jueves 6 de noviembre», con el badge Hoy, Pasado o Programado.
2. **Resumen** (hoy y días pasados), en una línea: «1 post · 6 comentarios · 3 reacciones · 4 seguidos · 2 invitaciones · 1 conexión nueva que encaja». Cada número se puede tocar y filtra «Ver todo lo del día».
3. **Tu parte:**
   - los elementos de Tu turno con plazo ese día y las reuniones, con el botón «Ir a Tu turno»;
   - lo que resolviste ese día, marcado con ✓.
4. **Publicación del día:** la tarjeta de la pieza.
   - Estado, hora, tesis y las 3 primeras líneas.
   - Si está publicada: impresiones y resultado.
   - Si aún no salió: **Vetar**.
   - «Ver cómo se escribió».
   - **Sin pieza en un día pasado:** «Sin publicación», con el motivo si el director decidió no publicar.
   - **Sin pieza en un día futuro:** «Hueco libre. El equipo prepara cada pieza {lead_hours} h antes de su hora».
5. **Programado** (hoy y días futuros):
   - las acciones que esperan la ventana horaria o el espaciado, con **Vetar**;
   - las invitaciones previstas, como estimación, con la lista de personas.
6. **Lo importante del día:** los eventos importantes de las capas visibles, en orden horario, con el componente de elemento de la línea de tiempo.
7. **Ver todo lo del día:** despliega la línea de tiempo completa de ese día, con los filtros por tipo.

### Bloque «Próximo»

Está arriba en la vista Lista, y en el panel del día de hoy como «Publicación del día» y «Programado».

**Pieza programada:**
- Fecha y hora («Hoy a las 09:00»), con cuenta atrás: «sale en 5 h 20 min».
- Badge de estado: Programada, Preparándose (con su etapa) o Publicándose.
- Tesis en negrita y las 3 primeras líneas del texto final, con «Ver todo».
- Pilar, modalidad y lector principal.
- **Vetar:** un modal con nota obligatoria. «La pieza no saldrá y ese día quedará sin publicación». Existe: `POST /api/v1/operador/actions/<id>/reject`.
- «Ver cómo se escribió» lleva al detalle de la pieza.

**En cola:** acciones aprobadas que esperan la ventana o el espaciado. Una línea por acción (tipo, destino y «saldrá cuando abra la ventana, a las 08:00»), con **Vetar**. Vetar una acción de red descarta a esa persona para siempre, y el modal lo avisa.

**Sin pieza programada:** «No hay pieza programada para los próximos días», con el botón secundario **Preparar la siguiente pieza**.
- Abre un modal de confirmación: «Tiene coste: cada etapa llama a Claude y gasta del presupuesto editorial».
- Existe: `POST /api/v1/editorial/plan`.

### Elementos de la línea de tiempo

Se usan en «Lo importante del día», en «Ver todo lo del día» y en la vista Lista.

Todos comparten: icono del tipo, hora, la frase principal, el badge de estado (si no es un éxito normal) y, opcionalmente, el retrato del rol que lo hizo.

| Tipo | ¿Importante? | Frase principal | Contenido | Al tocar |
|---|---|---|---|---|
| Publicación | Sí | «Publicaste: {tesis}» | Primera línea del texto, pilar, impresiones si las hay y enlace ↗ al post | Detalle de la pieza |
| Día sin pieza | Sí | «Ese día no hubo publicación» | Motivo del director (`skip_reason`) | Detalle de la pieza |
| Pieza bloqueada | Sí | «El verificador bloqueó la pieza» | El primer motivo del bloqueo | Detalle de la pieza |
| Pieza descartada | Sí | «La política no aprobó la pieza» | Motivos | Detalle de la pieza |
| Conexión nueva que encaja | Sí (agrupada) | «{persona} aceptó tu invitación» | Titular y chip del rol | Ficha en Personas |
| Aceptar | Sí | «Aceptaste la invitación de {persona}» | Titular y chip del rol | Ficha en Personas |
| Conversación nueva | Sí | «{persona} te escribió» | Resumen de una línea | Ficha en Personas |
| Oportunidad | Sí | «Oportunidad con {persona}: {etapa}» | Modalidad y siguiente paso | Ficha en Personas |
| Parada o reanudación | Sí | «Detuviste la máquina» o «Se reanudó la máquina» | Motivo y quién | Ajustes → Máquina |
| Comentario | No | «Comentaste en el post de {autor}» | Extracto del post original (2 líneas, en gris), tu comentario completo, enlace ↗ y «Por qué» plegable (`rationale`) | Se expande en el sitio |
| Reacción | No | «Reaccionaste {reacción} al post de {autor}» | Extracto del post y enlace ↗ | Se expande en el sitio |
| Seguir | No | «Seguiste a {persona}» | Titular y chip del rol | Ficha en Personas |
| Invitación | No | «Invitaste a {persona} (sin nota)» | Titular y chip del rol | Ficha en Personas |

Una acción incierta o fallida pasa a ser importante, sea del tipo que sea.

**Estado de cada elemento** (los estados de acción traducidos a lo que ve Gustavo):

| Estado técnico | Cómo se muestra |
|---|---|
| `confirmed` | Normal, sin badge. Es el éxito. |
| `executing`, `sent` | Badge «En curso». |
| `uncertain` | Badge rojo «Incierta», con «Resuélvela en Tu turno →». |
| `failed` | Badge rojo «Fallida» y la nota de ejecución. |
| `rejected` | Badge gris «Vetada por ti», con tu nota. |
| `discarded` | Badge gris «Descartada por la política», con el motivo. |
| `expired`, `superseded` | Badge gris «Caducada» o «Sustituida». |
| `proposed`, `approved` | No aparecen como hechos: se ven en «Próximo / En cola» o en «Programado» del día. |

### Detalle de una pieza (`/calendario/pieza/:id`)

Mantiene todo el contenido de la página Pieza actual (campos completos en [`VISTAS.md`](VISTAS.md), sección 6), reordenado y aligerado.

1. **Cabecera:** «← Calendario» (vuelve al día de la pieza), «Pieza del {día}», el badge de estado y la hora de salida.
2. **Resultado** (si está publicada):
   - Tabla de cortes a 24 h, 72 h y 7 días: impresiones, reacciones, comentarios, republicaciones e interacción % (nuevo).
   - Quién comentó, con chips por rol del barrio (nuevo).
   - Enlace ↗ al post.
3. **Veto** (si aún no salió): explicación de la autonomía y **Vetar**.
4. **Texto final:** completo, con **Copiar** y el número de caracteres. Aviso: «Se publica tal cual, en inglés».
5. **Cómo se escribió:** secciones plegadas, todas cerradas por defecto.
   - **Brief:** lector, modalidad, pilar, tesis, enfoque (sin enlace al curso), formato, valor, criterio de éxito, qué evitar, evidencia y por qué.
   - **Variantes A y B:** lado a lado en escritorio y en pestañas en móvil, con «Elegida».
   - **Panel de lectores:** 5 lectores × 2 variantes, con fortalezas y objeciones.
   - **Selección:** decisión, razonamiento y objeciones resueltas y conservadas.
   - **Verificador:** veredicto, motivos, hallazgos y afirmaciones comprobadas.
   - **Fuentes y coste:** citas como texto, señales de terceros y coste por etapa.
- **Preparándose:** muestra la etapa actual como un indicador de 5 pasos (Director → Redactores → Lectores → Selección → Verificador).

Redirecciones: `/editorial/:id` y `/contenido/:id` llevan a `/calendario/pieza/:id`; `/contenido`, `/acciones` y `/maquina` llevan a `/calendario`.

### Endpoint nuevo (forma propuesta)

`GET /api/v1/calendario?desde=2026-11-01&hasta=2026-11-30`

```json
{
  "timezone": "America/Bogota",
  "today": "2026-11-06",
  "days": [
    {
      "date": "2026-11-06",
      "counts": { "comments": 6, "reactions": 3, "follows": 4, "invites": 2, "accepts": 0, "connections_fit": 1 },
      "events": [
        {
          "id": "…",
          "layer": "tuyo | publicaciones | red | conversaciones | sistema",
          "kind": "piece_published | piece_scheduled | piece_skipped | piece_blocked | connection_fit | invite_expected | deadline | meeting | machine_paused | action_uncertain | …",
          "at": "ISO | null",
          "title": "…",
          "state": "…",
          "important": true,
          "link": "/calendario/pieza/… | /personas/… | /tu-turno"
        }
      ]
    }
  ]
}
```

Mientras no exista, el frontend puede montar las capas Publicaciones (calendario editorial), Sistema (feed) y Red (fechas de los contactos), y dejar Tuyo y Conversaciones con el estado «aún no disponible».

### Estados

- **Cargando:** esqueleto de la cuadrícula o de la tira semanal.
- **Mes sin eventos:** «No hay nada registrado en este mes».
- **Futuro lejano** (más de 15 días): «Todavía no hay nada programado tan lejos».
- **Capa sin datos todavía** (fase 1): su chip aparece desactivado, con «Aún no disponible».
- **Error:** con «Reintentar», sin perder la cuadrícula.

---

## 4. Resultados

**Objetivo:** saber si vamos bien, en el orden negocio → audiencia → contenido → equipo.

**Se llega desde:** la navegación.

### Estructura

- **Cabecera:** «Resultados» y dos controles.
  - **Periodo:** 7 días, 28 días (por defecto) o 90 días. Todo se compara con el periodo anterior de igual duración.
  - **Modalidad:** Todo, Startups (personal) o ProjectApp. Afecta a las secciones 1 y 2; el contenido y el equipo no se separan por modalidad.
  - Indicador «Periodo en curso: datos hasta hoy {hora}».
- **4 secciones** con su título y su pregunta, por ejemplo «1 · ¿Genera negocio?».
- **Escritorio:** las fichas de KPI en una rejilla de 4 columnas; los gráficos a 2 columnas o a ancho completo.
- **Móvil:** fichas en 2 columnas y gráficos a ancho completo. Las tablas pasan a lista de tarjetas.

### Ficha de KPI (componente)

| Parte | Contenido |
|---|---|
| Nombre | «Conversaciones pertinentes». |
| Valor | Número grande. |
| Variación | ▲ o ▼, con el valor absoluto o el %, frente al periodo anterior. Verde o rojo según convenga; gris si no hay comparación válida. |
| Minigráfico | Serie del periodo (opcional por ficha). |
| Definición | Icono ⓘ con la definición y la fórmula exacta. |
| Sin dato | Guion largo y el motivo: «Disponible cuando conectemos el inbox». **No mostrar 0.** |

### Sección 1 · ¿Genera negocio? (nuevo en su totalidad)

- **Fichas:**
  - Conversaciones pertinentes (abiertas en el periodo).
  - Oportunidades abiertas.
  - Reuniones.
  - Propuestas enviadas.
  - Acuerdos.
- **Embudo de oportunidades:** barras horizontales por etapa (conversación → necesidad → cualificada → reunión → propuesta → acuerdo), con el número de cada etapa y la conversión entre etapas. «Cerrada sin acuerdo» aparece aparte.
- **Reparto por modalidad:** barra apilada Startups / ProjectApp frente al objetivo 60/40, marcado con una línea.
- **Inbound:** ficha con las personas que encajan y escribieron o invitaron sin que las buscáramos.
- **Lista «Oportunidades activas»:** las 5 más recientes, cada una con persona, empresa, modalidad, etapa y siguiente paso. Lleva a la ficha en Personas.

### Sección 2 · ¿Llegamos a la gente correcta?

| Elemento | Definición | Datos |
|---|---|---|
| Seguidores | Total y crecimiento neto del periodo | Nuevo |
| Conexiones | Total y crecimiento neto | Nuevo |
| Visitas al perfil | Visitas en el periodo | Nuevo, por comprobar si se puede obtener |
| Conexiones nuevas que encajan | Contactos que pasaron a `connected` en el periodo y tienen `fit = true` | Existe: `red/contacts` |
| Composición por rol | Barras: comprador, par, recomendador, divulgador, líder y aliado entre las conexiones nuevas que encajan | Existe: `classification.role` |
| Tasa de aceptación | Conectados / (conectados + cerrados), sobre las invitaciones resueltas en el periodo | Existe: etapas e historial |
| Embudo de la red | Por clasificar → encaja → seguido → invitado → conectado, con descartados aparte | Existe: `red/summary.stages` |
| Personas recurrentes | Quienes interactuaron 2 o más veces en el periodo, con un top 5 enlazado a Personas | Nuevo |

### Sección 3 · ¿El contenido aporta?

- **Fichas:**
  - Impresiones (mediana por post, a los 7 días).
  - Interacción % = (reacciones + comentarios + republicaciones) / impresiones.
  - Comentarios con sustancia.
  - Constancia: días publicados frente a días previstos.
- **Gráfico:** barras de impresiones por post a lo largo del periodo, con una línea para la mediana de las 4 semanas anteriores. Cada barra lleva al detalle de la pieza.
- **Destacado «Mejor post del periodo»:** primera línea del texto, fecha, pilar, impresiones e interacción. Lleva al detalle.
- **Comparación por pilar:** barras pequeñas con la interacción media de Del negocio al producto, IA aplicada y Arquitectura y entrega.
- **Tabla «Posts del periodo»:**
  - Columnas: fecha, primera línea, pilar, impresiones a 24 h, impresiones a 7 días, reacciones, comentarios, republicaciones, interacción % y quién comentó (chips por rol del barrio).
  - Se puede ordenar por cualquier columna.
  - En móvil pasa a tarjetas.
- **Datos:**
  - Lista de posts publicados: existe (`editorial/calendar` y `pieces`).
  - Cortes a 24 h, 72 h y 7 días, reacciones, comentarios y republicaciones: nuevo. Hoy solo hay un corte de impresiones tomado al publicar, así que no es fiable.

### Sección 4 · ¿El equipo trabaja bien? (compacta)

- Una fila de fichas pequeñas:
  - Comentarios publicados y cuántos recibieron respuesta.
  - Seguidos, invitados y aceptados.
  - Piezas publicadas, bloqueadas y vetadas.
  - **Gasto de IA:** «X USD de Y USD», del día en la fase 1 y del mes cuando exista.
- **Datos:** los conteos existen en `operador/actions` (hace falta un endpoint que agregue); el gasto diario existe en el overview y en `red/summary`; el gasto mensual es nuevo.

### Reglas

- Nunca sumar alcance de posts distintos como personas únicas.
- Comparar posts con la misma edad: 24 h con 24 h y 7 días con 7 días.
- Si falta el denominador o es cero, la ficha muestra «sin dato», no 0 %.
- Las variaciones solo se calculan entre periodos completos y comparables. Si el periodo anterior no tiene datos, la variación va en gris: «sin comparación».

### Estados

- **Fase 1:** las fichas sin datos usan el estado «aún no disponible», que debe verse intencional y no roto. La sección 1 completa puede mostrar un único bloque: «Mediremos oportunidades cuando registres la primera o conectemos el inbox», con el botón «Registrar una oportunidad».
- **Cargando:** esqueleto de las fichas.
- **Error:** por sección.

---

## 5. Personas

**Objetivo:** con quién estamos hablando y cuál es el siguiente paso con cada persona.

**Se llega desde:** la navegación, las tarjetas de conversación de Tu turno, el Calendario (al tocar a una persona) y Resultados (oportunidades y recurrentes).

### Estructura

- **Pestañas:** **Barrio** (contactos, por defecto) · **Oportunidades** · **Referentes**.
- **Escritorio:** la lista a la izquierda (unos 420 px) y la ficha a la derecha. La URL cambia a `/personas/:id`.
- **Móvil:** la lista a pantalla completa; la ficha abre en otra pantalla, con «← Personas».

### Pestaña Barrio

**Datos:** existen `GET /api/v1/red/contacts?stage=&source=`, `GET /api/v1/red/contacts/<id>` y `GET /api/v1/red/summary`. **Nuevo:** las etapas «En conversación» y «Oportunidad», las notas y la búsqueda por nombre.

**Avisos arriba** (si aplican):
- «La red está apagada en el servidor» (`enabled = false`).
- «Invitaciones en pausa hasta {fecha}: LinkedIn las limitó» (`invites_blocked`), con el motivo.

**Embudo como filtro:** chips con recuento, en este orden:
- Por clasificar, Encaja, Seguido, Invitado, Conectado, En conversación, Oportunidad.
- Después, separados: Te invitó, Cerrado, Descartado.
- Tocar un chip filtra la lista; «Todas» lo quita.

**Más filtros:** búsqueda por nombre; rol del barrio; modalidad; origen (comentó en un post, búsqueda, te invitó o añadido a mano).

**Orden:** actividad más reciente primero.

**Fila de la lista:**

| Parte | Contenido |
|---|---|
| Avatar | Iniciales (hoy no hay foto en los datos). |
| Nombre | `display_name`. |
| Titular | Una línea, truncada. |
| Etapa | Badge. |
| Clasificación | Chip del rol y chip de la modalidad. «Sin clasificar todavía» si no hay. |
| Origen | Breve: «Comentó en un post de {referente}», «Búsqueda: {query}» o «Te invitó». |
| Última actividad | «Hace X» y el último evento: «Seguido hace 2 días». |
| Te toca | Punto o badge «Te toca» si tiene un elemento en Tu turno. |

**Ficha de la persona:**

1. **Cabecera:**
   - Nombre (enlace ↗ al perfil de LinkedIn), titular, ubicación, grado (1.er, 2.º, 3.er o fuera de tu red) y «Lo sigues» si aplica.
   - Botón **Abrir en LinkedIn**.
2. **Recorrido:** línea de etapas horizontal (vertical en móvil): Descubierto → Seguido → Invitado → Conectado → En conversación → Oportunidad.
   - Cada paso alcanzado lleva su fecha (`discovered_at`, `followed_at`, `invited_at` y `connected_at`).
   - Las ramas Cerrado y Descartado se muestran como final alternativo.
3. **Siguiente paso:** una frase, y de quién depende.
   - Del equipo: «El equipo la invitará a partir del {followed_at + 48 h}», «Esperando que acepte la invitación (enviada hace 3 días)» o «Se aceptará su invitación».
   - De Gustavo: «Te toca: responder su mensaje», con enlace a Tu turno.
   - Si hay una acción abierta: el tipo, el estado y el enlace al Calendario.
4. **Por qué encaja:** rol, modalidad, afinidad, el motivo (texto del modelo) y la confianza en %. Debajo, «Clasificada el {fecha}».
5. **De dónde salió:**
   - Comentó en un post: el referente, un extracto del comentario y el enlace al post.
   - Búsqueda: la consulta usada.
   - Te invitó: el mensaje de la invitación, si lo hay.
6. **Conversación** (nuevo): el resumen del analista, los últimos 3 mensajes con fecha y autor, y «Abrir en LinkedIn».
7. **Oportunidad** (nuevo; solo si la persona la tiene): ver la pestaña Oportunidades.
8. **Notas** (nuevo): notas libres de Gustavo con fecha, y «Añadir nota».
9. **Historial completo:** todos los eventos, del más reciente al más antiguo, cada uno con la etiqueta del evento, la fecha y el detalle.

**Acciones de la ficha:**
- **Marcar como oportunidad** (nuevo): abre el formulario de oportunidad.
- **Descartar:** con nota obligatoria. Solo en Por clasificar, Encaja, Seguido y Te invitó. Avisa de que la persona no volverá a proponerse. Existe: `POST /red/contacts/<id>/discard`.
- **Añadir nota** (nuevo).

**Estados:**
- **Vacío:** «Aún no hay personas. El equipo empieza a descubrir cuando lee los comentarios de los referentes».
- **Filtro sin resultados:** «Nadie en «{etapa}» ahora mismo».
- **Cargando:** esqueleto de filas.
- **Error:** con «Reintentar».

### Pestaña Oportunidades (nuevo)

- **Escritorio:** tablero por etapas en columnas (Conversación, Necesidad identificada, Cualificada, Reunión, Propuesta, Acuerdo), con «Cerradas sin acuerdo» plegada.
- **Móvil:** lista agrupada por etapa.
- **Tarjeta:** persona, empresa, badge de modalidad, siguiente acción con su fecha y los días que lleva en esa etapa.
- **Mover de etapa:** arrastrar en escritorio, o el selector «Etapa» dentro de la tarjeta (obligatorio en móvil).
- **Formulario «Nueva oportunidad / Editar»:**

| Campo | Tipo | Obligatorio |
|---|---|---|
| Persona | Buscador de Personas, o «Alguien fuera de la red» con nombre y empresa | Sí |
| Modalidad | Startups (personal), ProjectApp o Por clasificar | Sí |
| Canal | LinkedIn, email, llamada, evento u otro | Sí |
| Etapa | Las 7 etapas | Sí |
| Necesidad | Texto corto | No |
| Presupuesto / compensación | Texto o rango | No |
| Dedicación | Texto | No |
| Cómo llegó | Citó un post o el perfil, lo dijo la persona, se infiere o se desconoce | Sí |
| Siguiente acción y fecha | Texto y fecha | No |
| Notas | Texto | No |

### Pestaña Referentes

**Datos:** existen `GET /api/v1/operador/referents?account=`, `POST /api/v1/operador/referents` y `POST /api/v1/operador/observe`. **Nuevo:** desactivar y quitar referentes.

- **Lista:** nombre (con enlace ↗ al perfil), motivo, badge Activo o Inactivo, «Observado hace X» o «Aún sin observar».
- **Nuevo en la lista:** cuántas personas del barrio salieron de sus posts.
- **Botón «Añadir referente»:** abre un modal con la URL del perfil (validada como `linkedin.com/in/…`, con error en el propio campo) y el motivo, obligatorio.
- **Botón «Observar ahora»:** pone en cola una lectura y lo confirma con «Observación encolada. Los posts nuevos aparecerán en unos minutos».
- **Por referente (nuevo):** Desactivar o reactivar, y Quitar con confirmación.
- **Selector de cuenta:** solo si hay más de una.

---

## 6. Ajustes

**Objetivo:** conexiones, este dispositivo y los controles de la máquina que rara vez se tocan.

**Estructura:**
- **Escritorio:** un subíndice a la izquierda con anclas a cada sección, y las secciones a la derecha.
- **Móvil:** secciones apiladas, con las menos usadas plegadas.

### 6.1 Máquina

**Parada total** (existe: `overview.control` y `POST /operador/control`)
- **En marcha:** «La máquina está en marcha. Observa, redacta y actúa dentro de los topes», con el botón rojo **PARADA TOTAL**.
  - Abre un modal con el motivo obligatorio: «Se detiene todo el ciclo y ninguna acción se ejecuta hasta que la reanudes».
- **Detenida:** motivo, origen (desde la app o desde el servidor), quién y cuándo, con el botón **REANUDAR** y su modal de nota opcional.
- **Detenida desde el servidor:** el botón queda deshabilitado, con la explicación de `OPERATOR_PAUSED`.

**Cuenta de LinkedIn (Unipile)** (existe)
- Nombre de la cuenta y estado de conexión: Conectada, Sin comprobar o Token caducado.
- Badges En pausa y Bloqueada, y «Comprobada hace X».
- **Pausar solo esta cuenta**, con motivo obligatorio, o **Reanudar la cuenta**.

### 6.2 Autonomía y límites (plegado por defecto)

- **Modo por capacidad**, en solo lectura (se configura en el servidor):

| Capacidad | Modo |
|---|---|
| Comentarios | Badge: Auto, Aprobación o Apagado |
| Reacciones | ídem |
| Publicación diaria | ídem |
| Seguir | ídem |
| Invitar sin nota | ídem |
| Aceptar invitaciones | ídem |

- Debajo: «El equipo actúa solo en modo Auto. Puedes vetar lo programado desde el Calendario».
- **Ventana horaria:** horario, zona, abierta o cerrada ahora, y el espaciado mínimo entre acciones.
- **Topes de hoy y de la semana:** un medidor por capacidad (usados y tope), en verde, ámbar desde el 80 % y rojo al 100 %.
- **Lecturas de la red** frente a sus topes: comentarios, búsquedas, perfiles y sincronizaciones.
- **Datos:** existen `overview.window`, `overview.accounts[].capacity` y `red/summary`. El modo por capacidad hoy solo existe para la red; para el resto es nuevo.

### 6.3 Gasto de IA

- Una línea por presupuesto: General (comentarios), Editorial y Red, cada una con «X USD de Y USD hoy» y un medidor.
- Total del mes: nuevo.

### 6.4 LinkedIn oficial (publicación)

Igual que hoy (existe: `GET /api/v1/linkedin/status`):
- **Mensaje al volver de LinkedIn**, que se puede descartar: éxito o uno de los 7 motivos de error (sesión, permiso, state, denegado, code, scope y canje).
- **Estado:** Conectado, Caduca pronto, Caducado o Sin conectar.
- **Miembro, caducidad y permisos:** nombre y URN, la fecha de caducidad con los días que quedan y los permisos concedidos.
- **Avisos:**
  - caduca pronto;
  - caducado;
  - cuenta en pausa;
  - publicación real desactivada (`LIVE_LINKEDIN_OFFICIAL=false`);
  - falta configuración en el servidor;
  - tu usuario no tiene permiso.
- **Versión de la API** y el botón **Conectar** o **Reconectar LinkedIn**.

### 6.5 Notificaciones en este dispositivo

Igual que hoy:
- Pasos para iPhone, resaltados si hay que instalar la app.
- Aviso si el navegador no las admite.
- Estado: Activadas, Bloqueadas, Desactivadas o Comprobando.
- **Activar**, **Probar notificación** y **Desactivar**, con su confirmación.
- **Opcional (nuevo):** interruptores por tipo de notificación (ver [Notificaciones push](#notificaciones-push)).

### 6.6 Lo que el equipo sabe de ti

- Acceso directo a la pestaña de Tu turno, con el número de datos confirmados.

### 6.7 Sesión y Acerca de

- «Has entrado como {usuario}» y **Cerrar sesión**, con la nota «no desactiva las notificaciones de este dispositivo».
- Versión de la app y crédito del arte: LimeZu · Modern Interiors.

---

## 7. Login

Sin cambios funcionales; solo el estilo nuevo.

- **Contenido:** icono, «BARRIO AI · OFICINA», «Entrar», «Usa tu usuario y contraseña de Django», los campos Usuario y Contraseña, y el botón **Entrar** («Entrando…» mientras envía).
- **Errores:**
  - credenciales;
  - sin conexión;
  - «Demasiados intentos», cuando el servidor responde 429: «Espera unos minutos».
- **Estado inicial:** pantalla completa «Comprobando sesión…».

---

## Notificaciones push

El título, el texto y el destino al tocarla. Las URLs del backend que hoy apuntan a vistas que desaparecen deben cambiar (o redirigirse) a estas:

| Notificación | Texto | Destino nuevo | Estado |
|---|---|---|---|
| Pieza lista | «Se publicará el {d/m a las h:mm}. Puedes vetarla antes de esa hora.» | `/calendario/pieza/:id` | Existe (hoy apunta a `/editorial/:id`) |
| Pieza publicada | Las primeras 140 letras del texto | `/calendario/pieza/:id` | Existe |
| Pieza bloqueada | «El verificador bloqueó la pieza del {d/m}: {motivo}» | `/calendario/pieza/:id` | Existe |
| Pieza descartada | «La política no aprobó la pieza del {d/m}: {motivos}» | `/calendario/pieza/:id` | Existe |
| Acción incierta | «{capacidad}: el proveedor no confirmó…» | `/tu-turno` | Existe (hoy apunta a `/acciones?state=uncertain`) |
| Cuenta en pausa | «{cuenta}: {motivo}. Solo Gustavo puede reanudarla.» | `/tu-turno` | Existe (hoy apunta a `/maquina`) |
| LinkedIn caduca pronto | «El permiso de publicación caduca el {fecha}…» | `/tu-turno` | Existe (hoy apunta a `/ajustes`) |
| Pregunta nueva | «{Rol} te pregunta: {pregunta}» | `/tu-turno` | Nuevo |
| Tarea de perfil nueva | «Tu {sección} está lista para cambiar» | `/tu-turno` | Nuevo |
| Conversación que te toca | «{Persona} te escribió» | `/tu-turno` | Nuevo |

---

## Componentes comunes

Se diseñan una vez y se reutilizan:

| Componente | Variantes y partes |
|---|---|
| **Botón** | Principal, secundario, peligro (vetar, descartar, parada) y el botón grande de parar o reanudar. Cada uno con los estados normal, foco, deshabilitado y cargando («Enviando…»). |
| **Badge** | 5 tonos: ok (verde), info (azul), warn (ámbar), bad (rojo) y muted (gris). Opcionalmente con un punto de estado. |
| **Tarjeta** | Cabecera (título y badges), cuerpo y fila de acciones. |
| **Tarjeta de Tu turno** | Tipo, retrato del agente, título, plazo, cuerpo y acciones (ver Tu turno). |
| **Retrato de agente** | El retrato pixel del rol (`portrait{n}.png`) en tamaño pequeño (24 px) y mediano (40 px), con su nombre. |
| **Ficha de KPI** | Valor, variación, minigráfico, ⓘ con la definición y el estado «sin dato» o «aún no disponible». |
| **Embudo** | Barras horizontales con el recuento y la conversión entre pasos. |
| **Medidor** | Barra con el tope: verde por debajo del 80 %, ámbar desde el 80 % y rojo al 100 %. |
| **Elemento de línea de tiempo** | Icono, hora, frase, badge, contenido expandible y enlace. |
| **Celda de calendario** | Número del día, hoy resaltado, día de otro mes atenuado, hasta 3 chips de evento, «+N más», el punto «te toca» y la marca «sin post». Versión compacta con solo puntos para móvil. |
| **Chip de evento** | Color de la capa, icono, hora opcional y texto corto truncado. Estados normal, pasado (más tenue) y crítico. |
| **Tira semanal (móvil)** | 7 días con su inicial, número y puntos de capa. El día seleccionado se resalta y se desliza para cambiar de semana. |
| **Fila de persona** | Avatar con iniciales, nombre, titular, badges y última actividad. |
| **Recorrido de etapas** | Pasos con su fecha. Horizontal en escritorio y vertical en móvil. |
| **Comparador antes/después** | Dos bloques de texto con su etiqueta, un contador de caracteres y **Copiar**. |
| **Aviso (nota)** | info, ok, warn y error, con un título en negrita y texto. |
| **Modal de confirmación** | Título, explicación de la consecuencia, una nota (obligatoria u opcional según el caso) y Cancelar / Confirmar. Se cierra con Esc o tocando fuera. |
| **Toast** | Mensaje, con «Deshacer» opcional. |
| **Chips** | De filtro (alternables, con recuento) y de etiqueta (rol, modalidad o pilar). |
| **Estados vacíos** | Ilustración pequeña (un personaje idle de la escena), una frase y una acción opcional. |
| **Esqueletos de carga** | Para las tarjetas, las filas y las fichas de KPI. |
| **Error con reintentar** | Título («No se pudo completar»), el detalle y «Reintentar». La variante 409 dice «No se puede ahora». |
| **Enlace externo** | Texto y ↗; abre en otra pestaña. |

**Paleta actual** (referencia; el rediseño puede cambiarla):
- Fondo `#f7f6f0` y tarjeta `#fffef8`.
- Tinta `#263b32` y tinta suave `#5d665b`.
- Verde `#3e5d45`, salvia `#e2e9d9` y la barra lateral `#263c33`.
- Latón `#f8d47d`, óxido `#a54e35` y azul de información `#3f6585`.
- Foco `#d6754e`.

---

## Vocabularios: estados, etiquetas y tonos

### Estado de un rol en la escena

| Valor | Etiqueta | Tono |
|---|---|---|
| `trabajando` | Trabajando | ok |
| `en_espera` | En espera | info |
| `diseno` | En diseño | muted |
| (sin dato) | Sin datos | warn |

### Estado de una pieza

| Valor | Etiqueta | Tono |
|---|---|---|
| `preparing` | Preparándose | info |
| `scheduled` | Programada | info |
| `awaiting_approval` | Pendiente de aprobación (solo si la publicación vuelve a modo aprobación) | warn |
| `publishing` | Publicándose | warn |
| `published` | Publicada | ok |
| `uncertain` | Incierta | bad |
| `blocked` | Bloqueada por el verificador | bad |
| `failed` | Fallida | bad |
| `skipped` | Día sin pieza | muted |
| `vetoed` | Vetada | muted |
| `discarded` | Descartada por la política | muted |
| `expired` | Caducada | muted |
| `superseded` | Sustituida | muted |

Etapas de preparación: Director (idea y brief) → Redactores (variantes A y B) → Panel de lectores → Selección del texto final → Verificador.

### Etapa de una persona (contacto)

| Valor | Etiqueta | Tono | Notas |
|---|---|---|---|
| `candidate` | Por clasificar | muted | |
| `fit` | Encaja | info | |
| `followed` | Seguido | info | |
| `invited` | Invitado | warn | |
| `connected` | Conectado | ok | |
| (nuevo) | En conversación | ok | |
| (nuevo) | Oportunidad | ok | Se resalta |
| `incoming` | Te invitó | info | |
| `closed` | Cerrado | muted | Invitación ignorada o retirada |
| `discarded` | Descartado | muted | |

### Clasificación de personas

| Campo | Valores |
|---|---|
| Rol del barrio | Comprador, Par, Recomendador, Divulgador, Líder, Aliado |
| Modalidad (red) | Startups (personal), ProjectApp, Alianzas, Comunidad |
| Afinidad | Hispanohablante (declarado), Otra, Sin dato |
| Grado | 1.er grado, 2.º grado, 3.er grado, Fuera de tu red |
| Origen | Comentó en un post de {referente}, Búsqueda: {query}, Te invitó, Añadido a mano |
| Confianza | Porcentaje entero (0–100 %) |

### Etapa de una oportunidad (nuevo)

Conversación → Necesidad identificada → Cualificada → Reunión → Propuesta → Acuerdo. Final alternativo: Cerrada sin acuerdo.

«Cualificada» significa que hay una necesidad expresa, una modalidad pertinente y datos suficientes de presupuesto y dedicación.

### Contenido editorial

| Campo | Valores |
|---|---|
| Pilar | Del negocio al producto, IA aplicada, Arquitectura y entrega |
| Modalidad (editorial) | Personal · startups, ProjectApp, Alianzas, Comunidad |
| Lector principal | Lector comprador, recomendador, divulgador, líder de opinión, par profesional |

### Capas del calendario

| Capa | Color sugerido | Contenido |
|---|---|---|
| Tuyo | Naranja (foco) | Plazos de Tu turno, reuniones y caducidad de LinkedIn |
| Publicaciones | Verde | Piezas y su estado |
| Red | Azul | Conexiones que encajan, invitaciones recibidas y previstas |
| Conversaciones | Latón | Conversaciones nuevas y oportunidades |
| Sistema | Óxido | Pausas, acciones inciertas o fallidas, LinkedIn caducado |

### Tipos de elemento en Tu turno

| Tipo | Etiqueta | Tono del borde | ¿Crítico? |
|---|---|---|---|
| Aviso: LinkedIn caducado, acción incierta, máquina detenida | Aviso | bad | Sí |
| Aviso: LinkedIn caduca pronto, cuenta en pausa | Aviso | warn | No |
| Pregunta | Pregunta | info | No |
| Tarea de perfil | Perfil | ok | No |
| Conversación | Conversación | info | No |
