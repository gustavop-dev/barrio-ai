# Errores conocidos
Conservar reserva de solicitudes inciertas y revisar antes de repetir. ConnectError antes de envío admite reintento acotado. Evidencias contienen NUL: preservar columna json original, no convertir a jsonb. No reiniciar automáticamente trabajos running al perder el trabajador.

Revisión Django: corregidos dos fallos antes de activar el backend. Un fallo del hilo de latidos ahora detiene nuevas reclamaciones. La escritura de memoria y su auditoría utilizan una sola transacción psycopg: un error de auditoría revierte la propuesta/confirmación. Pruebas de regresión cubren ambos casos. El admin difiere los blobs de unidades/ejecuciones en listados.

Docker como usuario no privilegiado reveló una descarga del tokenizador durante import. Se empaquetó cl100k_base con SHA-256 verificado para arrancar sin esa dependencia de red.
