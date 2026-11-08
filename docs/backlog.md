# Backlog

Pendientes que quedan fuera de lo esencial. La fuente de verdad sigue siendo el catálogo (`docs/funcionalidades/`): cuando
algo de aquí se resuelve, se actualiza su ID allí y se borra de esta lista.

Prioridad: **A** (afecta seguridad o al uso diario), **B** (funciona, pero mal o incompleto) y **C** (detalle visual o
comodidad).

Leyenda de la columna «Quién»:

- **Gustavo**: necesita una acción o decisión suya.
- **Equipo**: lo resuelve el equipo de agentes; los cambios los hace Codex y Claude los sube y verifica en CI y QA.

## Dependen de Gustavo

| # | Prioridad | Qué | Por qué importa | Quién |
|---|---|---|---|---|
| 1 | A | Notificaciones push en el teléfono (Firebase) | El APK no tiene `googleServicesFile`, así que las push no llegan al celular; solo se ven dentro de la app (PUS-08, PUS-10). Pasos: crear un proyecto de Firebase, registrar la app Android `co.projectapp.office`, descargar `google-services.json` y subir la llave FCM V1 a las credenciales de EAS. Después hace falta un APK nuevo. | Gustavo + Equipo |
| 2 | A | Rotar llaves expuestas | El token de Expo se pegó en el chat. Las llaves de Unipile, el secreto de LinkedIn, TypeSafe y AssemblyAI se vieron en sesiones anteriores. Hay un script preparado; cada llave nueva se guarda en un archivo con permisos 600 y se sube al servidor sin imprimirla. | Gustavo |
| 3 | B | Hacer `qa` obligatorio antes de fusionar | Hoy un PR se puede fusionar con QA en rojo. El comando exacto (`gh api … /rulesets`) está en `movil/.maestro/README.md`, sección «Check obligatorio para los PR». | Gustavo |
| 4 | B | Compilar el APK en GitHub en vez de EAS | Las máquinas de GitHub no tienen cola ni límite de 15 builds al mes y tienen 16 GB de RAM; EAS gratis falló por falta de memoria. Requiere exportar la llave de firma desde EAS (`eas credentials`) para que el teléfono acepte el APK como actualización. | Gustavo + Equipo |
| 5 | B | Verificar la organización en OpenAI, si hace falta | La llave ve los modelos de imagen (`gpt-image-2` y otros), pero OpenAI puede exigir verificar la organización al generar. Se confirma con la primera edición real; si falla, el post sale con la foto original o con una imagen dibujada por código. | Gustavo |

## Bugs

| # | Prioridad | Qué | Detalle |
|---|---|---|---|
| 6 | A | El bloqueo por intentos de contraseña no es fiable (ACC-03) | El contador vive en la caché en memoria de cada proceso de gunicorn. Con varios procesos se pueden intentar más contraseñas antes del bloqueo. Hay que moverlo a la base de datos o a una caché compartida. Lo cubren las pruebas del backend; con 3 procesos, en E2E no bloquea. |
| 7 | A | Una respuesta de voz se pierde si la pregunta se cierra antes | Captura del 07/11 14:50: Gustavo respondió por voz una pregunta de Tu turno («arquitecturas de IA, RAG, embeddings…») y el procesamiento falló con «La pregunta ya no está abierta». El contenido no quedó guardado en ningún lado. Debería guardarse igual, como dato o como idea, y avisar que la pregunta ya estaba cerrada. |
| 8 | B | «Invitaciones previstas» cuenta invitaciones que ya están en cola | `invite_expected` no descuenta las invitaciones RED-02 ya aprobadas (por ejemplo, Camila Ortiz en los datos de QA). |
| 9 | B | Tres funcionalidades «con fallo conocido» en el catálogo | CAL-11, PRS-05 y PRS-07. Ver su ficha en `docs/funcionalidades/`. |
| 10 | B | Falta el botón «Desactivar notificaciones en este dispositivo» (PUS-03) | Está en el catálogo como parcial. |
| 11 | B | Un `POST` respondió 400 el 08/11 por la tarde | No fue una captura: las cinco del día están registradas. Revisar el log de la API con `request_id` si se repite. |

## Detalles visuales

Los encontraron los agentes de E2E en las capturas de pantalla, comparándolas con los tableros de
`movil/diseno-movimiento/tableros/`.

| # | Prioridad | Dónde | Qué |
|---|---|---|---|
| 12 | C | Calendario | Horas sin cero inicial: «8:30» en vez de «08:30», que es como lo muestran los tableros. |
| 13 | C | Calendario | Las piezas publicadas, bloqueadas o vetadas siguen diciendo «Se publica tal cual, en inglés». |
| 14 | C | Calendario | El chip «Comentario sobre la pieza» dice «Pieza del <día>»; el catálogo pide la tesis. |
| 15 | C | Calendario | Los separadores del resumen del día empiezan una línea («· 1 conexión nueva…»). |
| 16 | C | Resultados | «Periodo» no tiene etiqueta visible; el tablero sí la tiene. |
| 17 | C | Personas | El chip de etapa seleccionado queda medio fuera de pantalla. |
| 18 | C | Personas | Las etiquetas del recorrido siempre van en masculino («Descubierto», «Seguido»); el tablero de Persona usa la forma con género. |
| 19 | C | Ajustes | El gasto del mes por encima del límite («1,04 USD de 1,00 USD») no tiene tono de alerta. |
| 20 | C | Ajustes | La fecha de la orientación sale completa («27/10/2026, 4:57 a. m.») en vez de «hace X». |
| 21 | C | Ajustes | «Dispositivos con la app» muestra el modelo crudo (`sdk_gphone64_x86_64`). |
| 22 | C | Tu turno | La tarjeta de conversación no sigue TuTurno.dc.html: faltan «Resumen del hilo», «Borrador sugerido» y «Copiar borrador», y «Por qué importa» muestra porcentajes crudos. |
| 23 | C | Tu turno | La tarjeta de aprobación es un tipo nuevo que no está en el diseño. |
| 24 | C | Oficina | Franja blanca arriba a la izquierda de la escena, bajo la barra superior. |
| 25 | C | Login | Con el teclado abierto, los iconos oscuros de la barra de estado quedan sobre el fondo oscuro. |
| 26 | C | Visor de fotos | La barra de estado tiene iconos oscuros sobre el fondo tinta. |
| 27 | C | Galería | El error 413 muestra el detalle genérico, no la explicación «demasiado grande» de la captura. |
| 28 | C | Galería | Falta la marca «usada en la pieza del …» (IMG-12); el backend la guarda desde el flujo de imágenes. |

## Cobertura E2E que falta

Funcionalidades de la app sin flujo de Maestro. Hoy el catálogo cuenta 116 de 130 cubiertas; aquí solo las que se podrían
cubrir. Las que necesitan un teléfono real (push, OTA, cámara, permisos, límites de tamaño) se prueban a mano.

| # | Prioridad | ID | Qué falta |
|---|---|---|---|
| 29 | C | CAL-10 | Pieza en preparación: hay que sembrarla sin romper los flujos que esperan «nada en camino». |
| 30 | C | SEM-07 | «Generar ahora»: los datos de QA ya traen el resumen de la semana, así que el botón nunca aparece. |
| 31 | C | TUR-05 | LinkedIn caducado: `seed_qa` se niega a crear una credencial de LinkedIn. Necesita un modo de QA para simularla. |
