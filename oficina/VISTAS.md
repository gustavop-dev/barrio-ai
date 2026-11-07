# Vistas de la oficina

Inventario de las vistas de la PWA (`oficina/`) y de lo que hace cada una hoy, sacado del código. Sirve de base para el rediseño.

La app tiene **11 vistas**, un marco común y un conjunto de componentes que se repiten.

---

## 0. Marco común (todas las vistas)

- **Navegación con 9 secciones:** Oficina, Máquina, Acciones, Contenido, Referentes, Red, Conocimiento, Memoria y Ajustes.
  - En escritorio va en una barra lateral con el logo y el crédito de arte de LimeZu.
  - En móvil va en una barra superior con el logo y una barra inferior con las 9 entradas y etiquetas cortas.
- **Banner de pausa:** aparece en todas las vistas cuando la máquina está detenida. Muestra el motivo, avisa si la pausa viene del servidor y lleva a Máquina.
- **Rutas especiales:**
  - Sin sesión → Login, que luego te devuelve a donde ibas.
  - `/editorial/:id` → detalle de pieza. Es la URL que abren las notificaciones push.
  - Una ruta desconocida → Oficina.

## 1. Login (`/login`)

- Usuario y contraseña de Django, con el botón «Entrar».
- Errores de credenciales o de red, y un aviso propio para «Demasiados intentos» (429).
- Pantalla completa de «Comprobando sesión…».

## 2. Oficina (`/`, el inicio)

- **Escena pixel-art** con los 16 roles repartidos en 7 equipos. Cada personaje muestra su estado real (trabajando, en espera, en diseño o sin dato) y se refresca cada 15 s.
- **Controles:**
  - Luz de mañana o de tarde (cambia sola de 18:00 a 6:00).
  - Pausar o activar el ambiente (respeta `prefers-reduced-motion`).
- **Pie:** leyenda de estados y «Actividad real · hace X».
- **Error de actividad:** aviso con «Reintentar»; los personajes se quedan quietos.
- **Tira de chips** con los 7 equipos para seleccionarlos.
- **Panel lateral**, con dos modos:
  - **Equipo:** icono, número, badge «Nuevo», nombre, propósito, número de integrantes, lugar en la oficina, conteo por estado y lista de miembros (retrato, nombre, detalle y estado). Cada miembro abre su rol.
  - **Rol:** retrato, si es agente o servicio, equipo, misión, estado real (estado, detalle y desde cuándo), aviso si es un servicio o está en diseño, y el botón «Ver su equipo».
- **Equipos:** Estrategia y perfil (2), Observatorio (2), Mesa editorial (3), El barrio (5 lectores), Revisión (1), Relaciones (2) y Operación (1 servicio).

## 3. Máquina (`/maquina`)

- **Parada total:**
  - Muestra si la máquina está en marcha o detenida. Si está detenida: motivo, origen (app o entorno), quién la paró y cuándo.
  - Botón grande PARADA TOTAL / REANUDAR, que abre un modal. El motivo es obligatorio para parar y opcional para reanudar.
  - Si la pausa viene de `OPERATOR_PAUSED`, el botón queda bloqueado con una explicación.
- **Piloto automático:** activado o desactivado, y la versión de la política.
- **Ventana horaria:** si está abierta ahora, horario, zona y espaciado mínimo entre acciones.
- **Hoy:**
  - Medidores de gasto LLM frente al tope, gasto editorial (solo si el backend lo envía) y borradores frente al tope.
  - Chips de propuestas por estado, que llevan a Acciones ya filtradas.
  - Contadores de referentes, posts observados y acciones inciertas (con enlace).
- **Cuenta de LinkedIn** (una tarjeta por cuenta):
  - Badges: Conectada / Sin comprobar / Token caducado, En pausa, Bloqueada.
  - Conector usado y última comprobación.
  - Por cada capacidad: cuántas quedan hoy, medidor diario y medidor semanal.
  - «Pausar solo esta cuenta» (con motivo en el mismo formulario) o «Reanudar».
- **Actividad reciente:** los últimos 50 eventos del operador (acción, hace cuánto, objetivo y actor) con «Detalles» desplegable en JSON.
- Se refresca cada 30 s.

## 4. Acciones (`/acciones`)

- **Filtros** que se guardan en la URL:
  - Capacidad: comentarios, reacciones, publicaciones propias, seguimientos, invitaciones sin nota o invitaciones recibidas.
  - Estado, 11 en total: propuesta, aprobada, vetada, sustituida, descartada, ejecutándose, enviada, confirmada, incierta, fallida y caducada.
  - Muestra el total.
