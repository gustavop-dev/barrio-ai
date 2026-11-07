# Movimiento de la app (motion tokens)

Todo valor de movimiento de la app vive en un solo archivo: [`src/theme/motion.ts`](src/theme/motion.ts). Duraciones, resortes, curvas, umbrales de gestos y vibraciones salen de ahí. Ninguna pantalla escribe un número de movimiento. Para aplicar el diseño de movimiento de Gustavo, basta con cambiar los valores de ese archivo y recargar la app; no hay que tocar las pantallas.

Si una pieza nueva necesita un movimiento que no existe, se añade aquí primero: un token con nombre y una fila en esta tabla.

## Movimiento reducido

| Token | Valor | Qué hace |
|---|---|---|
| `REDUCE_MOTION` | `'system'` | `'system'` sigue el ajuste del teléfono («Quitar animaciones» en Android). `'always'` quita toda animación y `'never'` anima aunque el teléfono pida lo contrario. |
| `spring()` / `timing()` / `layout.*` | — | Cada configuración lleva `reduceMotion`. Con el movimiento reducido activo, Reanimated salta directamente al valor final. |
| `useMotion()` | — | Devuelve `{ reduced }` para lo que Reanimated no resuelve solo: bucles como el punto rojo, la bola que late, el esqueleto y el bibliotecario en reposo. Con `reduced` en `true` quedan quietos. |

## Resortes (`springs`: damping, stiffness, mass)

| Token | Valores | Dónde se usa |
|---|---|---|
| `snapBack` | 20 · 260 · 1 | Tu turno: la tarjeta deslizada que no llega al umbral vuelve a su sitio (`turno/SwipeableCard.tsx`). |
| `captureGrow` | 15 · 320 · 0.7 | El botón de captura crece a 72 px al mantenerlo y vuelve a 60 px (`capture/CaptureButton.tsx`). |
| `captureFollow` | 24 · 420 · 0.6 | El botón y el candado siguen al dedo hacia arriba y vuelven abajo (`capture/CaptureButton.tsx`). |
| `sheetOpen` | 24 · 260 · 1 | Las hojas inferiores suben y vuelven a su sitio tras arrastrarlas sin cerrar: captura, confirmaciones, oportunidad y datos (`components/ui/Sheet.tsx`). |
| `press` | 18 · 420 · 0.6 | Botón al soltarlo y píldora de la pestaña activa en la barra inferior (`components/ui/Button.tsx`, `components/shell/BottomBar.tsx`). |
| `toast` | 20 · 260 · 0.9 | El aviso inferior entra subiendo (`layout.toastIn`, en `components/ui/Toast.tsx`). |
| `dragLift` | 18 · 300 · 0.8 | Personas › Oportunidades: la tarjeta crece al levantarla con una pulsación larga y vuelve al soltarla (`personas/Oportunidades.tsx`). |
| `zoomSettle` | 22 · 240 · 1 | El visor de fotos de la Galería: el zoom con doble toque, la foto que vuelve dentro de sus bordes tras pellizcar o arrastrar, y la foto que vuelve a su sitio si el arrastre para cerrar no llega (`galeria/PhotoViewer.tsx`). |

## Duraciones y curvas (`timings`, `easings`)

Curvas disponibles: `standard` (bezier 0.2, 0, 0, 1), `enter` (salida cúbica), `exit` (entrada cúbica) y `pulse` (seno de ida y vuelta).

