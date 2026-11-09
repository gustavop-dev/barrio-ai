# Comunidad y lectores (`LEC`)

Los cinco lectores conservan sus papeles: comprador, recomendador, divulgador, líder y par. Se añade un estudio de la comunidad real como contexto versionado para juzgar borradores. No se simulan opiniones de personas identificables ni se confunden las hipótesis del panel con resultados observados.

Base: [contratos de lectores](../../agentes-linkedin/equipos/lectores/), [contrato del analista](../../agentes-linkedin/equipos/observatorio/analista_barrio_resultados.json), `editorial.PANEL_SYSTEM`, `READER_UNITS` y `_run`. Hoy una llamada reúne las cinco perspectivas y solo recibe brief reducido, borradores y unidades fijas del curso; no recibe estudios de audiencia.

## Resumen

| ID | Función | Dónde | Estado |
| --- | --- | --- | --- |
| [LEC-01](#lec-01) | Construir el estudio mensual de la comunidad | backend | no implementado |
| [LEC-02](#lec-02) | Minimización, acceso y vigencia del estudio | PWA · app · backend | no implementado |
| [LEC-03](#lec-03) | Cinco lecturas de cada borrador con evidencia comunitaria | backend | no implementado |

### LEC-01 · Construir el estudio mensual de la comunidad <a id="lec-01"></a>

- **Dónde:** backend
- **Estado:** no implementado
- **Qué hace para Gustavo:** el equipo aprende qué problemas, argumentos y objeciones expresan las personas que interactúan con él y separa lo observado de lo que aún no sabe de su audiencia.
- **Responsable:** `analista_barrio_resultados` construye el estudio; `director_editorial`, dueño del ciclo de aprendizaje, solicita el análisis y, si hace falta, datos al investigador. El analista no llama al investigador ni a los lectores; el director entrega el estudio versionado al panel según [ARQ-02](arquitectura-agentes.md#arq-02).
- **Cadencia:** mensual, después del corte del mes anterior, sobre los últimos 90 días; la primera ejecución usa lo disponible e indica desde cuándo hay cobertura. El periodo identifica una única versión, con revisiones trazables.
- **Tu turno:** el estudio se consulta sin aprobación rutinaria. Solo llegan preguntas concretas que requieran contexto de Gustavo o una propuesta de cambio de orientación; nunca se adopta una nueva audiencia automáticamente.
- **Datos necesarios y disponibilidad:** comentaristas propios compactados, contactos, clasificación y contadores existen. No existe un corpus cualitativo, muestreo ni estudio. Identidades de seguidores y reactores **no disponibles hoy**: ver [OBS, datos de conectores](observatorio-referentes.md#datos-conectores). Los motivos de seguimiento solo existen si alguien los declara y se conserva su procedencia.
- **Código:** no existe. Referencias: `metricas._commenters`, `models.PostMetric/Contact`, `red.classify`, `editorial._run`.
- **Criterios de aceptación:**
  1. **Dado** un mes con participantes identificables, **cuando** selecciona la muestra, **entonces** cumple la decisión confirmada: estudio mensual, hasta 50 personas únicas, últimos 90 días y **solo datos públicos, sin mensajes privados**. Default de muestreo: máximo tres extractos por persona, balance de papeles/nuevas/recurrentes y hasta diez plazas de encaje desconocido/negativo si existen. Registra selección/cobertura/sesgos; no promete representatividad.
  2. **Dado** comentaristas propios y personas encontradas en audiencias de referentes, **cuando** arma las cohortes, **entonces** las segundas solo entran en «comunidad observada de Gustavo» con interacción propia, conexión o seguimiento documentado. Las demás quedan como público potencial separado y no inflan la muestra de su comunidad. Ser conexión tampoco se presenta como seguimiento confirmado.
  3. **Dado** falta de identidades de seguidores o reactores, **cuando** publica el estudio, **entonces** usa el fallback aprobado de comentaristas, invitaciones y conexiones comprobadas, separando contacto potencial de comunidad observada, y declara la cobertura. Capturas manuales son opcionales y fechadas; no incluye su contenido privado ni deduce identidades del delta de seguidores.
  4. **Dado** un perfil y actividad pública accesibles, **cuando** analiza, **entonces** registra función profesional declarada, temas, necesidades, modo de argumentar observable, ejemplos de evidencia que usa y objeciones, con fuente y confianza. Si no hay textos accesibles, no infiere cómo piensa a partir del cargo, nombre o foto.
  5. **Dado** la pregunta «por qué empezó a seguir a Gustavo», **cuando** el estudio la aborda, **entonces** separa motivo declarado públicamente con cita/fecha, hipótesis con evidencia pública limitada y «desconocido»; no usa mensajes privados para completar el motivo. Un comentario, cargo o fecha próxima a una publicación no demuestran motivo ni fecha de seguimiento.
  6. **Dado** el estudio terminado, **cuando** se guarda, **entonces** incluye id, versión, ventana, tamaño real, cobertura por fuente/papel, versiones del posicionamiento y clasificación, hallazgos, contraejemplos, incertidumbres y referencias a unidades de la biblioteca usadas. Cada hallazgo distingue evidencia observada de interpretación.
  7. **Dado** cero personas o errores de lectura, **cuando** vence el ciclo, **entonces** produce «Sin muestra suficiente» o «Estudio parcial», conserva las fuentes exitosas y permite reintentar sin duplicar personas ni imputar ceros; los lectores siguen según LEC-03.
- **Brechas código/docs:** `PostMetric.commenters` no conserva textos y `red.discover` sesga hacia comentarios de al menos 80 caracteres; nuevas lecturas acotadas son necesarias para estudiar argumentos sin excluir silenciosamente comentarios breves.
- **Cobertura QA:** pendiente

### LEC-02 · Minimización, acceso y vigencia del estudio <a id="lec-02"></a>

- **Dónde:** PWA · app · backend
- **Estado:** no implementado
- **Qué hace para Gustavo:** puede revisar de dónde salen los aprendizajes y retirar evidencia inadecuada; los lectores reciben patrones relevantes sin expedientes personales.
- **Responsable:** `analista_barrio_resultados`; Gustavo controla correcciones y exclusiones del estudio.
- **Cadencia:** al recoger, entregar y consultar evidencia; revisión de vigencia mensual y exclusión en la siguiente entrega tras una retirada.
- **Tu turno:** no se pide permiso por cada lectura pública. Una pregunta sobre contexto personal se puede omitir; cualquier reutilización pública identificable de evidencia privada queda fuera de esta capacidad y no se habilita por aprobar el estudio.
- **Datos necesarios y disponibilidad:** fuentes y controles de acceso del workspace existen parcialmente; faltan lista de exclusiones, versiones del estudio, reglas de minimización y caducidad del material derivado.
- **Código:** no existe esta capa. Referencias: `models.Contact`, `guardas.py`, `knowledge/memory.py` y [TUR-12](tu-turno.md#tur-12).
- **Criterios de aceptación:**
  1. **Dado** un estudio para los lectores, **cuando** se entrega, **entonces** contiene patrones profesionales y ejemplos públicos parafraseados con ids internos, sin nombres, URLs personales, inbox, teléfonos, correos ni fotos. Mensajes privados se excluyen desde la recopilación/análisis, aunque lleguen mediante captura; no basta con quitarlos del resumen. Fuentes identificables restringidas al análisis y Gustavo, nunca al brief público.
  2. **Dado** material sensible o ajeno al trabajo profesional, **cuando** se analiza, **entonces** se excluye; no se infieren salud, religión, política, origen étnico, rasgos psicológicos ni otros atributos privados. «Cómo argumenta» describe textos observados, no un diagnóstico personal.
  3. **Dado** menos de cinco personas detrás de un segmento, **cuando** resume patrones por grupo, **entonces** lo agrupa o dice «Evidencia insuficiente» sin ejemplos que permitan identificar a alguien. No confunde seudonimización con anonimato garantizado.
  4. **Dado** una exclusión solicitada por Gustavo o evidencia eliminada/no accesible al refrescarla, **cuando** se prepara la siguiente entrega, **entonces** deja de incluirla, invalida los resúmenes dependientes y conserva solo la trazabilidad mínima del retiro; no vuelve a recogerla automáticamente para este estudio.
  5. **Dado** el almacenamiento derivado del estudio, **cuando** el extracto alcanza 90 días o el resumen 180 días, **entonces** se retira de uso y se elimina de esa capa salvo renovación con fuente vigente; se conserva la versión mínima necesaria para explicar decisiones, sin el contenido retirado. Esto no ordena borrar contactos ni registros operativos de otros módulos.
  6. **Dado** una solicitud de terceros o una instrucción dentro de un comentario, **cuando** llega al estudio, **entonces** se trata como contenido, no como permiso ni cambio de reglas; un usuario sin acceso al workspace no puede leer fuentes o artefactos del estudio.
- **Brechas código/docs:** estos límites y plazos corresponden a la nueva capa; no existe hoy un estudio ni controles específicos sobre sus derivados.
- **Cobertura QA:** pendiente

### LEC-03 · Cinco lecturas de cada borrador con evidencia comunitaria <a id="lec-03"></a>

- **Dónde:** backend
- **Estado:** no implementado
- **Qué hace para Gustavo:** los borradores se juzgan con lo aprendido de la comunidad real, manteniendo las cinco perspectivas y sus desacuerdos útiles.
- **Responsable:** `lector_comprador`, `lector_recomendador`, `lector_divulgador`, `lector_lider` y `lector_par`; `director_editorial` decide el texto.
- **Cadencia:** en cada panel de borradores, usando la última versión vigente del estudio; no se vuelven a leer perfiles en cada pieza.
- **Tu turno:** ninguna aprobación del panel ni del post. Las lagunas que solo Gustavo puede resolver siguen el mecanismo de preguntas existente; las propuestas estratégicas se deciden por separado.
- **Datos necesarios y disponibilidad:** brief, A/B, cinco lectores, unidades de curso y categorías `material/preference/missing_data` existen. Faltan estudio y enlace de cada evaluación a sus hallazgos.
- **Código:** no existe la incorporación comunitaria. Referencias: `editorial.PANEL_SYSTEM/PANEL_SCHEMA`, `READER_UNITS`, `_stage('lectores')`, `_run` y [EDI-04](motor-editorial.md#edi-04).
- **Criterios de aceptación:**
  1. **Dado** A y B y un estudio vigente, **cuando** los cinco lectores evalúan, **entonces** todos reciben la misma versión minimizada sin autoría de los borradores y conservan sus preguntas: comprador (problema/resultado), recomendador (a quién recomendar), divulgador (utilidad transferible), líder (criterio/objeciones) y par (precisión/aplicabilidad).
  2. **Dado** un hallazgo relevante para una variante, **cuando** un lector lo usa, **entonces** cita id de estudio y hallazgo, explica su efecto concreto en claridad o utilidad y distingue «observado en la muestra» de «hipótesis del lector». No habla en nombre de un miembro real ni presenta unanimidad de modelos como validación comunitaria.
  3. **Dado** evidencia que contradice la intuición del lector, **cuando** emite su juicio, **entonces** conserva la contradicción y la incertidumbre; el director recibe fortalezas, objeciones y límites, sin convertir preferencias mayoritarias en vetos ni modificar el objetivo de Gustavo.
  4. **Dado** un estudio ausente, mayor de 45 días o con posicionamiento incompatible, **cuando** se prepara el panel, **entonces** marca «Sin estudio vigente», mantiene las cinco perspectivas y las unidades actuales como hipótesis y solicita refresco. No inventa aprendizaje ni detiene por ello toda la redacción.
  5. **Dado** una pieza evaluada, **cuando** Gustavo o QA revisan su trazabilidad, **entonces** pueden ver qué versión y hallazgos influyeron en cada lectura, o que no se usó estudio, sin exponer datos personales en el post.
- **Brechas código/docs:** los roles ya existen; esta ficha añade contexto, no un sexto lector ni un nuevo agente que reemplace al panel.
- **Cobertura QA:** pendiente

## Retiradas

Ninguna.