- **Tarjeta de acción:**
  - Capacidad, versión, estado, origen (Tuya o Agente) y hace cuánto se creó.
  - Si es una publicación propia: día y hora programados, aviso de autonomía y enlace a la pieza.
  - Si es un comentario o una reacción: el post de origen (autor, texto, fecha y enlace a LinkedIn).
  - Si es una acción de red (seguir, invitar o aceptar): la persona (nombre, titular, grado y origen; si comentó, el referente y un extracto) y su clasificación (rol, modalidad y motivo). Vetarla descarta a la persona para siempre.
  - El texto o la reacción propuestos, la justificación, las citas del curso (chips que llevan a Conocimiento), los riesgos y la nota de decisión.
  - La ejecución: estado, código HTTP, fecha, nota y enlace a LinkedIn.
- **Botones según el estado:**
  - **Aprobar:** solo en propuestas; nota opcional; se aprueba ese texto exacto (hash).
  - **Vetar:** en propuestas y aprobadas; nota obligatoria.
  - **Resolver:** en inciertas; eliges «se publicó» o «no se aplicó» y la nota es obligatoria.
- Paginación, estados de vacío, cargando y error; se refresca cada 30 s.

## 5. Contenido (`/contenido`, el calendario editorial)

- **Aviso fijo** «Las piezas salen solas», con la hora, la zona y cuántas horas antes empieza la preparación.
- Aviso si la configuración editorial del servidor es inválida.
- **Próxima pieza:** su tarjeta y el botón «Preparar la siguiente pieza».
  - Abre un modal que avisa del coste y explica el circuito.
  - Al confirmar, muestra «en cola para el día X».
- **Calendario de 15 días:**
  - Navegación Anteriores / Hoy / Siguientes.
  - Cada día tiene su fecha, el badge «Hoy» y sus piezas, o un hueco: «Sin publicación» en el pasado, «Hueco libre» en el futuro.
- **Tarjeta de pieza** (también se usa en «Próxima pieza»):
  - Tesis como título, con enlace al detalle.
  - Uno de los 13 estados.
  - Hora, pilar, modalidad y lector principal.
  - Etapa si se está preparando, nota si se saltó, se bloqueó o falló, y enlace al post publicado.
  - «Vetar» mientras se pueda.
- Se refresca cada 60 s.

## 6. Pieza (`/contenido/:id`, el detalle)

Son 8 secciones apiladas; se refresca cada 30 s.

1. **Estado:** badge, hora de salida, etapa, explicación de la aprobación, «Vetar», «Aprobar desde Acciones», notas del circuito, de la decisión y de la ejecución, enlace al post e impresiones.
2. **Texto final:** en inglés, con el número de caracteres.
3. **Verificador:**
   - Veredicto, y si las guardas corrigieron al modelo.
   - Motivos de bloqueo y resumen.
   - Hallazgos con severidad, tipo, cita y detalle.
   - Afirmaciones comprobadas (desplegable) y hash del texto.
4. **Brief:**
   - Aviso si el director decidió no publicar.
   - Lector principal, modalidad, pilar, tesis, enfoque (enlace a la unidad del curso) y formato.
   - Valor para el lector, criterio de éxito, qué evitar, evidencia y por qué esta idea.
5. **Variantes A y B** lado a lado: autor, badge «Elegida», ángulo, texto, incertidumbres y afirmaciones.
6. **Panel de lectores:** 5 lectores × 2 variantes, con fortalezas y objeciones (cada una con severidad).
7. **Selección:** A, B, fusión o descartada; razonamiento; objeciones resueltas y conservadas.
8. **Fuentes y coste:** citas del curso, señales de terceros (autor, fecha y texto) y coste por etapa y modelo, con el total.

## 7. Referentes (`/referentes`)

- Selector de cuenta, que solo aparece si hay más de una.
- **Observar ahora:** pone en cola una lectura inmediata y lo confirma.
- **Añadir referente:**
  - URL de perfil, validada y normalizada a `linkedin.com/in/…`.
  - Motivo obligatorio.
  - Errores junto a cada campo.
- **Lista con contador:** nombre, Activo o Inactivo, motivo, «Observado hace X» o «Aún sin observar», y enlace al perfil.

## 7b. Red (`/red`)