| Token | ms · curva | Dónde se usa |
|---|---|---|
| `press` | 90 · standard | El botón se encoge al 97 % al pulsarlo (`components/ui/Button.tsx`). |
| `swipeExit` | 200 · exit | La tarjeta deslizada sale de la pantalla cuando la acción se confirma (`turno/SwipeableCard.tsx`). |
| `listExit` | 220 · exit | Una tarjeta sale de la lista y las demás cierran el hueco (`layout.listExit` y `layout.listMove`, en `turno/TuTurnoScreen.tsx`). |
| `listEnter` | 240 · enter | Las tarjetas y las etiquetas de grupo entran en la lista (`layout.listEnter`). |
| `fold` | 200 · standard | Los plegables «Pospuestas», «Hecho recientemente» y «Cómo se ordena»: giro del chevrón y aparición del contenido (`components/ui/Fold.tsx`). También abre la lista de opciones de un selector (`components/ui/Select.tsx`) y las semanas anteriores del resumen (`resultados/ResumenSemanal.tsx`). |
| `backdrop` | 180 · enter | El fondo oscuro de las hojas aparece y desaparece (`components/ui/Sheet.tsx`). |
| `sheetClose` | 200 · exit | La hoja baja al cerrarse (`components/ui/Sheet.tsx`). |
| `toastOut` | 160 · exit | El aviso inferior se desvanece (`layout.toastOut`). |
| `holdOverlay` | 140 · enter | Aparecen la banda de grabación, el candado y su pista al mantener el botón (`layout.overlayIn` y `layout.overlayOut`, en `capture/CaptureButton.tsx`). |
| `recordDot` | 1000 · pulse | Un parpadeo completo del punto rojo mientras se mantiene el botón (`capture/Pulse.tsx`). |
| `recordPulse` | 1400 · pulse | Un latido completo de la bola 0ff1ce con la grabación bloqueada (`capture/Pulse.tsx`, en `capture/CaptureSheet.tsx`). |
| `skeleton` | 1100 · pulse | Un ciclo de respiración de los esqueletos de carga (`components/ui/Skeleton.tsx`). |
| `screen` | 260 · standard | La transición de las pantallas de detalle (pieza, persona) en la pila (`app/_layout.tsx`, `app/(app)/_layout.tsx`). Android usa su animación nativa; la duración solo se aplica en iOS. |
| `spriteFrameMs` | 200 | Un fotograma del bibliotecario en reposo de los estados vacíos: 6 fotogramas en 1,2 s (`components/ui/Sprite.tsx`). |
| `toastDurations.withUndo` | 5000 | Lo que dura un aviso con «Deshacer» o «Recuperar», la ventana de acción reversible (`components/ui/Toast.tsx`). |
| `toastDurations.plain` | 4000 | Lo que dura un aviso sin acción. |
| `viewerFade` | 180 · enter | El visor de fotos a pantalla completa aparece y desaparece (`layout.viewerIn` y `layout.viewerOut`, en `galeria/PhotoViewer.tsx`). |
| `progress` | 240 · standard | La barra de «Subir fotos» avanza cada vez que entra una petición de hasta diez fotos (`galeria/UploadProgressCard.tsx`). |

## Umbrales de gestos (`gestures`)

| Token | Valor | Dónde se usa |
|---|---|---|
| `swipe.activeOffsetX` | 14 pt | Recorrido horizontal antes de que la tarjeta empiece a seguir al dedo (`turno/SwipeableCard.tsx`). |
| `swipe.failOffsetY` | 12 pt | Recorrido vertical que devuelve el toque al scroll de la lista. |
| `swipe.commitFraction` | 0.33 | Fracción del ancho de la tarjeta que confirma la acción al soltar (`turno/swipe.ts`). |
| `swipe.commitVelocity` | 900 pt/s | Velocidad mínima de un gesto rápido que confirma aunque no llegue al umbral. |
| `swipe.overdragResistance` | 0.35 | Resistencia pasado el umbral y hacia un lado sin acción. |
| `swipe.revealFraction` | 0.6 | El icono de la acción alcanza su tamaño completo a esta fracción del umbral. |
| `capture.holdDelayMs` | 220 ms | Tiempo que hay que mantener el botón antes de que empiece a grabar; menos cuenta como toque y abre la hoja (`capture/CaptureButton.tsx`). |
| `capture.minHoldMs` | 600 ms | Una pulsación más corta no guarda audio y abre la hoja vacía (`capture/hold.ts`). |
| `capture.lockDistance` | 64 pt | Deslizar hacia arriba esta distancia bloquea la grabación (`capture/hold.ts`). |
| `capture.discardDistance` | 110 pt | Deslizar hacia la izquierda esta distancia descarta la grabación y ofrece «Recuperar». |
| `capture.maxLift` | 60 pt | Altura máxima que el botón y el candado siguen al dedo. |
| `sheet.dismissDistance` | 120 pt | Arrastrar la hoja hacia abajo esta distancia la cierra (`components/ui/Sheet.tsx`). |
| `sheet.dismissVelocity` | 1000 pt/s | O lanzarla hacia abajo a esta velocidad. |
| `drag.longPressMs` | 400 ms | Personas › Oportunidades: mantener una tarjeta este tiempo la levanta para arrastrarla a otra etapa (`personas/Oportunidades.tsx`). |
| `drag.liftScale` | 1.03 | Escala de la tarjeta levantada. |
| `drag.autoScrollEdge` | 80 pt | Cerca del borde superior o inferior de la lista, la tarjeta arrastrada la desplaza. |
| `drag.autoScrollSpeed` | 700 pt/s | Velocidad de ese desplazamiento. |
| `zoom.maxScale` | 4 | Máximo del pellizco en el visor de fotos; 1 es la foto ajustada a la pantalla (`galeria/PhotoViewer.tsx`). |
| `zoom.doubleTapScale` | 2.5 | A dónde acerca un doble toque; otro doble toque vuelve a 1. |
| `zoom.doubleTapMaxDelayMs` | 250 ms | Separación máxima entre los dos toques del doble toque. |
| `viewer.activeOffsetY` | 16 pt | Recorrido vertical antes de que la foto sin zoom siga al dedo para cerrar el visor. |
| `viewer.failOffsetX` | 14 pt | Recorrido horizontal que deja el gesto al paginador (pasar de foto). |
| `viewer.dismissDistance` | 140 pt | Arrastrar la foto hacia arriba o abajo esta distancia cierra el visor. |
| `viewer.dismissVelocity` | 1000 pt/s | O lanzarla a esta velocidad. |
| `viewer.dragFade` | 0.4 | Cuánto se desvanece la foto (0–1) al llegar a `viewer.dismissDistance` mientras se arrastra para cerrar. |

