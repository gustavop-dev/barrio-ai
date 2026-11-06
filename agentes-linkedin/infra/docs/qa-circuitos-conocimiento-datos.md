# QA independiente: conocimiento y datos externos

Fecha: 2026-11-06. Revisión documental independiente del diseño. No se ejecutaron agentes, proveedores, conectores, publicación, pruebas del backend ni cambios del corpus. Se leyó `infra/AGENTS.md`. La única escritura de esta revisión es este informe.

## Dictamen y alcance

Sin P1 identificado. Un P2 de semántica del dato externo fue comunicado, corregido por el orquestador y vuelto a comprobar; no quedan P1/P2 abiertos en el alcance de esta revisión. Los contratos conservan la distinción entre evidencia del curso, decisiones propias de arquitectura, datos del usuario, hipótesis y observación real. Este resultado no acredita funcionamiento en runtime ni lectura integral F1.

Revisados los 13 contratos de `equipos/observatorio/`, `editorial/`, `lectores/`, `revision/` y `estrategia-perfil/contratos-v1/`; registros de lectura de Editorial, Observatorio y `arquitectura/lectura-contratos-root-v1.json`; catálogo de Editorial. Documentos revisados: `circuitos-equipo.md`, `datos-externos-por-equipo.md`, `ciclo-editorial.md`, `ciclo-lectores.md`, `ciclo-revision.md`, `ciclo-estrategia-perfil.md`, `plan-equipo-autonomo.md` y `recorrido-mesa-equipo-completo.md`.

También se revisó completo `ciclo-observatorio-aprendizaje.md` cuando terminó su escritura. Su separación entre investigación inicial, escucha real, rendimiento posterior a publicación, propuestas de participación orgánica y experimentos conserva las necesidades de datos y límites de los contratos individuales. No surgieron hallazgos adicionales P1/P2.

## P2-KD-01: ausencia de confirmación no acredita que el perfil no se aplicó

- **Localización:** `equipos/estrategia-perfil/contratos-v1/perfil.json`, `datos_externos[catalogo_id=D11].si_falta`, línea 363 de la versión revisada: `mantener aplicado=false`.
- **Problema:** `false` expresa una negación, mientras que falta la evidencia para saber si Gustavo aplicó el cambio fuera del sistema. Contradice `circuitos-equipo.md`, tabla de handoffs, que exige conservar «aprobado pero aplicación desconocida», y la instrucción general `si_falta_informacion` del mismo Perfil de conservar `unknown`.
- **Ejemplo reproducible de mesa:** dirección y texto aprobados; Gustavo cambia manualmente el perfil; todavía no aporta D11. Aplicar literalmente el fallback produce `aplicado=false`, aunque el estado externo real es desconocido para el equipo. Una posterior comparación podría tratar incorrectamente el periodo como anterior a la aplicación.
- **Solución propuesta:** representar `application_status=unknown` o `aplicado=null` más `confirmation_status=pending`; reservar `false/no_aplicado` para una confirmación negativa explícita. Sin D11 no atribuir métricas al cambio ni afirmar ausencia de aplicación. Añadir este ejemplo a la evaluación documental de Perfil.
- **Estado:** resuelto por el orquestador y comprobado mediante lectura posterior del JSON. El fallback vigente dice: `mantener aplicación desconocida (null); solo false si hay confirmación explícita de no aplicación`. La reproducción ahora conserva incertidumbre y coincide con el circuito transversal. No se editaron contratos desde esta revisión.

## Evidencia de conocimiento

Consultas a través de `knowledge.db.connect`, desde `infra` con `uv run python`, dentro de transacciones `SET TRANSACTION READ ONLY`:

- 104 referencias de las fichas corresponden a 57 unidades únicas: todas existen, están activas y tienen `sha256`, `source_path` y `pointer` coincidentes. Ninguna referencia corresponde a clase07 o posterior.
- Los identificadores de evidencia con prefijo de clase coinciden, retirando únicamente ese prefijo, con `original.source_ids` de las unidades correspondientes. No se encontraron fuentes ajenas añadidas a la cita.
- Los 13 contratos permiten clases01–06 y declaran `acceso_no_exclusivo=true`. La especialización no constituye propiedad exclusiva de una unidad.
- Se leyeron completos seis `original`, sin sustituirlos por títulos: `LI-01-M006-K02`, `LI-02-V019-K01`, `LI-03-M005-K05`, `LI-04-M007-K03`, `LI-06-M003-K06` y `LI-06-V009-K04`. Sus interpretaciones muestreadas conservan las excepciones: cuantificación solo con base; trayectoria real; papeles no excluyentes; 60/40 del adjunto distinto de prioridades de Gustavo; filtro humano; personas únicas diferentes de impresiones, sin confirmar conjeturas sobre IP.