- **Avisos:** el bloque está apagado en el servidor (`NETWORK_ENABLED=false`), o las invitaciones están en pausa 7 días porque LinkedIn las limitó.
- **Hoy:**
  - Por cada capacidad (seguir, invitar sin nota, aceptar): su modo (auto, aprobación o apagado) y un medidor diario y otro semanal.
  - Lecturas en LinkedIn frente a sus topes: comentarios, búsquedas, perfiles y sincronizaciones.
  - Gasto del modelo que clasifica, frente a su presupuesto.
- **Contactos:**
  - Filtro por etapa con su recuento: por clasificar, encaja, seguido, invitado, conectado, cerrado, te invitó y descartado.
  - Ficha de cada persona: nombre enlazado al perfil, etapa, titular, grado, ubicación y si la sigues.
  - De dónde salió: comentó en un post de un referente (con extracto), una búsqueda o te invitó.
  - Clasificación: rol del barrio, modalidad, afinidad, motivo y confianza.
  - Los tres últimos eventos de su historial y su acción abierta, con enlace a Acciones.
  - «Descartar», con nota obligatoria, mientras no esté invitada ni conectada.

## 8. Conocimiento (`/conocimiento`)

- **Buscador textual** sin coste en las unidades de las clases 01–06: hasta 12 resultados y los avisos del backend.
- **Resultados:** título, id, clase y relevancia. Cada uno abre su unidad.
- **Unidad** (se abre en la misma página con `?unidad=`):
  - Título y clase.
  - Los campos originales como desplegables («explanation» viene abierto).
  - Las fuentes, también desplegables, que cargan su evidencia al abrirse.
  - Botón «Cerrar».
- Es el destino de los chips de citas de Acciones y Pieza.

## 9. Memoria (`/memoria`)

- **Propuestos (n)** y **Confirmados (n)**.
  - Cada tarjeta muestra la clave, el estado, la versión, el valor, si es «Sobre ti» o «De trabajo», la procedencia y la fecha.
  - «Confirmar», con modal, solo en los datos propuestos sobre ti.
- **Proponer un dato:** nombre, valor y procedencia (ya rellenada por defecto).

## 10. Ajustes (`/ajustes`)

- **LinkedIn oficial:**
  - Mensaje al volver de LinkedIn, que se puede descartar: éxito o uno de los 7 motivos de error.
  - Estado: Conectado, Caduca pronto, Caducado o Sin conectar.
  - Miembro, fecha de caducidad con los días que quedan, permisos y versión de la API.
  - Avisos posibles: caduca pronto, caducado, cuenta en pausa, publicación real desactivada (`LIVE_LINKEDIN_OFFICIAL`), falta configuración en el servidor y tu usuario no tiene permiso.
  - Botón «Conectar» o «Reconectar LinkedIn».
- **Notificaciones push:**
  - Pasos para iPhone, resaltados cuando hay que instalar la app.
  - Aviso si el navegador no las admite.
  - Estado en este dispositivo: Activadas, Bloqueadas, Desactivadas o Comprobando.
  - Botones «Activar», «Probar» y «Desactivar», con su confirmación.
- **Sesión:** usuario y «Cerrar sesión».
- **Acerca de:** versión y crédito del arte.

---

## Componentes compartidos (se diseñan una vez)

- Cabecera de página: eyebrow, título y párrafo introductorio.
- Tarjeta con cabecera y badges.
- Badge con 5 tonos: ok, warn, bad, muted e info.
- Medidor con 3 niveles: normal (< 80 %), alerta (≥ 80 %) y agotado (≥ 100 %).
- Notas o avisos: info, ok, warn y error.
- Modal de confirmación con campo de nota.
- Chips que enlazan a filtros o a unidades del curso.
- Botones: primary, secondary, danger y el botón grande de parar o reanudar.
- Estados: cargando, vacío, error con reintentar, y conflicto 409 («No se puede ahora»).
- Enlace externo con ↗ (solo https).
- Feed o línea de tiempo.

## Cosas que vale la pena tener en cuenta al rediseñar

- **Navegación móvil:** las 9 entradas van todas en la barra inferior.
- **No hay una bandeja de pendientes.** Lo que espera una decisión tuya está repartido: inciertas y propuestas en Acciones, memoria por confirmar en Memoria, LinkedIn a punto de caducar en Ajustes y pausas en Máquina.
- **Datos en bruto:** Conocimiento, Memoria y el feed de Máquina muestran el contenido en JSON o texto preformateado.
- **Pieza es muy larga:** 8 secciones apiladas sin índice ni pestañas.
- **Funciones que hoy no existen**, por si las quieres incluir en el diseño: editar, desactivar o borrar referentes; rechazar o editar datos de memoria; filtrar el feed de actividad.
