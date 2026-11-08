# Imágenes en las publicaciones (`IMG`, `IMG-INF`)

Gustavo quiere que cada post salga con al menos una imagen. El equipo de redacción decide por contexto qué imagen lleva cada post:
- una foto de su Galería, editada o no, con las reglas de edición de este archivo;
- una infografía hecha desde cero;
- un carrusel.

**Regla dura: siempre hay al menos una imagen.** No existe el resultado «sin imagen»: si no se puede preparar ninguna imagen válida, la pieza no se publica (queda bloqueada con el motivo), nunca sale solo con texto.

Las fotos llegan con la nota de Gustavo (de voz o escrita) como contexto y, si la trae, como instrucción. La API de imágenes de OpenAI solo se usa para editar sus fotos reales. Las infografías y los carruseles no los dibuja ningún modelo de imagen: el agente elige una plantilla y escribe el contenido como datos, y el código lo dibuja exactamente con las reglas de marca de Gustavo («Infografías hechas con IA · reglas», ver [Infografías y carruseles](#infografias-y-carruseles)).

**Todo este archivo está en estado `no implementado`.** Comprobado en el código del commit `486a23d`:
- `knowledge/providers.py` solo llama a OpenAI para embeddings: no hay edición de imágenes;
- `GalleryPhoto.allow_ai_edit` se guarda y se devuelve (`capturas_views.PhotoDetail.patch`, `capturas.photo_payload`), pero ningún código lo lee para decidir nada;
- el circuito editorial nunca consulta la Galería: `editorial.py` no importa `GalleryPhoto`, y nada fija `state`, `chosen_piece`, `chosen_for` ni `published_at` de una foto;
- el brief solo admite `format: "text_only"` (`editorial.BRIEF_SCHEMA`); los formatos foto, infografía y carrusel del curso (`LI-05-M002-K05..K08`, `LI-05-M003-K01..K03`) están anotados en `editorial.py` como «wait for the image phase»;
- `connectors_linkedin.post_body` publica solo `commentary`: no hay subida de imágenes ni de documentos;
- no hay código que dibuje infografías ni una regla de agente de infografías (no existe nada parecido a `voz.py` + `recursos/tono-de-voz.md` para imágenes);
- el detalle de la pieza no tiene ningún campo de imagen en la API (`editorial_views.PieceDetail`), en los tipos (`compartido/src/api/types.ts`) ni en las pantallas de la PWA y la app;
- «Para qué es» solo tiene «Idea para un post», «Dato sobre mí», «Responde una pregunta» y «Foto para la galería» (`Capture.Purpose`).

Lo que sí existe y este flujo reutilizará: la captura con fotos ([CAP-05](captura.md#cap-05), que hoy falla en la app), la Galería con su nota y su interruptor de edición ([galeria.md](galeria.md)), el ledger de gasto con reserva y liquidación, el verificador y la ronda de reparación del circuito editorial ([EDI-07](motor-editorial.md#edi-07), [EDI-08](motor-editorial.md#edi-08)), la regla de agente de la voz ([EDI-16](motor-editorial.md#edi-16)), el veto de la pieza ([CAL-12](calendario-piezas.md#cal-12)) y la publicación por la API oficial ([EDI-11](motor-editorial.md#edi-11)).

- **Código de referencia:** `capturas.py`, `capturas_views.py`, `models.GalleryPhoto`, `models.Capture`, `editorial.py`, `voz.py`, `connectors_linkedin.py`, `knowledge/providers.py`; PWA `oficina/src/pages/PiezaDetalle.tsx`, `pages/galeria/*`; app `movil/src/pieza/*`, `movil/src/galeria/*`.
- **Documentación que lo anuncia:** «Fase de imagen» en [`capturas-galeria.md`](../../agentes-linkedin/infra/docs/capturas-galeria.md); «Límites y pendientes» en [`publicacion-diaria.md`](../../agentes-linkedin/infra/docs/publicacion-diaria.md); «Galería» en [`CONTRATO-API.md`](../../oficina/CONTRATO-API.md); [`herramientas-linkedin-v2.md`](../../agentes-linkedin/infra/docs/herramientas-linkedin-v2.md) («imágenes de OpenAI y fotos reales»).
- **Reglas de infografías:** tablero `Infografias.dc.html` («Infografías hechas con IA · reglas») del canvas de Gustavo, https://claude.ai/artifact/9ebjAHA228bpQJM9XP64ee. **No está en el repositorio:** `movil/diseno-movimiento/` es una copia anterior del canvas y no lo incluye.

## Resumen

| ID | Función | Dónde | Estado |
| --- | --- | --- | --- |
| [IMG-01](#img-01) | Mandar fotos con una nota de voz o escrita que da contexto e instrucción | PWA · app · backend | no implementado |
| [IMG-02](#img-02) | Opción «Propuesta de post» en «Para qué es» | PWA · app · backend | no implementado |
| [IMG-03](#img-03) | Las fotos siempre llegan a la Galería con su nota | backend | no implementado |
| [IMG-15](#img-15) | El equipo elige por contexto: foto, infografía o carrusel | backend | no implementado |
| [IMG-16](#img-16) | Opción «Edición con IA» en la captura, la Galería y Ajustes | PWA · app · backend | no implementado |
| [IMG-04](#img-04) | El equipo ve la Galería y elige las fotos de un post | backend | no implementado |
| [IMG-05](#img-05) | Todo post se publica con al menos una imagen | backend | no implementado |
| [IMG-06](#img-06) | La nota de una propuesta de post alimenta el brief | backend | no implementado |
| [IMG-07](#img-07) | Decidir si se edita una foto: manda la opción de edición; la nota dice cómo | backend | no implementado |
| [IMG-08](#img-08) | Ediciones que el equipo decide por su cuenta | backend | no implementado |
| [IMG-09](#img-09) | Editar con la API de imágenes de OpenAI sin perder el original | backend | no implementado |
| [IMG-10](#img-10) | Comprobación de la edición con un modelo con visión | backend | no implementado |
| [IMG-11](#img-11) | La imagen en el detalle de la pieza, con veto | PWA · app · backend | no implementado |
| [IMG-12](#img-12) | La Galería marca la foto «usada en la pieza del …» | PWA · app · backend | no implementado |
| [IMG-13](#img-13) | Coste de las imágenes en el ledger, con presupuesto propio | PWA · app · backend | no implementado |
| [IMG-14](#img-14) | Publicar en LinkedIn con la imagen o el carrusel | backend | no implementado |
| [IMG-INF-01](#img-inf-01) | Las reglas de infografías son una regla de agente | backend | no implementado |
| [IMG-INF-02](#img-inf-02) | El agente elige una plantilla y escribe el contenido como datos | backend | no implementado |
| [IMG-INF-03](#img-inf-03) | El código dibuja la infografía exactamente con las reglas | backend | no implementado |
| [IMG-INF-04](#img-inf-04) | Datos honestos y con fuente | backend | no implementado |
| [IMG-INF-05](#img-inf-05) | Carrusel: portada, láminas y cierre | backend | no implementado |
| [IMG-INF-06](#img-inf-06) | Revisión con la lista de 10 puntos | backend | no implementado |
| [IMG-INF-07](#img-inf-07) | Texto alternativo siempre | PWA · app · backend | no implementado |
| [IMG-INF-08](#img-inf-08) | Ningún modelo de imagen dibuja infografías ni texto | backend | no implementado |

`IMG-15` va arriba en la tabla porque es la primera decisión del flujo; conserva su número para no cambiar los enlaces de otras fichas.

## Pendiente de confirmar

- Nada. Las ediciones que decide el equipo quedan resueltas con la opción de edición de [IMG-16](#img-16) (decisión de Gustavo, 2026-11-08): con «Que decida el equipo» o «Editar», el equipo aplica la edición y la muestra para veto, sin preguntar antes.

---

### IMG-01 · Mandar fotos con una nota de voz o escrita que da contexto e instrucción <a id="img-01"></a>

- **Dónde:** PWA · app · backend
- **Estado:** no implementado
- **Qué hace para Gustavo:** manda una o varias fotos (de la cámara o de su galería) con una nota de voz, una nota escrita o las dos. Lo que dice es el contexto de las fotos y, cuando lo trae, una instrucción («úsala tal cual», «recórtala», «quita el fondo», «más luz»).
- **Código hoy:** la captura ya acepta fotos, audio y nota juntos (`capturas.create`, hasta 10 fotos). Nadie extrae una instrucción del texto: la nota y la transcripción solo se rutean como un todo (`capturas._destination`). En la app, enviar fotos o audio falla ([CAP-04](captura.md#cap-04), [CAP-05](captura.md#cap-05)).
- **Criterios de aceptación:**
  1. **Dado** dos fotos de la cámara y una nota de voz «la de la izquierda úsala tal cual; a la otra dale más luz», **cuando** las envía, **entonces** llega una sola captura con las dos fotos, el audio y su transcripción.
  2. **Dado** esa captura procesada, **cuando** el equipo la lee, **entonces** cada foto queda con su contexto (la nota y la transcripción) y con la instrucción que le corresponde, si la hay: «tal cual» para la primera, «más luz» para la segunda.
  3. **Dado** una nota que solo da contexto («esta es de la charla en Medellín»), **cuando** se procesa, **entonces** la foto queda sin instrucción y con ese contexto.
  4. **Dado** una instrucción que no se puede atribuir a una foto concreta («recórtalas»), **cuando** se procesa, **entonces** se aplica a todas las fotos de la captura.
  5. **Dado** que la instrucción no se pudo leer (por ejemplo, la transcripción falló), **cuando** se procesa, **entonces** la foto queda sin instrucción, la captura muestra el error de la transcripción y la foto sigue en la Galería.
  6. **Dado** la instrucción interpretada, **cuando** se guarda, **entonces** Gustavo la ve en la hoja de la foto, junto a su nota.
- **Brechas código/docs:** —
- **Cobertura QA:** pendiente

### IMG-02 · Opción «Propuesta de post» en «Para qué es» <a id="img-02"></a>

- **Dónde:** PWA · app · backend
- **Estado:** no implementado
- **Qué hace para Gustavo:** marca que lo que manda es una propuesta de post: fotos y una nota que quiere convertir en publicación. Si no elige nada, el equipo clasifica la captura como hasta ahora.
- **Código hoy:** `Capture.Purpose` tiene `post` («Idea para un post»), `dato`, `respuesta` y `galeria`. El clasificador (`capturas.classify`, Sonnet, propósito `capture-route`) elige entre `post`, `dato` y `galeria`.
- **Criterios de aceptación:**
  1. **Dado** la hoja de captura, **cuando** abre «Para qué es (opcional)», **entonces** ve la opción nueva «Propuesta de post» junto a las existentes.
  2. **Dado** «Propuesta de post» con fotos y una nota, **cuando** envía, **entonces** la API acepta el valor nuevo de `para`, las fotos quedan en la Galería con la nota ([IMG-03](#img-03)) y la captura llega al equipo de redacción como recomendación de contenido ([IMG-06](#img-06)), ligada a esas fotos.
  3. **Dado** que no elige nada, **cuando** se procesa, **entonces** el clasificador puede decidir «propuesta de post», y «Lo que enviaste» lo muestra con «… · lo decidió el equipo» y el motivo.
  4. **Dado** «Propuesta de post» sin fotos ni texto, **cuando** intenta enviar, **entonces** no puede: hace falta al menos una foto o una nota.
  5. **Dado** una propuesta procesada, **cuando** la mira en «Lo que enviaste», **entonces** el resultado dice dónde quedó (por ejemplo «Mesa editorial lo tendrá en cuenta») y, cuando se usa, «Usado» con enlace a la pieza.
  6. **Dado** que la pieza que usó la propuesta no sale, **cuando** se cierra, **entonces** la propuesta vuelve a la mesa editorial, como las ideas de hoy ([EDI-17](motor-editorial.md#edi-17)).
- **Brechas código/docs:** —
- **Cobertura QA:** pendiente

### IMG-03 · Las fotos siempre llegan a la Galería con su nota <a id="img-03"></a>

- **Dónde:** backend
- **Estado:** no implementado
- **Qué hace para Gustavo:** cualquier foto que manda acaba en su Galería con lo que dijo sobre ella, sea cual sea el destino de la captura.
- **Código hoy:** las fotos de cualquier captura ya se guardan en la Galería (`capturas._save_photos`), pero la nota solo se copia a la foto cuando la captura va a la Galería (`capturas._route_gallery`). Con «Idea para un post», un dato o un contexto, la foto queda sin nota y solo ligada a la captura por `capture`.
- **Criterios de aceptación:**
  1. **Dado** una captura con fotos y destino «Idea para un post», «Propuesta de post», «Dato sobre mí» o un contexto, **cuando** se procesa, **entonces** cada foto queda en la Galería con la nota de la captura (y la transcripción, si hubo audio) como su nota.
  2. **Dado** una foto que ya tenía una nota escrita por Gustavo en la Galería, **cuando** llega otra captura sobre ella, **entonces** su nota no se sobrescribe.
  3. **Dado** que Gustavo deshace la captura en los 2 minutos, **cuando** se deshace, **entonces** sus fotos desaparecen de la Galería, como hoy ([CAP-10](captura.md#cap-10)).
  4. **Dado** una nota de más de 2.000 caracteres, **cuando** se copia a la foto, **entonces** se recorta al máximo de la nota de una foto y la captura conserva el texto completo.
- **Brechas código/docs:** `capturas-galeria.md` dice que con `para=galeria` «el texto pasa a ser su nota», y no lo dice para los demás destinos.
- **Cobertura QA:** pendiente

### IMG-15 · El equipo elige por contexto: foto, infografía o carrusel <a id="img-15"></a>

- **Dónde:** backend
- **Estado:** no implementado
- **Qué hace para Gustavo:** para cada post, el equipo de redacción decide qué imagen lo cuenta mejor: una de sus fotos, una infografía o un carrusel.
- **Código hoy:** no existe. El brief solo admite `text_only`.
- **Criterios de aceptación:**
  1. **Dado** el brief de una pieza, **cuando** se guarda, **entonces** incluye el tipo de imagen elegido (`foto`, `infografia` o `carrusel`) y el motivo, a partir de la tesis, el enfoque, la propuesta de Gustavo si la hay y las fotos disponibles.
  2. **Dado** una propuesta de post de Gustavo con fotos, **cuando** se decide, **entonces** sus fotos son la primera opción, salvo que el equipo explique por qué otra imagen sirve mejor.
  3. **Dado** un post que explica un proceso o una idea en pasos, **cuando** se decide, **entonces** el equipo puede elegir un carrusel ([IMG-INF-05](#img-inf-05)).
  4. **Dado** un post con un dato o una frase protagonista, **cuando** se decide, **entonces** el equipo puede elegir una infografía de imagen única ([IMG-INF-02](#img-inf-02)).
  5. **Dado** que la Galería está vacía o ninguna foto encaja, **cuando** se decide, **entonces** el equipo elige una infografía o un carrusel; nunca «sin imagen».
  6. **Dado** que la foto elegida deja de estar disponible (Gustavo la borra) o no pasa sus comprobaciones, **cuando** se prepara la pieza, **entonces** el equipo cambia a otra foto o a una infografía, y lo registra.
  7. **Dado** que no se puede preparar ninguna imagen válida, **cuando** termina la preparación, **entonces** la pieza queda bloqueada con el motivo y llega el aviso de pieza bloqueada ([EDI-09](motor-editorial.md#edi-09)); no se publica sin imagen.
- **Brechas código/docs:** —
- **Cobertura QA:** pendiente

### IMG-16 · Opción «Edición con IA» en la captura, la Galería y Ajustes <a id="img-16"></a>

- **Dónde:** PWA · app · backend
- **Estado:** no implementado
- **Qué hace para Gustavo:** al adjuntar fotos elige si el equipo puede editarlas con IA, sin tener que decirlo en el audio: «No editar», «Que decida el equipo» o «Editar».
- **Código hoy:** solo existe el interruptor booleano «Permitir edición con IA» en la hoja de cada foto de la Galería (`allow_ai_edit`) y su valor por defecto en Ajustes › Captura y galería (`gallery_ai_edit_default`). La hoja de captura no lo muestra.
- **Criterios de aceptación:**
  1. **Dado** la hoja de captura con al menos una foto adjunta, **cuando** se abre, **entonces** muestra el control «Edición con IA» con tres opciones («No editar», «Que decida el equipo», «Editar»), preseleccionado con el valor por defecto de Ajustes.
  2. **Dado** que elige una opción y envía, **cuando** las fotos llegan a la Galería, **entonces** cada foto guarda esa opción.
  3. **Dado** la hoja de una foto en la Galería, **cuando** se abre, **entonces** el interruptor actual pasa a ser el mismo control de tres opciones y guardar envía solo el campo cambiado.
  4. **Dado** Ajustes › Captura y galería, **cuando** se cambia el valor por defecto, **entonces** las fotos nuevas lo toman y las existentes no cambian.
  5. **Dado** fotos guardadas antes del cambio, **cuando** se migra, **entonces** `allow_ai_edit=false` pasa a «No editar» y `true` a «Que decida el equipo», sin perder ninguna.
  6. **Dado** una foto ya usada en una pieza, **cuando** se cambia su opción, **entonces** solo afecta a usos futuros.
  7. **Dado** lectores de pantalla, **cuando** recorren el control, **entonces** es un grupo de opciones con nombre y la opción elegida anunciada.
- **Brechas código/docs:** el backend pasa de un booleano a un valor de tres estados (`ai_edit`: `no` · `auto` · `si`), con migración y contrato actualizados.
- **Cobertura QA:** pendiente

### IMG-04 · El equipo ve la Galería y elige las fotos de un post <a id="img-04"></a>

- **Dónde:** backend
- **Estado:** no implementado
- **Qué hace para Gustavo:** cuando un post va con foto, el equipo mira sus fotos, con sus notas y transcripciones, la fecha, si ya se usaron y si permite editarlas, y elige una o varias.
- **Código hoy:** `editorial._run` no recibe fotos. Los campos para registrar la elección ya existen sin usar: `GalleryPhoto.state` (`sin_usar`, `elegida`, `editada`, `publicada`), `chosen_piece`, `chosen_for`, `published_at`.
- **Criterios de aceptación:**
  1. **Dado** fotos en la Galería, **cuando** corre la etapa del director, **entonces** recibe por cada foto candidata su `id`, su nota, la nota y la transcripción de su captura de origen, la fecha de subida, si ya se usó (y en qué pieza) y su opción de edición ([IMG-16](#img-16)).
  2. **Dado** un brief con tipo `foto`, **cuando** se guarda, **entonces** incluye las fotos elegidas (al menos una) con el motivo de cada elección.
  3. **Dado** una foto elegida, **cuando** se liga a la pieza, **entonces** su estado pasa a `elegida`, `chosen_piece` apunta a la pieza y `chosen_for` es el día de la pieza.
  4. **Dado** que la pieza no sale (saltada, bloqueada, fallida, descartada, vetada o caducada), **cuando** se cierra, **entonces** sus fotos vuelven a `sin_usar`.
  5. **Dado** fotos más grandes de lo que admite el modelo, **cuando** se le envían para elegir, **entonces** recibe versiones reducidas y el original queda intacto.
- **Brechas código/docs:** —
- **Cobertura QA:** pendiente

### IMG-05 · Todo post se publica con al menos una imagen <a id="img-05"></a>

- **Dónde:** backend
- **Estado:** no implementado
- **Qué hace para Gustavo:** ningún post suyo sale solo con texto.
- **Código hoy:** `BRIEF_SCHEMA` fuerza `format: "text_only"`; `autopiloto.post_issues` no mira imágenes.
- **Criterios de aceptación:**
  1. **Dado** una propuesta CONT-09 sin imagen, **cuando** la revisa la política autónoma, **entonces** la descarta con un motivo como «Sin imagen».
  2. **Dado** una propuesta CONT-09 con imagen (foto, infografía o carrusel), **cuando** se calcula su `payload_hash`, **entonces** cubre el texto, el hash de cada imagen o lámina y su texto alternativo; cambiar cualquiera invalida la aprobación igual que cambiar el texto.
  3. **Dado** una imagen sin su comprobación favorable sobre su hash exacto ([IMG-10](#img-10) para fotos editadas, [IMG-INF-06](#img-inf-06) para infografías y carruseles), **cuando** la revisa la política, **entonces** la descarta.
  4. **Dado** una pieza publicada, **cuando** se abre el post en LinkedIn, **entonces** lleva la imagen o el carrusel que muestra el detalle de la pieza.
  5. **Dado** el veredicto del verificador del texto, **cuando** se calcula, **entonces** sigue valiendo solo para el texto exacto; la imagen tiene su propia comprobación.
- **Brechas código/docs:** `publicacion-diaria.md`: «Solo texto. Imágenes, carruseles y vídeo (CONT-04) llegan en una fase posterior».
- **Cobertura QA:** pendiente

### IMG-06 · La nota de una propuesta de post alimenta el brief <a id="img-06"></a>

- **Dónde:** backend
- **Estado:** no implementado
- **Qué hace para Gustavo:** lo que dice en una «Propuesta de post», o en una captura que el equipo lee como tal, le sirve al equipo como recomendación de contenido: de qué escribir y con qué imagen.
- **Código hoy:** el director recibe el texto de las capturas en estado `idea` (`ideas_from_gustavo`, [EDI-17](motor-editorial.md#edi-17)), sin sus fotos; las notas de las fotos de la Galería no le llegan.
- **Criterios de aceptación:**
  1. **Dado** una propuesta de post de los últimos 14 días sin usar, **cuando** corre el director, **entonces** la recibe con su texto, su transcripción y sus fotos, como recomendación de contenido.
  2. **Dado** que el director la usa, **cuando** guarda el brief, **entonces** queda constancia de qué propuesta usó, la captura pasa a «Usado» con enlace a la pieza y sus fotos son candidatas preferentes ([IMG-15](#img-15)).
  3. **Dado** una propuesta que menciona un hecho sobre Gustavo, **cuando** el texto público o una infografía lo usa, **entonces** solo puede atribuírselo si está en `public_facts`, igual que con las ideas.
  4. **Dado** una propuesta que no encaja en 14 días, **cuando** pasa el plazo, **entonces** queda «Sin usar», como las ideas.
- **Brechas código/docs:** —
- **Cobertura QA:** pendiente

### IMG-07 · Decidir si se edita una foto: manda la opción de edición; la nota dice cómo <a id="img-07"></a>

- **Dónde:** backend
- **Estado:** no implementado
- **Qué hace para Gustavo:** cada foto lleva una opción de edición que él elige ([IMG-16](#img-16)). Esa opción decide **si** se edita; su nota de voz o escrita dice **cómo**. Así una foto que necesita retoque se puede editar aunque él no lo diga en el audio.
- **Código hoy:** ninguno decide nada. `GalleryPhoto.allow_ai_edit` (booleano) se guarda y no se lee; pasará a la opción de tres valores de [IMG-16](#img-16) (`false` → «No editar», `true` → «Que decida el equipo»).
- **Las tres opciones (decisión de Gustavo, 2026-11-08):**
  1. **«No editar»:** nunca se envía a la API de imágenes, diga lo que diga la nota.
  2. **«Que decida el equipo»** (por defecto): se edita si la nota lo pide **o** si el equipo lo juzga necesario ([IMG-08](#img-08)).
  3. **«Editar»:** siempre se edita; sigue la instrucción de la nota si la hay y, si no, el equipo decide cómo ([IMG-08](#img-08)).
- **Criterios de aceptación:**
  1. **Dado** una foto con «No editar» y la nota «recórtala», **cuando** se elige, **entonces** no se edita, se publica el original y queda registrado «Edición prohibida en la foto».
  2. **Dado** una foto con «Que decida el equipo» y la nota «úsala tal cual», **cuando** se elige, **entonces** no se edita.
  3. **Dado** una foto con «Que decida el equipo» y la nota «recórtala», «quita el fondo» o «más luz», **cuando** se elige, **entonces** la edición hace exactamente eso y nada más.
  4. **Dado** una foto con «Que decida el equipo» y sin instrucción, **cuando** se elige, **entonces** decide el equipo según [IMG-08](#img-08).
  5. **Dado** una foto con «Editar» y una instrucción, **cuando** se elige, **entonces** se edita siguiendo la instrucción.
  6. **Dado** una foto con «Editar» y sin instrucción, **cuando** se elige, **entonces** se edita igualmente: el equipo elige el retoque que más mejora la foto para LinkedIn (luz, enderezar, encuadre 4:5 o 1:1, quitar distracciones) y registra cuál.
  7. **Dado** cualquier foto elegida, **cuando** se decide, **entonces** queda registrado qué se decidió y por qué: «Edición prohibida en la foto», «Instrucción de Gustavo: …», «Decisión del equipo: …» o «Edición pedida en la foto: …».
  8. **Dado** que la instrucción pide algo que la API no puede hacer bien («cambia la persona de la izquierda»), **cuando** se decide, **entonces** no se hace esa edición, se publica el original o el retoque seguro, y el motivo queda registrado.
- **Brechas código/docs:** la Galería ya promete «El equipo decide cuándo usarlas y si las edita con IA. Tú puedes dejar una nota o prohibir la edición en cada foto.» (PWA y app); nada lo cumple todavía.
- **Cobertura QA:** pendiente

### IMG-08 · Ediciones que el equipo decide por su cuenta <a id="img-08"></a>

- **Dónde:** backend
- **Estado:** no implementado
- **Qué hace para Gustavo:** con «Que decida el equipo» y sin instrucción, el equipo solo edita cuando importa (oscura o torcida, encuadre para LinkedIn, objetos que distraen); con «Editar» y sin instrucción, elige el retoque que más mejora la foto. En los dos casos él la ve, con veto, antes de que salga.
- **Código hoy:** no existe.
- **Criterios de aceptación:**
  1. **Dado** una foto con «Que decida el equipo», sin instrucción y bien expuesta, recta y sin distracciones, **cuando** se elige, **entonces** no se edita.
  2. **Dado** una foto oscura, torcida, mal encuadrada para LinkedIn o con objetos que distraen, **cuando** se elige, **entonces** el equipo la edita para corregir solo eso y registra el motivo («Estaba oscura: se aclaró»).
  3. **Dado** una edición decidida por el equipo, **cuando** se prepara la pieza, **entonces** se aplica y se muestra en el detalle de la pieza para que Gustavo pueda vetarla, sin preguntarle antes: elegir «Que decida el equipo» o «Editar» es su permiso.
  4. **Dado** que el equipo duda si editar una foto con «Que decida el equipo», **cuando** decide, **entonces** no edita. (Con «Editar» no hay duda: se edita.)
- **Brechas código/docs:** —
- **Cobertura QA:** pendiente

### IMG-09 · Editar con la API de imágenes de OpenAI sin perder el original <a id="img-09"></a>

- **Dónde:** backend
- **Estado:** no implementado
- **Qué hace para Gustavo:** cuando toca editar una de sus fotos, el equipo usa la API de imágenes de OpenAI; su foto original nunca se toca y la versión editada se guarda aparte.
- **Código hoy:** no existe.
- **Criterios de aceptación:**
  1. **Dado** una foto que debe editarse, **cuando** se edita, **entonces** se llama a la API de edición de imágenes de OpenAI con el original y una instrucción derivada de la nota de Gustavo o del motivo del equipo.
  2. **Dado** la edición terminada, **cuando** se guarda, **entonces** el archivo original queda idéntico (mismo SHA-256 antes y después) y la versión editada se guarda en otro archivo, ligada a la foto y a la pieza.
  3. **Dado** la versión editada, **cuando** se pide, **entonces** se sirve por una ruta autenticada y privada, como el original (`GET /api/v1/galeria/<id>/imagen`): sin URL pública y con `Cache-Control: private`.
  4. **Dado** la foto editada, **cuando** se consulta en la Galería, **entonces** su estado es `editada` y su etiqueta «Editada con IA».
  5. **Dado** un error o un tiempo de espera de OpenAI, **cuando** falla la edición, **entonces** no se repite sola (un paso pagado nunca se repite) y se publica el original, con el motivo registrado.
  6. **Dado** que se agotó el presupuesto de imágenes ([IMG-13](#img-13)), **cuando** toca editar, **entonces** no se edita y se publica el original, con el motivo registrado.
  7. **Dado** que Gustavo borra la foto de la Galería, **cuando** se borra, **entonces** se borran el original y todas sus versiones editadas.
  8. **Dado** `LIVE_PROVIDERS=false` o sin clave de OpenAI, **cuando** toca editar, **entonces** no se llama a nadie y se publica el original.
  9. **Dado** una infografía o un carrusel, **cuando** se prepara, **entonces** nunca se llama a la API de imágenes de OpenAI ([IMG-INF-08](#img-inf-08)).
- **Brechas código/docs:** —
- **Cobertura QA:** pendiente

### IMG-10 · Comprobación de la edición con un modelo con visión <a id="img-10"></a>

- **Dónde:** backend
- **Estado:** no implementado
- **Qué hace para Gustavo:** antes de publicar una foto editada, un modelo que ve imágenes (Claude) confirma que la edición hizo lo que él pidió y no deforma a las personas, los textos ni la marca. Si no pasa, sale la foto original.
- **Código hoy:** no existe. El verificador editorial (`editorial._check`) solo recibe texto, y Jev (el agente líder) no ve imágenes.
- **Criterios de aceptación:**
  1. **Dado** una foto editada, **cuando** se comprueba, **entonces** Claude recibe el original, la versión editada, la instrucción o el motivo y el texto del post, y devuelve un veredicto con sus motivos.
  2. **Dado** una edición que no sigue la instrucción (se pidió recortar y además cambió los colores), **cuando** se comprueba, **entonces** el veredicto es desfavorable.
  3. **Dado** una edición que cambia caras, cuerpos o el número de personas, deforma textos o altera un logotipo o la marca, **cuando** se comprueba, **entonces** el veredicto es desfavorable.
  4. **Dado** un veredicto desfavorable, **cuando** termina, **entonces** se publica el original, el detalle de la pieza muestra por qué se descartó la edición y la foto no queda como `editada`.
  5. **Dado** un veredicto favorable, **cuando** se guarda, **entonces** va ligado al SHA-256 de la imagen exacta; si la imagen cambia después, deja de valer.
  6. **Dado** que la comprobación falla por un error del proveedor, **cuando** termina, **entonces** se publica el original (nunca una edición sin comprobar).
  7. **Dado** una foto sin editar, **cuando** se prepara la pieza, **entonces** no hace falta esta comprobación.
- **Brechas código/docs:** —
- **Cobertura QA:** pendiente

### IMG-11 · La imagen en el detalle de la pieza, con veto <a id="img-11"></a>

- **Dónde:** PWA · app · backend
- **Estado:** no implementado
- **Qué hace para Gustavo:** en el detalle de la pieza, en la PWA y en la app, ve la imagen que saldrá: la foto (original y editada, con el motivo de la edición), la infografía o las láminas del carrusel, con su texto alternativo, y puede vetar hasta la hora de salida.
- **Código hoy:** ni `GET /api/v1/editorial/pieces/<id>` ni `PieceDetail` (`compartido/src/api/types.ts`) ni `PiezaDetalle.tsx` (PWA) ni `movil/src/pieza/PiezaScreen.tsx` (app) tienen un campo o una vista de imagen. El veto de la pieza existe ([CAL-12](calendario-piezas.md#cal-12)).
- **Criterios de aceptación:**
  1. **Dado** una pieza con una foto sin editar, **cuando** abre su detalle, **entonces** ve la foto con «Se publica tal cual» y el motivo («Instrucción de Gustavo: úsala tal cual», «Edición prohibida en la foto»…).
  2. **Dado** una pieza con una foto editada, **cuando** abre su detalle, **entonces** ve el original y la versión editada (lado a lado en escritorio, alternables en el teléfono), el motivo de la edición y el veredicto de la comprobación.
  3. **Dado** una edición descartada por la comprobación, **cuando** abre el detalle, **entonces** ve que sale el original y por qué.
  4. **Dado** una pieza con infografía o carrusel, **cuando** abre su detalle, **entonces** ve la imagen o cada lámina en orden («1/5», «2/5»…), la plantilla usada, el resultado de la lista de 10 puntos y el texto alternativo de cada una.
  5. **Dado** una pieza programada, **cuando** la veta antes de su hora, **entonces** no sale ni el texto ni la imagen, como hoy.
  6. **Dado** que ya pasó la hora o la pieza se está publicando, **cuando** abre el detalle, **entonces** no hay botón de veto.
  7. **Dado** que la imagen no carga, **cuando** abre el detalle, **entonces** ve un aviso en su lugar («No se pudo cargar la imagen») con «Reintentar», y el resto del detalle sigue.
  8. **Dado** una pieza en preparación sin imagen todavía, **cuando** abre el detalle, **entonces** ve «La imagen aparece cuando el equipo la prepare».
- **Brechas código/docs:** —
- **Cobertura QA:** pendiente

### IMG-12 · La Galería marca la foto «usada en la pieza del …» <a id="img-12"></a>

- **Dónde:** PWA · app · backend
- **Estado:** no implementado
- **Qué hace para Gustavo:** en la Galería ve qué fotos usó el equipo, en qué pieza y si las editó.
- **Código hoy:** la API ya calcula la etiqueta y `used_in` a partir de `state` y `chosen_piece` (`capturas.photo_status`, `photo_used_in`), y las dos interfaces muestran `used_in.text` o «Todavía sin usar». Como nada cambia el estado de las fotos, todas quedan «Nueva» o «Sin usar». `used_in.piece_id` no se enlaza a la pieza en ninguna interfaz.
- **Criterios de aceptación:**
  1. **Dado** una foto elegida para la pieza del domingo 8, **cuando** abre la Galería, **entonces** su etiqueta es «Elegida · dom 8» y la hoja de la foto dice «Usada en la pieza del domingo 8» con enlace a `/calendario/pieza/<id>`.
  2. **Dado** una foto editada, **cuando** abre su hoja, **entonces** ve «Editada con IA», el original y la versión editada.
  3. **Dado** una foto publicada, **cuando** abre la Galería, **entonces** su etiqueta es «Publicada · <fecha>» y aparece en el filtro «Publicadas».
  4. **Dado** los filtros, **cuando** elige «Elegidas», **entonces** aparecen las elegidas y las editadas; «Sin usar» incluye las nuevas.
  5. **Dado** que la pieza no salió, **cuando** abre la Galería, **entonces** la foto vuelve a «Sin usar».
  6. **Dado** que quiere quitar una foto elegida, **cuando** pulsa «Quitar de la galería», **entonces** la confirmación avisa «Ojo: elegida para el post del <día>.».
- **Brechas código/docs:** —
- **Cobertura QA:** pendiente

### IMG-13 · Coste de las imágenes en el ledger, con presupuesto propio <a id="img-13"></a>

- **Dónde:** PWA · app · backend
- **Estado:** no implementado
- **Qué hace para Gustavo:** cada edición de foto y cada comprobación de imagen queda registrada con su coste, contra un presupuesto de imágenes propio que ve en Ajustes.
- **Código hoy:** el ledger (`usage_ledger`, `knowledge.providers.reserve`) ya registra reservas y liquidaciones por proveedor y propósito, con techos mensuales por proveedor (`<PROVEEDOR>_LIMIT_USD`). No hay propósito ni presupuesto de imágenes. Ajustes › Gasto muestra General, Editorial y Red (`rediseno_views.Settings`, `ai_spend.today`).
- **Criterios de aceptación:**
  1. **Dado** una edición con OpenAI, **cuando** se llama, **entonces** antes se reserva su peor caso en el ledger con un propósito propio (por ejemplo `image-edit`, proveedor `openai`) y al terminar se liquida con el coste real.
  2. **Dado** una comprobación con Claude (de una foto editada o de una infografía), **cuando** se llama, **entonces** también pasa por el ledger con su propósito (por ejemplo `image-check`).
  3. **Dado** una infografía o un carrusel, **cuando** se dibuja, **entonces** no hay coste de modelo de imagen: solo cuentan la llamada que escribe su contenido y la comprobación visual.
  4. **Dado** un presupuesto de imágenes (una variable como `IMAGE_DAILY_USD`), **cuando** lo gastado llega al tope, **entonces** no se hace ninguna edición más en ese periodo y se publica el original.
  5. **Dado** el gasto de imágenes, **cuando** se calculan los presupuestos editorial y de comentarios, **entonces** no cuenta en ellos.
  6. **Dado** un fallo de OpenAI que no se cobra, **cuando** termina, **entonces** la reserva queda `rejected`; un fallo incierto la deja `uncertain` y no se reintenta.
  7. **Dado** Ajustes › Gasto de IA, en la PWA y en la app, **cuando** lo abre, **entonces** ve una línea «Imágenes» con lo gastado hoy frente a su tope.
  8. **Dado** el resumen semanal, **cuando** se calculan sus cifras, **entonces** `gasto_ia` incluye el gasto de imágenes.
- **Brechas código/docs:** —
- **Cobertura QA:** pendiente

### IMG-14 · Publicar en LinkedIn con la imagen o el carrusel <a id="img-14"></a>

- **Dónde:** backend
- **Estado:** no implementado
- **Qué hace para Gustavo:** la pieza sale en LinkedIn con su imagen o su carrusel, por la API oficial, con las mismas garantías de hoy: una sola vez y sin repetir si el resultado es incierto.
- **Código hoy:** `connectors_linkedin.post_body` solo envía `commentary`; no hay subida de imágenes ni de documentos. El permiso `w_member_social` que ya tiene la cuenta es el que pide la subida.
- **Criterios de aceptación:**
  1. **Dado** una pieza aprobada con una foto o una infografía de imagen única, **cuando** llega su hora, **entonces** primero se sube la imagen a LinkedIn (registrar la subida y enviar los bytes) y después se crea el post que la referencia en `content.media`, con su texto alternativo, usando el mismo permiso `w_member_social`.
  2. **Dado** una pieza con carrusel, **cuando** llega su hora, **entonces** se sube como documento de hasta 8 láminas de 1080×1350 y se crea el post que lo referencia.
  3. **Dado** la imagen que se publica, **cuando** se prepara, **entonces** tiene formato vertical 1080×1350 o cuadrado 1080×1080; nunca horizontal.
  4. **Dado** una foto que no tiene ese formato y que se puede editar, **cuando** se prepara, **entonces** adaptar el encuadre cuenta como una edición y sigue [IMG-07](#img-07) a [IMG-10](#img-10).
  5. **Dado** una foto con «No editar» en otro formato, **cuando** se prepara, **entonces** se publica tal cual, sin recortarla.
  6. **Dado** que falla la subida de la imagen o del documento antes de crear el post, **cuando** termina, **entonces** la acción queda `failed` sin publicar nada (resultado definitivo) y llega el aviso correspondiente.
  7. **Dado** un 401, 403 o 429 al subir, **cuando** termina, **entonces** la cuenta pasa a pausa con aviso, como al publicar texto.
  8. **Dado** que la creación del post da un resultado incierto, **cuando** termina, **entonces** queda `uncertain` y nunca se repite ([EDI-12](motor-editorial.md#edi-12)).
  9. **Dado** el post publicado, **cuando** se confirma, **entonces** cada foto usada pasa a `publicada` con `published_at`.
  10. **Dado** el conector simulado (`linkedin_fake`), **cuando** se publica con imagen o carrusel, **entonces** guarda lo subido en su memoria para que las pruebas lo comprueben.
- **Brechas código/docs:** el contrato de la Posts API que cita `publicacion-diaria.md` es solo de texto; hay que verificar el de imágenes y documentos contra la documentación de LinkedIn antes de implementar.
- **Cobertura QA:** pendiente

---

## Infografías y carruseles <a id="infografias-y-carruseles"></a>

Las reglas son las del tablero «Infografías hechas con IA · reglas» (`Infografias.dc.html`, canvas https://claude.ai/artifact/9ebjAHA228bpQJM9XP64ee). El tablero las organiza en nueve partes: principio, formatos y rejilla, color, tipografía, datos y gráficos, composición (con las cuatro plantillas), «sí y no», una especificación JSON para los agentes y la lista de revisión de 10 puntos. Su frase de partida: «Si una regla estorba, gana la claridad».

### IMG-INF-01 · Las reglas de infografías son una regla de agente <a id="img-inf-01"></a>

- **Dónde:** backend
- **Estado:** no implementado
- **Qué hace para Gustavo:** su manual de infografías se aplica siempre, igual que su documento de tono de voz: no es una unidad de conocimiento que el agente pueda leer o no.
- **Código hoy:** no existe. El modelo a seguir es la voz: `voz.py` añade `recursos/tono-de-voz.md`, precedido de `voz.VOICE_GUIDE`, al final del system de los agentes que escriben texto público ([EDI-16](motor-editorial.md#edi-16)).
- **Criterios de aceptación:**
  1. **Dado** el repositorio, **cuando** se busca la regla, **entonces** el contenido del tablero (principio, formatos, color, tipografía, datos, composición, sí y no, especificación JSON y lista de revisión) está guardado en el backend como un recurso versionado, junto a la voz.
  2. **Dado** el agente que diseña infografías y carruseles, **cuando** se arma su system, **entonces** lleva siempre la regla completa, con la especificación JSON del tablero.
  3. **Dado** el verificador de imágenes, **cuando** revisa una infografía, **entonces** usa la misma versión de la regla que el agente que la diseñó, y la pieza guarda qué versión se aplicó.
  4. **Dado** que Gustavo cambia el tablero, **cuando** quiere que cambien las infografías, **entonces** se actualiza el recurso del backend y se despliega, como con la voz.
  5. **Dado** la búsqueda de unidades del curso, **cuando** se consulta, **entonces** la regla no aparece como unidad de conocimiento.
- **Brechas código/docs:** el tablero solo vive en el canvas; no hay copia en el repositorio.
- **Cobertura QA:** pendiente

### IMG-INF-02 · El agente elige una plantilla y escribe el contenido como datos <a id="img-inf-02"></a>

- **Dónde:** backend
- **Estado:** no implementado
- **Qué hace para Gustavo:** para una infografía, el agente decide qué plantilla usar y qué dice cada parte; no dibuja nada.
- **Código hoy:** no existe.
- **Criterios de aceptación:**
  1. **Dado** una pieza con tipo `infografia` o `carrusel`, **cuando** corre el agente, **entonces** devuelve datos estructurados validados con un esquema: la plantilla (portada de carrusel, pasos, barras o número protagonista), el formato, los textos de cada elemento (etiqueta, titular, bajada, cuerpo, cifra con su unidad, pasos, barras con su valor), la fuente de los datos, el texto alternativo y, en un carrusel, las láminas en orden.
  2. **Dado** un titular de más de 8 palabras, una lámina de más de 30 palabras o una imagen única de más de 40, **cuando** se valida, **entonces** se rechaza y el agente lo corrige antes de dibujar.
  3. **Dado** un tipo de gráfico que no está permitido (torta de más de 3 partes, 3D, doble eje, medidores, nubes de palabras), **cuando** se valida, **entonces** se rechaza; solo pasan número protagonista, barras horizontales (hasta 5), línea simple (una serie, dos como máximo), antes y después, pasos (3 a 5) y lista numerada.
  4. **Dado** unos pasos con 2 o con 6 elementos, o unas barras con 6 categorías, **cuando** se valida, **entonces** se rechaza.
  5. **Dado** el texto público, **cuando** se valida, **entonces** está en inglés, sin emojis, sin hashtags, sin dobles exclamaciones y con mayúsculas solo en las etiquetas.
  6. **Dado** un titular de portada, **cuando** se valida, **entonces** va en minúsculas salvo la primera letra.
  7. **Dado** una respuesta que no cumple el esquema tras la corrección, **cuando** termina, **entonces** no se dibuja nada y el equipo elige otra imagen o la pieza queda bloqueada con el motivo ([IMG-15](#img-15)).
- **Brechas código/docs:** —
- **Cobertura QA:** pendiente

### IMG-INF-03 · El código dibuja la infografía exactamente con las reglas <a id="img-inf-03"></a>

- **Dónde:** backend
- **Estado:** no implementado
- **Qué hace para Gustavo:** cada infografía se ve de 0ff1ce: limpia, simple y legible en el teléfono, porque la dibuja código con su manual, no un modelo.
- **Código hoy:** no existe.
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
- **Brechas código/docs:** —
- **Cobertura QA:** pendiente

### IMG-INF-04 · Datos honestos y con fuente <a id="img-inf-04"></a>

- **Dónde:** backend
- **Estado:** no implementado
- **Qué hace para Gustavo:** ninguna infografía inventa un dato ni lo exagera; todo número dice de dónde sale.
- **Código hoy:** no existe. Para el texto ya existen las guardas de hechos públicos (`guardas.invented_experience`) y el verificador ([EDI-07](motor-editorial.md#edi-07)).
- **Criterios de aceptación:**
  1. **Dado** un dato, **cuando** se valida, **entonces** sale de la memoria confirmada pública de Gustavo o de una fuente citada; si no, se rechaza.
  2. **Dado** una estimación, **cuando** se dibuja, **entonces** lo dice («estimate»).
  3. **Dado** un gráfico de barras, **cuando** se dibuja, **entonces** las barras empiezan en cero, van de mayor a menor (salvo que el orden sea el mensaje), llevan la etiqueta al lado y no hay leyenda aparte; solo la barra del foco va en el color de acento, las demás en línea `#DEDFD4`.
  4. **Dado** un número, **cuando** se dibuja, **entonces** va redondeado y con su unidad («6 days», no «6,24 days»).
  5. **Dado** cualquier dato, **cuando** se dibuja, **entonces** lleva al pie, a 28 px, de dónde sale y de cuándo es.
  6. **Dado** que el color marca algo, **cuando** se dibuja, **entonces** lleva también etiqueta o posición: el color nunca va solo.
- **Brechas código/docs:** —
- **Cobertura QA:** pendiente

### IMG-INF-05 · Carrusel: portada, láminas y cierre <a id="img-inf-05"></a>

- **Dónde:** backend
- **Estado:** no implementado
- **Qué hace para Gustavo:** cuando un post explica algo en pasos, sale como carrusel con su portada, una idea por lámina y una pregunta al final.
- **Código hoy:** no existe.
- **Criterios de aceptación:**
  1. **Dado** un carrusel, **cuando** se valida, **entonces** tiene como mucho 8 láminas de 1080×1350.
  2. **Dado** la primera lámina, **cuando** se dibuja, **entonces** es la portada: fondo tinta, una sola palabra en 0ff1ce, titular de 8 palabras como máximo y bajada; las interiores van en papel.
  3. **Dado** cada lámina, **cuando** se valida, **entonces** responde una sola idea; si hacen falta dos, son dos láminas.
  4. **Dado** la última lámina, **cuando** se valida, **entonces** cierra con una pregunta para la conversación, nunca con un «sígueme».
  5. **Dado** el carrusel, **cuando** se numeran las láminas, **entonces** cada pie dice «n/N».
- **Brechas código/docs:** —
- **Cobertura QA:** pendiente

### IMG-INF-06 · Revisión con la lista de 10 puntos <a id="img-inf-06"></a>

- **Dónde:** backend
- **Estado:** no implementado
- **Qué hace para Gustavo:** antes de publicar, el verificador revisa cada infografía con su lista de 10 puntos; si falla uno, vuelve a Mesa editorial.
- **Código hoy:** no existe. El circuito ya tiene un verificador de texto y una ronda de reparación ([EDI-07](motor-editorial.md#edi-07), [EDI-08](motor-editorial.md#edi-08)).
- **La lista del tablero:**
  1. Responde una sola pregunta y se entiende en 3 segundos.
  2. Tiene un único punto focal y un único color de acento.
  3. El titular tiene 8 palabras o menos; ninguna lámina pasa de 30.
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
  3. **Dado** que falla cualquier punto, **cuando** termina la revisión, **entonces** la infografía vuelve a Mesa editorial con los puntos fallidos para una corrección, y se vuelve a revisar.
  4. **Dado** que sigue fallando tras la corrección, **cuando** termina, **entonces** no se publica: el equipo elige otra imagen o la pieza queda bloqueada con los motivos ([IMG-15](#img-15)).
  5. **Dado** una infografía que pasa los 10 puntos, **cuando** se guarda el veredicto, **entonces** va ligado al SHA-256 de cada lámina exacta y el detalle de la pieza muestra el resultado ([IMG-11](#img-11)).
  6. **Dado** que la revisión visual falla por un error del proveedor, **cuando** termina, **entonces** la infografía no se da por buena.
- **Brechas código/docs:** —
- **Cobertura QA:** pendiente

### IMG-INF-07 · Texto alternativo siempre <a id="img-inf-07"></a>

- **Dónde:** PWA · app · backend
- **Estado:** no implementado
- **Qué hace para Gustavo:** cada imagen que publica lleva un texto alternativo con el dato y la conclusión, para quien no puede verla.
- **Código hoy:** no existe.
- **Criterios de aceptación:**
  1. **Dado** una infografía o cada lámina de un carrusel, **cuando** se prepara, **entonces** lleva texto alternativo en inglés con el dato y la conclusión.
  2. **Dado** una foto de la Galería, **cuando** se prepara, **entonces** también lleva texto alternativo que la describe.
  3. **Dado** una imagen sin texto alternativo, **cuando** la revisa la política, **entonces** la descarta.
  4. **Dado** la publicación, **cuando** se crea el post, **entonces** el texto alternativo viaja a LinkedIn con la imagen ([IMG-14](#img-14)).
  5. **Dado** el detalle de la pieza en la PWA o la app, **cuando** lo abre, **entonces** ve el texto alternativo de cada imagen, y la imagen lo usa como su etiqueta accesible.
- **Brechas código/docs:** —
- **Cobertura QA:** pendiente

### IMG-INF-08 · Ningún modelo de imagen dibuja infografías ni texto <a id="img-inf-08"></a>

- **Dónde:** backend
- **Estado:** no implementado
- **Qué hace para Gustavo:** las infografías nunca tienen letras deformes ni cifras inventadas por un generador de imágenes: la API de imágenes de OpenAI solo toca sus fotos reales.
- **Código hoy:** no existe.
- **Criterios de aceptación:**
  1. **Dado** la preparación de una infografía o un carrusel, **cuando** se registra en el ledger, **entonces** no hay ninguna llamada a un modelo de generación o edición de imágenes.
  2. **Dado** una llamada a la API de imágenes de OpenAI, **cuando** se hace, **entonces** su entrada es siempre una foto de la Galería de Gustavo.
  3. **Dado** el texto que aparece en una infografía, **cuando** se dibuja, **entonces** sale tal cual de los datos estructurados, dibujado con la fuente Ubuntu.
- **Brechas código/docs:** —
- **Cobertura QA:** pendiente

## Retiradas

Ninguna.
