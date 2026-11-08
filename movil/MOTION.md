# Movimiento de la app (motion tokens)

Todo valor de movimiento de la app vive en un solo archivo: [`src/theme/motion.ts`](src/theme/motion.ts). Duraciones, resortes, curvas, umbrales de gestos y vibraciones salen de ahí. Ninguna pantalla escribe un número de movimiento. Para aplicar el diseño de movimiento de Gustavo, basta con cambiar los valores de ese archivo y recargar la app; no hay que tocar las pantallas.

Si una pieza nueva necesita un movimiento que no existe, se añade aquí primero: un token con nombre y una fila en esta tabla.

## Base del diseño (Claude Design)

El diseño de movimiento de Gustavo está en [`diseno-movimiento/`](diseno-movimiento/README.md) y es la fuente. Todos sus tableros usan el mismo motor, y estos son sus valores. Los resortes del diseño integran `−k·(x − destino) − c·v` con masa 1, el mismo modelo de Reanimated: `k` es `stiffness` y `c` es `damping`.

| Token | Valor | Qué es |
|---|---|---|
| `durations.instant` / `fast` / `base` / `slow` | 100 / 180 / 260 / 400 ms | Las cuatro duraciones. `fast` es la de casi todas las transiciones. `base` es para pantallas y paneles, y `slow` para las revelaciones grandes. |
| `FIRM` | 20 · 260 · 1 | Hojas, pushes, navegación, selecciones y todo lo que sigue al dedo (`TOK.firm`). |
| `SOFT` | 14 · 160 · 1 | Pulsaciones, latidos, contadores y transformaciones (`TOK.soft`). |
| `easings.enter` | bezier(0.2, 0, 0, 1) | Lo que entra: arranca rápido y se asienta (`EASE_OUT`). |
| `easings.exit` | bezier(0.3, 0, 1, 1) | Lo que sale: arranca suave y se va rápido (`EASE_IN`). |
| `RUBBER` / `rubberBand()` | 0.35 | Pasado un borde, el arrastre conserva el 35 % de la distancia extra. |

Los resortes y tiempos genéricos de las tablas de abajo ya apuntan a esta base (`snapBack`, `sheetOpen`, `press`…). La coreografía de cada pantalla se afina en su sección.

## Movimiento reducido

| Token | Valor | Qué hace |
|---|---|---|
| `REDUCE_MOTION` | `'system'` | `'system'` sigue el ajuste del teléfono («Quitar animaciones» en Android). `'always'` quita toda animación y `'never'` anima aunque el teléfono pida lo contrario. |
| `spring()` / `timing()` / `layout.*` | — | Cada configuración lleva `reduceMotion`. Con el movimiento reducido activo, Reanimated salta directamente al valor final. |
| `useMotion()` | — | Devuelve `{ reduced }` para lo que Reanimated no resuelve solo: bucles como el punto rojo, la bola que late, el esqueleto y el bibliotecario en reposo. Con `reduced` en `true` quedan quietos. |

## Resortes (`springs`: damping, stiffness, mass)

| Token | Valores | Dónde se usa |
|---|---|---|
| `snapBack` | FIRM (20 · 260 · 1) | Tu turno: la tarjeta deslizada que no llega al umbral vuelve a su sitio (`turno/SwipeableCard.tsx`). |
| `captureGrow` | SOFT (14 · 160 · 1) | El botón de captura crece a 72 px al mantenerlo y vuelve a 60 px (`capture/CaptureButton.tsx`). |
| `captureFollow` | FIRM (20 · 260 · 1) | El botón y el candado siguen al dedo hacia arriba y vuelven abajo (`capture/CaptureButton.tsx`). |
| `sheetOpen` | FIRM (20 · 260 · 1) | Las hojas inferiores suben y vuelven a su sitio tras arrastrarlas sin cerrar: captura, confirmaciones, oportunidad y datos (`components/ui/Sheet.tsx`). |
| `press` | SOFT (14 · 160 · 1) | Botón al soltarlo y píldora de la pestaña activa en la barra inferior (`components/ui/Button.tsx`, `components/shell/BottomBar.tsx`). |
| `toast` | FIRM (20 · 260 · 1) | El aviso inferior entra subiendo (`layout.toastIn`, en `components/ui/Toast.tsx`). |
| `pageSnap` | FIRM (20 · 260 · 1) | Calendario: la tira de la semana o el mes se asientan en la página siguiente o anterior tras deslizar, o vuelven a su sitio (`calendario/Pager.tsx`). |
| `dragLift` | 18 · 300 · 0.8 | Personas › Oportunidades: la tarjeta crece al levantarla con una pulsación larga y vuelve al soltarla (`personas/Oportunidades.tsx`). |
| `zoomSettle` | 22 · 240 · 1 | El visor de fotos de la Galería: el zoom con doble toque, la foto que vuelve dentro de sus bordes tras pellizcar o arrastrar, y la foto que vuelve a su sitio si el arrastre para cerrar no llega (`galeria/PhotoViewer.tsx`). |

