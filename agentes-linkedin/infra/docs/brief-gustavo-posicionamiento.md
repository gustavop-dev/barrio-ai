# Brief de Gustavo y ProjectApp — versión inicial

Fecha: 2026-11-06. Uso interno de diseño. Fuente principal: respuesta directa de Gustavo en este hilo. No es copy público ni autorización para divulgar información de clientes. No modifica las unidades del curso ni confirma inferencias dentro de la memoria de ejecución.

## Dirección expresada por Gustavo

- Objetivos principales: oportunidades personales en startups, alianzas y clientes de servicios de desarrollo. Autoridad y comunidad como medios y objetivos secundarios. Reparto entre vías todavía pendiente.
- Mercado inicial: Estados Unidos; preferencia por founders latinoamericanos o hispanohablantes por afinidad cultural y facilidad de comunicación. Contenido en inglés desde el inicio para conservar continuidad al ampliar a audiencia angloparlante. Abierto a buenas oportunidades de founders no hispanohablantes. No inferir idioma, etnia o identidad por nombres/apariencia; usar información declarada y contexto profesional.
- Startups prioritarias: con financiación o preparándose para levantar capital, con necesidad técnica real. Gustavo quiere aprender del entorno startup; considera que allí puede encontrar procesos de contratación más directos. Esto es una preferencia/hipótesis, no una garantía general sobre startups o capital disponible.
- Dos vías: contratación personal de Gustavo y contratación de ProjectApp. Aclaración vigente del usuario: en contratos personales él piensa, ejecuta y participa directamente. ProjectApp es una oferta separada de ejecución del equipo bajo su liderazgo.
- ProjectApp: desarrollo a medida; equipo continuo con pago mensual, objetivos de desempeño y roadmap; también proyectos de alcance/requisitos definidos. Hosting, soporte y mantenimiento son continuidad posterior.
- IA: arquitecturas, sistemas agénticos y workflows específicos de negocio. Evitar posicionamiento genérico de “automatizaciones” y promesas de soluciones baratas; demostrar complejidad y valor con casos. Coste y valor comercial no están cuantificados todavía.
- Identidad pública deseada: credibilidad técnica y comercial, vinculada a software, startups e ingeniería de IA. No limitar el perfil a vendedor de agencia.
- Cadencia deseada: publicación diaria; tiempo personal y horario por definir. Aspiración de crecimiento rápido, sin promesa de resultados ni obligación de publicar material insuficiente.
- Límites: no humo, no temas que desconoce, no conexiones indiscriminadas. Puede comentar sobre tecnología en otros sectores cuando tenga algo relevante que aportar.
- Preferencia de interacción: preguntas con opciones, no formularios abiertos extensos.

## Trayectoria y casos declarados por el usuario

Fundador de ProjectApp, más de cuatro años en desarrollo; empezó a programar a los 12, consiguió proyectos a los 16 y trabaja en ProjectApp desde los 17. No inferir edad actual ni fechas exactas.

Describe ERP de inventario/RFID usado en cadenas como Falabella y Éxito; ERP para firma jurídica; plataforma educativa Littigio con vídeo/streaming y protección de contenidos; SaaS Waiter y Fiscal. En Yapa declara ser el único desarrollador, haber construido la solución, arquitectura AWS y scraper con 96% de accuracy. Próxima incorporación a Beloz, fintech mexicana: aún no presentarla como empleo iniciado. La atribución personal exacta y la posibilidad de nombrar clientes se deben verificar por caso antes de publicarlos.

## Contraste documental inicial

Revisión selectiva, no auditoría exhaustiva de repositorios, todos los tickets o producción. README y planes acreditan lo documentado; no equivalen por sí solos a despliegue o adopción.

