# Captura, transcripción y Galería

Este backend sostiene dos funciones nuevas de 0ff1ce (`FUNCIONES-NUEVAS.md`):
- **El botón de captura.** Con un gesto, Gustavo le manda al equipo un audio, fotos y una nota. El equipo lo transcribe y decide qué hacer con ello.
- **La Galería.** Son las fotos que Gustavo sube para sus posts. El equipo decide cuándo usarlas y si las edita con IA.

El contrato HTTP para la PWA está en [`oficina/CONTRATO-API.md`](../../../oficina/CONTRATO-API.md), sección «Captura y Galería».

## Piezas

| Pieza | Dónde |
| --- | --- |
| Modelos `Capture`, `GalleryPhoto` y `OfficePreference` | `team_backend/models.py`, migración `0011_capturas_galeria` |
| Validación, procesamiento, ruteo, deshacer e integración con el director | `team_backend/capturas.py` |
| Endpoints y servicio privado de archivos | `team_backend/capturas_views.py` |
| Transcripción con AssemblyAI | `knowledge/providers.py`, `assemblyai_transcribe` |
| Trabajo `process_capture` | `jobs.py` (permisos y operación pagada) y `operador.run_job` |

## Recorrido de una captura

1. **Recepción.** `POST /api/v1/capturas` (multipart) valida todo antes de guardar nada:
   - que no venga vacía;
   - los tipos de archivo, mirando la cabecera real del archivo y no solo lo que declara el navegador;
   - los tamaños;
   - que exista el contexto (la pregunta, la persona o la pieza).

   Después guarda el audio y las fotos, crea las filas de la Galería y encola `process_capture`. Ese trabajo tiene un identificador determinista, así que hay un solo trabajo por captura.