## Duraciones y curvas (`timings`, `easings`)

Curvas disponibles: `standard` (bezier 0.2, 0, 0, 1), `enter` (salida cúbica), `exit` (entrada cúbica) y `pulse` (seno de ida y vuelta).

| Token | ms · curva | Dónde se usa |
|---|---|---|
| `press` | 100 (instant) · standard | El botón se encoge al 97 % al pulsarlo (`components/ui/Button.tsx`). |
| `swipeExit` | 180 (fast) · exit | La tarjeta deslizada sale de la pantalla cuando la acción se confirma (`turno/SwipeableCard.tsx`). |
| `listExit` | 180 (fast) · exit | Una tarjeta sale de la lista y las demás cierran el hueco (`layout.listExit` y `layout.listMove`, en `turno/TuTurnoScreen.tsx`). |
| `listEnter` | 260 (base) · enter | Las tarjetas y las etiquetas de grupo entran en la lista (`layout.listEnter`). |
| `fold` | 180 (fast) · standard | Los plegables «Pospuestas», «Hecho recientemente» y «Cómo se ordena»: giro del chevrón y aparición del contenido (`components/ui/Fold.tsx`). También abre la lista de opciones de un selector (`components/ui/Select.tsx`) y las semanas anteriores del resumen (`resultados/ResumenSemanal.tsx`). |
| `backdrop` | 180 (fast) · enter | El fondo oscuro de las hojas aparece y desaparece (`components/ui/Sheet.tsx`). |
| `sheetClose` | 180 (fast) · exit | La hoja baja al cerrarse (`components/ui/Sheet.tsx`). |
| `toastOut` | 180 (fast) · exit | El aviso inferior se desvanece (`layout.toastOut`). |
| `holdOverlay` | 100 (instant) · enter | Aparecen la banda de grabación, el candado y su pista al mantener el botón (`layout.overlayIn` y `layout.overlayOut`, en `capture/CaptureButton.tsx`). |
| `recordDot` | 1000 · pulse | Un parpadeo completo del punto rojo mientras se mantiene el botón (`capture/Pulse.tsx`). |
| `recordPulse` | 1400 · pulse | Un latido completo de la bola 0ff1ce con la grabación bloqueada (`capture/Pulse.tsx`, en `capture/CaptureSheet.tsx`). |
| `skeleton` | 1100 · pulse | Un ciclo de respiración de los esqueletos de carga (`components/ui/Skeleton.tsx`). |
| `screen` | 260 (base) · enter | La transición de las pantallas de detalle (pieza, persona) en la pila (`app/_layout.tsx`, `app/(app)/_layout.tsx`). Android usa su animación nativa; la duración solo se aplica en iOS. |
| `spriteFrameMs` | 200 | Un fotograma del bibliotecario en reposo de los estados vacíos: 6 fotogramas en 1,2 s (`components/ui/Sprite.tsx`). |
| `toastDurations.withUndo` | 5000 | Lo que dura un aviso con «Deshacer» o «Recuperar», la ventana de acción reversible (`components/ui/Toast.tsx`). |
| `toastDurations.plain` | 4000 | Lo que dura un aviso sin acción. |
| `toastDurations.withUndo` (veto) | 5000 | El veto de una pieza o de una acción en cola espera esta ventana antes de enviarse, para que «Deshacer» lo anule (`calendario/pendingVeto.ts`). |
| `copiedLabelMs` | 2000 | Lo que dura «Copiado» en el botón Copiar del texto final (`pieza/FinalText.tsx`). |
| `viewerFade` | 180 (fast) · enter | El visor de fotos a pantalla completa aparece y desaparece (`layout.viewerIn` y `layout.viewerOut`, en `galeria/PhotoViewer.tsx`). |
| `progress` | 260 (base) · standard | La barra de «Subir fotos» avanza cada vez que entra una petición de hasta diez fotos (`galeria/UploadProgressCard.tsx`). |

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
| `pager.activeOffsetX` | 16 pt | Calendario: recorrido horizontal antes de que la semana o el mes sigan al dedo (`calendario/Pager.tsx`). |
| `pager.failOffsetY` | 14 pt | Recorrido vertical que deja el toque al scroll de la página. |
| `pager.commitFraction` | 0.25 | Fracción del ancho que pasa de página al soltar. |
| `pager.commitVelocity` | 700 pt/s | O un gesto rápido a esta velocidad. |
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
| `pageChange` | selección | Calendario: deslizar pasa la semana o el mes (`calendario/Pager.tsx`). |
| `copied` | éxito | El texto final quedó en el portapapeles (`pieza/FinalText.tsx`). |
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
| `timings.officeNowIn` / `officeNowOut`, `officeLayout.nowIn/nowOut` | 260 (base) enter / 180 (fast) exit | Entrada y salida de la narración flotante en `scene/OficinaScreen.tsx`. |
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

