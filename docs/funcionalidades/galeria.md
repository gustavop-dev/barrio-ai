# Galería (`GAL`)

Las fotos que Gustavo sube para sus posts, con una nota para el equipo y un interruptor para prohibir la edición con IA en cada una. El backend ya selecciona, edita y publica las fotos; los controles de tres estados quedan para fase 2 (ver «Imágenes» al final).

- **Código:** backend `capturas_views.Gallery`, `PhotoDetail`, `PhotoImage`, `capturas.add_photos`, `delete_photo`, `photo_payload`, `photo_status`, `photo_used_in`, modelo `GalleryPhoto`; PWA `oficina/src/pages/Galeria.tsx`, `pages/galeria/PhotoSheet.tsx`; app `movil/src/galeria/*` (`GaleriaScreen.tsx`, `PhotoSheet.tsx`, `PhotoViewer.tsx`, `upload.ts`, `UploadProgressCard.tsx`), `movil/src/components/ui/ApiImage.tsx`; común `compartido/src/api/capturas.ts`, `compartido/src/logic/galeria.ts`.
- **Documentación:** sección «Galería» de [`capturas-galeria.md`](../../agentes-linkedin/infra/docs/capturas-galeria.md) y de [`CONTRATO-API.md`](../../oficina/CONTRATO-API.md).

## Resumen

