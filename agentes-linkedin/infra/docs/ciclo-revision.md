# Ciclo de revisión y salida al usuario

Estado: diseño propuesto. Agente `editor_verificador`, ficha en `equipos/revision/`. Fuentes: LI-06-M002-K09/K10, LI-06-M003-K06, LI-02-V019-K01. La guía aporta criterios editoriales; nuestras severidades, eventos y límite de rondas son arquitectura propia.

## Entradas y activación

`candidate_selected` (post), `profile_proposal_ready` (perfil) u `organic_participation_proposed` (borrador de comentario contextual del analista): candidato con hash exacto; brief/dirección vigentes; registro de decisión editorial cuando corresponda; pruebas por afirmación; permisos de uso de recursos; voz confirmada y objeciones no resueltas. Sin pruebas de una afirmación accesoria, proponer omisión; sin brief o dirección aceptada, devolver dependencia.

Para participación orgánica se recibe `organic_participation_proposal`: referencia del hilo, contexto leído con versión/hash y fecha, propósito y pertinencia, borrador exacto, afirmaciones, fuentes y permisos. D06 aporta contexto suficiente del hilo; un fragmento aislado no autoriza inferir el resto. Si falta contexto se devuelve `needs_evidence` al analista. Si cambia el hilo se marca la dependencia afectada como desactualizada. La revisión conserva el carácter de propuesta: pasa a Gustavo y nunca envía el comentario.

D03 sostiene hechos y contribución personal/equipo. D09 sostiene voz y assets. D12 es necesario si se afirma actualidad. No necesita ver todo el CRM ni cifras salariales. Si la evidencia es privada, comprobar permiso para el texto derivado: acceso interno no es permiso de publicar la fuente. Se puede redactar un aprendizaje general o anonimizado sin divulgar detalles.

## Decisiones y entregables

1. Comprobar identidad/versión, propósito, origen de cada afirmación y separación hecho/opinión/ejemplo.
2. Revisar que gancho y texto concuerden, que exista utilidad y claridad y que la modalidad ofrecida sea la correcta.
3. Contrastar cifras con evidencia y condiciones (muestra, periodo, desarrollo versus producción). La coincidencia entre modelos no verifica una cifra.
4. Clasificar hallazgos. Material: falsedad, prueba esencial ausente, exposición privada, promesa incumplida, contradicción de oferta, entrada obsoleta. Menor: gusto estilístico sin efecto material. Aplicar la guía en contexto, sin bloquear por porcentajes mecánicos de recorte o preferencias de puntuación.
5. Emitir `review_record` ligado al hash: `ready_for_human`, `needs_revision`, `needs_evidence` o `discard_recommended`, con dueño y motivo por hallazgo. Revisión no aprueba públicamente en nombre de Gustavo.
6. Si pasa, crear `approval_package`: texto exacto, assets y permisos, fuentes relevantes, modalidad, límites y qué decisión se solicita. Gustavo conserva filtro de voz y lectura final.

## Devoluciones y publicación

Forma/claridad → Director o Perfil; aporte/contexto de comentario → analista del Observatorio. Hechos actuales → solicitud agrupada al Observatorio. Experiencia personal → autor mediante orquestador. Cambio de audiencia → Posicionamiento; no resolverlo alterando el post silenciosamente.

Dos rondas globales correctivas por pieza: mismo contador de Editorial y Lectores. Omitir una afirmación requiere una ronda disponible. Tras agotarlo, descartar o esperar evidencia; no aprobar por fatiga. Revisor no rehace el post sin pasar la versión nueva por los controles afectados. Un cambio de copy/asset invalida el visto bueno previo.

Aprobación humana de texto exacto (`content_approved`) permite formar un paquete listo para aplicación. No autoriza un adaptador de publicación inexistente. En fase inicial Gustavo publica fuera del sistema y confirma URL, fecha y versión final; el registro `publication_confirmed` alimenta Observatorio. Si publica un texto distinto, guardar ambas versiones, registrar discrepancia y no atribuir el visto bueno al texto editado. Una publicación manual no aprobada puede registrarse como observación real, con ese estado, sin excluir sus resultados.

## Paradas y evaluación

Inputs obsoletos, falta de evidencia esencial, presupuesto/tiempo agotado o cancelación detienen solo dependientes afectados. La preferencia del usuario no transforma una cifra sin prueba en hecho verificado.

Casos: propuesta orgánica sin hilo o con contexto cambiado, fuente privada sin permiso, 96% sin denominador, RFID aún no desplegado, diferencia personal/equipo, gancho que no se cumple, edición tras aprobación, aprobado no publicado, texto publicado distinto. QA de diseño no prueba comportamiento de un modelo ni runtime.

Regla global de rondas: una omisión o cambio de texto requiere ronda disponible; tras la verificación final de ronda2 fallida solo esperar evidencia o descartar, sin ronda3 implícita. El documento circuitos-equipo.md precisa el contador compartido y la diferencia entre ACK y aprobación de contenido.