El panel del día del Calendario también es un `SnapSheet` (`calendario/CalendarioScreen.tsx`), con los mismos tokens.

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

## Navegación, Entrada y Detalle (MovNavegacion, MovEntrada, MovDetalle)

Grupos propios en `motion.ts`: `navSprings`, `navTimings`, `navValues`, `navGestures` y `entrada`, con `navSpring()`, `navTiming()`, `crossfade()` y `navLayout`. `BEZIER` da los puntos de control de `easings.enter` y `easings.exit` al `Animated` de React Native (las escenas de las pestañas). No hay vibraciones nuevas: el cambio de pestaña usa `tabChange`.

| Token | Valor | Dónde se usa |
|---|---|---|
| `navSprings.pill` | FIRM | La píldora de la barra inferior se desliza a la pestaña tocada (`components/shell/BottomBar.tsx`). Sin pestaña inferior activa (Tu turno, Notificaciones, Calendario, Ajustes) se oculta. |
| `navSprings.tabIcon` / `navValues.tabIconFrom` | SOFT · 0.92 | El icono de la pestaña nueva salta a 0.92 y vuelve a 1 (`BottomBar.tsx`). |
| `navTimings.tabIn` / `navValues.tabRise` | 180 (fast) · enter · 8 pt | El contenido de la pestaña nueva aparece y sube 8 pt; la barra superior queda quieta (`components/shell/tabTransitions.ts`, en `app/(app)/(tabs)/_layout.tsx`). |
| `navTimings.tabOut` | 108 (60 % de fast) · exit | El contenido de la pestaña anterior se desvanece. |
| `navSprings.push` | FIRM | El push: una pantalla de detalle (pieza, persona) entra desde la derecha y vuelve con «‹», el botón atrás de Android o cualquier navegación que la quite (`components/shell/DetailScreen.tsx`, `components/shell/push.ts`). También abre las pantallas de los iconos de arriba (`tabTransitions.ts`). |
| `navValues.pushParallax` / `pushDim` | 0.3 · 0.08 | La pantalla de debajo se mueve a la izquierda el 30 % del ancho y se oscurece con tinta al 8 % (`push.ts`, `(tabs)/_layout.tsx`). Con movimiento reducido solo se oscurece. |
| `navGestures.edgeWidth` | 24 pt | Franja del borde izquierdo de un detalle (bajo la barra superior) que lo arrastra hacia atrás (`DetailScreen.tsx`). |
| `navGestures.grabFrom` | 0.5 | La franja solo agarra un detalle que está al menos a medio entrar. |
| `navGestures.stayOpen` / `velocityProjection` | 0.6 · 0.25 | Al soltar, el progreso se proyecta con la velocidad (`progreso − vx[pt/ms] · 0.25`): por debajo de 0.6 el detalle se va, si no vuelve a su sitio (`push.ts › edgeRelease`). |
| `navSprings.flight` | FIRM | Personas › Barrio: el retrato y el nombre viajan de la fila a la cabecera de la ficha y de vuelta (`components/shell/flight.tsx`, `personas/Barrio.tsx`, `personas/PersonaScreen.tsx`). |
| `navTimings.cardBlock` / `navValues.cardBlockRise` | 180 (fast) · enter · 8 pt | El resto de la ficha entra escalonado en cuatro bloques (`navLayout.cardBlock`, en `PersonaScreen.tsx`). |
| `navValues.cardBlockDelayMs` / `cardBlockStepMs` | 120 · 30 ms | Retraso del primer bloque y de cada siguiente. |
| `entrada.leafHalf` / `leafOpen` / `leafStepMs` | 0.5 · 0.125 · 80 ms | Entrada: la hoja de la puerta se pliega sobre su bisagra en dos saltos (`entrada/useEntrada.ts`, `entrada/PixelDoor.tsx`). |
| `entrada.zoom2Ms` / `zoom2` · `zoom3Ms` / `zoom3` | 160 ms · 2× · 310 ms · 3× | La imagen del login salta a 2× y a 3× sobre la puerta, con píxeles nítidos (Skia, vecino más cercano). |
| `navTimings.entradaCut` | 0 | La puerta y el zoom saltan, nunca se interpolan. |
| `entrada.formOutMs` / `formDrop` · `navTimings.entradaFormOut` | 160 ms · 16 pt · 180 (fast) · exit | El formulario baja y se va con el lema (`app/login.tsx`). |
| `entrada.fadeMs` · `navTimings.entradaFade` | 460 ms · 260 (base) · enter | El login se funde con la Oficina viva, que ya está montada debajo. Con movimiento reducido es lo único que pasa (`crossfade()`). |