| ID | Función | Dónde | Estado |
| --- | --- | --- | --- |
| [GAL-01](#gal-01) | Ver la Galería y filtrar | PWA · app · backend | funciona |
| [GAL-02](#gal-02) | Subir fotos | PWA · app · backend | parcial |
| [GAL-03](#gal-03) | Dejar una nota para el equipo en una foto | PWA · app · backend | funciona |
| [GAL-04](#gal-04) | Prohibir o permitir la edición con IA de una foto | PWA · app · backend | parcial |
| [GAL-05](#gal-05) | Quitar una foto de la Galería | PWA · app · backend | funciona |
| [GAL-06](#gal-06) | Ver las fotos a pantalla completa | app | funciona |
| [GAL-07](#gal-07) | Las fotos son privadas | PWA · app · backend | funciona |

---

### GAL-01 · Ver la Galería y filtrar <a id="gal-01"></a>

- **Dónde:** PWA · app · backend
- **Estado:** funciona
- **Qué hace para Gustavo:** ve sus fotos en una rejilla, cada una con su estado, y filtra por las que están sin usar, elegidas o publicadas.
- **Código:** `GET /api/v1/galeria?filtro=todas|sin_usar|elegidas|publicadas&page=N`; PWA `Galeria.tsx`; app `GaleriaScreen.tsx` (rejilla virtualizada de 3 columnas).
- **Criterios de aceptación:**
  1. **Dado** fotos subidas, **cuando** abre la Galería, **entonces** ve «Fotos para tus posts.», «Subir fotos», la pista «Para usar la cámara, toca el botón aguamarina y elige «Foto para la galería».», la nota «El equipo decide cuándo usarlas y si las edita con IA. Tú puedes dejar una nota o prohibir la edición en cada foto.» y la rejilla, de la más reciente a la más antigua.
  2. **Dado** una foto subida hace menos de 24 h y sin usar, **cuando** se pinta, **entonces** su etiqueta es «Nueva»; pasadas 24 h, «Sin usar».
  3. **Dado** los chips «Todas», «Sin usar», «Elegidas» y «Publicadas», **cuando** elige uno, **entonces** la lista se filtra y el filtro queda en la URL (`?filtro=`). «Sin usar» incluye las nuevas y «Elegidas» incluye las editadas.
  4. **Dado** más de una página, **cuando** pulsa «Ver más fotos», **entonces** carga la siguiente.
  5. **Dado** ninguna foto, **cuando** abre la Galería, **entonces** ve «Todavía no hay fotos» y «Sube fotos tuyas, de eventos o de tu trabajo. El equipo las usará en tus posts cuando encajen.».
  6. **Dado** un filtro sin resultados, **cuando** lo elige, **entonces** ve «No hay fotos con este filtro.».
  7. **Dado** la carga en curso, **cuando** abre la vista, **entonces** ve «Cargando la galería…»; si falla, ve el error con «Reintentar».
  8. **Dado** un filtro desconocido, **cuando** se pide a la API, **entonces** responde 400 «Usa todas, sin_usar, elegidas o publicadas.».
- **Brechas código/docs:** las etiquetas «Elegida», «Editada con IA» y «Publicada» existen en la API pero nada las alcanza todavía ([IMG-12](imagenes-en-publicaciones.md#img-12)). En la app, una foto que no carga se queda gris, sin aviso.
- **Cobertura QA:** E2E `10-galeria` (criterios 1, 2, 3: los textos, «Nueva» y «Sin usar», los cuatro filtros; 6, un filtro vacío con el interruptor de fallos) y `10-galeria-subir` (5, la Galería vacía con el interruptor de fallos). 4, 7 y 8: Jest y backend.

### GAL-02 · Subir fotos <a id="gal-02"></a>

- **Dónde:** PWA · app · backend
- **Estado:** parcial
- **Qué hace para Gustavo:** elige fotos de su teléfono o de su ordenador y las sube a la Galería.
- **Código:** `POST /api/v1/galeria` (multipart, partes `fotos` repetidas, lotes de 10, `capturas.add_photos`); PWA `Galeria.tsx` (botón y arrastrar y soltar); app `upload.ts` (`launchImageLibraryAsync`, partes `{uri, name, type}`), `UploadProgressCard.tsx`.
- **Lo que falta:** en la app funciona desde el PR #43 (las subidas van por `XMLHttpRequest`, `movil/src/api/multipart.ts`). En la PWA falla el criterio 4: tras un segundo lote fallido solo muestra el error, sin decir que el primero sí se guardó.
- **Criterios de aceptación:**
  1. **Dado** tres fotos JPEG elegidas, **cuando** las sube, **entonces** la API responde 201 con las fotos creadas, aparecen en la rejilla como «Nueva» y se ve «3 fotos subidas. El equipo las verá en su próxima ronda.» (o «Foto subida. …» con una).
  2. **Dado** la app, **cuando** sube fotos, **entonces** la tarjeta muestra «Subiendo X de N fotos…» con una barra y una miniatura por foto (en espera, enviando, subida).
  3. **Dado** 15 fotos, **cuando** las sube, **entonces** se envían en lotes de 10 y llegan las 15.
  4. **Dado** que el segundo lote falla, **cuando** vuelve el error, **entonces** ve cuántas se subieron y puede reintentar solo las que faltan (la app lo hace con «Reintentar» y «Descartar las que faltan»). **Hoy falla en la PWA:** solo muestra el error, sin decir que el primer lote sí se guardó.
  5. **Dado** una foto de más de 10 MB o que no es JPEG, PNG, WebP o HEIC, **cuando** la elige, **entonces** ve «No se subió <nombres>: solo JPEG, PNG, WebP o HEIC de hasta 10 MB.» y las demás se suben.
  6. **Dado** cada foto nueva, **cuando** se crea, **entonces** toma `allow_ai_edit` del valor por defecto de Ajustes › Captura y galería ([AJU-09](ajustes.md#aju-09)).
  7. **Dado** que la subida falla, **cuando** vuelve el error, **entonces** se ve en español; nunca un mensaje técnico en inglés.
- **Brechas código/docs:** en la app la línea de fotos rechazadas no se borra tras una subida correcta posterior.
- **Cobertura QA:** E2E `10-galeria-subir` (criterios 1 y 7: una foto elegida en el selector de Android llega al backend, «Foto subida. El equipo la verá en su próxima ronda.» y la foto en la rejilla como «Nueva»; 4, un 413 con el interruptor de fallos, «0 de 1 foto subida» y «Reintentar»). 2, 3, 5 y 6: Jest y backend.

### GAL-03 · Dejar una nota para el equipo en una foto <a id="gal-03"></a>

- **Dónde:** PWA · app · backend
- **Estado:** funciona
- **Qué hace para Gustavo:** al tocar una foto escribe una nota («recórtala para que no se lean nombres de clientes») que el equipo verá.
- **Código:** `PATCH /api/v1/galeria/<id> {note}`; `PhotoSheet.tsx` en las dos interfaces (`photoPatch` envía solo lo que cambió).
- **Criterios de aceptación:**
  1. **Dado** una foto, **cuando** la toca, **entonces** se abre la hoja con la imagen, la etiqueta, `used_in.text` o «Todavía sin usar», «Nota para el equipo (opcional)» (con el ejemplo «Por ejemplo: recórtala para que no se lean nombres de clientes.»), el interruptor «El equipo puede editarla con IA», «Guardar» y «Quitar de la galería».
  2. **Dado** que escribe una nota, **cuando** pulsa «Guardar», **entonces** se envía solo `note`, aparece «Foto guardada.» y la hoja se cierra.
  3. **Dado** que no cambió nada, **cuando** mira «Guardar», **entonces** está desactivado.
  4. **Dado** una nota de más de 2.000 caracteres, **cuando** se envía, **entonces** la API responde 400.
  5. **Dado** un error al guardar, **cuando** vuelve, **entonces** se ve dentro de la hoja y la nota no se pierde.
- **Brechas código/docs:** el director recibe y usa las notas ([IMG-04](imagenes-en-publicaciones.md#img-04)). En la PWA, la X de la hoja sigue activa mientras guarda y puede cerrarla antes de ver el resultado.
- **Cobertura QA:** E2E `10-galeria` (criterios 1 a 3; la foto abierta otra vez enseguida, con la Galería recargando despacio por el interruptor de fallos, muestra lo guardado). 4 y 5: backend y Jest.

### GAL-04 · Prohibir o permitir la edición con IA de una foto <a id="gal-04"></a>

- **Dónde:** PWA · app · backend
- **Estado:** parcial
- **Qué hace para Gustavo:** en cada foto decide si el equipo puede editarla con IA.
- **Código:** `PATCH /api/v1/galeria/<id> {allow_ai_edit}`; interruptor «El equipo puede editarla con IA» en `PhotoSheet.tsx` de las dos interfaces. El backend usa `ai_edit`; `allow_ai_edit` permanece como alias de compatibilidad.
- **Criterios de aceptación:**
  1. **Dado** una foto, **cuando** apaga el interruptor y guarda, **entonces** se envía `{allow_ai_edit: false}`, aparece «Foto guardada.» y la foto vuelve con `allow_ai_edit: false`; queda registrado `gallery.updated` en la auditoría.
  2. **Dado** una foto nueva, **cuando** se crea, **entonces** el interruptor viene con el valor por defecto de Ajustes ([AJU-09](ajustes.md#aju-09)).
  3. **Dado** una foto con `allow_ai_edit=false`, **cuando** el equipo prepara un post con ella, **entonces** nunca la edita, aunque la nota pida editar; ver [IMG-07](imagenes-en-publicaciones.md#img-07).
- **Brechas código/docs:** el backend aplica no/auto/si; la interfaz de tres opciones queda para fase 2.
- **Cobertura QA:** E2E `10-galeria` (criterio 1: el interruptor apagado y guardado sigue apagado al volver). 2, Jest; 3 no aplica todavía.

### GAL-05 · Quitar una foto de la Galería <a id="gal-05"></a>

- **Dónde:** PWA · app · backend
- **Estado:** funciona
- **Qué hace para Gustavo:** borra una foto y su archivo, con confirmación.
- **Código:** `DELETE /api/v1/galeria/<id>` (`capturas.delete_photo`); confirmación en `PhotoSheet.tsx`.
- **Criterios de aceptación:**
  1. **Dado** una foto, **cuando** pulsa «Quitar de la galería», **entonces** ve «¿Quitar esta foto de la galería?» con «Se borran la foto y su archivo; el equipo ya no podrá usarla.».
  2. **Dado** una foto elegida para un post, **cuando** aparece la confirmación, **entonces** añade «Ojo: elegida para el post del <día>.».
  3. **Dado** que confirma con «Quitar la foto», **cuando** termina, **entonces** la API responde 204, el archivo se borra del almacenamiento, aparece «Foto quitada de la galería.» y desaparece de la rejilla.
  4. **Dado** un error, **cuando** vuelve, **entonces** se ve dentro de la confirmación.
  5. **Dado** el borrado, **cuando** termina, **entonces** no hay «Deshacer» (comportamiento actual).
- **Brechas código/docs:** —
- **Cobertura QA:** E2E `10-galeria` (criterios 1 a 3 y 5: la confirmación, «Cancelar», «Quitar la foto» y la foto fuera de la rejilla; 2, el aviso de la foto elegida). 4: Jest.

### GAL-06 · Ver las fotos a pantalla completa <a id="gal-06"></a>

- **Dónde:** app
- **Estado:** funciona
- **Qué hace para Gustavo:** en el teléfono abre una foto a pantalla completa, pasa a la siguiente y hace zoom.
- **Código:** `movil/src/galeria/PhotoViewer.tsx`.
- **Criterios de aceptación:**
  1. **Dado** la hoja de una foto, **cuando** toca la imagen, **entonces** se abre a pantalla completa con «N de M», «Cerrar» y el pie con la etiqueta y `used_in.text`.
  2. **Dado** el visor, **cuando** desliza a un lado, **entonces** pasa a la foto siguiente o anterior.
  3. **Dado** el visor, **cuando** pellizca o toca dos veces, **entonces** hace zoom y puede moverse por la foto.
  4. **Dado** el visor, **cuando** arrastra hacia arriba o abajo sin zoom, **entonces** se cierra.
- **Brechas código/docs:** la PWA no tiene visor.
- **Cobertura QA:** E2E `10-galeria` (criterios 1, 2 y 4, y el doble toque del 3: con zoom, deslizar no cambia de foto). El pellizco necesita dos dedos, que Maestro no hace en Android. El fondo de tinta del visor: Jest (`GaleriaScreen.test.tsx`) y la captura `10-galeria-08-visor`.

### GAL-07 · Las fotos son privadas <a id="gal-07"></a>

- **Dónde:** PWA · app · backend
- **Estado:** funciona
- **Qué hace para Gustavo:** sus fotos nunca están en una URL pública: solo las ve él con su sesión.
- **Código:** `GET /api/v1/galeria/<id>/imagen` (`capturas_views.PhotoImage`, `serve`); PWA `<img src>` del mismo origen; app `ApiImage` con `Authorization: Bearer`.
- **Criterios de aceptación:**
  1. **Dado** una foto, **cuando** se pide su imagen sin sesión ni token, **entonces** la API responde 401 o 403.
  2. **Dado** una sesión con `operate_linkedin`, **cuando** se pide, **entonces** responde 200 con el tipo real del archivo, `Cache-Control: private, max-age=3600`, `Content-Security-Policy: … sandbox` y `X-Content-Type-Options: nosniff`.
  3. **Dado** un archivo que ya no existe en el disco, **cuando** se pide, **entonces** responde 404 «El archivo ya no está disponible.».
  4. **Dado** la PWA o la app, **cuando** recibe una URL de imagen de otro origen, **entonces** no la carga (la app muestra un recuadro azul con un icono).
  5. **Dado** una rejilla con muchas fotos, **cuando** se cargan, **entonces** estas lecturas no cuentan para el límite de peticiones de la API.
- **Brechas código/docs:** —
- **Cobertura QA:** E2E `10-galeria` (criterio 1: la imagen de una foto sin sesión ni token responde 401 o 403; 2, la app muestra las fotos con su token en la rejilla, la hoja y el visor). 3 a 5: backend.

---

## Imágenes

La Galería es la fuente del flujo de imagen, implementado en el backend; interfaz de fase 2 pendiente ([imagenes-en-publicaciones.md](imagenes-en-publicaciones.md)). Las fichas que la tocan:
- [IMG-03](imagenes-en-publicaciones.md#img-03): las fotos llegan siempre con la nota de su captura;
- [IMG-15](imagenes-en-publicaciones.md#img-15) e [IMG-04](imagenes-en-publicaciones.md#img-04): el equipo decide por contexto si un post lleva una foto de la Galería, una infografía o un carrusel; cuando es una foto, ve la Galería (notas, transcripciones, fecha, uso, `allow_ai_edit`) y elige;
- [IMG-07](imagenes-en-publicaciones.md#img-07) e [IMG-09](imagenes-en-publicaciones.md#img-09): cuándo se edita una foto y cómo se guarda la versión editada sin tocar el original;
- [IMG-12](imagenes-en-publicaciones.md#img-12): la Galería marca la foto «usada en la pieza del …», con enlace a la pieza.

## Retiradas

Ninguna.
