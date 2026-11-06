# Datos externos: observación continua de LinkedIn y contexto del equipo

Estado: diseño de necesidades, sin conexiones habilitadas ni permisos efectivos verificados. Las capacidades documentadas de proveedores se distinguen de una integración probada. Este es el catálogo transversal que complementa [datos y resultados](datos-y-resultados-del-equipo.md). Clases01–06; outbound no activado.

Aclaración vigente de Gustavo: el equipo debe comprender la actividad de su cuenta como si trabajara dentro de ella, con acceso contextual a publicaciones, métricas, audiencia, conversaciones y referentes del nicho. La capacidad objetivo es consultar y sincronizar estas fuentes de forma continua; los aportes manuales son un recurso de arranque o recuperación. El diseño ampliado está en [observación integral de LinkedIn](observacion-integral-linkedin.md), con métricas, herramientas, ciclos y comprobación documental de APIs. Las integraciones todavía no están conectadas. Acceso para observar y autoridad para actuar se mantienen separados.

## Diccionario de entradas

| ID | Datos y campos concretos | Origen candidato | Consumidores y decisión | Necesidad y alternativa |
| --- | --- | --- | --- | --- |
| D01 | Objetivos, prioridades, ofertas, dedicación, preferencias, correcciones; autor, fecha, versión y estado confirmado/provisional | Gustavo | Estrategia; porciones pertinentes para todos | Obligatorio para dirección; falta puntual produce pregunta agrupada, sin inventar |
| D02 | Perfil actual: titular, acerca de, experiencias, destacados, banner/foto, idioma, fecha de captura | Copia/exportación/capturas aportadas; lectura autorizada si disponible | Perfil y Revisión: diagnóstico y comparación | Obligatorio para auditar perfil real; sin él solo propuesta nueva |
| D03 | Fichas de casos: problema, decisión, contribución personal/equipo, estado desarrollo/producción, resultado, medición, fuente y permiso de uso | Repos/docs, notas de Gustavo, informes autorizados | Estrategia, Editorial, escritores y Revisión | Obligatorio por afirmación factual; omitir cifra/caso no sustentado |
| D04 | Referentes: URL/ID, función, organización, especialidad, temas, idioma declarado, evidencia de pertinencia de audiencia; fecha y grado de certeza | Perfiles y páginas públicas accesibles, lista aportada | Investigador: seleccionar referencias y espacios de conversación | Necesario para investigación de referentes; sin acceso, registrar selección incompleta. Insignia Top Voice opcional, no requisito |
| D05 | Posts ajenos: autor, enlace, fecha, texto/extracto, tema, formato, contexto, métricas visibles con fecha de captura | Enlaces/texto aportados o acceso público autorizado | Investigador y analista: estudiar conversación y ángulos | Necesario para analizar ese post; impresiones/guardados privados no se inventan. Likes visibles no prueban audiencia objetivo |
| D06 | Comentarios y respuestas: vínculo al post/hilo, fecha, texto mínimo, contexto y rol profesional conocido/no conocido; reacción observable | Selección aportada o lectura autorizada | Observatorio: problemas, lenguaje, objeciones; Editorial recibe extractos permitidos; Revisión recibe contexto suficiente para comentarios propuestos | Necesario para atribuir hallazgo a conversación real; sin él mantener hipótesis. No extrapolar una muestra a todo el nicho |
| D07 | Posts propios: ID/URL, texto y assets finales, fecha real, versión de brief/estrategia, audiencia prevista, objetivo, formato y cambios | Registro de publicación confirmado por usuario o integración verificada | Analista: vincular rendimiento con versión efectivamente publicada | Obligatorio para afirmar que una pieza se publicó; borrador aprobado no basta |
| D08 | Métricas propias disponibles: impresiones, miembros alcanzados, reacciones, comentarios, compartidos, guardados, visitas, seguidores y composición; definición, intervalo, captura, ámbito y tipo de contador | Entrada manual, captura validada, archivo exportado cuando exista o API autorizada a verificar | Analista: exposición, respuesta y composición; agregados a Estrategia/Editorial | Obligatorias solo para la afirmación métrica correspondiente. null ≠ 0; no presumir lista nominal de visitantes/seguidores ni disponibilidad de todos los campos |
| D09 | Voz y recursos: notas de voz/transcripción, textos propios representativos, opiniones confirmadas, casos narrables, imágenes/video/derechos, restricciones de cliente | Gustavo y repositorio de recursos autorizados | Escritores, Perfil y Revisión; lector recibe lo mínimo | Para autenticidad y medios; sin voz propia, borrador provisional. Sin asset, texto o espera; no fingir anécdotas |
| D10 | Conversaciones/oportunidades: ID, canal, fecha, necesidad expresa, modalidad, etapa, origen conocido/desconocido, presupuesto, dedicación, compatibilidad, objeciones y desenlace | Registro de Gustavo; CRM/correo/agenda/mensajes solo si se habilitan | Analista y Estrategia: oportunidades pertinentes por modalidad | Necesario para medir negocio. Escritores reciben patrones anonimizados; sin registro no concluir cero oportunidades |
| D11 | Decisiones externas: aprobación de versión exacta, confirmación de cambio de perfil/publicación, rechazo/cancelación, fecha, enlace/evidencia y versión efectivamente aplicada | Gustavo; adaptador autorizado y verificado posteriormente | Orquestador, Perfil, Editorial y analista | Obligatorio para transiciones externas; espera sin repetir llamadas ni asumir publicación |
| D12 | Tendencias/hechos actuales: pregunta, consulta, fuente primaria, URL, extracto, fechas de publicación/evento/acceso, alcance, contradicciones y posible caducidad | Fuentes públicas especializadas, documentación oficial, informes, conversación sectorial | Investigador; Revisión pide comprobación; Editorial recibe evidencia | Necesario si se afirma actualidad/tendencia. Sin serie temporal decir tema observado, no tendencia medida; sin fuente omitir afirmación o tratar como pregunta |