## Vibraciones (`haptics`)

`HAPTICS_ENABLED` las apaga todas. Para quitar una sola, se pone su entrada a `null`.

| Token | Vibración | Dónde se usa |
|---|---|---|
| `swipeThreshold` | selección | La tarjeta cruza el umbral de confirmación, también al volver atrás (`turno/SwipeableCard.tsx`). |
| `swipeCommit` | impacto medio | El deslizamiento confirma su acción. |
| `captureStart` | impacto medio | Empieza a grabar al mantener el botón, o al pulsar «Grabar un audio» en la hoja. |
| `captureLock` | impacto ligero | Deslizar hacia arriba bloquea la grabación. |
| `captureDiscard` | aviso (warning) | Deslizar hacia la izquierda descarta la grabación. |
| `captureSent` | éxito | La captura llegó al equipo (`capture/CaptureSheet.tsx`). |
| `actionSuccess` | éxito | Una acción de tarjeta, una respuesta o una oportunidad se guardaron (`turno/*`). |
| `actionError` | error | Una acción o un envío fallaron. |
| `tabChange` | selección | Cambiar de pestaña en la barra inferior o en las pestañas de una vista. |
| `toggle` | sin vibración | Marcar un chip o una opción (`components/ui/Chip.tsx`, `components/ui/Options.tsx`, `components/ui/Select.tsx`). |
| `dragStart` | impacto medio | Personas › Oportunidades: la tarjeta se levanta tras la pulsación larga (`personas/Oportunidades.tsx`). |
| `dragOver` | selección | La tarjeta arrastrada pasa sobre otra etapa. |
| `dragDrop` | impacto ligero | La tarjeta se suelta en una etapa nueva. |
| `toggle` | sin vibración | Marcar un chip o una opción (`components/ui/Chip.tsx`, `components/ui/Options.tsx`). |
| `switchToggle` | sin vibración | Cambiar un interruptor de fila: Ajustes y la hoja de la foto (`components/ui/SwitchRow.tsx`). |
| `uploadDone` | éxito | Las fotos llegaron a la Galería (`galeria/upload.ts`). |

## Usos en Galería, Ajustes y Notificaciones

Estas vistas reutilizan tokens que ya existían, sin valores nuevos:

- `listEnter` y `listMove`: las miniaturas de la Galería y las filas de Notificaciones al entrar y al moverse.
- `fold`: los plegables «Autonomía y límites» y «Por tipo de notificación» de Ajustes.
- `sheetOpen`, `backdrop` y `sheetClose`: la hoja de la foto y las confirmaciones de Ajustes.
- `actionSuccess` y `actionError`: guardar o quitar una foto, la parada y la reanudación de la máquina, la pausa de una cuenta, la orientación y «Probar notificación».

## Oficina · escena y hoja de detalle

