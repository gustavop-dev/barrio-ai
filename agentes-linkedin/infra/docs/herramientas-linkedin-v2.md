# Herramientas de Barrio AI: selección revisada

Actualizado el 6 de noviembre de 2026 por las decisiones de Gustavo. Sustituye la recomendación de [herramientas v1](herramientas-linkedin-v1.md), conservada como historial. Es diseño documental: no hay nuevas conexiones, llamadas pagadas ni acciones sobre LinkedIn. Los ciclos y la asignación de autoridad todavía requieren implementación.

## Selección vigente

**Unipile v2 + API oficial de LinkedIn + Django/PostgreSQL + investigación web con Claude + imágenes de OpenAI + biblioteca de fotos reales.** Zernio y Canva salen de la selección. La sustitución completa de la analítica de Zernio queda condicionada a obtener y probar los permisos oficiales; no basta con que existan los endpoints.

| Componente | Responsabilidad propuesta | Dependencia pendiente |
| --- | --- | --- |
| Unipile v2 | Buscar perfiles y contenido, explorar referentes, conexiones, comentarios, reacciones, mensajes y cambios de perfil documentados | Cuenta conectada y prueba de cada operación; cobertura según LinkedIn Classic/Sales Navigator. [Funciones del proveedor](https://developer.unipile.com/v2.0/docs/list-provider-features). |
| API oficial de LinkedIn | Publicación, edición admitida, retirada y analítica propia | OAuth, productos y permisos efectivos de nuestra aplicación. |
| Django/PostgreSQL y cola existente | Programación, memoria compartida, decisiones, versiones, ejecución y registro de resultados | Adaptadores y trabajos por implementar; que exista una cola no significa que ya publique en LinkedIn. |
| Claude Web Search + Web Fetch | Noticias, opiniones, blogs, investigación, anuncios y contexto del mundo; lectura de fuentes accesibles | Habilitar herramientas en el entorno ejecutor, presupuesto y políticas de consulta. [Búsqueda](https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-search-tool), [lectura](https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-fetch-tool). |
| API de imágenes de OpenAI | Generar infografías y otros recursos; editar imágenes de referencia | Directrices visuales de Gustavo pendientes y prueba de calidad. [Generación y edición](https://developers.openai.com/api/docs/guides/image-generation). |
| Biblioteca propia de fotos | Seleccionar fotos reales del día a día, proyectos y equipo para acompañar contenido | Carpeta o almacenamiento y contexto de cada foto por aportar; originales conservados. |
| Agenda, opcional | Disponibilidad real y registro de reuniones acordadas | Elegir y conectar la agenda cuando se habilite esa capacidad. |

Sales Navigator continúa siendo opcional para búsquedas que necesiten sus filtros. No se añade un segundo proveedor de LinkedIn ni un agregador de noticias de pago por defecto.

## Corroboración de la API oficial

### Publicar y programar

La [Posts API](https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/posts-api) documenta creación en nombre del miembro con `w_member_social`, medios, edición de campos admitidos y eliminación. El permiso de publicación está disponible mediante el producto Share on LinkedIn, según la [tabla de acceso](https://learn.microsoft.com/en-us/linkedin/shared/authentication/getting-access). Eso no concede automáticamente acceso a analítica ni lectura general de posts.

El [esquema de posts](https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/post-api-schema) acepta `PUBLISHED` al crear. No documenta una fecha de ejecución futura. `publishedAt` describe la publicación y no acredita programación; `PUBLISH_REQUESTED` indica procesamiento asíncrono. Por tanto, diseñamos la programación en nuestro backend: guardar la fecha y ejecutar la creación al vencimiento. El post pendiente no aparecerá por ello en el programador nativo de LinkedIn.

La cola debe conservar versión aprobada, zona horaria, fecha UTC, medios preparados y estado. Reprogramar o cancelar modifica el trabajo pendiente. Si el envío ya comenzó, primero se concilia su resultado: cancelar la cola no retira un post publicado. Cada pieza tiene un único ejecutor; un timeout no dispara una segunda publicación por Unipile.

Guardar el identificador nativo devuelto, la URL resuelta y los identificadores de cada proveedor. No convertir una activity URN en share/ugcPost URN cambiando prefijos. La confirmación posterior necesita lectura permitida o conciliación por Unipile; tener permiso de escritura no acredita esa lectura. [Identificadores de Unipile](https://developer.unipile.com/v2.0/docs/linkedin-retrieve-posts).

### Métricas de un perfil personal

| Datos | API y permiso | Alcance comprobado documentalmente |
| --- | --- | --- |
| Resultados de publicaciones propias | `memberCreatorPostAnalytics`, `r_member_postAnalytics` | Consultas por publicación y agregadas del miembro. Impresiones, alcance, reacciones, comentarios, compartidos; también guardados, envíos, clics y seguidores/visitas atribuidos al contenido en versiones compatibles. [Estadísticas de posts](https://learn.microsoft.com/en-us/linkedin/marketing/community-management/members/post-statistics). |
| Evolución del número de seguidores | `memberFollowersCount`, `r_member_profileAnalytics` | Total y consultas por intervalo; no identifica por sí solo a cada seguidor. [Estadísticas de seguidores](https://learn.microsoft.com/en-us/linkedin/marketing/community-management/members/follower-statistics). |

No todas las métricas admiten las mismas agregaciones o ventanas. Las visitas al perfil atribuidas a contenido no son el total general de visitas al perfil. El alcance no se debe sumar como si fueran personas distintas entre posts. Conservar definición, intervalo, fecha de observación y disponibilidad; un dato ausente no es cero. No se promete todo el panel de LinkedIn, desgloses demográficos completos ni las métricas privadas de otros autores.

Los permisos de analítica pertenecen a Community Management y requieren aprobación: [productos y permisos](https://learn.microsoft.com/en-us/linkedin/marketing/increasing-access). La [revisión de aplicaciones](https://learn.microsoft.com/en-us/linkedin/marketing/community-management-app-review) exige una organización legal y un caso comercial, además de verificar la empresa y aplicación. ProjectApp es una posible vía para solicitar acceso, no una aprobación ya obtenida. Hay niveles Development y Standard con evaluación propia.

`r_member_social`, para lectura general de contenido del miembro, continúa cerrado a nuevas solicitudes según la [FAQ oficial](https://learn.microsoft.com/en-us/linkedin/marketing/community-management/community-management-overview). Es un permiso diferente: no implica que `r_member_postAnalytics` esté cerrado, ni que obtener analítica otorgue lectura general.

**Dependencia principal de esta decisión:** comprobar elegibilidad y permisos efectivos antes de contar con analítica automática. Si no se concede acceso, el ciclo debe marcar las métricas como no disponibles y admitir observaciones/importaciones manuales con procedencia. Eso no resuelve la necesidad de automatización: habría que volver a evaluar un proveedor autorizado para esa función. No contratarlo ni suponer que Unipile devuelve impresiones privadas.

## Observatorio más amplio: LinkedIn y lo que sucede fuera

La investigación incorpora tres corrientes de entrada que alimentan los ciclos existentes:

1. **Conversaciones en LinkedIn:** referentes, publicaciones, comentarios y participantes, mediante Unipile. Los referentes se eligen por temas, pertinencia y audiencia observada; no solo por una insignia Top Voice.
2. **Actualidad y contexto:** noticias mundiales, tecnología, economía, negocio, inversión, startups y anuncios de empresas. La búsqueda puede ser amplia; la selección editorial debe explicar por qué un hallazgo importa a la audiencia de Gustavo.
3. **Opiniones y profundidad:** blogs, newsletters públicas, ensayos, análisis especializados, documentación e investigaciones. Guardar puntos de vista contrapuestos cuando cambien la interpretación del tema.

Web Search descubre fuentes; Web Fetch lee las páginas y PDF accesibles. Como diseño complementario, el backend puede revisar RSS/Atom de fuentes seleccionadas cuando existan, deduplicar y conservar novedades. Ningún rastreador ni suscripción se activa en este incremento. No hay garantía de cobertura exhaustiva, contenido de pago o páginas que requieran sesión.

Cada hallazgo debe conservar URL, autor/medio, fecha de publicación, fecha del acontecimiento si se conoce, fecha de consulta, tipo de fuente, hechos y opiniones distinguidos, evidencia, incertidumbre y vínculo con un tema o pregunta editorial. La opinión de un autor no se convierte en un hecho ni en la opinión personal de Gustavo.

El Observatorio entrega evidencia y posibles ángulos a Editorial; los copywriters reciben el brief con fuentes, perspectivas y relevancia. La revisión comprueba afirmaciones y voz. Los resultados de publicaciones y conversaciones vuelven al aprendizaje para ajustar fuentes, temas y selección. Ampliar la observación no autoriza atribuir a Gustavo experiencias o especialidades nuevas.

## Recursos visuales y fotos reales

OpenAI proporciona generación y edición a partir de instrucciones e imágenes. Es adecuado como proveedor candidato para las infografías; estilo, plantillas y criterios de aceptación esperan las directrices de Gustavo. Una imagen generada sigue necesitando revisión de texto, cifras y correspondencia con el contenido antes de aprobar la pieza. No se generó ninguna en esta tarea.

Las fotos reales constituyen una entrada distinta: conservar original, contexto proporcionado por Gustavo, fecha conocida y usos autorizados. La selección puede apoyarse en una descripción o etiquetas. No hace falta generar de nuevo una foto para publicarla. Las versiones recortadas o editadas conservan su relación con el original y no se presentan como evidencia de un acontecimiento distinto.

Para un carrusel de varias páginas, producir imágenes es solo parte del trabajo: todavía hay que ordenar páginas y componer/exportar el documento en el backend, si ese formato se elige. La creación o edición audiovisual completa permanece fuera de esta selección de herramientas de imágenes. CONT-04, que incluye recursos audiovisuales, continúa con cobertura parcial.

## Qué queda sin cobertura completa

“Sin contrato verificado” significa que no se encontró una operación específica en la documentación consultada; no demuestra imposibilidad técnica. Se conserva intervención manual hasta verificar otra vía.

| Capacidad del catálogo | Estado con esta selección |
| --- | --- |
| INT-07: Guardar nativamente en LinkedIn | Biblioteca interna viable; botón Guardar de LinkedIn sin contrato específico verificado. |
| CONT-12/13: artículos largos nativos y newsletters | Preparación editorial viable; creación/mantenimiento nativo manual. El tipo `article` de Posts API comparte una URL, no acredita el editor de artículos/newsletters. |
| PERF-05/06: Destacados y datos de contacto/enlaces | Sin cobertura específica verificada para administrarlos. |
| PERF-08/09: recomendaciones recibidas y preferencias de visibilidad/seguimiento | Sin cobertura específica verificada para administrar todas esas opciones. |
| PERF-07: solicitud formal de recomendación | Mensaje contextual cubierto; formulario nativo no verificado. |
| PERF-03/10: todos los campos del perfil y resultado visual | Experiencia, educación y habilidades documentadas; proyectos y otros campos requieren contraste. Leer campos no sustituye inspeccionar la presentación pública/móvil. |
| ADM-01/02/03: notificaciones, moderación y denuncias | Eventos y operaciones concretas documentadas; no espejo completo del centro de notificaciones. Bloqueo documentado, denuncia no verificada; moderación de terceros depende de permisos reales. |
| CHAT-10: organización nativa del inbox | Estados internos viables; archivar/silenciar/marcar leído requieren verificar campos exactos de LinkedIn en Unipile v2. |
| CHAT-07: agenda real | Conversación por mensaje cubierta; disponibilidad y creación de reuniones pendientes de conexión a una agenda. |
| APRE-01: todo el panel de analítica | Métricas propias documentadas pero acceso sin comprobar. No se acreditó cobertura completa de visitas generales, apariciones en búsqueda, identidad de visitantes o demografía. |
| CONT-04/10: todos los formatos y cambios de medios | Imágenes y fotos contempladas; producción audiovisual completa no. Editar un post no permite asumir sustitución de cualquier medio. |

La matriz mantiene **72 acciones**, con fuentes y estado de cada una: [especificación v2](../../arquitectura/matriz-herramientas-linkedin-v2.json). Las siete acciones sin contrato específico de v1 continúan pendientes. A ellas se suman los límites parciales anteriores y la dependencia de permisos; no se convierten todos esos casos en funciones imposibles ni implementadas.

## Continuación del plan

Mantener los cinco equipos, trece roles, memoria compartida y autoridad editorial del [plan](plan-equipo-autonomo.md). Esta elección no asigna todavía nuevas acciones a agentes ni cierra F1/F2/F3. Las condiciones de los proveedores y la limitación sobre automatización de terceros documentada en v1 siguen siendo aplicables.

El siguiente incremento de diseño es repartir responsabilidades y autoridad del catálogo usando esta selección. La preparación del piloto deberá comprobar permisos de LinkedIn, lectura/conciliación de identificadores y cobertura real de Unipile; especificar programación, fuentes del Observatorio y biblioteca de medios. Las directrices de infografías y la agenda continúan pendientes. Ningún presupuesto histórico se amplía con esta decisión.

[Validación documental v2](../../arquitectura/validacion-herramientas-linkedin-v2.json): consistencia con las 72 acciones y referencias locales, sin pruebas de integración ni QA independiente nuevo. La validación v1 corresponde a sus artefactos históricos.