2. **Transcripción** (estado `transcribiendo`), solo si hay audio. Ver [la sección de AssemblyAI](#transcripción-con-assemblyai).
3. **Ruteo** (estado `procesando`). El texto que se rutea es la nota más la transcripción.

   | Caso | Qué crea | Estado y resultado |
   | --- | --- | --- |
   | Contexto `pregunta` | Responde la pregunta con `preguntas.answer` como Gustavo, con la visibilidad elegida (`public_use`; si no la eligió, la que sugiere la pregunta). En las preguntas tipadas (sí/no, opción, número, fecha), el texto se guarda como respuesta libre: «{pregunta} {texto}». | `dato_guardado` · «Está en Lo que el equipo sabe de ti · Público/Privado» |
   | Contexto `persona` | Una nota en `Contact.notes`, con la misma forma que las notas a mano más `source: "captura"` y `capture` | `anotado` · «Quedó en las notas de {nombre}» |
   | Contexto `pieza` | Un comentario para el equipo. Sale en `team_comments` del detalle de la pieza y en `feedback_from_gustavo` del director | `anotado` · «Quedó como comentario para el equipo en la pieza del jueves 12» |
   | `para=dato` | Un hecho confirmado privado `nota.captura-<id>`: `{texto, uso_publico: false, tema}` | `dato_guardado` · «Está en Lo que el equipo sabe de ti · Privado» |
   | `para=respuesta` sin pregunta ligada | Lo mismo que `dato`: queda privado en la memoria | `dato_guardado` |
   | `para=post` | Una idea para el director editorial | `idea` · «Mesa editorial lo tendrá en cuenta» |
   | `para=galeria` (exige fotos) | Las fotos ya están en la Galería; el texto pasa a ser su nota | `dato_guardado` · «Está en tu Galería» |
   | Sin `para` ni contexto, solo fotos | Galería | `dato_guardado` |
   | Sin `para` ni contexto, con texto | Una clasificación barata con Sonnet (`claude-sonnet-5-5`, propósito `capture-route`) entre post, dato y galeria (esta última solo si hay fotos), con un motivo de una frase en español. Ante la duda gana `dato`, que es privado | Según el destino; `team_decided` lo cuenta |
   | Sin texto ni fotos (audio sin voz) | Nada | `sin_usar` |

   Las fotos de cualquier captura quedan siempre en la Galería, ligadas a ella. El texto que va a la memoria se recorta a 2.000 caracteres, el de las notas a 4.000 y el de las ideas a 1.500 para el director. La captura conserva siempre el texto completo.
4. **Escena de la oficina.** Cada ruteo emite una `entrega` desde `operador_cuenta` hacia quien recibe:
   - las ideas, las fotos y los comentarios de pieza van a `director_editorial`;
   - la memoria va a `posicionamiento`, salvo la respuesta a una pregunta, que va al agente que la hizo;
   - las personas van a `relaciones_comunidad`.

   La transcripción no emite `consulta_biblioteca`.

**Errores.** Si algo falla (la transcripción, el permiso o la clasificación), la captura queda en `error` con un mensaje claro y su texto intacto. Un paso pagado nunca se repite solo:
- si el trabajo murió a medias, la captura pasa a `error` y no se vuelve a transcribir;
- si su trabajo quedó cancelado, fallido o interrumpido, la lista lo muestra como `error`.

## Deshacer

`DELETE /api/v1/capturas/<id>` funciona durante los 2 minutos siguientes al envío. Pasado ese tiempo devuelve 409 y lo creado se corrige desde su sitio. Solo puede deshacer quien envió la captura.

Al deshacer:
1. Cancela el trabajo si aún estaba en cola. Si ya está corriendo, el ruteo comprueba el estado bajo bloqueo de fila y no hace nada.
2. Revierte lo que anotó `routed_to`:
   - la pregunta se reabre con `preguntas.undo`, que restaura la memoria anterior; si no se puede, el dato queda retirado;
   - el dato pasa a lápida (`retirado: true`);
   - se quita la nota de la persona;
   - las ideas y los comentarios desaparecen con el estado `deshecha`.
3. Borra el audio y las fotos de la captura.
4. La fila queda en `deshecha`, sin nota ni transcripción, y deja de salir en el historial.

El coste de una transcripción ya hecha no se devuelve.

## Director editorial

- **Lo que recibe el director:**
  - `ideas_from_gustavo`: hasta 5 ideas en estado `idea` de los últimos 14 días, con `{id, text, date}`;
  - `feedback_from_gustavo`: los comentarios de pieza de los últimos 30 días, con `{piece_date, thesis, comment, date}`.
- **Lo que devuelve:** `BRIEF_SCHEMA` incluye `ideas_used`, la lista de ids de las ideas que usó. `DIRECTOR_SYSTEM` le pide dos cosas:
  - que dé prioridad a las ideas cuando encajen;
  - que no las cite como hechos, salvo que sean hechos sobre Gustavo, y en público solo si están en `public_facts`.
- **Después:** tras la etapa del director, las ideas usadas (y que se le ofrecieron) pasan a `usado` con «El Director editorial lo usó en el brief del jueves 12» y un enlace a la pieza. Las ideas que pasan 14 días sin usarse quedan en `sin_usar`.

## Transcripción con AssemblyAI

**Contrato.** Consultado el 2026-11-07 en `https://www.assemblyai.com/docs/llms.txt` y las páginas «Upload a media file», «Create transcript», «Get transcript», «Model selection» y «Billing and pricing».

1. **Subida.** `POST https://api.assemblyai.com/v2/upload`, con cabecera `authorization: <clave>`, `content-type: application/octet-stream` y los bytes crudos en el cuerpo. Devuelve `{upload_url}`.
2. **Transcripción.** `POST /v2/transcript` con `{audio_url, speech_models: ["universal-3-5-pro","universal-2"], language_detection: true}`, sin etiquetas de hablante ni extras. Se usa el primer modelo que soporte el idioma. Devuelve `{id, status}`.
3. **Consulta.** `GET /v2/transcript/{id}` cada 3 s hasta `completed` o `error`, como mucho `ASSEMBLYAI_TIMEOUT_S` (300). Se usan:
   - `status`;
   - `text`;
   - `language_code`;
   - `audio_duration` (segundos, entero);
   - `speech_model_used`;
   - `error`.

   Si una lectura falla de forma transitoria (429, 5xx o red), solo espera a la siguiente: leer no se cobra.

**Activación.** Exige `LIVE_PROVIDERS=true` y `ASSEMBLYAI_API_KEY`. La clave solo llega por el entorno.

**Ledger** (proveedor `assemblyai`, propósito `capture-transcribe`, dentro del presupuesto de IA del equipo, `AI_MONTHLY_LIMIT_USD`, y del techo opcional `ASSEMBLYAI_LIMIT_USD` si se fija):
- **Reserva.** Antes de subir nada, reserva el peor caso según la duración que dice el cliente: hasta 30 minutos, o 30 minutos si no la dice, a `ASSEMBLYAI_USD_PER_HOUR` (0,21 USD/h, Universal-3.5 Pro).
- **Liquidación.** Se liquida con la `audio_duration` real y la tarifa del modelo usado. Universal-2 cuesta 0,15 USD/h.
- **Fallos sin coste.** Una transcripción en `error` no se cobra, así que queda `rejected`. Lo mismo pasa con una subida fallida o un 4xx al crear.
- **Fallos inciertos.** Un 5xx o un corte de red al crear, o agotar el tiempo de espera, dejan la reserva `uncertain`: AssemblyAI podría terminarla y cobrarla. No se reintenta. Los mismos bytes no se pueden volver a enviar hasta revisar esa reserva (`authorize_uncertain_retry`).
- **Ajustes.** `GET /api/v1/ajustes` muestra el gasto del mes en `ai_spend.transcription_month_usd`.

**Cuánto cuesta.** Un audio de 1 minuto cuesta unos 0,0035 USD; con 5 USD caben unas 24 horas de audio.

## Galería

- **Estados de una foto:**
  - `sin_usar`, `elegida`, `editada` y `publicada` son los guardados en la base;
  - «Nueva» solo existe en pantalla: es `sin_usar` y subida hace menos de 24 h.
- **Etiquetas** (`display_state`, `label` y `tone`):

  | Estado | Etiqueta | Tono |
  | --- | --- | --- |
  | Nueva | Nueva | info |
  | Sin usar | Sin usar | muted |
  | Elegida | Elegida · dom 8 | info |
  | Editada | Editada con IA | ok |
  | Publicada | Publicada · 2 nov | ok |

- **Filtros:**
  - `sin_usar` incluye las nuevas;
  - `elegidas` incluye las editadas;
  - `publicadas`.
- **`ai_edit`:** no/auto/si; cada foto nueva toma la opción de la captura o `gallery_ai_edit` de Ajustes (auto por defecto). Los booleanos anteriores siguen como alias de API. La migración convierte false→no y true→auto.
- **Fase de imagen implementada en backend.** `imagenes.py` selecciona, edita, verifica y marca usos; `PieceImage` conserva dimensiones, alt, origen y revisión. Pillow dibuja infografías y tarjeta fija sin claves. Véase `docs/imagenes-fase-1.md` del repositorio y la sección de fase 2 del contrato.

## Archivos privados y almacenamiento

- **Ubicación.** Los archivos viven en `MEDIA_ROOT` (por defecto `<infra>/media`; en producción `/app/media`, en el volumen `media`):
  - el audio en `capturas/audio/AAAA/MM/<uuid>.<ext>`;
  - las fotos en `galeria/AAAA/MM/<uuid>.<ext>`.

  El nombre nunca viene del cliente.
- **Servicio.** No hay ruta pública: no existe `MEDIA_URL` y Caddy no sirve `/media`. Solo se sirven por `GET /api/v1/capturas/<id>/audio` y `GET /api/v1/galeria/<id>/imagen`, que exigen sesión (o credencial) con `operate_linkedin`. Responden con:
  - `Cache-Control: private, max-age=3600`;
  - `Content-Security-Policy: sandbox`;
  - `nosniff`;
  - el tipo comprobado del archivo.

  El audio admite rangos de bytes (206), que Safari exige para reproducir. Estas vistas no cuentan para el límite de peticiones de la API, porque una rejilla de fotos son muchas lecturas.
- **Límites:**
  - audio ≤ 25 MB y ≤ 30 minutos;
  - cada foto ≤ 10 MB;
  - ≤ 10 fotos por envío.
- **Tipos admitidos:**
  - audio: webm/opus (Chrome y Android), mp4/m4a (Safari), ogg, mp3, aac, wav y flac;
  - fotos: JPEG, PNG, WebP y HEIC/HEIF.
- **Caddy** rechaza cuerpos de más de 130 MB en `/api/v1/capturas` y `/api/v1/galeria`, y permite cámara y micrófono al propio origen (`Permissions-Policy`).

## Servidor

1. **`.env`:**
   - `ASSEMBLYAI_API_KEY` (la clave del proyecto de AssemblyAI);
   - `ASSEMBLYAI_USD_PER_HOUR=0.21`; `ASSEMBLYAI_LIMIT_USD` es opcional (vacío: solo cuenta el presupuesto general de IA, `AI_MONTHLY_LIMIT_USD`);
   - `MEDIA_ROOT=/app/media` (no cambiarlo: es la ruta del volumen y la imagen la crea con dueño `app`).
2. **Volumen.** `compose.prod.yaml` monta el volumen con nombre `media` en `/app/media` para `api` y `worker`. El worker lee el audio para transcribirlo, así que ambos deben ver los mismos archivos. Docker inicializa el volumen con el dueño del directorio de la imagen (uid 10001).
3. **Copias.** `deploy/backup.sh` guarda junto al volcado de la base un `backups/media-<fecha>.tar.gz` y conserva 14 días. Para restaurar:

   ```bash
   docker compose -f compose.prod.yaml --env-file .env exec -T api sh -c 'tar -C "${MEDIA_ROOT:-/app/media}" -xzf -' < backups/media-<fecha>.tar.gz
   ```