El motor compartido recibe `officeMotion` desde este módulo. Sus valores iniciales proceden de
`compartido/src/scene/motion.ts` para conservar la coreografía de la PWA; cualquier ajuste nativo se
sobrescribe en `officeMotion`, sin editar la pantalla ni el motor. El zoom se ajusta a píxeles físicos
enteros y el doble toque vuelve inmediatamente al encuadre inicial, sin escalas intermedias borrosas.

| Token | Valor | Dónde se usa |
|---|---|---|
| `timings.officeNowIn` / `officeNowOut`, `officeLayout.nowIn/nowOut` | 240 ms enter / 160 ms exit | Entrada y salida de la narración flotante en `scene/OficinaScreen.tsx`. |
| `officeMotion.walkSpeed` | 40 px lógicos/s | Caminatas del motor compartido (`scene/runtime.ts`). |
| `officeMotion.startGap` / `summaryHold` | 1800 / 2600 ms | Espaciado de eventos y resúmenes. |
| `officeMotion.ambientFirst` / `ambientEvery` | 9000 / 20000 ms | Café y charla únicamente para roles en espera. |
| `officeMotion.fadeMs` | 500 ms | Operación sale y vuelve por la puerta. |
| `officeMotion.questionMs` / `bookMs` / `readMs` | 1800 / 2200 / 1600 ms | Consulta de biblioteca. |
| `officeMotion.searchMs` / `librarianBookMs` / `handBookMs` | 1400 / 1200 / 900 ms | Búsqueda y entrega del bibliotecario. |
| `officeMotion.sheetMs` / `handSheetMs` / `conversationMs` / `deliveryMs` | 2200 / 900 / 1800 / 1500 ms | Entrega entre equipos. |
| `officeMotion.outsideMs` / `doneMs` / `returnMs` | 1300 / 2000 / 800 ms | Publicación ejecutada. |
| `officeMotion.coffeeMs` / `chatMs` / `chatReplyMs` | 2600 / 2000 / 2200 ms | Pausas de café y conversación. |
| `officeMotion.runFrameMs` / `idleFrameMs` | 110 / 220 ms | Fotogramas del atlas en `scene/sprites.ts`. |
| `officeMotion.lightMs` / `bubbleFrameMs` | 700 / 300 ms | Luces de actividad y bocadillos en `scene/Decorations.tsx`. |
| `officeFrames.stepMs` / `maxDeltaMs` | 16 / 64 ms | Paso fijo y límite de recuperación tras un frame lento. |
| `officeFrames.reportFrames` / `slowFrameMs` | 300 / 1000÷60 ms | Diagnóstico de desarrollo: delta medio/máximo, frames sobre presupuesto y coste medio del motor. |
| `officeGestures.minZoom` / `maxZoom` | 1 / 3 | Límites relativos a la escala inicial. |
| `officeGestures.panDistance` / `tapDistance` | 8 / 10 dp | Activación del desplazamiento y tolerancia de toque. |
| `officeGestures.tapDurationMs` / `doubleTapMs` | 250 / 280 ms | Duración máxima de toque e intervalo de doble toque. |
| `officeGestures.touchTarget` | 48 dp | Área mínima al tocar personajes en el canvas. |
| `officeGestures.sheetActivation` | 8 dp | Inicio del arrastre del asa de `SnapSheet`. |
| `officeGestures.sheetHalf` / `sheetFull` | 0.5 / 0.88 | Puntos de ajuste de `SnapSheet`, sobre el espacio disponible. |
| `haptics.officePick` | selección | Selección de un personaje, zona o equipo. |

`SnapSheet` reutiliza `springs.sheetOpen`, `timings.sheetClose` y `gestures.sheet` para volver a un
punto de ajuste o cerrar; ofrece ampliar/reducir mediante acciones de accesibilidad y Cerrar.
Con movimiento reducido se desactiva el callback de frames, todos vuelven a su puesto y los nuevos
eventos solo se narran. La ausencia de foco, el segundo plano y la pausa de máquina también paran el
callback; los observers de Oficina dejan de consultar al perder foco o pasar a segundo plano.

Para medir en un teléfono: `cd movil && npm start -- --offline`, abrir Oficina en Expo Go con una
sesión de desarrollo y observar `[Oficina/UI]` cada 300 frames. `meanSimulationMs` mide solo el motor;
los deltas incluyen el ritmo de presentación, no aíslan el coste de GPU. Comprobar también pan,
pinch, regreso del fondo y movimiento reducido. El render local de CanvasKit y las pruebas no
constituyen una medición de 60 fps en Android.