Los textos completos del curso, su índice y los artefactos internos no son datos externos nuevos. Se consultan desde memoria y biblioteca con versiones.

## Qué acceso necesita cada grupo

| Grupo | Acceso directo mínimo | Material derivado que recibe | Lo que no necesita por defecto |
| --- | --- | --- | --- |
| Estrategia/Perfil | D01, D02 y D03 pertinentes; D11 | Hallazgos D04–06/08/10 preparados por Observatorio | Cada mensaje privado o todas las métricas crudas |
| Observatorio | D04–08, D12; D07/11 para resultados propios; D10 autorizado | Objetivo, audiencia y restricciones D01 | Contraseñas, datos de contacto irrelevantes o ingresos detallados para analizar temas |
| Editorial | D03 y D09 permitidos | Paquetes D04–06/08/10/12 con alcance y fuentes | Buscar tendencias duplicadamente, navegar buzones o cambiar hechos personales |
| Lectores | Ninguna cuenta externa | Brief, borradores, muestra de audiencia D06 y evidencia pública pertinente | Identidades de contactos, compensación y conversaciones privadas completas |
| Revisión | D03/D09 pertinentes, D06 para comentario orgánico y fuentes citadas | Verificación D12 solicitada al Observatorio; evaluación de lectores | Acceso indiscriminado a cuentas; aprobación de publicación por sí mismo |

Equivalencias con el catálogo del Observatorio: OBS-EXT-01→D04; 02→D05/D06; 03→D12; 04→D08 (red/composición); 05→D07/D11; 06→D08; 07→D06/D10; 08→D10. Sus contratos detallan necesidades condicionadas por tarea. IDs locales de Editorial se remiten por significado a este diccionario; ningún alias implica duplicar almacenamiento.

## Frescura, calidad y comparabilidad

- D01/D02/D09: conservar versión y fecha; una corrección del autor invalida dependientes afectados. Antes de preparar cambios del perfil, comprobar que la captura sigue representando el estado actual.
- D03: el hecho histórico no vence automáticamente, pero cambian el estado de despliegue, permisos de uso y alcance de una métrica. Registrar fecha del resultado y de la verificación.
- D04–D06/D12: registrar consulta/muestra/fecha; actualidad se comprueba al usarse en una afirmación temporal. Una fuente inaccesible o sin fecha limita la conclusión. Sin periodo comparable no afirmar crecimiento de una tendencia.
- D07/D11: almacenar lo realmente aplicado, incluidos cambios manuales posteriores. Si difiere del aprobado, no reutilizar el visto bueno ni atribuir el resultado al texto no publicado.
- D08: ventanas y edad de posts comparables; alcance por post no se suma como personas únicas. Ratios calculados en código con fórmula/denominador visible. Capturas acumuladas no se suman.
- D10: conservar historial de etapas y origen de oportunidad. Entrevista, oferta, contrato e ingreso son eventos distintos. Presupuesto o disponibilidad desactualizados quedan por confirmar.

Frecuencia de captura, ventanas y presupuesto quedan pendientes de acordar con la línea base; no se activa sondeo diario por el deseo de publicar diario.

## Secuencia inicial de datos, complementada por sincronización continua

1. Contexto confirmado, estado de perfil y dos o tres casos/ejemplos de voz autorizados (D01–03/D09).
2. Muestra inicial de referentes y conversaciones pertinentes (D04–06), con trazabilidad y límites. Se puede arrancar sin analytics propios.
3. Registro real de publicaciones/cambios (D07/D11) y una línea base de campos disponibles de D08.
4. Registro simple de oportunidades por modalidad (D10), sin exigir mensajes completos.
5. Habilitar los conectores de observación como capacidad central, tras verificar campos, acceso y costes. Importar historial y continuar con sincronización incremental; no convertir la captura manual en el flujo objetivo. Investigación actual D12 se usa cuando la pieza la necesita.

Estas categorías son necesidades del sistema, no un cuestionario para que Gustavo produzca reportes manuales. La investigación comercial real, concesión de accesos y publicación permanecen sin ejecutar. La revisión de observación integral es posterior al QA v1 de este catálogo.
