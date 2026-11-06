# Lemlist y Unipile para Barrio AI

Investigación del 6 de noviembre de 2026, solicitada por Gustavo para decidir si lemlist sustituye a Unipile y si aporta acceso a la base de Sales Navigator. Fuentes públicas primarias; no se conectaron cuentas ni se probaron resultados reales. Complementa la [selección v2](herramientas-linkedin-v2.md), sin sustituirla ni modificar contratos de agentes.

## Conclusión para nuestro diseño

La recomendación sigue siendo **Unipile como conector operativo de la cuenta**. Lemlist aporta una plataforma de prospección más preparada: base B2B, enriquecimiento, señales y campañas. Puede ser una fuente complementaria valiosa, pero la documentación revisada no demuestra que sustituya todas las operaciones que necesita nuestro equipo.

La decisión depende del propósito: gestionar conversaciones, contenido y relaciones desde nuestros ciclos favorece Unipile; operar campañas multicanal con una base de contactos y herramientas de entrega de correo ya integradas favorece lemlist. Esta es una valoración de encaje, no una prueba comparativa de calidad de datos.

## No son la misma base de datos

Lemlist describe People Database como una agregación de perfiles públicos de LinkedIn, con enriquecimiento adicional. No se encontró evidencia de que sea una licencia de la base de Sales Navigator ni una copia completa y sincronizada de ella. La comparación comercial con Sales Navigator no acredita esa equivalencia. Consultar People Database no se documenta como dependiente de una licencia Sales Navigator. [Origen y uso de los datos](https://help.lemlist.com/en/articles/8255808-use-the-people-database).

Sí es accesible para nuestros agentes: `POST /api/database/people` permite buscar con filtros y paginación y devuelve, entre otros campos, enlaces de LinkedIn. [API People Database](https://developer.lemlist.com/api-reference/endpoints/people-database/search-people-database). La web comercial anuncia 650M+ registros mientras la ayuda conserva 450M+; no usamos esos tamaños como evidencia de calidad o cobertura del nicho.

Unipile declara que no mantiene una base independiente: consulta lo accesible a la cuenta conectada. [Explicación del proveedor](https://www.unipile.com/data-extraction-and-enrichment/). Permite búsquedas de personas en LinkedIn Classic y Sales Navigator, mediante filtros o URL de búsqueda. **Sales Navigator requiere la suscripción correspondiente en la cuenta; Unipile no la incluye.** [Búsqueda v2](https://developer.unipile.com/v2.0/docs/linkedin-search-users), [productos y suscripciones](https://developer.unipile.com/v2.0/docs/linkedin-link-accounts).

Por tanto, Unipile sí permite buscar perfiles para incorporarlos al barrio sin comprar otra base. Classic sirve para iniciar; Sales Navigator amplía los filtros cuando tengamos esa licencia. La amplitud de datos sigue limitada por cuenta, producto y operación.

## Comparación de capacidades relevantes

| Necesidad | Lemlist | Unipile | Consecuencia para Barrio AI |
| --- | --- | --- | --- |
| Buscar personas y empresas | Base B2B propia accesible por API | Búsqueda sobre LinkedIn de la cuenta, incluyendo Sales Navigator con licencia | Ambas vías sirven para descubrir candidatos; no garantizan los mismos resultados ni actualidad. |
| Obtener emails y teléfonos | Enriquecimiento de pago mediante proveedores | Datos de contacto visibles a la cuenta; no sustituye un proveedor de enriquecimiento | Ventaja de lemlist si necesitamos canales externos a LinkedIn. |
| Encontrar participantes de posts | API que devuelve personas que comentaron/reaccionaron | Métodos de posts, comentarios y reacciones | Ambas pueden aportar candidatos al barrio. |
| Invitaciones y mensajes | Pasos de secuencia y envío por inbox documentados | Operaciones de cuenta e invitaciones independientes de campañas | Ambas cubren contacto; cambia quién controla el proceso. |
| Conversaciones orgánicas entrantes | La ayuda limita el inbox a conversaciones iniciadas en lemlist | Lista inboxes/chats de la cuenta, sin exigir que nazcan en una campaña | Límite material de lemlist para nuestro requisito de atender la cuenta completa. |
| Comentar y gestionar hilos | La función revisada de comentar el último post genera una tarea manual | Creación, respuesta, edición y borrado de comentarios documentados | No tratar la función manual de lemlist como API genérica para cualquier hilo. |
| Editar perfil, seguir y gestionar relaciones | No se verificó equivalencia general en el catálogo público | Existen métodos específicos, con los límites ya registrados en v2 | Unipile ofrece más operaciones útiles para los ciclos propios. |
| Campañas de email + LinkedIn y entregabilidad | Producto ya preparado | Conector; la secuencia, reglas y operación corresponden a nuestra aplicación | Lemlist es más completo como producto de outbound. |
| Integración con Claude | API y MCP | API y MCP | Ambos se pueden integrar; MCP no decide por nosotros la autoridad ni la memoria. |

Referencias de operaciones: [participantes de posts en lemlist](https://developer.lemlist.com/api-reference/endpoints/people-database/search-linkedin-post-engagers), [pasos de secuencia](https://developer.lemlist.com/api-reference/objects-definitions/step), [envío de mensajes](https://developer.lemlist.com/api-reference/endpoints/inbox/send-linkedin-message), [límite del inbox](https://help.lemlist.com/en/articles/10035229-use-the-lemlist-inbox), [comentario como tarea manual](https://help.lemlist.com/en/articles/15062863-how-to-add-a-comment-last-post-step-to-a-sequence), [operaciones de Unipile](https://developer.unipile.com/v2.0/docs/list-provider-features), [chats de cuenta en Unipile v2](https://developer.unipile.com/v2.0/docs/linkedin-quickstart), [MCP de lemlist](https://www.lemlist.com/product/lemlist-mcp).

No encontrar un método en el catálogo consultado no prueba imposibilidad. Sí impide dar por verificada la sustitución. La disponibilidad comercial tampoco garantiza que cada función esté expuesta con el mismo alcance en su API.

## Valor específico para nuestro nicho

Lemlist ofrece señales de empresas que levantaron fondos, contratación, cambios de empleo y actividad relacionada con perfiles o temas. Esto tiene relación directa con founders de startups financiadas y posibles oportunidades para Gustavo. Hay además seguimiento de la audiencia que interactúa con referentes. [Signal Agents](https://help.lemlist.com/en/articles/14321798-signal-agents-overview), [seguimiento de referentes](https://help.lemlist.com/en/articles/14076306-how-to-set-up-an-influencer-engagement-signal-agent-in-lemlist).

Son candidatos útiles como entrada del Observatorio; no equivalen por sí solos a presupuesto disponible, intención de contratar a Gustavo ni afinidad con el barrio. La señal y su fecha deben contrastarse. En Unipile obtendríamos actividad accesible y nuestro Observatorio tendría que componer esas señales con fuentes externas.

Para buscar, combinar cargo, compañía, ubicación y actividad; comprobar idioma declarado cuando exista. El idioma del perfil no demuestra todos los idiomas hablados, y un apellido no es evidencia de afinidad cultural. Ninguno de los proveedores entrega una lista ya validada de nuestros compradores, divulgadores y aliados.

## Costes comparables

Precios públicos consultados en esta fecha, antes de impuestos y sin consumo de modelos, infraestructura o extras. No constituyen contratación ni presupuesto autorizado.

| Opción | Referencia mensual | Qué aporta |
| --- | --- | --- |
| Unipile | USD 55, o EUR 49 según moneda de facturación, mínimo hasta diez cuentas | Conector con búsqueda Classic; no incluye Sales Navigator. |
| Unipile + Sales Navigator Core | Desde USD 174,99 sumando tarifas mensuales USD | Conector más búsqueda avanzada de la cuenta. Core aparece desde USD 119,99/mes; precio local puede variar. |
| Lemlist Multichannel | USD 109 por usuario/mes; USD 87/mes equivalente con facturación anual | Base y plataforma de campañas con automatización LinkedIn; datos y señales pueden requerir extras/créditos. |
| Unipile + lemlist Email como fuente de datos | USD 124/mes sumando USD 55 + USD 69, antes de extras | Hipótesis de complemento: el plan Email anuncia base y API. Validar acceso, límites de búsqueda/exportación y señales concretas antes de elegirlo. No activa automatización LinkedIn de lemlist. |

Fuentes: [Unipile](https://www.unipile.com/pricing-api/), [LinkedIn](https://business.linkedin.com/sell/sales-navigator/compare-plans), [lemlist](https://www.lemlist.com/pricing), [créditos](https://help.lemlist.com/en/articles/8944295-credits-how-they-work). No se garantiza un coste por señal a partir de anuncios generales: las páginas de precios y ayuda muestran modalidades distintas, por lo que hay que comprobar el presupuesto efectivo de la cuenta al probarlas.

## Recomendación y criterio de prueba

Mantener Unipile para el primer circuito del barrio. No contratar Sales Navigator y lemlist a la vez por defecto. Cuando la búsqueda Classic resulte insuficiente, comparar **Sales Navigator sobre Unipile** y **People Database de lemlist como fuente adicional**, conservando la misma ejecución y memoria en Django.

La comparación debe usar los mismos perfiles objetivo y medir: pertinencia de candidatos, datos vigentes, enlaces utilizables, presencia de idioma/evidencias de financiación, participantes relevantes del barrio, duplicados, coste y tiempo por candidato útil. No se ejecutó este piloto ni se extrajeron prospectos en esta investigación.

Si se usa lemlist solo como fuente, la cadena propuesta sería: búsqueda/señal → Observatorio → evaluación de pertinencia → memoria compartida → acción autorizada mediante Unipile. Evitar dos motores enviando invitaciones o mensajes al mismo contacto. Las campañas de la segunda mitad del curso siguen fuera del alcance implementado; se podrá evaluar lemlist como ejecutor de campañas cuando se diseñe esa fase.

Las decisiones de publicación oficial, programación propia, imágenes y analítica con permisos de v2 permanecen. La analítica de campañas de lemlist no demuestra cobertura del panel privado de contenido de LinkedIn. La limitación de uso de intermediarios ya documentada en v1/v2 sigue aplicando; ninguno se presenta como acceso oficial ilimitado a LinkedIn.
