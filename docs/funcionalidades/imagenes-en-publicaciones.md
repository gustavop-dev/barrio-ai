# Imágenes en las publicaciones (`IMG`, `IMG-INF`)

Gustavo quiere que cada post salga con al menos una imagen. El equipo de redacción decide por contexto qué imagen lleva cada post:
- una foto de su Galería, editada o no, con las reglas de edición de este archivo;
- una infografía hecha desde cero;
- un carrusel.

**Regla dura: siempre hay al menos una imagen.** No existe el resultado «sin imagen»: si no se puede preparar ninguna imagen válida, la pieza no se publica (queda bloqueada con el motivo), nunca sale solo con texto.

Las fotos llegan con la nota de Gustavo (de voz o escrita) como contexto y, si la trae, como instrucción. La API de imágenes de OpenAI solo se usa para editar sus fotos reales. Las infografías y los carruseles no los dibuja ningún modelo de imagen: el agente elige una plantilla y escribe el contenido como datos, y el código lo dibuja exactamente con las reglas de marca de Gustavo («Infografías hechas con IA · reglas», ver [Infografías y carruseles](#infografias-y-carruseles)).

**Fase 1 backend implementada; CI pendiente de ejecutar por Claude.** `funciona` significa que hay implementación y pruebas de backend escritas; no acredita una ejecución local ni QA de interfaz. IMG-11 e IMG-16 ya tienen UI en app y PWA, pruebas y flujos escritos en fase 2; su ejecución en CI y la QA visual siguen pendientes. Las demás funciones mixtas conservan su estado.

- **Código:** `team_backend/{imagenes,infografias,connectors_images,capture_intent,urgente}.py`, circuito editorial, captura, galería y conector oficial. Migración `0019_imagenes_y_urgencia`.
- **Regla de agente:** copia versionada íntegra del tablero local `movil/diseno-movimiento/tableros/Infografias.dc.html` en `team_backend/recursos/infografias.html`, con Ubuntu y su licencia incluidos. No se incorpora al corpus de unidades.
- **Contrato de fase 2:** [CONTRATO-API.md](../../oficina/CONTRATO-API.md#fase-2-imágenes-y-publicación-prioritaria).
- **Decisiones, archivos y límites de validación:** [Fase 1 de imágenes](../imagenes-fase-1.md).

## Resumen

| ID | Función | Dónde | Estado |
| --- | --- | --- | --- |
| [IMG-01](#img-01) | Mandar fotos con una nota de voz o escrita que da contexto e instrucción | PWA · app · backend | parcial |
| [IMG-02](#img-02) | Opción «Propuesta de post» en «Para qué es» | PWA · app · backend | parcial |
| [IMG-03](#img-03) | Las fotos siempre llegan a la Galería con su nota | backend | funciona |
| [IMG-15](#img-15) | El equipo elige por contexto: foto, infografía o carrusel | backend | funciona |
| [IMG-16](#img-16) | Opción «Edición con IA» en la captura, la Galería y Ajustes | PWA · app · backend | funciona |
| [IMG-04](#img-04) | El equipo ve la Galería y elige las fotos de un post | backend | funciona |
| [IMG-05](#img-05) | Todo post se publica con al menos una imagen | backend | funciona |
| [IMG-06](#img-06) | La nota de una propuesta de post alimenta el brief | backend | funciona |
| [IMG-07](#img-07) | Decidir si se edita una foto: manda la opción de edición; la nota dice cómo | backend | funciona |
| [IMG-08](#img-08) | Ediciones que el equipo decide por su cuenta | backend | funciona |
| [IMG-09](#img-09) | Editar con la API de imágenes de OpenAI sin perder el original | backend | funciona |
| [IMG-10](#img-10) | Comprobación de la edición con un modelo con visión | backend | funciona |
| [IMG-11](#img-11) | La imagen en el detalle de la pieza, con veto | PWA · app · backend | funciona |
| [IMG-12](#img-12) | La Galería marca la foto «usada en la pieza del …» | PWA · app · backend | funciona |
| [IMG-13](#img-13) | Coste de las imágenes en el ledger, dentro del presupuesto general | PWA · app · backend | parcial |
| [IMG-14](#img-14) | Publicar en LinkedIn con la imagen o el carrusel | backend | funciona |
| [IMG-INF-01](#img-inf-01) | Las reglas de infografías son una regla de agente | backend | funciona |
| [IMG-INF-02](#img-inf-02) | El agente elige una plantilla y escribe el contenido como datos | backend | funciona |
| [IMG-INF-03](#img-inf-03) | El código dibuja la infografía exactamente con las reglas | backend | funciona |
| [IMG-INF-04](#img-inf-04) | Datos honestos y con fuente | backend | funciona |
| [IMG-INF-05](#img-inf-05) | Carrusel: portada, láminas y cierre | backend | funciona |
| [IMG-INF-06](#img-inf-06) | Revisión con la lista de 10 puntos | backend | funciona |
| [IMG-INF-07](#img-inf-07) | Texto alternativo siempre | PWA · app · backend | parcial |
| [IMG-INF-08](#img-inf-08) | Ningún modelo de imagen dibuja infografías ni texto | backend | funciona |
| [IMG-INF-09](#img-inf-09) | La imagen amplía el post; el estilo se corrige, no descarta | backend | funciona |
| [IMG-INF-10](#img-inf-10) | Plantillas tabla, comparación, línea y lista | backend | funciona |
| [IMG-INF-11](#img-inf-11) | El editor visual elige el layout y no repite el anterior | backend | funciona |
| [IMG-INF-12](#img-inf-12) | Lienzo libre en HTML y CSS (`INFOGRAFIA_LIENZO`, apagado) | backend | funciona |
| [IMG-INF-13](#img-inf-13) | Respaldo con la frase del post antes que la tarjeta genérica | backend | funciona |
| [IMG-INF-14](#img-inf-14) | Una investigación propia para la imagen (`INFOGRAFIA_INVESTIGACION`, apagado) | backend | funciona |
| [IMG-INF-15](#img-inf-15) | Rehacer las piezas que salieron con la tarjeta genérica | backend | funciona |

`IMG-15` va arriba en la tabla porque es la primera decisión del flujo; conserva su número para no cambiar los enlaces de otras fichas.

## Pendiente de confirmar

- No quedan decisiones de producto sin confirmar. Las ediciones que decide el equipo quedan resueltas con la opción de edición de [IMG-16](#img-16) (decisión de Gustavo, 2026-11-08): con «Que decida el equipo» o «Editar», el equipo aplica la edición y la muestra para veto, sin preguntar antes.
- Por confirmar con Gustavo (recorte sin IA, 2026-11-14): «No editar» impide hoy también el recorte, así que esa foto sale en su formato original ([IMG-14](#img-14), criterio 5). Si el recorte sin IA debe aplicarse también con «No editar», basta con quitar esa excepción.

- Valores técnicos elegidos: `ai_edit=auto`; `IMAGE_DAILY_USD=1` (retirado desde el 10/11/2026: presupuesto general, ver `knowledge/presupuesto.py`); `EDITORIAL_VETO_MINUTES=60`; urgencias en orden de llegada y sin desplazar piezas preparadas; búsqueda de hueco hasta 14 días; carrusel de 2–8 láminas (3–8 hasta el 19/11/2026). Se conserva la hora y cadencia configuradas.
- Sin claves, presupuesto de IA o revisión visual: foto original si es válida; si no, la frase clave del post en una tarjeta sin cifras ([IMG-INF-13](#img-inf-13)) y, solo si el post no tiene una frase que sirva, la tarjeta de marca fija sin datos variables. Solo se bloquea si tampoco puede prepararse/servirse esa imagen.
- Documento LinkedIn: no tiene campo de alt por página; el PDF lleva `/Alt` por lámina, y la API de la pieza conserva cada alt.

---

### IMG-01 · Mandar fotos con una nota de voz o escrita que da contexto e instrucción <a id="img-01"></a>

- **Dónde:** PWA · app · backend
- **Estado:** parcial
- **Qué hace para Gustavo:** manda una o varias fotos (de la cámara o de su galería) con una nota de voz, una nota escrita o las dos. Lo que dice es el contexto de las fotos y, cuando lo trae, una instrucción («úsala tal cual», «recórtala», «quita el fondo», «más luz»).
- **Implementación backend:** `capture_intent` amplía la clasificación estructurada con instrucciones por índice; conserva nota y transcripción.
- **Criterios de aceptación:**
  1. **Dado** dos fotos de la cámara y una nota de voz «la de la izquierda úsala tal cual; a la otra dale más luz», **cuando** las envía, **entonces** llega una sola captura con las dos fotos, el audio y su transcripción.
  2. **Dado** esa captura procesada, **cuando** el equipo la lee, **entonces** cada foto queda con su contexto (la nota y la transcripción) y con la instrucción que le corresponde, si la hay: «tal cual» para la primera, «más luz» para la segunda.
  3. **Dado** una nota que solo da contexto («esta es de la charla en Medellín»), **cuando** se procesa, **entonces** la foto queda sin instrucción y con ese contexto.
  4. **Dado** una instrucción que no se puede atribuir a una foto concreta («recórtalas»), **cuando** se procesa, **entonces** se aplica a todas las fotos de la captura.
  5. **Dado** que la instrucción no se pudo leer (por ejemplo, la transcripción falló), **cuando** se procesa, **entonces** la foto queda sin instrucción, la captura muestra el error de la transcripción y la foto sigue en la Galería.
  6. **Dado** la instrucción interpretada, **cuando** se guarda, **entonces** Gustavo la ve en la hoja de la foto, junto a su nota.
- **Brechas código/docs:** Interfaz y QA de fase 2 pendientes.
- **Cobertura QA:**

### IMG-02 · Opción «Propuesta de post» en «Para qué es» <a id="img-02"></a>

- **Dónde:** PWA · app · backend
- **Estado:** parcial
- **Qué hace para Gustavo:** marca que lo que manda es una propuesta de post: fotos y una nota que quiere convertir en publicación. Si no elige nada, el equipo clasifica la captura como hasta ahora.
- **Implementación backend:** `Capture.Purpose.PROPOSAL=propuesta`, clasificador y ruta editorial con ciclo usado/liberado.
- **Criterios de aceptación:**
  1. **Dado** la hoja de captura, **cuando** abre «Para qué es (opcional)», **entonces** ve la opción nueva «Propuesta de post» junto a las existentes.
  2. **Dado** «Propuesta de post» con fotos y una nota, **cuando** envía, **entonces** la API acepta el valor nuevo de `para`, las fotos quedan en la Galería con la nota ([IMG-03](#img-03)) y la captura llega al equipo de redacción como recomendación de contenido ([IMG-06](#img-06)), ligada a esas fotos.
  3. **Dado** que no elige nada, **cuando** se procesa, **entonces** el clasificador puede decidir «propuesta de post», y «Lo que enviaste» lo muestra con «… · lo decidió el equipo» y el motivo.
  4. **Dado** «Propuesta de post» sin fotos ni texto, **cuando** intenta enviar, **entonces** no puede: hace falta al menos una foto o una nota.
  5. **Dado** una propuesta procesada, **cuando** la mira en «Lo que enviaste», **entonces** el resultado dice dónde quedó (por ejemplo «Mesa editorial lo tendrá en cuenta») y, cuando se usa, «Usado» con enlace a la pieza.
  6. **Dado** que la pieza que usó la propuesta no sale, **cuando** se cierra, **entonces** la propuesta vuelve a la mesa editorial, como las ideas de hoy ([EDI-17](motor-editorial.md#edi-17)).
- **Brechas código/docs:** Interfaz y QA de fase 2 pendientes.
- **Cobertura QA:**

### IMG-03 · Las fotos siempre llegan a la Galería con su nota <a id="img-03"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Qué hace para Gustavo:** cualquier foto que manda acaba en su Galería con lo que dijo sobre ella, sea cual sea el destino de la captura.
- **Implementación backend:** `capturas._save_photos` y `process` copian el contexto en todos los destinos (máximo 2.000 caracteres).
- **Criterios de aceptación:**
  1. **Dado** una captura con fotos y destino «Idea para un post», «Propuesta de post», «Dato sobre mí» o un contexto, **cuando** se procesa, **entonces** cada foto queda en la Galería con la nota de la captura (y la transcripción, si hubo audio) como su nota.
  2. **Dado** una foto que ya tenía una nota escrita por Gustavo en la Galería, **cuando** llega otra captura sobre ella, **entonces** su nota no se sobrescribe.
  3. **Dado** que Gustavo deshace la captura en los 2 minutos, **cuando** se deshace, **entonces** sus fotos desaparecen de la Galería, como hoy ([CAP-10](captura.md#cap-10)).
  4. **Dado** una nota de más de 2.000 caracteres, **cuando** se copia a la foto, **entonces** se recorta al máximo de la nota de una foto y la captura conserva el texto completo.
- **Brechas código/docs:** Validación en CI pendiente; no se ejecutaron pruebas locales.
- **Cobertura QA:**

### IMG-15 · El equipo elige por contexto: foto, infografía o carrusel <a id="img-15"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Qué hace para Gustavo:** para cada post, el equipo de redacción decide qué imagen lo cuenta mejor: una de sus fotos, una infografía o un carrusel.
- **Implementación backend:** `BRIEF_SCHEMA.image`, candidatas con vistas reducidas y elección explicada; `imagenes.prepare` resuelve archivos desaparecidos con tarjeta de marca.
- **Criterios de aceptación:**
  1. **Dado** el brief de una pieza, **cuando** se guarda, **entonces** incluye el tipo de imagen elegido (`foto`, `infografia` o `carrusel`) y el motivo, a partir de la tesis, el enfoque, la propuesta de Gustavo si la hay y las fotos disponibles.
  2. **Dado** una propuesta de post de Gustavo con fotos, **cuando** se decide, **entonces** sus fotos son la primera opción, salvo que el equipo explique por qué otra imagen sirve mejor.
  3. **Dado** un post que avanza por partes (los pasos de un proceso, una lista de errores, lecciones o señales, un antes y después, un marco con sus piezas o varias opciones comparadas), **cuando** se decide, **entonces** el equipo elige un carrusel ([IMG-INF-05](#img-inf-05)) si su foto no lo cuenta mejor.
  4. **Dado** un post con un dato o una frase protagonista, **cuando** se decide, **entonces** el equipo puede elegir una infografía de imagen única ([IMG-INF-02](#img-inf-02)).
  5. **Dado** que la Galería está vacía o ninguna foto encaja, **cuando** se decide, **entonces** el equipo elige una infografía o un carrusel según cómo avance el texto (antes elegía siempre infografía); nunca «sin imagen».
  6. **Dado** que la foto elegida deja de estar disponible (Gustavo la borra) o no pasa sus comprobaciones, **cuando** se prepara la pieza, **entonces** el equipo cambia a otra foto o a una infografía, y lo registra.
  7. **Dado** que no se puede preparar ninguna imagen válida, **cuando** termina la preparación, **entonces** la pieza queda bloqueada con el motivo y llega el aviso de pieza bloqueada ([EDI-09](motor-editorial.md#edi-09)); no se publica sin imagen.
  8. **Dado** que Gustavo pide un formato para el post (en la idea que usa la pieza o en un comentario sobre ella: «hazlo carrusel»), **cuando** se decide, **entonces** ese es el formato: el director lo lee en su idea y `editor_visual` recibe sus palabras en `gustavo_request` (las mismas que lee el líder, `lider.piece_request`).
  9. **Dado** el historial que recibe el director, **cuando** decide, **entonces** cada pieza reciente dice su formato de imagen (`history[].image`), para no repetir uno por costumbre.
  10. **Dado** un día con idea planeada en la semana GASP ([EDI-29](motor-editorial.md#edi-29)) y sin un formato pedido por Gustavo, **cuando** el director usa esa idea, **entonces** el formato planeado es el formato, salvo que no encaje con el texto final: un carrusel pasa a infografía si el texto no avanza por partes y una foto sin foto pertinente pasa a infografía o carrusel.
- **Brechas código/docs:** Validación en CI pendiente; no se ejecutaron pruebas locales. Hasta el 14/11/2026 nunca salió un carrusel. Causas leídas en el código (no se miraron datos de producción): los prompts solo lo proponían para «un proceso en pasos» y elegían infografía con la Galería vacía; `editor_visual` no veía lo que Gustavo pidió; un carrusel con láminas o títulos numerados («3 mistakes») choca con la regla de cifras sin fuente y, tras la corrección, la tarjeta de marca ocupa su lugar y cambia `image_kind`, así que el intento no se ve; y un comentario no podía pedir uno.
- **Cobertura QA:** criterios 3, 5, 8 y 10 en `test_imagenes.CarouselTests` (`test_a_carousel_the_director_chooses_reaches_linkedin_as_a_document_with_its_cover_title`, `test_the_team_is_told_when_a_carousel_fits_and_not_to_number_its_slides`) y `test_editor_visual.VisualTests.test_the_format_gustavo_asks_for_reaches_the_selector`. Escritas; ejecución pendiente del CI.

### IMG-16 · Opción «Edición con IA» en la captura, la Galería y Ajustes <a id="img-16"></a>

- **Dónde:** PWA · app · backend
- **Estado:** funciona
- **Qué hace para Gustavo:** al adjuntar fotos elige si el equipo puede editarlas con IA, sin tener que decirlo en el audio: «No editar», «Que decida el equipo» o «Editar».
- **Implementación backend:** `AIEdit`: no/auto/si; migración booleana; captura, galería y preferencias. Los booleanos de API siguen como alias transitorios.
- **Criterios de aceptación:**
  1. **Dado** la hoja de captura con al menos una foto adjunta, **cuando** se abre, **entonces** muestra el control «Edición con IA» con tres opciones («No editar», «Que decida el equipo», «Editar»), preseleccionado con el valor por defecto de Ajustes.
  2. **Dado** que elige una opción y envía, **cuando** las fotos llegan a la Galería, **entonces** cada foto guarda esa opción.
  3. **Dado** la hoja de una foto en la Galería, **cuando** se abre, **entonces** el interruptor actual pasa a ser el mismo control de tres opciones y guardar envía solo el campo cambiado.
  4. **Dado** Ajustes › Captura y galería, **cuando** se cambia el valor por defecto, **entonces** las fotos nuevas lo toman y las existentes no cambian.
  5. **Dado** fotos guardadas antes del cambio, **cuando** se migra, **entonces** `allow_ai_edit=false` pasa a «No editar» y `true` a «Que decida el equipo», sin perder ninguna.
  6. **Dado** una foto ya usada en una pieza, **cuando** se cambia su opción, **entonces** solo afecta a usos futuros.
  7. **Dado** lectores de pantalla, **cuando** recorren el control, **entonces** es un grupo de opciones con nombre y la opción elegida anunciada.
- **Brechas código/docs:** Implementación de interfaz terminada; CI y QA visual pendientes.
- **Cobertura QA:** `05-captura-envios` (selector y envío), `11-ajustes` (default y reversión tras error); Jest y Vitest de captura, Galería y Ajustes. Escritos; ejecución pendiente de Claude.

### IMG-04 · El equipo ve la Galería y elige las fotos de un post <a id="img-04"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Qué hace para Gustavo:** cuando un post va con foto, el equipo mira sus fotos, con sus notas y transcripciones, la fecha, si ya se usaron y si permite editarlas, y elige una o varias.
- **Implementación backend:** `imagenes.candidates`, `previews`, elección por IDs ofrecidos y `PieceImage`; `release` y `published` actualizan la galería.
- **Criterios de aceptación:**
  1. **Dado** fotos en la Galería, **cuando** corre la etapa del director, **entonces** recibe por cada foto candidata su `id`, su nota, la nota y la transcripción de su captura de origen, la fecha de subida, si ya se usó (y en qué pieza) y su opción de edición ([IMG-16](#img-16)).
  2. **Dado** un brief con tipo `foto`, **cuando** se guarda, **entonces** incluye las fotos elegidas (al menos una) con el motivo de cada elección.
  3. **Dado** una foto elegida, **cuando** se liga a la pieza, **entonces** su estado pasa a `elegida`, `chosen_piece` apunta a la pieza y `chosen_for` es el día de la pieza.
  4. **Dado** que la pieza no sale (saltada, bloqueada, fallida, descartada, vetada o caducada), **cuando** se cierra, **entonces** sus fotos vuelven a `sin_usar`.
  5. **Dado** fotos más grandes de lo que admite el modelo, **cuando** se le envían para elegir, **entonces** recibe versiones reducidas y el original queda intacto.
- **Brechas código/docs:** Validación en CI pendiente; no se ejecutaron pruebas locales.
- **Cobertura QA:**

### IMG-05 · Todo post se publica con al menos una imagen <a id="img-05"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Qué hace para Gustavo:** ningún post suyo sale solo con texto.
- **Implementación backend:** `imagenes.issues` en política y ejecución exige archivos, alt y manifiesto exactos. Sin claves hay tarjeta fija renderizada por código.
- **Criterios de aceptación:**
  1. **Dado** una propuesta CONT-09 sin imagen, **cuando** la revisa la política autónoma, **entonces** la descarta con un motivo como «Sin imagen».
  2. **Dado** una propuesta CONT-09 con imagen (foto, infografía o carrusel), **cuando** se calcula su `payload_hash`, **entonces** cubre el texto, el hash de cada imagen o lámina y su texto alternativo; cambiar cualquiera invalida la aprobación igual que cambiar el texto.
  3. **Dado** una imagen sin su comprobación favorable sobre su hash exacto ([IMG-10](#img-10) para fotos editadas, [IMG-INF-06](#img-inf-06) para infografías y carruseles), **cuando** la revisa la política, **entonces** la descarta. Una foto sin editar o recortada sin IA no necesita esa comprobación: sus bytes exactos quedan ligados por SHA-256 y por el manifiesto ([IMG-14](#img-14)).
  4. **Dado** una pieza publicada, **cuando** se abre el post en LinkedIn, **entonces** lleva la imagen o el carrusel que muestra el detalle de la pieza.
  5. **Dado** el veredicto del verificador del texto, **cuando** se calcula, **entonces** sigue valiendo solo para el texto exacto; la imagen tiene su propia comprobación.
- **Brechas código/docs:** Validación en CI pendiente; no se ejecutaron pruebas locales.
- **Cobertura QA:**

### IMG-06 · La nota de una propuesta de post alimenta el brief <a id="img-06"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Qué hace para Gustavo:** lo que dice en una «Propuesta de post», o en una captura que el equipo lee como tal, le sirve al equipo como recomendación de contenido: de qué escribir y con qué imagen.
- **Implementación backend:** `ideas_for_director` incluye propuestas, fotos y urgencia; los hechos siguen limitados a public_facts.
- **Criterios de aceptación:**
  1. **Dado** una propuesta de post de los últimos 14 días sin usar, **cuando** corre el director, **entonces** la recibe con su texto, su transcripción y sus fotos, como recomendación de contenido.
  2. **Dado** que el director la usa, **cuando** guarda el brief, **entonces** queda constancia de qué propuesta usó, la captura pasa a «Usado» con enlace a la pieza y sus fotos son candidatas preferentes ([IMG-15](#img-15)).
  3. **Dado** una propuesta que menciona un hecho sobre Gustavo, **cuando** el texto público o una infografía lo usa, **entonces** solo puede atribuírselo si está en `public_facts`, igual que con las ideas.
  4. **Dado** una propuesta que no encaja en 14 días, **cuando** pasa el plazo, **entonces** queda «Sin usar», como las ideas.
- **Brechas código/docs:** Validación en CI pendiente; no se ejecutaron pruebas locales.
- **Cobertura QA:**

### IMG-07 · Decidir si se edita una foto: manda la opción de edición; la nota dice cómo <a id="img-07"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Qué hace para Gustavo:** cada foto lleva una opción de edición que él elige ([IMG-16](#img-16)). Esa opción decide **si** se edita; su nota de voz o escrita dice **cómo**. Así una foto que necesita retoque se puede editar aunque él no lo diga en el audio.
- **Implementación backend:** `imagenes.edit_decision` respeta no > instrucción; auto conservador y si con retoque mínimo; decisión congelada en PieceImage.
- **Las tres opciones (decisión de Gustavo, 2026-11-08):**
  1. **«No editar»:** nunca se envía a la API de imágenes, diga lo que diga la nota.
  2. **«Que decida el equipo»** (por defecto): se edita si la nota lo pide **o** si el equipo lo juzga necesario ([IMG-08](#img-08)).
  3. **«Editar»:** siempre se edita; sigue la instrucción de la nota si la hay y, si no, el equipo decide cómo ([IMG-08](#img-08)).
- **Criterios de aceptación:**
  1. **Dado** una foto con «No editar» y la nota «recórtala», **cuando** se elige, **entonces** no se edita, se publica el original y queda registrado «Edición prohibida en la foto».
  2. **Dado** una foto con «Que decida el equipo» y la nota «úsala tal cual», **cuando** se elige, **entonces** no se edita.
  3. **Dado** una foto con «Que decida el equipo» y la nota «quita el fondo» o «más luz», **cuando** se elige, **entonces** la edición hace exactamente eso y nada más.
  4. **Dado** una foto con «Que decida el equipo» y sin instrucción, **cuando** se elige, **entonces** decide el equipo según [IMG-08](#img-08).
  5. **Dado** una foto con «Editar» y una instrucción, **cuando** se elige, **entonces** se edita siguiendo la instrucción.
  6. **Dado** una foto con «Editar» y sin instrucción, **cuando** se elige, **entonces** se edita igualmente: el equipo elige el retoque que más mejora la foto para LinkedIn (luz, enderezar, quitar distracciones) y registra cuál. El encuadre no es un retoque con IA: lo hace siempre el recorte sin IA de [IMG-14](#img-14).
  7. **Dado** cualquier foto elegida, **cuando** se decide, **entonces** queda registrado qué se decidió y por qué: «Edición prohibida en la foto», «Instrucción de Gustavo: …», «Decisión del equipo: …» o «Edición pedida en la foto: …».
  8. **Dado** que la instrucción pide algo que la API no puede hacer bien («cambia la persona de la izquierda»), **cuando** se decide, **entonces** no se hace esa edición, se publica el original o el retoque seguro, y el motivo queda registrado.
  9. **Dado** una foto con «Que decida el equipo» o «Editar» cuya nota solo pide recortarla o encuadrarla («recórtala»), **cuando** se elige, **entonces** no se llama a ningún modelo de imagen: el código la recorta, centrada ([IMG-14](#img-14)), y queda «Instrucción de Gustavo: recórtala; sale recortada a 1080×1350, centrada y sin IA».
- **Brechas código/docs:** Validación en CI pendiente; no se ejecutaron pruebas locales.
- **Cobertura QA:** `test_imagenes.ImageWorkflowTests.test_edit_options_note_precedence_and_conservative_team_decision`; criterio 9 en `PlainCropTests.test_his_choices_on_the_photo_still_decide_and_his_own_rejected_ai_edit_keeps_the_original` y en `CaptureImageApiTests.test_structured_understanding_assigns_per_photo_instructions_without_a_second_call` (la captura entiende «recórtala» como `crop`). Escritas; ejecución pendiente del CI.

### IMG-08 · Ediciones que el equipo decide por su cuenta <a id="img-08"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Qué hace para Gustavo:** con «Que decida el equipo» y sin instrucción, el equipo solo edita cuando importa (oscura o torcida, objetos que distraen); con «Editar» y sin instrucción, elige el retoque que más mejora la foto. En los dos casos él la ve, con veto, antes de que salga. El encuadre para LinkedIn no es una edición: es el recorte sin IA de [IMG-14](#img-14).
- **Implementación backend:** El director recibe previews y propone solo luz, enderezar o distracciones (`crop` sigue en el contrato, pero nunca va al modelo de imagen: se resuelve con el recorte de `imagenes.crop`). `auto` con duda conserva el original.
- **Criterios de aceptación:**
  1. **Dado** una foto con «Que decida el equipo», sin instrucción y bien expuesta, recta y sin distracciones, **cuando** se elige, **entonces** no se edita.
  2. **Dado** una foto oscura, torcida o con objetos que distraen, **cuando** se elige, **entonces** el equipo la edita para corregir solo eso y registra el motivo («Estaba oscura: se aclaró»). Si además no tiene el tamaño de LinkedIn, el resultado se recorta igual que el recorte sin IA, centrado.
  3. **Dado** una edición decidida por el equipo, **cuando** se prepara la pieza, **entonces** se aplica y se muestra en el detalle de la pieza para que Gustavo pueda vetarla, sin preguntarle antes: elegir «Que decida el equipo» o «Editar» es su permiso.
  4. **Dado** que el equipo duda si editar una foto con «Que decida el equipo», **cuando** decide, **entonces** no edita. (Con «Editar» no hay duda: se edita.)
  5. **Dado** una edición que decidió el equipo y que no pasa la comprobación, falla o no tiene proveedor, **cuando** termina, **entonces** sale la foto recortada sin IA ([IMG-14](#img-14)), nunca una foto de 9:16 sin recortar; si la comprobación la rechazó, se ve la edición descartada con sus motivos ([IMG-11](#img-11)).
- **Brechas código/docs:** Validación en CI pendiente; no se ejecutaron pruebas locales.
- **Cobertura QA:** criterio 5 en `test_imagenes.PlainCropTests.test_a_team_edit_that_does_not_pass_or_cannot_run_falls_back_to_the_crop`. Escrita; ejecución pendiente del CI.

### IMG-09 · Editar con la API de imágenes de OpenAI sin perder el original <a id="img-09"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Qué hace para Gustavo:** cuando toca editar una de sus fotos, el equipo usa la API de imágenes de OpenAI; su foto original nunca se toca y la versión editada se guarda aparte.
- **Implementación backend:** `connectors_images.ImageConnector.edit`: multipart OpenAI, ledger, un intento; original intacto, derivado privado y borrado de versiones.
- **Criterios de aceptación:**
  1. **Dado** una foto que debe editarse, **cuando** se edita, **entonces** se llama a la API de edición de imágenes de OpenAI con el original y una instrucción derivada de la nota de Gustavo o del motivo del equipo.
  2. **Dado** la edición terminada, **cuando** se guarda, **entonces** el archivo original queda idéntico (mismo SHA-256 antes y después) y la versión editada se guarda en otro archivo, ligada a la foto y a la pieza.
  3. **Dado** la versión editada, **cuando** se pide, **entonces** se sirve por una ruta autenticada y privada, como el original (`GET /api/v1/galeria/<id>/imagen`): sin URL pública y con `Cache-Control: private`.
  4. **Dado** la foto editada, **cuando** se consulta en la Galería, **entonces** su estado es `editada` y su etiqueta «Editada con IA».
  5. **Dado** un error o un tiempo de espera de OpenAI, **cuando** falla la edición, **entonces** no se repite sola (un paso pagado nunca se repite) y se publica la foto sin editar, con el motivo registrado: recortada sin IA si la edición la decidió el equipo, su original si la pidió Gustavo ([IMG-14](#img-14)).
  6. **Dado** que se agotó el presupuesto de imágenes ([IMG-13](#img-13)), **cuando** toca editar, **entonces** no se edita y se publica la foto sin editar como en el criterio 5, con el motivo registrado.
  7. **Dado** que Gustavo borra la foto de la Galería, **cuando** se borra, **entonces** se borran el original, todas sus versiones editadas y sus recortes ([IMG-14](#img-14)).
  8. **Dado** `LIVE_PROVIDERS=false` o sin clave de OpenAI, **cuando** toca editar, **entonces** no se llama a nadie y se publica la foto sin editar como en el criterio 5.
  9. **Dado** una infografía o un carrusel, **cuando** se prepara, **entonces** nunca se llama a la API de imágenes de OpenAI ([IMG-INF-08](#img-inf-08)).
- **Brechas código/docs:** Validación en CI pendiente; no se ejecutaron pruebas locales.
- **Cobertura QA:** criterios 5, 7 y 8 con el recorte en `test_imagenes.PlainCropTests` (`test_a_team_edit_that_does_not_pass_or_cannot_run_falls_back_to_the_crop`, `test_deleting_the_photo_deletes_its_crop_too`). Escritas; ejecución pendiente del CI.

### IMG-10 · Comprobación de la edición con un modelo con visión <a id="img-10"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Qué hace para Gustavo:** antes de publicar una foto editada, un modelo que ve imágenes (Claude) confirma que la edición hizo lo que él pidió y no deforma a las personas, los textos ni la marca. Si no pasa, sale la foto sin editar: recortada sin IA si la edición la decidió el equipo, su original si la pidió él ([IMG-14](#img-14)).
- **Implementación backend:** Claude recibe original y resultado exacto, instrucción y post; revisión por SHA-256. Fallo o rechazo conserva el original.
- **Criterios de aceptación:**
  1. **Dado** una foto editada, **cuando** se comprueba, **entonces** Claude recibe el original, la versión editada, la instrucción o el motivo y el texto del post, y devuelve un veredicto con sus motivos.
  2. **Dado** una edición que no sigue la instrucción (se pidió recortar y además cambió los colores), **cuando** se comprueba, **entonces** el veredicto es desfavorable.
  3. **Dado** una edición que cambia caras, cuerpos o el número de personas, deforma textos o altera un logotipo o la marca, **cuando** se comprueba, **entonces** el veredicto es desfavorable.
  4. **Dado** un veredicto desfavorable, **cuando** termina, **entonces** se publica la foto sin editar (recortada sin IA si la edición la decidió el equipo; su original si la pidió Gustavo), el detalle de la pieza muestra por qué se descartó la edición y la foto no queda como `editada`.
  5. **Dado** un veredicto favorable, **cuando** se guarda, **entonces** va ligado al SHA-256 de la imagen exacta; si la imagen cambia después, deja de valer.
  6. **Dado** que la comprobación falla por un error del proveedor, **cuando** termina, **entonces** se publica la foto sin editar como en el criterio 4 (nunca una edición sin comprobar).
  7. **Dado** una foto sin editar, también una recortada sin IA, **cuando** se prepara la pieza, **entonces** no hace falta esta comprobación ni se llama a ningún modelo.
  8. **Dado** una edición que pidió Gustavo (su nota en la foto o su comentario en la pieza), **cuando** se comprueba, **entonces** la revisión es tolerante: solo la rechaza si el cambio pedido no se ve, una persona deja de parecer la misma o sale deformada, aparecen texto, cifras, logos o marcas nuevos, o se ven caras o nombres de otras personas que pidió ocultar. Objetos añadidos o quitados, detalles del portátil o de las pantallas redibujados, luz o encuadre no la hacen fallar; quedan anotados en los motivos. Las ediciones que decide el equipo (criterios 2 y 3) siguen con la revisión estricta.
  9. **Dado** una edición cuyo resultado se recorta al tamaño de LinkedIn (4:5 o 1:1, centrado), **cuando** se comprueba, **entonces** el encuadre y lo que deja fuera el recorte nunca la hacen fallar, ni en la revisión estricta ni en la tolerante.
- **Brechas código/docs:** Validación en CI pendiente; no se ejecutaron pruebas locales.
- **Cobertura QA:** criterios 4, 7 y 8 en `test_imagenes.PlainCropTests.test_his_choices_on_the_photo_still_decide_and_his_own_rejected_ai_edit_keeps_the_original` y `test_a_team_edit_that_does_not_pass_or_cannot_run_falls_back_to_the_crop`; el criterio 9 es una regla de los prompts de `connectors_images` (sin prueba de modelo). Escritas; ejecución pendiente del CI.

### IMG-11 · La imagen en el detalle de la pieza, con veto <a id="img-11"></a>

- **Dónde:** PWA · app · backend
- **Estado:** funciona
- **Qué hace para Gustavo:** en el detalle de la pieza, en la PWA y en la app, ve la imagen que saldrá: la foto (original y editada, con el motivo de la edición), la infografía o las láminas del carrusel, con su texto alternativo, y puede vetar hasta la hora de salida.
- **Implementación backend:** Detalle con images[], origen, alt, motivo, revisión y PDF privado. `PieceImages.tsx` en app y PWA presenta foto, comparación y carrusel; tipos y lógica en `compartido/`.
- **Criterios de aceptación:**
  1. **Dado** una pieza con una foto sin editar ni recortar, **cuando** abre su detalle, **entonces** ve la foto con «Se publica tal cual» y el motivo («Instrucción de Gustavo: úsala tal cual», «Edición prohibida en la foto»…).
  2. **Dado** una pieza con una foto editada, **cuando** abre su detalle, **entonces** ve el original y la versión editada (lado a lado en escritorio, alternables en el teléfono), el motivo de la edición y el veredicto de la comprobación.
  3. **Dado** una edición descartada por la comprobación, **cuando** abre el detalle, **entonces** ve que sale el original y por qué, y en la app ve también la edición descartada («Edición con IA descartada») con las razones, para juzgarla él mismo. El servidor guarda solo la última descartada de cada foto (`PieceImage.data.rejected_edit`, fuera del manifiesto: nunca se publica) y la sirve en `GET /api/v1/editorial/pieces/{id}/images/{img}/descartada`; una edición aceptada después la borra.
  4. **Dado** una pieza con infografía o carrusel, **cuando** abre su detalle, **entonces** ve la imagen o cada lámina en orden («1/5», «2/5»…), la plantilla usada, el resultado de la lista de 10 puntos y el texto alternativo de cada una.
  5. **Dado** una pieza programada, **cuando** la veta antes de su hora, **entonces** no sale ni el texto ni la imagen, como hoy.
  6. **Dado** que ya pasó la hora o la pieza se está publicando, **cuando** abre el detalle, **entonces** no hay botón de veto.
  7. **Dado** que la imagen no carga, **cuando** abre el detalle, **entonces** ve un aviso en su lugar («No se pudo cargar la imagen») con «Reintentar», y el resto del detalle sigue.
  8. **Dado** una pieza en preparación sin imagen todavía, **cuando** abre el detalle, **entonces** ve «La imagen aparece cuando el equipo la prepare».
  9. **Dado** una imagen rehecha (por un comentario suyo, [EDI-22](motor-editorial.md#edi-22)), **cuando** vuelve a abrir el detalle, **entonces** ve la imagen nueva y no la que guardó antes el teléfono o el navegador: la URL de cada imagen lleva su versión (`?v=` + los primeros 16 caracteres de su sha256, `imagenes.url`), así que cambia con su contenido.
  10. **Dado** una pieza con una foto recortada sin IA ([IMG-14](#img-14)), **cuando** abre su detalle en la app, **entonces** ve «Recortada, sin IA» (nunca «Editada con IA» ni «Se publica tal cual»), el motivo («…; sale recortada a 1080×1350, centrada y sin IA») y puede alternar con el original («Ver original» / «Ver recortada»). La API lo dice con `images[].cropped`.
- **Brechas código/docs:** Implementación de interfaz terminada; CI y QA visual pendientes. Criterio 10: solo en la app (primero el móvil); la PWA aún muestra una foto recortada como «Se publica tal cual».
- **Cobertura QA:** `16-imagenes` (foto, infografía, carrusel de cuatro láminas y alt); `07-pieza-veto` (veto de la pieza completa). Jest/Vitest: original y editada, reintento, revisión, preparación, alt, paginación, hash recibido y fin del veto. Criterio 10: Jest `PiezaScreen.test.tsx` («marks a plain crop without AI apart from an AI edit…») y `compartido/src/logic/imagenes.test.ts` (`photoTreatment`); `test_imagenes.PlainCropTests` comprueba `cropped` en la API. Escritos; ejecución pendiente de Claude.

### IMG-12 · La Galería marca la foto «usada en la pieza del …» <a id="img-12"></a>

- **Dónde:** PWA · app · backend
- **Estado:** funciona
- **Qué hace para Gustavo:** en la Galería ve qué fotos usó el equipo, en qué pieza y si las editó.
- **Implementación backend:** Estados elegida/editada/publicada, `used_in` y `versions`; se libera al cerrar sin publicar.
- **Criterios de aceptación:**
  1. **Dado** una foto elegida para la pieza del domingo 8, **cuando** abre la Galería, **entonces** su etiqueta es «Elegida · dom 8» y la hoja de la foto dice «Usada en la pieza del domingo 8» con enlace a `/calendario/pieza/<id>`.
  2. **Dado** una foto editada, **cuando** abre su hoja, **entonces** ve «Editada con IA», el original y la versión editada.
  3. **Dado** una foto publicada, **cuando** abre la Galería, **entonces** su etiqueta es «Publicada · <fecha>» y aparece en el filtro «Publicadas».
  4. **Dado** los filtros, **cuando** elige «Elegidas», **entonces** aparecen las elegidas y las editadas; «Sin usar» incluye las nuevas.
  5. **Dado** que la pieza no salió, **cuando** abre la Galería, **entonces** la foto vuelve a «Sin usar».
  6. **Dado** que quiere quitar una foto elegida, **cuando** pulsa «Quitar de la galería», **entonces** la confirmación avisa «Ojo: elegida para el post del <día>.».
- **Brechas código/docs:** Interfaz y QA de fase 2 pendientes.
- **Cobertura QA:**

### IMG-13 · Coste de las imágenes en el ledger, dentro del presupuesto general <a id="img-13"></a>

- **Dónde:** PWA · app · backend
- **Estado:** parcial
- **Qué hace para Gustavo:** cada edición de foto y cada comprobación de imagen queda registrada con su coste, dentro del presupuesto de IA de todo el equipo; en Ajustes ve lo gastado hoy en imágenes.
- **Implementación backend:** reserva atómica entre ambos proveedores, propósitos image-*, línea Imágenes (solo gasto, `limit_usd: 0`) y total semanal. Desde el 10/11/2026 no hay presupuesto propio (`IMAGE_DAILY_USD` retirado): cuenta en `AI_MONTHLY_LIMIT_USD` y en el tope de seguridad diario `AI_DAILY_FUSE_USD` (`knowledge/presupuesto.py`).
- **Criterios de aceptación:**
  1. **Dado** una edición con OpenAI, **cuando** se llama, **entonces** antes se reserva su peor caso en el ledger con un propósito propio (por ejemplo `image-edit`, proveedor `openai`) y al terminar se liquida con el coste real.
  2. **Dado** una comprobación con Claude (de una foto editada o de una infografía), **cuando** se llama, **entonces** también pasa por el ledger con su propósito (por ejemplo `image-check`).
  3. **Dado** una infografía o un carrusel, **cuando** se dibuja, **entonces** no hay coste de modelo de imagen: solo cuentan la llamada que escribe su contenido y la comprobación visual.
  4. **Dado** que se agotó el presupuesto de IA del equipo (`AI_MONTHLY_LIMIT_USD` o el tope de seguridad diario `AI_DAILY_FUSE_USD`), **cuando** toca editar, **entonces** no se hace ninguna edición más y se publica la foto sin editar (recortada sin IA si la edición la decidió el equipo, [IMG-14](#img-14)). El recorte no cuesta nada: no llama a ningún proveedor.
  5. **Dado** el gasto de imágenes, **cuando** se calcula el presupuesto general de IA, **entonces** cuenta en él, como el de cualquier área.
  6. **Dado** un fallo de OpenAI que no se cobra, **cuando** termina, **entonces** la reserva queda `rejected`; un fallo incierto la deja `uncertain` y no se reintenta.
  7. **Dado** Ajustes › Gasto de IA, en la PWA y en la app, **cuando** lo abre, **entonces** ve una línea «Imágenes» con lo gastado hoy, sin tope propio.
  8. **Dado** el resumen semanal, **cuando** se calculan sus cifras, **entonces** `gasto_ia` incluye el gasto de imágenes.
- **Brechas código/docs:** Interfaz y QA de fase 2 pendientes.
- **Cobertura QA:**

### IMG-14 · Publicar en LinkedIn con la imagen o el carrusel <a id="img-14"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Qué hace para Gustavo:** la pieza sale en LinkedIn con su imagen o su carrusel, por la API oficial, con las mismas garantías de hoy: una sola vez y sin repetir si el resultado es incierto.
- **Implementación backend:** `upload_media`: initializeUpload, PUT, AVAILABLE; Posts API content.media/multiImage, documentos PDF; fake registra bytes. Contratos escritos offline: validación externa pendiente.
- **Criterios de aceptación:**
  1. **Dado** una pieza aprobada con una foto o una infografía de imagen única, **cuando** llega su hora, **entonces** primero se sube la imagen a LinkedIn (registrar la subida y enviar los bytes) y después se crea el post que la referencia en `content.media`, con su texto alternativo, usando el mismo permiso `w_member_social`.
  2. **Dado** una pieza con carrusel, **cuando** llega su hora, **entonces** se sube como documento de hasta 8 láminas de 1080×1350 y se crea el post que lo referencia. El título del documento en LinkedIn es el titular de su portada (antes, «Ideas · Gustavo» para todos); va en el manifiesto (`document_title`, solo en carruseles), así que cambiarlo invalida la aprobación como cambiar un byte.
  3. **Dado** la imagen que se publica, **cuando** se prepara, **entonces** tiene formato vertical 1080×1350 o cuadrado 1080×1080; nunca horizontal. Una foto más pequeña que ese tamaño conserva su resolución con esa proporción (nunca se agranda), y una foto que sale tal cual (criterio 5) conserva la suya.
  4. **Dado** una foto que no tiene ese formato (por ejemplo, una 9:16 del teléfono) y que se puede editar, **cuando** se prepara, **entonces** el código la recorta, centrada, sin ningún modelo de imagen ni comprobación visual (decisión de Gustavo, 2026-11-14: «centrar y recortar arriba y abajo»): una foto vertical conserva todo su ancho y pierde lo mismo arriba y abajo hasta 4:5 (1080×1350); una horizontal o cuadrada pierde lo mismo a cada lado hasta 1:1 (1080×1080). Antes se endereza según su EXIF y el resultado no copia sus metadatos. Si además lleva una edición con IA ([IMG-07](#img-07) a [IMG-10](#img-10)), esta se pide al modelo en la orientación de la foto (1024×1536 vertical, 1536×1024 horizontal) y su resultado se recorta igual, centrado, nunca se aplasta.
  5. **Dado** una foto con «No editar», con la nota «úsala tal cual» o con una instrucción no segura, en otro formato, **cuando** se prepara, **entonces** se publica tal cual, sin recortarla.
  6. **Dado** que falla la subida de la imagen o del documento antes de crear el post, **cuando** termina, **entonces** la acción queda `failed` sin publicar nada (resultado definitivo) y llega el aviso correspondiente.
  7. **Dado** un 401, 403 o 429 al subir, **cuando** termina, **entonces** la cuenta pasa a pausa con aviso, como al publicar texto.
  8. **Dado** que la creación del post da un resultado incierto, **cuando** termina, **entonces** queda `uncertain` y nunca se repite ([EDI-12](motor-editorial.md#edi-12)).
  9. **Dado** el post publicado, **cuando** se confirma, **entonces** cada foto usada pasa a `publicada` con `published_at`.
  10. **Dado** el conector simulado (`linkedin_fake`), **cuando** se publica con imagen o carrusel, **entonces** guarda lo subido en su memoria para que las pruebas lo comprueben.
  11. **Dado** una foto recortada, **cuando** se guarda, **entonces** el original queda intacto, el recorte va en otro archivo ligado a la pieza (`PieceImage.cropped`, con la caja del recorte y el SHA-256 del original en `data.crop`), el motivo dice «sale recortada a 1080×1350, centrada y sin IA» y la foto queda `elegida`, no `editada`.
  12. **Dado** un recorte, **cuando** lo revisan la política, el verificador, el líder o cualquier agente que elige la imagen, **entonces** nunca retiene la pieza por el encuadre ni por lo que dejó fuera: no pasa por la comprobación visual, sus bytes exactos quedan ligados por SHA-256 y por el manifiesto, y los prompts que ven la foto dicen que su formato no es motivo para descartarla ni para editarla.
  13. **Dado** una foto 9:16 de una propuesta de Gustavo, **cuando** el circuito diario prepara la pieza y llega su hora, **entonces** la pieza queda lista y sale en LinkedIn con la foto recortada a 1080×1350, sin ninguna llamada a un modelo de imagen ni a la comprobación visual y sin ningún bloqueo por el encuadre.
  14. **Dado** una foto que ya mide 1080×1350 o 1080×1080, **cuando** se prepara, **entonces** sale tal cual, sin recortar.
  15. **Dado** una edición con IA que decidió el equipo y que no pasa la comprobación, falla o no tiene proveedor, **cuando** termina, **entonces** sale la foto recortada sin IA; si la edición la pidió Gustavo y no pasa, sale su original, como dice [IMG-10](#img-10).
- **Brechas código/docs:** Validación en CI pendiente; no se ejecutaron pruebas locales.
- **Cobertura QA:** criterios 3 a 5 y 11 a 15 en `test_imagenes.PlainCropTests` (`test_every_orientation_is_cut_by_code_to_its_size_without_upscaling_or_any_model_call`, `test_the_crop_is_centred_and_a_photo_with_linkedin_size_goes_out_as_it_is`, `test_a_phone_jpeg_is_turned_upright_cropped_and_loses_its_exif`, `test_his_choices_on_the_photo_still_decide_and_his_own_rejected_ai_edit_keeps_the_original`, `test_a_team_edit_that_does_not_pass_or_cannot_run_falls_back_to_the_crop`, `test_the_agents_that_choose_the_photo_are_told_its_format_never_rules_it_out`, `test_a_phone_photo_goes_from_his_capture_to_linkedin_without_an_image_model_or_a_block`) y `test_retoque.EditSizeTests.test_reframing_a_vertical_original_keeps_it_vertical_without_ai`. Escritas; ejecución pendiente del CI.

---

## Infografías y carruseles <a id="infografias-y-carruseles"></a>

Las reglas son las del tablero «Infografías hechas con IA · reglas» (`Infografias.dc.html`, canvas https://claude.ai/artifact/9ebjAHA228bpQJM9XP64ee). El tablero las organiza en nueve partes: principio, formatos y rejilla, color, tipografía, datos y gráficos, composición (con las cuatro plantillas), «sí y no», una especificación JSON para los agentes y la lista de revisión de 10 puntos. Su frase de partida: «Si una regla estorba, gana la claridad».

### IMG-INF-01 · Las reglas de infografías son una regla de agente <a id="img-inf-01"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Qué hace para Gustavo:** su manual de infografías se aplica siempre, igual que su documento de tono de voz: no es una unidad de conocimiento que el agente pueda leer o no.
- **Implementación backend:** `infografias.with_rule` adjunta la regla completa y su versión SHA-256 al diseñador y verificador.
- **Criterios de aceptación:**
  1. **Dado** el repositorio, **cuando** se busca la regla, **entonces** el contenido del tablero (principio, formatos, color, tipografía, datos, composición, sí y no, especificación JSON y lista de revisión) está guardado en el backend como un recurso versionado, junto a la voz.
  2. **Dado** el agente que diseña infografías y carruseles, **cuando** se arma su system, **entonces** lleva siempre la regla completa, con la especificación JSON del tablero.
  3. **Dado** el verificador de imágenes, **cuando** revisa una infografía, **entonces** usa la misma versión de la regla que el agente que la diseñó, y la pieza guarda qué versión se aplicó.
  4. **Dado** que Gustavo cambia el tablero, **cuando** quiere que cambien las infografías, **entonces** se actualiza el recurso del backend y se despliega, como con la voz.
  5. **Dado** la búsqueda de unidades del curso, **cuando** se consulta, **entonces** la regla no aparece como unidad de conocimiento.
- **Brechas código/docs:** Validación en CI pendiente; no se ejecutaron pruebas locales.
- **Cobertura QA:**

### IMG-INF-02 · El agente elige una plantilla y escribe el contenido como datos <a id="img-inf-02"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Qué hace para Gustavo:** para una infografía, el agente decide qué plantilla usar y qué dice cada parte; no dibuja nada.
- **Implementación backend:** `TEMPLATE_DESIGN_SCHEMA` (o `CANVAS_DESIGN_SCHEMA` con el lienzo), `infografias.fix` (corrige el estilo con código) y `infografias.validate` (solo verdad y legibilidad), y una corrección pagada; cuatro plantillas del tablero más cierre, `preguntas`, `tabla`, `comparacion`, `linea` y `lista` ([IMG-INF-10](#img-inf-10)). Desde el 19/11/2026 el estilo ya no descarta: ver [IMG-INF-09](#img-inf-09).
- **Criterios de aceptación:**
  1. **Dado** una pieza con tipo `infografia` o `carrusel`, **cuando** corre el agente, **entonces** devuelve datos estructurados validados con un esquema: la plantilla (portada de carrusel, pasos, barras o número protagonista), el formato, los textos de cada elemento (etiqueta, titular, bajada, cuerpo, cifra con su unidad, pasos, barras con su valor), la fuente de los datos, el texto alternativo y, en un carrusel, las láminas en orden.
  2. **Dado** un titular de más de 8 palabras o una lámina con más palabras que la guía (30; 40 en imagen única; tabla 70, comparación y lista 60, pasos y preguntas 55), **cuando** se valida, **entonces** el código quita primero el texto secundario (cuerpo, bajada, detalles, respuestas cortas) y lo anota; solo un titular de más de 14 palabras (24 en `cita`) o un texto que no cabe en la rejilla tras acortarlo se rechaza.
  3. **Dado** un tipo de gráfico que no está permitido (torta de más de 3 partes, 3D, doble eje, medidores, nubes de palabras), **cuando** se valida, **entonces** se rechaza; solo pasan número protagonista, barras horizontales (hasta 5), línea simple (una serie, dos como máximo), antes y después, pasos (3 a 5) y lista numerada.
  4. **Dado** unos pasos con 7 elementos o unas barras con 6 categorías, **cuando** se valida, **entonces** el código deja los primeros 6 pasos o las 5 barras mayores (con el foco); por debajo del mínimo (un solo paso) la plantilla no tiene qué dibujar y se rechaza.
  5. **Dado** el texto público, **cuando** se valida, **entonces** está en inglés y sin emojis (la fuente no los dibuja: se quitan y, si queda alguno, se rechaza); los hashtags, las dobles exclamaciones y las palabras en mayúsculas se corrigen con código. Las siglas conocidas (AI, MVP, CTO, API, US…, `infografias.ACRONYMS`) son palabras, no gritos; los plurales y formas mixtas (APIs, B2B, SaaS) nunca chocaron con la regla.
  6. **Dado** un titular de portada, **cuando** se valida, **entonces** la guía pide minúsculas salvo la primera letra y las siglas conocidas («Ship AI agents safely»); si no, queda anotado, no se rechaza.
  7. **Dado** una respuesta que no cumple el esquema tras la corrección, **cuando** termina, **entonces** no se dibuja ese diseño y sale el respaldo ([IMG-INF-13](#img-inf-13)).
  8. **Dado** que Gustavo pide preguntas (o «preguntas y respuestas rápidas») o el post remite a las preguntas de la imagen, **cuando** diseña, **entonces** usa la plantilla `preguntas`: de 1 a 4 preguntas en viñetas (el código quita la numeración y lo que no es pregunta), sin numerar, cada una con una respuesta corta opcional después del «?»; sin cifras no necesita fuente. Origen: 12/11/2026, el diseñador puso tres preguntas en la plantilla `numero` («3 questions»), que siempre es un dato, y la pieza salió con la tarjeta de marca.
  9. **Dado** un rechazo por «Dato sin fuente», **cuando** se pide la corrección, **entonces** el motivo dice qué lo volvió un dato (la plantilla o las cifras del texto) y cómo corregirlo, para que el segundo intento no repita el diseño.
- **Brechas código/docs:** Validación en CI pendiente; no se ejecutaron pruebas locales.
- **Cobertura QA:** criterios 5 y 6 con siglas en `test_imagenes.RendererTests.test_known_acronyms_are_words_and_shouting_is_still_rejected`. Escrita; ejecución pendiente del CI.

### IMG-INF-03 · El código dibuja la infografía exactamente con las reglas <a id="img-inf-03"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Qué hace para Gustavo:** cada infografía se ve de 0ff1ce: limpia, simple y legible en el teléfono, porque la dibuja código con su manual, no un modelo.
- **Implementación backend:** Pillow, Ubuntu incluido, rejilla/paleta/medidas y límites de desbordamiento. Referencia geométrica escrita; comparación visual del render en CI pendiente.
- **Criterios de aceptación:**
  1. **Dado** los datos de una infografía, **cuando** se dibuja, **entonces** el lienzo mide 1080×1080 (imagen única) o 1080×1350 (carrusel), nunca horizontal.
  2. **Dado** cualquier lámina, **cuando** se dibuja, **entonces** respeta el margen de 96 px por los cuatro lados, la rejilla de 6 columnas con medianil de 24 px y la línea base de 8 px, todo alineado a la izquierda (centrado solo para un número protagonista solo).
  3. **Dado** la tipografía, **cuando** se dibuja, **entonces** todo va en Ubuntu, con Bold solo para el nombre 0ff1ce, y con estos tamaños en el lienzo de 1080: titular de portada 96/104 px, titular de lámina 72/80 px, cifra protagonista 240–280 px (unidad al lado a 96 px), bajada 40–48/52–60 px, cuerpo 34–36/46–48 px, etiqueta 30/36 px en mayúsculas con +0,06 em, fuente y pie 28/36 px; nada por debajo de 28 px.
  4. **Dado** el color, **cuando** se dibuja, **entonces** usa solo la paleta (papel `#F7F6F0`, tinta `#1E1E2B`, tinta suave `#565972`, línea `#DEDFD4`, 0ff1ce hondo `#00715E`, 0ff1ce `#0FF1CE`, post-it `#F8D47D` solo para anotaciones, óxido `#A54E35` solo para caídas o errores) y un solo acento por pieza: 0ff1ce hondo sobre papel, 0ff1ce sobre tinta, nunca 0ff1ce sobre papel.
  5. **Dado** el fondo, **cuando** se dibuja, **entonces** el claro lleva texto en tinta y el oscuro (portadas y número protagonista) texto en papel, con la bajada en `#B9BCCB` sobre tinta.
  6. **Dado** cualquier pieza, **cuando** se dibuja, **entonces** no lleva degradados, sombras, transparencias superpuestas, 3D, iconos decorativos, robots, cerebros o circuitos, fotos de stock, pixel art de la oficina ni logos de terceros; los iconos, si explican algo, son de línea de 2 px, redondeados, en tinta y uno por bloque como máximo.
  7. **Dado** cada lámina, **cuando** se dibuja, **entonces** lleva el pie fijo a 28 px: el autor a la izquierda (no el logo de 0ff1ce) y la numeración («3/5») a la derecha.
  8. **Dado** el lienzo terminado, **cuando** se mide, **entonces** al menos el 40 % queda vacío.
  9. **Dado** las cuatro plantillas del tablero, **cuando** se dibujan con sus datos de ejemplo, **entonces** el resultado coincide con el tablero (prueba de referencia visual).
- **Brechas código/docs:** Validación en CI pendiente; no se ejecutaron pruebas locales.
- **Cobertura QA:**

### IMG-INF-04 · Datos honestos y con fuente <a id="img-inf-04"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Qué hace para Gustavo:** ninguna infografía inventa un dato ni lo exagera; todo número dice de dónde sale.
- **Implementación backend:** Fuentes por referencia pública, fecha y estimate; barras desde cero, ordenadas, rotuladas y con foco único.
- **Criterios de aceptación:**
  1. **Dado** un dato, **cuando** se valida, **entonces** sale de la memoria confirmada pública de Gustavo o de una fuente citada; si no, se rechaza.
  2. **Dado** una estimación, **cuando** se dibuja, **entonces** lo dice («estimate»).
  3. **Dado** un gráfico de barras, **cuando** se dibuja, **entonces** las barras empiezan en cero, van de mayor a menor (salvo que el orden sea el mensaje), llevan la etiqueta al lado y no hay leyenda aparte; solo la barra del foco va en el color de acento, las demás en línea `#DEDFD4`.
  4. **Dado** un número, **cuando** se dibuja, **entonces** va redondeado y con su unidad («6 days», no «6,24 days»).
  5. **Dado** cualquier dato, **cuando** se dibuja, **entonces** lleva al pie, a 28 px, de dónde sale y de cuándo es.
  6. **Dado** que el color marca algo, **cuando** se dibuja, **entonces** lleva también etiqueta o posición: el color nunca va solo.
- **Brechas código/docs:** Validación en CI pendiente; no se ejecutaron pruebas locales.
- **Cobertura QA:**

### IMG-INF-05 · Carrusel: portada, láminas y cierre <a id="img-inf-05"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Qué hace para Gustavo:** cuando un post avanza por partes (pasos, errores, lecciones, antes y después) o él lo pide, sale como carrusel con su portada, una idea por lámina y una pregunta al final.
- **Implementación backend:** Carrusel de 2–8 láminas: portada, interiores y cierre (con pregunta como guía, no como requisito); PDF etiquetado con alt por lámina. `imagenes.DESIGN_SYSTEM` le dice al diseñador cómo repartir el post en láminas y que no numere; su respuesta tiene hasta 8.000 tokens (5.000 una infografía). Un comentario puede pedirlo (`image_route="carrusel"`, [EDI-22](motor-editorial.md#edi-22)).
- **Criterios de aceptación:**
  1. **Dado** un carrusel, **cuando** se valida, **entonces** tiene como mucho 8 láminas de 1080×1350.
  2. **Dado** la primera lámina, **cuando** se dibuja, **entonces** es la portada: fondo tinta, una sola palabra en 0ff1ce, titular de 8 palabras como máximo y bajada; las interiores van en papel.
  3. **Dado** cada lámina, **cuando** se valida, **entonces** responde una sola idea; si hacen falta dos, son dos láminas.
  4. **Dado** la última lámina, **cuando** se valida, **entonces** lo natural es que devuelva la pregunta del post; si no lo hace queda anotado y el carrusel sale igual (era uno de los motivos reales de la tarjeta genérica, 19/11/2026). Un «sígueme» se quita.
  5. **Dado** el carrusel, **cuando** se numeran las láminas, **entonces** cada pie dice «n/N».
  6. **Dado** el diseño de un carrusel, **cuando** se escribe, **entonces** ni las láminas ni sus títulos llevan cifras para numerarse («1.», «Step 2», «3 mistakes»): el pie ya dice «n/N» y la plantilla `pasos` numera sus pasos; una cifra sin fuente sigue rechazándose ([IMG-INF-04](#img-inf-04)).
  7. **Dado** un comentario de Gustavo que pide un carrusel sobre una pieza lista con foto o infografía, **cuando** se rehace, **entonces** la imagen pasa a ser un carrusel diseñado con su comentario y la foto vuelve a la Galería.
  8. **Dado** un carrusel que no pasa el diseño ni la revisión tras la corrección, **cuando** termina, **entonces** sale el respaldo, como con una infografía: la frase clave del post y, como último recurso, la tarjeta de marca (la pieza no se retrasa por intentarlo). Una lámina cuya cifra no tiene fuente sale del carrusel mientras queden dos.
- **Brechas código/docs:** Validación en CI pendiente; no se ejecutaron pruebas locales. El criterio 8 no prueba antes una infografía: el ciclo diario permite dos llamadas de diseño y las gasta el carrusel.
- **Cobertura QA:** `test_imagenes.ImageWorkflowTests.test_infographic_and_carousel_use_code_and_one_bounded_repair`; `test_imagenes.CarouselTests` (del brief del director al documento en LinkedIn con el título de su portada; título ligado a la aprobación); `test_retoque.ReworkTests.test_a_comment_asking_for_a_carousel_turns_the_image_into_one`. Escritas; ejecución pendiente del CI.

### IMG-INF-06 · Revisión con la lista de 10 puntos <a id="img-inf-06"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Qué hace para Gustavo:** antes de publicar, el verificador revisa cada infografía con su lista de 10 puntos; si falla uno, vuelve a Mesa editorial.
- **Implementación backend:** Comprobaciones medibles y lista visual de 10 puntos, una reparación y veredicto ligado a cada SHA-256. Desde el 19/11/2026 solo los puntos 1 (tema y que amplíe el post), 4 (28 px), 5 (fuentes), 8 (contraste) y 9 (inglés) descartan una infografía (`connectors_images.BLOCKING`); un fallo en los demás queda como observación (`observations`) y la imagen sale. Las fotos editadas siguen igual: cualquier fallo la descarta. La tarjeta fija tiene revisión de plantilla, identificada como fixed_brand_card; la tarjeta con la frase del post, como tarjeta_contenido.
- **La lista del tablero:**
  1. Trata la tesis del post y la amplía: aporta algo que el texto no dice ya; nada genérico ni de relleno. Responde una sola pregunta y se entiende en 3 segundos.
  2. Tiene un único punto focal y un único color de acento.
  3. El titular busca 8 palabras o menos y cada lámina unas 30 (guía de estilo: anota, no descarta).
  4. Nada está por debajo de 28 px en el lienzo de 1080.
  5. Todo dato tiene fuente, y si es estimación lo dice.
  6. Las barras empiezan en cero y se etiquetan directamente, sin leyenda.
  7. No hay degradados, sombras, 3D, emojis ni iconos decorativos.
  8. El contraste del texto es de 4,5:1 o más.
  9. El texto público está en inglés, sin errores.
  10. Lleva texto alternativo con el dato y la conclusión.
- **Criterios de aceptación:**
  1. **Dado** una infografía dibujada, **cuando** se revisa, **entonces** el código comprueba lo medible sin modelo: número de palabras (3), tamaño mínimo de 28 px (4), fuente presente en cada dato y «estimate» en las estimaciones (5), barras desde cero y sin leyenda (6), ausencia de degradados, sombras y elementos prohibidos en los datos de la plantilla (7), contraste de 4,5:1 para el texto y 3:1 para los elementos gráficos (8), un solo color de acento (2) y texto alternativo presente (10).
  2. **Dado** la misma infografía, **cuando** pasa lo medible, **entonces** un modelo con visión revisa lo visual: que responda una sola pregunta y se entienda en 3 segundos (1), que tenga un único punto focal (2) y que el texto en inglés no tenga errores (9), y que no haya nada decorativo (7).
  3. **Dado** que falla un punto que descarta (1, 4, 5, 8 o 9), **cuando** termina la revisión, **entonces** la infografía vuelve al diseñador con esos puntos para una corrección, y se vuelve a revisar; un punto de estilo que falla queda como observación.
  4. **Dado** que sigue fallando tras la corrección, **cuando** termina, **entonces** ese diseño no se publica y sale el respaldo ([IMG-INF-13](#img-inf-13)).
  5. **Dado** una infografía que pasa los 10 puntos, **cuando** se guarda el veredicto, **entonces** va ligado al SHA-256 de cada lámina exacta y el detalle de la pieza muestra el resultado ([IMG-11](#img-11)).
  6. **Dado** que la revisión visual falla por un error del proveedor, **cuando** termina, **entonces** la infografía no se da por buena.
- **Brechas código/docs:** Validación en CI pendiente; no se ejecutaron pruebas locales.
- **Cobertura QA:**

### IMG-INF-07 · Texto alternativo siempre <a id="img-inf-07"></a>

- **Dónde:** PWA · app · backend
- **Estado:** parcial
- **Qué hace para Gustavo:** cada imagen que publica lleva un texto alternativo con el dato y la conclusión, para quien no puede verla.
- **Implementación backend:** Alt obligatorio en API y manifiesto; altText en imágenes LinkedIn y /Alt en cada página del PDF.
- **Criterios de aceptación:**
  1. **Dado** una infografía o cada lámina de un carrusel, **cuando** se prepara, **entonces** lleva texto alternativo en inglés con el dato y la conclusión.
  2. **Dado** una foto de la Galería, **cuando** se prepara, **entonces** también lleva texto alternativo que la describe.
  3. **Dado** una imagen sin texto alternativo, **cuando** la revisa la política, **entonces** la descarta.
  4. **Dado** la publicación, **cuando** se crea el post, **entonces** el texto alternativo viaja a LinkedIn con la imagen ([IMG-14](#img-14)).
  5. **Dado** el detalle de la pieza en la PWA o la app, **cuando** lo abre, **entonces** ve el texto alternativo de cada imagen, y la imagen lo usa como su etiqueta accesible.
- **Brechas código/docs:** Interfaz y QA de fase 2 pendientes.
- **Cobertura QA:**

### IMG-INF-08 · Ningún modelo de imagen dibuja infografías ni texto <a id="img-inf-08"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Qué hace para Gustavo:** las infografías nunca tienen letras deformes ni cifras inventadas por un generador de imágenes: la API de imágenes de OpenAI solo toca sus fotos reales.
- **Implementación backend:** Solo Pillow y código PDF dibujan infografías; la API de imágenes se limita a fotos reales.
- **Criterios de aceptación:**
  1. **Dado** la preparación de una infografía o un carrusel, **cuando** se registra en el ledger, **entonces** no hay ninguna llamada a un modelo de generación o edición de imágenes.
  2. **Dado** una llamada a la API de imágenes de OpenAI, **cuando** se hace, **entonces** su entrada es siempre una foto de la Galería de Gustavo.
  3. **Dado** el texto que aparece en una infografía, **cuando** se dibuja, **entonces** sale tal cual de los datos estructurados, dibujado con la fuente Ubuntu.
- **Brechas código/docs:** Validación en CI pendiente; no se ejecutaron pruebas locales.
- **Cobertura QA:**

### IMG-INF-09 · La imagen amplía el post; el estilo se corrige, no descarta <a id="img-inf-09"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Qué hace para Gustavo:** la infografía aporta algo que el post no dice ya, siempre sobre su tesis: un gráfico con datos reales y su fuente, un caso real (una empresa, un producto, un informe, el blog de una compañía de IA), una comparación, los pasos que el post solo menciona o preguntas que llevan la idea más lejos. Y el verificador deja de bloquear por estilo (Gustavo, 19/11/2026: «que no bloquee todo»).
- **Origen:** de las últimas 14 piezas listas, 4 salieron con la tarjeta genérica «A question worth exploring». Motivos reales: «El cierre es una pregunta» (dos veces), «Demasiadas palabras» y «Dato sin fuente pública identificable y fecha».
- **Implementación backend:** `imagenes.DESIGN_SYSTEM` (propósito «amplía el post») y el punto 1 de la revisión; `infografias.fix` corrige el estilo con código antes de `infografias.validate`, que solo comprueba verdad y legibilidad; `connectors_images.soften` aplica la misma división al veredicto visual. Las correcciones pagadas siguen siendo dos (el arco `disenar` admite 2 llamadas por ciclo y `grafo.py` no admite bucles de más de 2 rondas); las rondas extra son gratis: `fix` entre una y otra, acortar el texto secundario si no cabe en la rejilla, y en el lienzo la plantilla de la misma respuesta.
- **Reglas, antes y después:**

| Regla | Antes | Ahora |
| --- | --- | --- |
| Toda cifra con fuente pública identificable y fecha | descarta | **dura**; la cifra sin fuente se quita del texto secundario (bajada, cuerpo, pasos, filas) y solo descarta si la cifra es la lámina (número, barras, línea, titular, encabezados) |
| Fuente que no está en `public_facts` ni `sources` | descarta | se retira la cita (y la cifra que dependía de ella) |
| Estimación sin la palabra «estimate» | descarta | se añade «(estimate)» |
| Sin experiencias inventadas ni hechos privados del dueño (`guardas`) | descarta | **dura** |
| Texto alternativo presente (8–1.500 caracteres) | descarta | se escribe desde el titular si falta; **dura** si sigue sin haber |
| Emojis | descarta | se quitan; **dura** si queda alguno (la fuente no los dibuja) |
| Legible: 28 px, contraste 4,5:1, nada se desborda | descarta | **dura**; si no cabe se quita el texto secundario y se dibuja otra vez |
| Estructura mínima de la plantilla (2 pasos, 1 pregunta, 2 columnas, valores desde cero…) | descarta | **dura** (sin eso no hay qué dibujar ni el gráfico es honesto) |
| Número de láminas | 1 (imagen) / 3–8 (carrusel) | 1 / **2–8** |
| Titular de 8 palabras | descarta | nota; **dura** solo por encima de 14 (24 en `cita`) |
| Palabras por lámina (30 / 40) | descarta | guía por plantilla (tabla 70, comparación y lista 60, pasos y preguntas 55); el código quita texto secundario |
| Mayúsculas solo en etiquetas | descarta | se pasan a minúsculas (las siglas conocidas se quedan) |
| Hashtags y «!!» | descarta | se corrigen |
| Etiqueta con decoración | descarta | se limpia |
| Portada en minúsculas | descarta | nota |
| Palabra de acento de la portada | descarta | se quita si no está en el titular |
| El carrusel empieza con portada | descarta | nota |
| El cierre es una pregunta | descarta | nota |
| Una sola portada | descarta | **quitada** |
| Pasos 3–5, preguntas 2–4, barras 1–5 con un foco | descarta | se quedan los primeros (las 5 barras mayores) y el foco se fija; mínimo duro: 2 pasos, 1 pregunta, 1 barra |
| Preguntas numeradas o con viñetas; elementos que no son pregunta | descarta | se quitan las marcas y los elementos que no son pregunta |
| Pasos o preguntas en otra plantilla, campos sueltos | descarta | se quitan |
| «Sígueme» | descarta | se quita |
| Revisión visual: cualquier punto que falle | descarta | solo 1 (tema y amplía), 4, 5, 8 y 9 descartan; 2, 3, 6, 7 y 10 son observaciones |
| Lienzo: 40 % vacío y titular dentro del lienzo | descartaba en el prototipo | **quitadas**; tope de palabras 80 → 90 |

- **Criterios de aceptación:**
  1. **Dado** un carrusel cuyo cierre no es una pregunta, **cuando** se valida, **entonces** sale como carrusel con una nota.
  2. **Dado** una lámina con más palabras que la guía, **cuando** se valida, **entonces** el código quita el texto secundario y la imagen sale.
  3. **Dado** una cifra sin fuente en el texto secundario, **cuando** se valida, **entonces** se quita esa cifra y la imagen sale; si la cifra es la lámina, se pide una corrección con el motivo exacto.
  4. **Dado** el verificador visual, **cuando** falla solo un punto de estilo, **entonces** la imagen sale y el detalle muestra la observación.
- **Cobertura QA:** `test_infografias_libres.RulesTests`, `test_infografias_libres.RealReasonsFlowTests` y las pruebas de reglas de `test_imagenes.RendererTests`.

### IMG-INF-10 · Plantillas tabla, comparación, línea y lista <a id="img-inf-10"></a>

- **Dónde:** backend (la PWA y la app ya muestran el nombre de la plantilla en el detalle de la pieza)
- **Estado:** funciona
- **Qué hace para Gustavo:** más formas de ampliar un post: una tabla (varias cosas con los mismos atributos), una comparación en dos columnas (antes y después, dos opciones), una línea simple (una evolución, siempre con fuente) y una lista numerada con detalle corto. La plantilla `cita` la reserva el código para el respaldo ([IMG-INF-13](#img-inf-13)).
- **Implementación backend:** `infografias.SLIDE` (campos `columns`, `rows`, `series`), `_structure` (reglas duras de cada una) y `render` (`_table`, `_comparison`, `_line_chart`). Un diseño guardado antes de estos campos se lee igual (`normalize`).
- **Criterios de aceptación:**
  1. **Dado** cada plantilla nueva, **cuando** se dibuja, **entonces** mide 1080×1080 (imagen) o 1080×1350 (carrusel) y respeta márgenes, paleta y 28 px.
  2. **Dado** una tabla sin 2 a 4 columnas, una fila sin una celda por columna, una comparación sin dos encabezados, una línea con valores que no cuadran con sus puntos o negativos, o una lista de un solo punto, **cuando** se valida, **entonces** se rechaza con el motivo.
  3. **Dado** una línea, **cuando** se valida, **entonces** necesita fuente como cualquier dato.
- **Cobertura QA:** `test_infografias_libres.NewTemplatesTests`.

### IMG-INF-11 · El editor visual elige el layout y no repite el anterior <a id="img-inf-11"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Qué hace para Gustavo:** sus imágenes no salen todas iguales: el editor visual elige el layout de la imagen única según el contenido (dato, barras, línea, tabla, comparación, pasos, lista, preguntas, portada) y, si coincide con el de la imagen anterior y otro también encaja, cambia.
- **Implementación backend:** `editor_visual.request` añade `recent_layouts` (las 5 últimas imágenes listas de la cuenta) y `referent_visual` (el recurso visual del post referente que inspiró la pieza, solo como etiqueta: imagen, video, documento…; se lee a la defensiva y, si no hay, no se manda nada); `infografias.choice_schema` añade `layout` y `alternatives`; `editor_visual.settle_layout` aplica la regla de no repetir y la anota en el motivo. El diseñador recibe el layout en `brief.image.layout`.
- **Criterios de aceptación:**
  1. **Dado** que la imagen anterior fue `pasos` y el editor vuelve a elegir `pasos` con `lista` como alternativa, **cuando** se fija la elección, **entonces** sale `lista` y el motivo lo dice.
  2. **Dado** que no hay alternativa, **cuando** se fija, **entonces** se mantiene la elección.
  3. **Dado** el lienzo apagado, **cuando** el editor elige `lienzo`, **entonces** se usa su primera alternativa.
- **Cobertura QA:** `test_infografias_libres.LayoutChoiceTests`.

### IMG-INF-12 · Lienzo libre en HTML y CSS <a id="img-inf-12"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Interruptor:** `INFOGRAFIA_LIENZO`, apagado por defecto.
- **Qué hace para Gustavo:** cuando ninguna plantilla le hace justicia al contenido (un esquema, un mapa, una composición propia), el diseñador escribe la composición en HTML y CSS con los colores, la tipografía y los márgenes del manual, y el código la valida y la dibuja. Si no pasa, sale la plantilla de la misma respuesta.
- **Implementación backend:** `lienzo.py` y `lienzo_render.py`.
  - **Saneado (rechaza con el motivo, nunca recorta en silencio):** sin scripts, manejadores `on…`, enlaces, imágenes, svg, iframes, formularios, `meta` distinto de `charset`, `javascript:` ni `data:`; atributos solo `class`, `style`, `colspan` y `rowspan`; CSS sin `url()`, `@import`, `@font-face`, `@media`, cadenas, degradados, sombras, transparencias, transformaciones, `!important`, variables propias, selectores de id, `html`, `body`, `:root` ni pseudo-elementos; colores solo de la paleta (hex o `var()`), nada por debajo de 28 px, sin `overflow` oculto ni `display:none`. El renderizador solo recibe la reconstrucción del documento, nunca la cadena del diseñador.
  - **Verdad:** las mismas reglas que una plantilla (toda cifra con fuente, sin emojis, alt) y un tope de 90 palabras.
  - **Render:** WeasyPrint (HTML/CSS a PDF, sin motor de JavaScript) y pdfium (PDF a PNG) en un proceso hijo `python -I` con el entorno filtrado (ninguna clave del worker), la red bloqueada (solo puede leer la fuente Ubuntu del paquete; cualquier otra URL hace fallar el render), memoria limitada a 1.024 MB de espacio de direcciones, un render a la vez (cerrojo en el proceso y en el contenedor) y un límite de tiempo (`INFOGRAFIA_LIENZO_TIMEOUT_S`, 45 s).
  - **Medición del resultado:** una página, nada fuera del área de 888×744, nada por debajo de 28 px, colores de la paleta, contraste de 4,5:1, sin texto encima de texto; el código dibuja la fuente y el pie. Después pasa la misma revisión visual que una plantilla, con sus puntos propios.
  - **Respaldo:** la plantilla de la misma respuesta (sin otra llamada pagada); después, la corrección ya es de plantilla; después, [IMG-INF-13](#img-inf-13).
- **Elección del renderizador y su coste:**

| Opción | Memoria del render (medida) | Imagen del contenedor | Decisión |
| --- | --- | --- | --- |
| WeasyPrint 70 + pypdfium2, proceso hijo | ~95–100 MiB PSS de pico; 1,4–2 s por render en local | +65–70 MB (Pango ~17 MB y paquetes Python ~50 MB) | **elegida**: sin JavaScript ni navegador, cabe en los 768 MB del worker |
| Chromium headless (Playwright) | ~200 MiB PSS (515 MiB RSS) | +450–550 MB | descartada: ejecuta JavaScript y pesa el doble |
| Servicio «navegador» aparte | un contenedor más | — | descartado: más superficie y red entre servicios |

  WeasyPrint no ejecuta JavaScript y no soporta todo el CSS moderno (por ejemplo, `position: sticky` o algunas propiedades de grid), pero flex, grid básico, tablas y bordes alcanzan para una infografía.
- **Para encenderlo en producción:** reconstruir la imagen del backend (el `Dockerfile` ya instala Pango), poner `INFOGRAFIA_LIENZO=true` y, si el servidor es lento, subir `INFOGRAFIA_LIENZO_TIMEOUT_S`.
- **Criterios de aceptación:**
  1. **Dado** el interruptor apagado, **cuando** se diseña, **entonces** la petición al diseñador es la de plantillas (mismo system, mismo esquema, mismas claves, 5.000 tokens) y no se renderiza ningún lienzo.
  2. **Dado** un lienzo con algo fuera de la lista permitida, **cuando** se valida, **entonces** se rechaza con el motivo y sale la plantilla de la misma respuesta.
  3. **Dado** un lienzo cuya medición falla, **cuando** se dibuja, **entonces** sale la plantilla de la misma respuesta, sin otra llamada.
  4. **Dado** una página que pide recursos externos, **cuando** la renderiza el proceso hijo, **entonces** no sale ninguna conexión.
- **Cobertura QA:** `test_infografias_libres.CanvasSanitizerTests`, `RealRenderTests` (render real; en CI no se salta) y `CanvasFlowTests`.

### IMG-INF-13 · Respaldo con la frase del post antes que la tarjeta genérica <a id="img-inf-13"></a>

- **Dónde:** backend (la PWA y la app muestran el respaldo y su motivo en el detalle de la revisión)
- **Estado:** funciona
- **Qué hace para Gustavo:** si ningún diseño pasa, la pieza ya no sale con «A question worth exploring»: sale la frase clave de su post (y su pregunta, si la hace) en una tarjeta sin cifras; si no, la foto que propuso el editor visual; y solo si el post no tiene ninguna frase que sirva, la tarjeta genérica de marca.
- **Implementación backend:** `imagenes.fallback` → `content_card` (plantilla `cita`, modo `tarjeta_contenido`; frases de 4 a 24 palabras sin cifras, enlaces, menciones ni llamadas a seguir, tal cual las dice el post) → `fallback_photo` (solo si la elección traía fotos con su alt; modo `foto_respaldo`) → `brand_card` (modo `fixed_brand_card`). Cada respaldo guarda `fallback: {level, reason}` en la revisión y una auditoría `editorial.image_fallback`. `imagenes.fallback_counts` los cuenta y `operador respaldos-imagen` los muestra.
- **Cuántos respaldos se esperan:** solo un fallo de verdad que persiste tras la corrección (una cifra que es la lámina sin fuente, un dato privado, un texto que no cabe aun acortado) o un proveedor caído llevan al respaldo, y casi siempre a la frase del post. La tarjeta genérica queda para posts sin ninguna frase de 4 a 24 palabras sin cifras ni enlaces, sin foto propuesta: se estima por debajo del 5 % de las piezas (estimación, sin medir todavía en producción).
- **Comando:** `python manage.py operador --usuario <admin> respaldos-imagen --cuenta <uuid> [--dias 30]`.
- **Criterios de aceptación:**
  1. **Dado** cada uno de los tres motivos reales, **cuando** se prepara la imagen, **entonces** sale una imagen con contenido (el diseño corregido o la frase del post), no la tarjeta genérica.
  2. **Dado** un post sin ninguna frase que sirva y sin foto propuesta, **cuando** no pasa ningún diseño, **entonces** sale la tarjeta genérica y queda contada como último recurso.
- **Cobertura QA:** `test_infografias_libres.RealReasonsFlowTests`, `ContentCardTests`; `test_imagenes.ImageWorkflowTests` y `test_editor_visual` (respaldo sin claves).

### IMG-INF-14 · Una investigación propia para la imagen <a id="img-inf-14"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Interruptor:** `INFOGRAFIA_INVESTIGACION`, apagado por defecto.
- **Qué hace para Gustavo:** si la pieza no trae ningún dato con fuente que una imagen pueda mostrar, el equipo busca una vez en la web un dato reciente o un caso real sobre la tesis, con su fuente y fecha, para que la infografía lo enseñe.
- **Implementación backend:** `imagenes.research_for_image`, llamado por el director antes de pedirle la imagen al editor visual (`editorial._visual`, una línea). Usa el mismo arco `investigar_pieza` de la pieza (1 por ciclo), su reserva y sus topes. Solo corre si la reserva de la investigación (~0,83 USD con la configuración actual) **y** la de la etapa de imagen que viene después (~0,39 USD; 0,45 un carrusel) caben en lo que queda del ciclo (`pieza_diaria`, tope 8 USD) y en el presupuesto de IA del día; si no, se salta y lo anota en `usage` (`investigacion_imagen`), así nunca detiene el ciclo. La pregunta pasa por `research.safe_question`. No corre si el director ya usó la investigación de la pieza ni en fotos.
- **Criterios de aceptación:**
  1. **Dado** el interruptor apagado, **cuando** se prepara la imagen, **entonces** no hay ninguna búsqueda.
  2. **Dado** que no cabe en el ciclo o en el presupuesto, **cuando** se prepara, **entonces** se salta con el motivo.
  3. **Dado** que el ciclo se reanuda, **cuando** vuelve a pasar, **entonces** no se repite la búsqueda ni se duplica la fuente.
- **Cobertura QA:** `test_infografias_libres.ImageResearchTests` (con la investigación simulada).

### IMG-INF-15 · Rehacer las piezas que salieron con la tarjeta genérica <a id="img-inf-15"></a>

- **Dónde:** backend
- **Estado:** funciona
- **Qué hace para Gustavo:** «ayúdame a corregir las piezas que ya tienen esa infografía genérica»: lista las piezas no publicadas con la tarjeta genérica y, si se confirma, rehace su imagen; la nueva versión pasa por el líder a la misma hora.
- **Comando:** `python manage.py operador --usuario <admin> rehacer-tarjetas --cuenta <uuid>` (solo lista, con el costo estimado y el presupuesto que queda) y el mismo con `--confirmar` (llamadas pagadas).
- **Implementación backend:** `retoque.redo_plan`, `redo_images` y `redo_image`, sobre la maquinaria de los retoques (ciclo `retoque_pieza`): la versión abierta se reemplaza, la imagen se diseña otra vez con sus respaldos, el paquete visual se vuelve a atar y se crea una versión nueva para el líder. No había una ruta «Rehecha a petición de Gustavo / image_review.redo» en el código: se construyó sobre los retoques.
- **Criterios de aceptación:**
  1. **Dado** una pieza ya publicada, **cuando** se lista, **entonces** dice «publicada, no se puede cambiar» (LinkedIn no permite cambiar la imagen de un post).
  2. **Dado** una pieza a menos del plazo de veto de su hora, una sin versión pendiente o sin revisiones del líder en su ciclo, **cuando** se lista, **entonces** se omite y dice por qué.
  3. **Dado** que no queda presupuesto de IA para su estimación, **cuando** se confirma, **entonces** no se toca.
  4. **Dado** un fallo después de reemplazar la versión, **cuando** termina, **entonces** la pieza queda bloqueada con el motivo, como un retoque fallido.
- **Cobertura QA:** `test_infografias_libres.RedoBrandCardsTests`.

## Retiradas

Ninguna.