La comprobación de las 57 identidades/hashes no equivale a leer sus 57 originales. La muestra de seis no prueba retrospectivamente todos los actos de lectura declarados por los autores; sí permite contrastar la fidelidad de las interpretaciones seleccionadas. Los registros limitan su cobertura a unidades seleccionadas y mantienen F1 parcial. No se inspeccionaron aquí imágenes originales ni se comprobó nuevamente todo el corpus contra sus archivos de origen.

Los cinco papeles proceden de clase03; convertirlos en cinco lectores, disponer dos escritores, centralizar research, usar hashes/ACK y limitar rondas son decisiones declaradas de arquitectura. El curso no se usa como prueba de tendencias actuales, capacidades de API, rendimiento de formatos o resultados de Gustavo.

## Cobertura de datos externos y límites

| Grupo | Datos y necesidad comprobados | Frescura, permiso y ausencia |
| --- | --- | --- |
| Estrategia/Perfil | D01 contexto; D02 perfil para auditoría; D03 prueba por afirmación; D04/D10 contraste; D09 voz; D11 aplicación | Catálogo común conserva versiones/fechas; sin perfil solo propuesta; sin pruebas omisión/pendiente; D11 corregido conserva desconocido sin confirmación |
| Observatorio investigador | OBS-EXT-01 perfiles; 02 posts/comentarios; 03 contraste sectorial; identidad, función, evidencia de audiencia, fuentes, muestra, fechas, dependencia entre fuentes | Actividad/cargo/distintivo revalidados; permisos de acceso y uso separados; sin datos plan de búsqueda; no nombres, tendencias o métricas privadas inventados |
| Observatorio analista | OBS-EXT-04 red/composición; 05 versión publicada; 06 métricas; 07 conversación; 08 oportunidades por modalidad | Ventana/definición/contador; null distinto de cero; no sumar snapshots o personas únicas; fragmentos autorizados; cualificación pendiente sin presupuesto/dedicación; origen desconocido no implica causalidad |
| Editorial | Evidencia de demanda, casos con contribución personal/equipo, voz, assets y resultados derivados | Uso condicionado a afirmación/formato; permiso de recurso distinto de crédito; voz provisional explícita; sin historial permite borrador; sin asset texto o espera |
| Lectores | D06 lenguaje anonimizado, D03 prueba citada, D09 voz, recibidos en paquete | Ninguna cuenta propia; faltantes producen juicio provisional; cinco opiniones simuladas nunca se convierten en muestra real de audiencia |
| Revisión | D03 hechos, D09 voz/recursos, D12 actualidad | Evidencia privada no autoriza publicación; pide contraste a Observatorio; omite o espera afirmación sin prueba; visto bueno documental no equivale a publicación |

Comentarios, reacciones, alcance, referentes, tendencias y oportunidades tienen destino y función distintos. El investigador conserva sesgos de selección y dependencia de fuentes; el analista separa exposición, interacción, composición y negocio. Un comentario permite proponer una pieza, pero no demostrar demanda del mercado. Las oportunidades personales y ProjectApp conservan modalidad, etapa y compatibilidad, sin mezclar salario personal con tarifa del equipo.

No se detectó acceso privado indiscriminado exigido por el diseño. Datos comerciales, identidad de contactos y conversaciones completas no pasan por defecto a escritores/lectores. Se prohíben inferencias de idioma/etnia por nombre o foto. La actualidad se revalida al usarla; la frecuencia, caducidad operativa y conectores siguen pendientes de configuración y verificación, sin presentarlos como capacidad activa.

## Límites y siguiente comprobación

Los recorridos son razonamientos de mesa con escenarios identificados, no pruebas de comportamiento. No se revisó exhaustivamente coordinación técnica, responsabilidad de cada evento o compatibilidad de esquemas: corresponde a la otra revisión independiente. No se llamaron APIs externas para investigar mercado o validar disponibilidad de LinkedIn porque esta tarea es documental.

Antes de activar, sigue pendiente completar la lectura pertinente F1, concretar políticas de datos y evaluar recuperación/comportamiento. Estos pendientes están declarados en el diseño; no se presentan como defectos descubiertos ni como fases ya realizadas.
