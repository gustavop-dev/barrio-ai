# Errores conocidos
Conservar reserva de solicitudes inciertas y revisar antes de repetir. ConnectError antes de envío admite reintento acotado. Evidencias contienen NUL: preservar columna json original, no convertir a jsonb. No reiniciar automáticamente trabajos running al perder el trabajador.

Revisión Django: corregidos dos fallos antes de activar el backend. Un fallo del hilo de latidos ahora detiene nuevas reclamaciones. La escritura de memoria y su auditoría utilizan una sola transacción psycopg: un error de auditoría revierte la propuesta/confirmación. Pruebas de regresión cubren ambos casos. El admin difiere los blobs de unidades/ejecuciones en listados.

Docker como usuario no privilegiado reveló una descarga del tokenizador durante import. Se empaquetó cl100k_base con SHA-256 verificado para arrancar sin esa dependencia de red.

Perfil tras #90: el 400 `Transparent background is not supported for this model.` venía de enviar `background=transparent` a `gpt-image-2`. La capacidad ahora es explícita por modelo, con salida opaca por defecto y recorte croma validado en Pillow. El ledger y los motivos conservan `error.message`, `param` y `code` redactados. Un `context.banner={}` también omitía la frase disponible en la sección; se recupera allí primero y después del checkpoint privado, se persiste y se calcula el ajuste. La versión del recorte entra en la firma de la operación para que un job terminado anterior no absorba el pedido corregido. No se reintentan reservas inciertas. Regresiones sintéticas escritas; ejecución y QA pendientes.