| Caso | Evidencia consultada | Qué permite sostener / qué falta |
| --- | --- | --- |
| Vástago | [PRD en master](https://github.com/ProjectAppForge/vastago_project/blob/master/docs/methodology/product_requirement_docs.md), README y arquitectura | ERP con inventario, trazabilidad, permisos y analítica. PRD distingue Fase 1 entregada, refinamientos y RFID como Fase 3 pendiente. Conciliar con versión realmente usada; no confirma relación comercial directa con Falabella/Éxito. |
| G&M | [README](https://github.com/ProjectAppSunset/gym_project/blob/master/README.md), secciones iniciales | Gestión de casos legales, documentos dinámicos, firmas, organizaciones y suscripciones. Pendientes resultados de uso, contribución individual y métricas. |
| Littigio | [PRD de ola 4](https://github.com/ProjectAppForge/littigio_project/blob/feat/05112026-ola4-delivery/docs/methodology/product_requirement_docs.md), contexto activo | La rama master conservaba plantilla; la rama de desarrollo sí documenta plataforma por cohortes, contenidos protegidos y simulacros. Proveedores reales, DRM efectivo y aceptación operativa pendientes según documento. No confundir implementación local con servicio completo en producción. |
| Waiter | [README](https://github.com/ProjectAppVentures/waiter_project/blob/main/README.md) | POS y menú de comensal sobre sistema propio. Descripción GitHub antigua menciona Odoo; README lo declara retirado. Pago del comensal es demo; Mesero IA y conexión Meta siguen como pasos posteriores en esa fuente. |
| Fiscal | [README](https://github.com/ProjectAppVentures/fiscal_project/blob/master/README.md) | Microservicio de facturación, estado F1 sin DIAN real. No afirmar emisión real validada ni SaaS maduro a partir de esa versión. |
| Yapa — AWS | [Y2-1515](https://app.notion.com/p/3ec106ca217f811eb62dd56efd8650b4) | Ticket Done documenta endpoint Django desplegado en AWS y pruebas HTTP. Mediana reportada 26 ms vs 392 ms con diez llamadas calientes desde us-east-1: es una medición delimitada, no rendimiento global ni benchmark replicado aquí. |
| Yapa — entregas recientes | [Ola 1](https://app.notion.com/p/40f106ca217f813fb2d3c63c57bfdf9a) | Evidencias de PRs y pruebas sobre datos y Learn, con aceptación e integración pendientes en varios puntos. No prueba por sí sola autoría exclusiva ni que todo esté en producción. |
| Yapa — scraper | [Spike 19 de octubre](https://app.notion.com/p/3fe106ca217f81c5a5dcd72adc5b9672) | Métricas por campo/muestra y varias revisiones: 92.2% global, 95.4% tarjetas abiertas y 97.9% en campos autoaceptados en la actualización. El 96% declarado requiere versión, dataset, denominador y evaluación correspondiente; no reemplazarlo por la cifra más alta. Holdout inicial inferior y pendiente de nueva validación ciega. |

Fuentes de Notion consultadas mediante cuenta Trabajo Yapa. También se consultó el hub YAPA 2.0 y el esquema del backlog; no se revisaron todos los requerimientos. No se hicieron modificaciones en Notion ni repositorios externos.

El MCP específico de comunicaciones de ProjectApp no está expuesto en esta sesión; correos de Dewis pendientes. Los repositorios fueron accesibles con GitHub CLI autenticado. No se descargaron correos ni se enviaron mensajes.

## Coherencia del destino comercial

La [web inglesa de ProjectApp](https://projectapp.co/en-us/) comunica desarrollo a medida, entregas rápidas y precios orientativos en COP. Esto muestra la oferta pública actual, no verifica sus cifras ni plazos. Debemos valorar su coherencia con relaciones continuas y soluciones técnicas complejas para startups estadounidenses. No se modifica la web en esta etapa.

## Hipótesis de posicionamiento — propuesta, no aprobada

Fundador técnico que construye productos y sistemas reales, con capacidad de asumir responsabilidad individual o liderar la entrega con ProjectApp. Software es la base; ingeniería de IA es una capacidad demostrable dentro de esa base. La afinidad lingüística facilita relaciones iniciales, mientras el contenido en inglés permite ampliar el mercado.

Los dos compradores tienen necesidades distintas: el founder que incorpora capacidad técnica interna y el que contrata una entrega externa. Mantener briefs, pruebas, llamadas a la acción y medición diferenciadas bajo una misma identidad profesional coherente.

El barrio puede incluir engineers, líderes técnicos, operadores de startups y personas que recomiendan talento/equipos. Son candidatos de diseño, todavía no perfiles seleccionados ni audiencia validada.

## Historial de preguntas iniciales — respondidas en actualizaciones posteriores

1. Primeros 90 días: equilibrio 50/50; prioridad startups 70/30; prioridad ProjectApp 30/70. Respondida más adelante; no usar como pendiente vigente.
2. Papel principal: founding engineer; technical partner con equipo; especialista de ingeniería IA. Respondida más adelante; no usar como pendiente vigente.
3. Participación de ProjectApp cuando Gustavo firma personalmente: depende del acuerdo; individual con contratos separados; liderazgo personal con equipo conocido/autorizado. Respondida más adelante; no usar como pendiente vigente.

Después: rango económico mínimo por modalidad, capacidad real del equipo, fechas/disponibilidad, pruebas y permiso de mención de casos, línea base de LinkedIn, métricas y tiempo para revisión. No fijar títulos como CTO, promesas, cuotas de publicación o metas de ingresos sin esa información.

## Incremento anterior — sustituido por la propuesta v1

Integrar las tres respuestas al contrato de Estrategia y Perfil. Vincular contexto personal con métodos del curso; convertir casos en fichas de problema → decisión técnica → contribución → resultado → evidencia → límites de uso. Priorizar unas pocas pruebas sólidas antes de investigar exhaustivamente todo el historial.

## Actualización del usuario — prioridades y forma de trabajo

Decisiones expresas posteriores a las preguntas iniciales:

- Reparto de esfuerzo: 60% oportunidades personales en startups y 40% contratos de ProjectApp. Es distribución estratégica, no una proyección de ingresos ni una obligación de mencionar ofertas en esa proporción en los posts.
- Papel buscado: técnico con comprensión profunda del negocio y su lógica, integrado en decisiones de producto y operación. Evitar una presentación limitada a ejecutar tickets o producir código. Denominación provisional propuesta: ingeniero de producto con criterio de negocio; founding engineer puede ser una modalidad objetivo, no un cargo previamente acreditado.
- Modalidad vigente, aclarada posteriormente por Gustavo: en los contratos personales él ejecuta, piensa y participa directamente, tanto en la comunicación como en la práctica. La explicación anterior queda sustituida; no usarla para caracterizar su oferta actual. Los contratos ProjectApp corresponden a ejecución del equipo bajo su liderazgo.
- Tratamiento del posicionamiento: describir responsabilidades y contribuciones reales. Puede presentar liderazgo, interlocución y responsabilidad por entregas cuando correspondan; no atribuir autoría individual al trabajo colectivo ni preparar comunicaciones destinadas a ocultarlo. Separar oportunidades que requieren ejecución personal de contratos que admiten un equipo conocido por el cliente.
- Gustavo considera más fácil conseguir oportunidades en startups que contratos de agencia y valora la estabilidad de estos últimos. Conservarlo como criterio suyo para priorizar, no como hecho universal de mercado.
- Menciona recibir pagos de clientes estadounidenses mediante una LLC. No consta existencia, titularidad ni condiciones de esa entidad. Ruta de cobro pendiente de concretar; no prueba contratación laboral, autorización para subcontratar, garantía de ingreso ni tratamiento fiscal. Este brief no realiza asesoría jurídica o fiscal.

Distinción confirmada: contratación personal con ejecución directa de Gustavo; contratación ProjectApp con ejecución de equipo bajo su liderazgo. Pendientes: alcance, disponibilidad y condiciones de cada oferta.

Hipótesis de mensaje para desarrollar, todavía no copy aprobado: ingeniería de producto conectada con decisiones de negocio, desde el problema hasta una entrega verificable. Los casos deben identificar por separado contribución personal y contribución del equipo.

## Paso anterior: precisar el segmento — completado en los apartados siguientes

Prioridades y modalidades confirmadas. Definir etapa de startup, necesidad técnica principal y perfil de founder; después condiciones de oportunidad y métricas. No asumir que una startup preparando una ronda ya tiene presupuesto. Preferencias comerciales nuevas se mantienen como preguntas pendientes hasta que Gustavo responda.

## Segmento inicial confirmado por Gustavo

- Etapa preferida: startups tempranas, especialmente presemilla que ya hayan recibido inversión. Es una preferencia inicial, no una exclusión rígida de otras etapas.
- Condición económica: trabajo remunerado y presupuesto para contratar; no trabajo gratuito. Haber recibido inversión es una señal para investigar, no prueba suficiente de presupuesto disponible para este puesto. No inferir aceptación de equity como única remuneración.
- Necesidad principal combinada: convertir necesidades del negocio en producto funcional, evolucionarlo e incorporar capacidades de IA en producto o procesos cuando sean pertinentes. IA complementa la ingeniería de producto; no debe añadirse como requisito artificial a todos los problemas.
- Interlocutor: founders técnicos o de negocio. Importan más el producto y la capacidad de decisión que la formación del founder.
- Se mantienen Estados Unidos como mercado inicial, contenido en inglés y afinidad preferente con founders hispanohablantes/latinoamericanos, sin exclusión de otras oportunidades relevantes.

Síntesis de trabajo, no titular aprobado: ingeniero de producto con criterio de negocio que ayuda a startups tempranas financiadas a construir y evolucionar software, integrando IA cuando aporte valor.

Pendientes para cualificar oportunidades: modalidad/dedicación, remuneración mínima y disponibilidad. No convertir preferencias iniciales en filtros excluyentes sin autorización del usuario.

## Condiciones de oportunidad confirmadas

- Dedicación: considerar tiempo completo y parcial según remuneración, producto y autonomía.
- Referencia económica elegida: USD 5.000–7.999 mensuales antes de impuestos para una oportunidad personal de tiempo completo. Es una banda de referencia interna; no un techo ni un mínimo exacto ya fijado. No trasladarla automáticamente a tiempo parcial o contratos de ProjectApp.
- Estrategia de disponibilidad: sumar colaboraciones compatibles; no reemplazar ni abandonar trabajos u oportunidades actuales por defecto. Reconsiderar solamente si la carga, exigencias o condiciones de una oportunidad lo requieren.
- No asumir disponibilidad simultánea para múltiples jornadas completas. Evaluar horas reales, solapamiento de reuniones, entregas, responsabilidades y condiciones de cada acuerdo. La disponibilidad concreta todavía no está cuantificada.
- La posible incorporación a Beloz sigue siendo futura según el contexto disponible; no registrarla como iniciada.

Criterios para cualificar: remuneración; producto; margen de decisión; etapa y presupuesto; dedicación real; compatibilidad con compromisos existentes. Registrar por separado compatibilidad confirmada y datos pendientes. Una buena remuneración no convierte por sí sola una oportunidad en compatible.

Estado del brief: dirección y preferencias iniciales suficientes para elaborar una propuesta de posicionamiento. Antes de aceptar oportunidades faltarán datos concretos de dedicación, condiciones y capacidad. No es necesario detener el diseño de los agentes por esos datos pendientes.

## Propuesta derivada

Ver [propuesta de posicionamiento v1](propuesta-posicionamiento-gustavo-v1.md). Es una síntesis por revisar, no un cambio de los hechos confirmados ni una aprobación automática del mensaje público.
