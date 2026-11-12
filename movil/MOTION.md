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
| `copiedLabelMs` | 1500 | Lo que dura «Copiado» en el botón Copiar (`components/ui/CopyButton.tsx`, en `pieza/FinalText.tsx`; MovMicro: 1,5 s). |
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
| `captureLock` | éxito | Deslizar hacia arriba bloquea la grabación (MovCaptura: «HÁPTICO · ÉXITO»). |
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
| `switchToggle` | selección | Cambiar un interruptor de fila: Ajustes y la hoja de la foto (`components/ui/SwitchRow.tsx`; MovMicro: «HÁPTICO · SELECCIÓN»). |
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
sobrescribe en `officeMotion`, sin editar la pantalla ni el motor. El plano ocupa todo el ancho de la pantalla
(escala inicial = ancho ÷ 192, sin márgenes ni desplazamiento lateral) y solo se desplaza hacia arriba y abajo. Al
pellizcar, el zoom se ajusta a píxeles físicos enteros, nunca por debajo de esa escala, y el doble toque vuelve
inmediatamente al encuadre inicial, arriba de la oficina, sin escalas intermedias borrosas.
La escena llena la pantalla: la recarga se hace tirando hacia abajo desde arriba del plano.

| Token | Valor | Dónde se usa |
|---|---|---|
| `timings.officeNowIn` / `officeNowOut`, `officeLayout.nowIn/nowOut` | 180 (fast) enter / 120 exit | Entrada y salida del texto de la narración flotante (MovOficina) en `scene/OfficeNarration.tsx`. |
| `officeMotion.walkSpeed` | 40 px lógicos/s | Caminatas del motor compartido (`scene/runtime.ts`). |
| `officeMotion.startGap` / `summaryHold` | 1800 / 2600 ms | Espaciado de eventos y resúmenes. |
| `officeMotion.fadeMs` | 500 ms | Operación sale y vuelve por la puerta. |
| `officeMotion.questionMs` / `bookMs` / `readMs` | 1800 / 2200 / 1600 ms | Consulta de biblioteca. |
| `officeMotion.searchMs` / `librarianBookMs` / `handBookMs` | 1400 / 1200 / 900 ms | Búsqueda y entrega del bibliotecario. |
| `officeMotion.sheetMs` / `handSheetMs` / `conversationMs` / `deliveryMs` | 2200 / 900 / 1800 / 1500 ms | Entrega entre equipos. |
| `officeMotion.outsideMs` / `doneMs` / `returnMs` | 1300 / 2000 / 800 ms | Publicación ejecutada. |
| `officeMotion.lifeTickMs` | 250 ms | Cada cuánto el motor decide quién va a su puesto, quién sale a descansar y quién cambia de juego. |
| `officeMotion.restLeaveMinMs` / `restLeaveMaxMs` | 1200 / 6000 ms | Pausa, distinta para cada uno, antes de que un agente libre deje su puesto. |
| `officeMotion.stayMinMs` / `stayMaxMs` | 16000 / 42000 ms | Tiempo en un mismo juego antes de cambiar. |
| `officeMotion.emoteGapMinMs` / `emoteGapMaxMs` / `emoteMs` / `replyMs` | 3500 / 9000 / 1900 / 900 ms | Emojis de los que descansan; la pareja contesta a los 900 ms. |
| `officeMotion.dutyMs` / `callMs` / `workMs` / `awaitSeatMs` | 15000 / 30000 / 2200 / 16000 ms | Tiempo en el puesto tras terminar o tras ser llamado, el trabajo en el escritorio antes de una entrega y la espera máxima a que el que recibe se siente. |
| `officeMotion.hurryFactor` | 1,6 | Quien va a su puesto desde la sala de juegos camina así de rápido. |
| `officeMotion.lightFadeMs` | 900 ms | Las zonas se iluminan o se apagan en este tiempo. |
| `officeMotion.partyMs` / `partyFirstMs` / `partyGapMinMs` / `partyGapMaxMs` | 30000 / 60000 / 180000 / 420000 ms | Duración de una fiesta, la primera y la separación entre fiestas. |
| `officeMotion.danceStepMs` / `discoMs` / `bulbMs` / `screenFrameMs` | 380 / 420 / 600 / 160 ms | Paso de baile, pista de colores, guirnalda de luces y pantallas de la consola y los arcades. |
| `officeMotion.runFrameMs` / `idleFrameMs` | 110 / 220 ms | Fotogramas del atlas en `scene/sprites.ts`. |
| `officeMotion.lightMs` / `bubbleFrameMs` | 700 / 300 ms | Luces de actividad y bocadillos: el dibujo compartido `compartido/src/scene/art.ts`, grabado en cada frame en `scene/Decorations.tsx`. |
| `officeFrames.stepMs` / `maxDeltaMs` | 16 / 60 ms | Paso fijo y límite de recuperación tras un frame lento. |
| `officeFrames.reportFrames` / `slowFrameMs` | 300 / 1000÷60 ms | Diagnóstico de desarrollo: delta medio/máximo, frames sobre presupuesto y coste medio del motor. |
| `officeGestures.minZoom` / `maxZoom` | 1 / 3 | Límites relativos a la escala inicial. |
| `officeGestures.panDistance` / `tapDistance` | 8 / 10 dp | Activación del desplazamiento y tolerancia de toque. |
| `officeGestures.tapDurationMs` / `doubleTapMs` | 250 / 280 ms | Duración máxima de toque e intervalo de doble toque. |
| `officeGestures.touchTarget` | 48 dp | Área mínima al tocar personajes en el canvas. |
| `officeGestures.pullRefresh`, `rubberBand`, `springs.snapBack` | 64 dp, 0,35, FIRM | Pasado cualquiera de los dos extremos del plano, este cede un 35 % bajo el dedo y vuelve con `snapBack` al soltar. Tirando hacia abajo desde arriba de la escena, además recarga al soltar pasado 64 dp. |
| `officeGestures.flingDeceleration` / `flingBounce` | 0,998 / 0,6 | Al soltar el plano con velocidad sigue deslizándose como un scroll (`withDecay`), frena y rebota en los extremos. Un toque lo detiene sin elegir nada. De lado solo con zoom (`scene/OfficeCanvas.tsx`). |
| `officeGestures.sheetActivation` | 8 dp | Inicio del arrastre del asa de `SnapSheet`. |
| `officeGestures.sheetHalf` / `sheetFull` | 0.5 / 0.88 | Puntos de ajuste de `SnapSheet`, sobre el espacio disponible. |
| `haptics.officePick` | selección | Selección de un personaje, zona o equipo. |

El panel del día del Calendario también es un `SnapSheet` (`calendario/CalendarioScreen.tsx`), con los mismos tokens.

`SnapSheet` reutiliza `springs.sheetOpen`, `timings.sheetClose` y `gestures.sheet` para volver a un
punto de ajuste o cerrar; ofrece ampliar, reducir y cerrar mediante acciones de accesibilidad. No muestra un botón «Cerrar»:
se cierra deslizándolo hacia abajo o con atrás de Android.
Con movimiento reducido se desactiva el callback de frames, cada uno queda en su puesto o en un lugar de
descanso fijo (en orden, con las luces ya puestas) y los nuevos eventos solo se narran. La ausencia de foco, el segundo plano y la pausa de máquina también paran el
callback; los observers de Oficina dejan de consultar al perder foco o pasar a segundo plano.

Para medir en un teléfono: `cd movil && npm start -- --offline`, abrir Oficina en Expo Go con una
sesión de desarrollo y observar `[Oficina/UI]` cada 300 frames. `meanSimulationMs` mide solo el motor;
los deltas incluyen el ritmo de presentación, no aíslan el coste de GPU. Comprobar también pan,
pinch, regreso del fondo y movimiento reducido. El render local de CanvasKit y las pruebas no
constituyen una medición de 60 fps en Android.

## Tu turno y Notificaciones (MovTuTurno, MovNotificaciones)

Los tableros de la fase 2 en `diseno-movimiento/tableros/`. Los valores viven en el bloque «Tu turno and Notificaciones» al final de `motion.ts`.

**Tu turno** (`turno/exits.ts` lleva los pasos). Una tarjeta solo sale cuando el backend confirma. Desde el POST hasta el final, la lista conserva las filas que mostraba y reproduce sobre ellas:

1. la salida de la tarjeta, según cómo se resolvió;
2. el colapso;
3. los contadores.

Con movimiento reducido, cada paso es inmediato.

| Token | Valor | Dónde se usa |
|---|---|---|
| `turnoTimings.check` / `turnoMotion.checkFrom` | 180 (fast) · enter, desde 0.6 | El botón que resolvió la tarjeta pasa a 0ff1ce-hondo con un ✓ que crece. La tarjeta se vuelve 0ff1ce-claro (`turno/DoneButton.tsx`, `turno/TurnoCard.tsx`, `turno/QuestionForm.tsx`). |
| `turnoMotion.doneHoldMs` | 220 ms | Lo que la tarjeta resuelta enseña el ✓ antes de colapsar. Si se deslizó a la derecha, el ✓ es el del fondo que dejó al salir. |
| `turnoTimings.laterSlide` / `turnoMotion.laterShift` | 260 (base) · exit, 40 · 6 pt | «Más tarde» con su botón: la tarjeta se desliza a la derecha y abajo, hacia «Pospuestas», mientras se desvanece (`turno/ExitRow.tsx`). |
| `turnoTimings.collapse`, `turnoLayout.collapse` / `collapseSpace` / `listMove` | 260 (base) · exit | La tarjeta colapsa: su altura se cierra y se desvanece. La lista cierra el hueco al mismo ritmo (`itemLayoutAnimation` en `turno/TuTurnoScreen.tsx`). Igual si se resolvió con botón o deslizando. |
| `turnoTimings.rollOut` / `rollIn`, `turnoMotion.rollDistance` | 90 · exit, luego 90 · enter, 8 pt | Un contador cambia girando: el número viejo sube y se va, y el nuevo entra desde abajo (`turno/RollingNumber.tsx`). Los usan el contador de cada grupo, «Pospuestas · N» y el de la barra superior. |
| `turnoSprings.badge` / `turnoMotion.badgePop` | SOFT, desde 1.25 | El contador de Tu turno en la barra superior salta y vuelve cuando cambia (`components/shell/TopBar.tsx`). Baja cuando la tarjeta ya salió, no cuando el backend la quita (`turno/heldCount.ts`). |
| `turnoMotion.labelDelayMs` | 260 ms (base) | La etiqueta de un grupo que se queda en 0 colapsa este tiempo después de que su última tarjeta deja de contar. |
| `turnoMotion.emptyDelayMs` / `emptyRise`, `turnoTimings.emptyIn` | 340 ms, 8 pt, 260 (base) · enter | «Nada depende de ti hoy» aparece tras la última tarjeta, cuando el hueco ya se cerró. El bibliotecario sube 8 pt mientras aparece. |
| `turnoMotion.postponedFlashMs` (`postponedFlashTiming()`) | 420 ms · lineal | La fila «Pospuestas» se ilumina en 0ff1ce-claro, subiendo y bajando como un seno, cuando recibe una tarjeta (`turno/PostponedFold.tsx`). |
| `haptics.turnoLater` | impacto ligero | «Más tarde» manda la tarjeta a «Pospuestas», con el botón o deslizando (LEVE). Resolver con el botón sigue usando `actionSuccess` (ÉXITO). |

**Notificaciones**

Una notificación nueva puede llegar de dos formas:

- el refresco de GET /tu-turno trae un `notifications_unread` mayor;
- llega una push con la app abierta, y entonces la barra superior refresca Notificaciones y Tu turno (`notificaciones/arrival.ts`).

| Token | Valor | Dónde se usa |
|---|---|---|
| `notifTimings.arrive`, `notifLayout.arrive` / `arriveContent` / `listMove`, `notifMotion.arriveDrop` | 260 (base) · enter, 8 pt | La notificación nueva abre su espacio arriba y cae 8 pt hasta su sitio. El resto de la lista baja al mismo ritmo: cada celda lleva una animación de layout (`notificaciones/NotificacionesScreen.tsx`). |
| `notifMotion.bellSway` / `bellSwayMs` / `bellPivot`, `notifTimings.bellStep` | 12°, −9°, 6°, −3°, 0° en 600 ms; cada paso 120 · enter, pivote arriba al centro | La campana se balancea al llegar una notificación (`components/shell/TopBar.tsx`). Con movimiento reducido no se mueve. |
| `notifSprings.dotIn` / `dotOut` | SOFT / FIRM | El punto de la campana salta desde 0 cuando llega una (`dot`) y se cierra cuando todo está leído. |
| `notifMotion.readStaggerMs` / `readChipTo`, `notifTimings.readOff` | 30 ms por fila, 0.7, 180 (fast) · exit | «Marcar todo como leído» apaga «Nueva» y el resaltado de cada fila en cascada, de arriba abajo. La etiqueta encoge a 0.7 mientras se desvanece. |
| `haptics.notificationArrive` | impacto ligero | Llega una notificación con la app abierta (LEVE). Vibra una sola vez aunque haya una barra superior por pestaña. |

### MovOficina · selección, captura y narración

Fuente: [`MovOficina.dc.html`](diseno-movimiento/tableros/MovOficina.dc.html), script completo,
`person`, `brackets`, `receiveCapture` y `caption` (el `ambient` del tablero lo reemplaza la sala de juegos). `officeMotion` entrega los valores al
intérprete compartido; `compartido/src/scene/motion.ts` conserva los mismos valores por defecto para
la PWA. No se reproduce el ciclo editorial de demostración: las tareas siguen viniendo de eventos
reales y la captura se confirma mediante el éxito de la mutación existente `createCaptura`.

| Token | Valor | Dónde se usa |
|---|---|---|
| `officeMotion.hopPx` / `hopSettlePx` | 2 / 1 px lógicos | `sceneHop` y el atlas de Skia: solo sube el personaje seleccionado, no su silla, su posición ni su área de toque. |
| `officeMotion.hopStepMs` / `hopEndMs` | 90 / 180 ms | Salto escalonado: 2 px hasta 90 ms, 1 px hasta 180 ms, luego 0. Seleccionar otra vez el mismo personaje no reinicia el salto, como en el tablero. |
| `officeMotion.bracketPx` / `bracketMs` | 7 px / 120 ms | Los cuatro corchetes crecen linealmente desde 1 px, redondeados a píxeles enteros. Skia selecciona entre siete dibujos precalculados. |
| `officeMotion.mailX` / `mailStartY` / `mailLandingY` | 98 / −6 / 68 px lógicos | Posición y caída del sobre delante de Operación. |
| `officeMotion.mailAcceleration` / `mailStepMs` | 0,9 px por paso / 16 ms | Aceleración discreta del tablero, incluido el primer paso inmediato; el sobre permanece en el suelo hasta que Operación esté libre. |
| `officeMotion.captureFreePollMs` | 300 ms | Espera de Operación ocupada, sin sustituir una publicación u otra ruta en curso. |
| `officeMotion.captureQuestionMs` | 700 ms | Bocadillo de pregunta y espera al recoger el sobre. |
| `officeMotion.captureSheetMs` / `capturePickupMs` | 1600 / 500 ms | Bocadillo de hoja al recoger y espera antes de caminar hacia Mesa editorial. |
| `officeMotion.captureHandoffMs` | 1800 ms | Hoja de Operación y charla del Director al llegar; espera `deliveryMs` (1500 ms) y regreso a casa a `walkSpeed` (40 px/s). |
| `officeNarration.enterDelayMs` / `enterY` | 60 ms / 6 dp | La nueva línea entra subiendo con `timings.officeNowIn`: 180 ms, `easings.enter`. |
| `officeNarration.exitY` | −4 dp | La línea anterior sale subiendo con `timings.officeNowOut`: 120 ms, `easings.exit`. |
| `officeNarration.holdMs` | 3500 ms | Desde cada narración, programa la retirada de la caja; una nueva narración cancela el reloj anterior. |
| `officeNarration.retireY` / `timings.officeNowRetire` | −6 dp / 180 ms, `easings.exit` | Salida de la caja; al terminar se retira también su nodo de accesibilidad. |

El ambiente del tablero conserva la primera pausa a 9 s y vuelve a intentarlo cada 11 s: café para
Posicionamiento, Perfil, Investigador, Lector par y Lector divulgador; charla en Relaciones a los
2000 / 2200 ms existentes. Solo participan roles realmente en espera y libres, sin interferir con
los eventos reales ni las entregas de capturas.

Adaptaciones nativas: el salto, los corchetes y el sobre son píxeles lógicos del mapa (la pantalla
los amplía a escala entera); la narración usa dp. El motor conserva pasos fijos de 16 ms y limita
cada delta a 60 ms, como el frame del tablero, guardando el resto para el frame siguiente. Skia y
Reanimated realizan el movimiento en UI; React solo recibe cambios de narración/tarea. La tira,
los paneles, el pan, el pinch y los objetivos de toque de 48 dp conservan su comportamiento.

No hay vibraciones nuevas en el tablero: se conserva `officePick` para seleccionar y el único
`captureSent` existente en la hoja. Oficina escucha el cache de mutaciones sin tocar la hoja,
los requests ni «Deshacer»; deduplica por id de captura y serializa varios envíos. Una captura no
crea eventos ficticios en «Lo último que hizo».

Con `useMotion().reduced`, no hay salto, caída, paseo, bucles ni dibujo progresivo de corchetes;
los corchetes aparecen completos. Las narraciones se sustituyen al instante y **no se retiran**,
igual que el retorno temprano de `caption` en el tablero. Activar movimiento reducido durante una
entrega elimina el sobre y devuelve los personajes a casa; desactivarlo no repite lo ya recibido.
Se mantiene la adaptación de quietud de la app, evitando dejar a un personaje elevado o un sobre
suspendido al congelar el reloj. La velocidad de demostración y «Simular un envío» no se añaden a
la app: el envío real es su disparador.

## Navegación, Entrada y Detalle (MovNavegacion, MovEntrada, MovDetalle)

Grupos propios en `motion.ts`: `navSprings`, `navTimings`, `navValues`, `navGestures` y `entrada`, con `navSpring()`, `navTiming()`, `crossfade()` y `navLayout`. `BEZIER` da los puntos de control de `easings.enter` y `easings.exit` al `Animated` de React Native (las escenas de las pestañas). No hay vibraciones nuevas: el cambio de pestaña usa `tabChange`.

| Token | Valor | Dónde se usa |
|---|---|---|
| `navSprings.pill` | FIRM | La píldora de la barra inferior se desliza a la pestaña tocada (`components/shell/BottomBar.tsx`). Sin pestaña inferior activa (Tu turno, Notificaciones, Calendario, Ajustes) se oculta. |
| `navSprings.tabIcon` / `navValues.tabIconFrom` | SOFT · 0.92 | El icono de la pestaña nueva salta a 0.92 y vuelve a 1 (`BottomBar.tsx`). |
| `navTimings.tabIn` / `navValues.tabRise` | 180 (fast) · enter · 8 pt | El contenido de la pestaña nueva aparece y sube 8 pt; la barra superior queda quieta (`components/shell/tabTransitions.ts`, en `app/(app)/(tabs)/_layout.tsx`). |
| `navTimings.tabOut` | 108 (60 % de fast) · exit | El contenido de la pestaña anterior se desvanece. |
| `navSprings.push` | FIRM | El push: una pantalla de detalle (pieza, persona) entra desde la derecha y vuelve con «‹», el botón atrás de Android o cualquier navegación que la quite (`components/shell/DetailScreen.tsx`, `components/shell/push.ts`). También abre las pantallas de los iconos de arriba (`tabTransitions.ts`). Entre dos de ellas, ir a una anterior en el orden Tu turno, Notificaciones, Calendario, Ajustes es la vuelta: la de arriba sale por la derecha y destapa la otra. Las pestañas se dibujan en ese orden, no la enfocada encima. |
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

## Captura, hojas y microinteracciones (MovCaptura, MovHojas, MovMicro)

Los valores salen del código de los tableros `MovCaptura`, `MovHojas` y `MovMicro`. Los grupos viven al final de `motion.ts`: `sheetMotion`, `captureMotion`, `captureTimeline`, `microMotion`, `microLayout` y `curves`, con los ayudantes `springWith()`, `timingWith()` y `timelineWith()`.

### Hojas (`components/ui/Sheet.tsx`, `SnapSheet.tsx` y, a través de `Sheet`, `ConfirmSheet.tsx`)

La posición de la hoja (`p`) sube y baja con `springs.sheetOpen` (FIRM), también al cerrarse. La hoja deja de estar en cuanto `p` llega a 0, sin esperar a que el resorte se asiente. El fondo oscuro sigue a `p`.

| Token | Valor | Qué hace |
|---|---|---|
| `sheetMotion.snaps` | 0,5 / 0,9 | Puntos de ajuste de `SnapSheet`, sobre el espacio disponible (`SNAPS`). El primero es `officeGestures.sheetHalf`, el que la Oficina deja a su escena. La hoja modal tiene un solo punto: su altura. |
| `sheetMotion.projectionS` | 0,15 s | Al soltar, la hoja se proyecta 150 ms en la dirección del impulso (`p + v · 0,15`) y va al punto de ajuste más cercano a esa proyección. |
| `sheetMotion.closeBelow` | 0,5 | Si la proyección queda bajo la mitad del punto más bajo, se cierra (0,25 de la pantalla con el punto 0,5; la mitad de su altura en la hoja modal). |
| `rubberBand()` / `RUBBER` | 0,35 | Pasado el punto más alto, la hoja conserva el 35 % del arrastre. |
| `sheetMotion.closedGap` | 20 px | Cerrada, la hoja queda 20 px por debajo de su altura, para que ningún borde asome (`SH + 20` de MovCaptura). |
| `sheetMotion.activation` | 8 pt | Recorrido antes de que la manija tome el arrastre, hacia arriba o hacia abajo. Adaptación nativa: así los toques en la cabecera siguen funcionando. `SnapSheet` mantiene `officeGestures.sheetActivation`. |
| `haptics.sheetSnap` | impacto ligero | La hoja se asienta en un punto nuevo, también al abrirse («HÁPTICO · LEVE»). La hoja de captura abierta desde el botón no vibra, porque su apertura es parte de la coreografía de la captura. |

Ya no los usan las hojas: `gestures.sheet.dismissDistance` y `dismissVelocity` (los sustituye la proyección), `timings.backdrop` y `timings.sheetClose` (el fondo y el cierre siguen a FIRM) y `officeGestures.sheetFull` (lo sustituye `sheetMotion.snaps`).

### Botón de captura (`capture/CaptureButton.tsx`, `capture/hold.ts`)

| Token | Valor | Qué hace |
|---|---|---|
| `springs.captureGrow` | SOFT | El botón crece a `captureMotion.holdScale` (1,2) al empezar a grabar, y vuelve desde 0 tras descartar. |
| `springs.captureFollow` | FIRM | El botón vuelve a su sitio y a escala 1 cuando el gesto termina en la hoja. |
| `captureMotion.hintMs` | 8000 | La pista del primer uso («Mantén oprimido para grabar. Toca para foto o nota.») se quita sola a los 8 s, en cada arranque hasta el primer uso: no tapa la Oficina ni la Galería todo el rato. |
| `captureMotion.follow` | 0,6 | El botón sigue el 60 % del dedo, solo hacia arriba y hacia la izquierda. Sigue al dedo directamente, sin resorte. |
| `captureMotion.lockRise` / `lockFollow` | 12 px / 0,35 | El candado sube 12 px al aparecer y acompaña al botón con el 35 % de su subida. |
| `captureMotion.lockRestOpacity` / `lockRestScale` | 0,55 / 0,85 | Opacidad y escala del candado antes de mover el dedo; llegan a 1 en el punto de bloqueo. |
| `captureMotion.shackleDrop` / `shackleMs` | 3 px / 120 ms | Al bloquear, el arco del candado baja 3 px en 120 ms (EASE_OUT). |
| `captureMotion.barRise` / `barCancelFade` | 56 px / 0,6 | La franja con el tiempo sube desde 56 px (fast, EASE_OUT al entrar y EASE_IN al salir) y pierde el 60 % de su opacidad en el punto de descarte. |
| `captureMotion.holdDim` | 0,5 | Al deslizar hacia arriba, la pantalla se oscurece hasta la mitad del fondo de las hojas. |
| `captureMotion.trashShowAt` / `trashRestScale` / `lidOpenDeg` | 0,05 / 0,8 / −28° | La papelera aparece pasado el 5 % del camino a la izquierda, crece desde 0,8 y su tapa se abre hasta −28°. |
| `captureMotion.dropScale` / `trashLingerMs` | 0,2 / 220 ms | Al descartar, el botón cae en la papelera encogiéndose a 0,2 (fast, EASE_IN). La papelera espera `fast + 220` ms, se cierra, el botón vuelve con SOFT y llega el aviso con «Recuperar». |
| `captureMotion.sentPulse` / `pulse` | 1,18 / SOFT | Tras «Guardar», el botón late de 1,18 a 1. |
| `haptics.captureStart` / `captureLock` / `captureDiscard` | medio / éxito / aviso | Empezar a grabar, bloquear y descartar. |

### Hoja de captura (`capture/CaptureSheet.tsx`, `capture/choreo.ts`, `capture/glyphs.tsx`)

| Token | Valor | Qué hace |
|---|---|---|
| `captureMotion.morph` | SOFT | Abierta desde el botón, el botón se convierte en el elemento de audio de la hoja: la bola de grabación, el icono de «Grabar un audio» o el botón de escuchar. |
| `captureMotion.dockWithin` | 0,002 | Adaptación nativa: la bola que vuela cede su lugar al elemento de la hoja cuando está a menos del 0,2 % del final y quieta, o en cuanto la hoja se arrastra o se cierra. |
| `captureMotion.ballBeat` / `ballPausedScale` | 0,08 / 0,96 | La bola late con la voz (1 + 0,08 · nivel). En pausa queda a 0,96, en 0ff1ce claro con un aro de 3 px. |
| `captureMotion.ringBase` / `ringLevel` / `ringOpacity` / `ringFade` | 4 px / 18 px / 0,35 / 0,5 | El aro alrededor de la bola viva: 4 px más 18 px por el nivel, al 35 %, y se aclara a la mitad con la voz. |
| `captureMotion.levelFollow` / `levelRelease` | 0,25 / 0,2 | El nivel sigue al micrófono a esa tasa por fotograma de 60 Hz, y vuelve al silencio a la otra. Se calcula en el hilo de la interfaz. |
| `captureMotion.levelEveryMs` | 90 ms | La onda suma una barra cada 90 ms (`capture/recorder.tsx`). |
| `captureMotion.pausedBlinkMs` / `pausedBlinkOpacity` | 500 ms / 0,35 | En pausa, el tiempo parpadea cada 500 ms hasta el 35 %. |
| `captureMotion.iconTurnDeg` / `pauseFrom` / `playFrom` | 90° / 0,8 / 0,6 | Los iconos de la bola se cruzan girando 90° (fast, EASE_OUT): la pausa crece desde 0,8 y escuchar desde 0,6. |
| `captureMotion.thumbFrom` / `thumbOvershoot` / `thumbPeakAt` | 0,6 / 1,06 / 60 % | Cada foto añadida entra de 0,6 a 1,06 al 60 % del tiempo y se asienta en 1 (`durations.base`, EASE_OUT; un valor compartido en `Thumb` de `CaptureSheet.tsx`, no `entering`: al volver del selector de fotos de Android la animación podía quedarse en su primer fotograma y la foto no se veía). |
| `captureTimeline.discard` | 780 ms | «Descartar» la grabación: los controles se desvanecen (0–0,2), la papelera aparece con un rebote del 10 % (0–0,2) a 116 px bajo la bola, la tapa se abre, la bola vuela en arco (60 px a la derecha, 40 px arriba) y cae encogiéndose a 22 px (0,22–0,55, EASE_IN), «HÁPTICO · AVISO» a 0,55, la tapa se cierra (0,55–0,66), la papelera tiembla ±4 px (0,66–0,82) y se va (0,82–1). |
| `captureTimeline.send` | 1000 ms | «Guardar», cuando el equipo ya tiene la captura: el contenido se desvanece (0–0,16), el audio se encoge al 45 % y entra en el sobre (0–0,36), el sobre aparece (0,02–0,2), las fotos vuelan a él escalonadas 40 ms, la solapa se cierra (0,3–0,42), «HÁPTICO · ÉXITO» a 0,42, la hoja baja a 0,45 y el sobre sale volando arriba a la derecha (0,45–1, EASE_IN), girando −18° y encogiéndose al 60 %. Al final, el botón late y llega el aviso. |
| `curves.enter` / `curves.exit` | EASE_OUT / EASE_IN | Las curvas del diseño como funciones, para colocar piezas a lo largo de una línea de tiempo. |
| `timelineWith()` | lineal | El reloj de esas líneas de tiempo. Corre también con movimiento reducido: como en los tableros, ese modo elige piezas más simples (el sobre se desvanece en vez de volar, la bola se encoge sin rebote, la papelera no tiembla) y las hojas saltan a su sitio. |

Ya no los usa la captura: `timings.recordDot` (la franja muestra el punto quieto, como en el tablero), `timings.recordPulse` (la bola late con la voz), `timings.holdOverlay` y `layout.overlayIn`/`overlayOut` (la franja y el candado tienen sus tiempos), y `gestures.capture.maxLift` (el seguimiento es el 60 % del dedo).

### Microinteracciones (`components/ui/Button.tsx`, `SwitchRow.tsx`, `Chip.tsx`, `CopyButton.tsx`, `Field.tsx`, `Skeleton.tsx`, `Toast.tsx`)

| Token | Valor | Qué hace |
|---|---|---|
| `microMotion.pressDown` / `pressedScale` | 60 · 900 · 1 / 0,97 | Al presionar, el botón cede a 0,97 con un resorte rígido. |
| `microMotion.pressUp` | FIRM | Al soltar, vuelve a 1. |
| `microMotion.switchKnob` / `switchColorAt` | FIRM / 0,5 | La perilla del interruptor se desliza con FIRM. La pista y el borde de la perilla pasan a 0ff1ce hondo a mitad de un tween fast con EASE_OUT. |
| `microMotion.chipCheckShift` | 6 px | Al elegir un chip, se rellena de tinta al instante y su marca entra desde 6 px a la izquierda (fast; EASE_OUT al entrar, EASE_IN al salir). |
| `haptics.chipToggle` | selección | Elegir o soltar un chip de filtro. |
| `microMotion.copyTurnDeg` / `copyCheckFrom` | 90° / 0,6 | «Copiado»: el icono de copiar gira 90° y se va, y la marca entra girando desde −90° y creciendo desde 0,6 (fast, EASE_OUT). Pasado `copiedLabelMs`, ambos vuelven sin animación. |
| `microMotion.skeletonPeriodMs` / `skeletonLow` / `skeletonLag` / `skeletonStill` | 1200 ms / 0,55 / 0,4 rad / 0,7 | Cada bloque de carga late en opacidad entre el 55 % y el 100 % cada 1,2 s, 0,4 rad detrás del anterior. Con movimiento reducido queda quieto al 70 %. |
| `microMotion.toastRise` | 12 px | El aviso entra subiendo 12 px (fast, EASE_OUT) y sale bajando (fast, EASE_IN), con un valor compartido en `ToastCard` (no con `entering`/`exiting`: en Android una animación de entrada que empezaba mientras se cerraba el Modal de una hoja podía quedarse invisible). Dentro de una hoja abierta, el aviso se dibuja en su ventana (`ToastOutlet`). |

El campo de texto no anima: al enfocarlo, el borde pasa a 2 px 0ff1ce hondo (el relleno devuelve el píxel, así el texto no se mueve) y la etiqueta pasa a 0ff1ce hondo.

Ya no los usan los botones ni el aviso: `timings.press` y `springs.press` en `Button.tsx` (la barra inferior sigue usando `springs.press`), `springs.toast`, `layout.toastIn` y `layout.toastOut`.

## Calendario y Resultados (MovCalendario, MovResultados)

Los dos tableros de la fase 3 que mueven datos. Los valores del tablero que no son de `TOK` (las salidas de 120 ms, los retrasos, las cascadas y los desplazamientos en px) tienen nombre propio en `motion.ts`.

| Token | Valor | Dónde se usa |
|---|---|---|
| `calendarSprings.daySelect` | FIRM (20 · 260 · 1) | Calendario: la selección oscura (`px`, `py`, `pw`, `ph`) se desliza al día tocado y viaja a su celda al cambiar entre Semana y Mes (`calendario/Selection.tsx`). La primera vez, y con movimiento reducido, salta. |
| `calendarSprings.segment` | FIRM (20 · 260 · 1) | La superficie del control segmentado (`seg`) se desliza a la opción elegida: Vista en Calendario y Periodo en Resultados (`components/ui/Segmented.tsx`). |
| `calendarTimings.panelOut` | 120 · exit | Calendario: el panel del día que se va se desvanece y se aparta 12 px hacia el lado contrario (`calendario/DaySwap.tsx`), en línea y en la hoja del día. |
| `calendarTimings.panelIn` | 180 (fast) · enter | El panel nuevo entra desde el lado hacia el que avanzó la fecha. |
| `calendarTimings.viewOut` | 120 · exit | La vista que se va, semana o mes, se desvanece debajo de la nueva (`calendario/ViewSwitch.tsx`). |
| `calendarTimings.viewIn` | 180 (fast) · enter | La semana, o cada fila del mes, aparece (`calendarLayout.weekIn` y `calendarLayout.monthRowIn`, en `calendario/Grids.tsx`). |
| `calendarTimings.height` | 260 (base) · enter | La altura del calendario (`h`) pasa de la semana al mes, o de un mes de 5 filas a uno de 6 (`calendario/Pager.tsx`). |
| `calendarChoreography.panelShift` / `panelRise` | 12 / 8 px | Lo que se desliza el panel: 12 px de lado (al salir y al entrar) y 8 px de abajo arriba al entrar. |
| `calendarChoreography.panelInDelayMs` | 60 ms | Lo que espera el panel nuevo antes de entrar. |
| `calendarChoreography.monthRowDelayMs` / `monthRowStaggerMs` | 60 / 30 ms | La primera fila del mes espera 60 ms y cada fila siguiente 30 ms más. |
| `calendarChoreography.monthRowDrop` | 6 px | Cada fila del mes baja desde 6 px más arriba. |
| `calendarChoreography.weekInDelayMs` | 80 ms | La semana espera 80 ms antes de aparecer al volver del Mes. |
| `calendarChoreography.pillTallAt` | 56 pt | Por encima de esta altura la selección tiene el radio de un día de la semana (`radius.md`); por debajo, el de una celda del mes (`radius.sm`). |
| `resultsTimings.countFirst` | 600 · enter | Resultados: la primera vez, cada cifra cuenta desde 0 (`resultados/CountUp.tsx`): las cifras de los KPI y las de los embudos. |
| `resultsTimings.count` | 400 (slow) · enter | Al cambiar de periodo (o de modalidad, o al refrescar), cuenta del valor que se ve al nuevo. |
| `resultsTimings.bar` | 260 (base) · enter | Cada barra de los embudos y de «Interacción media por pilar» crece hasta su largo. |
| `resultsChoreography.barFirstDelayMs` / `barStaggerMs` | 120 / 40 ms | Las barras crecen en cascada: 40 ms más por barra, y 120 ms de espera la primera vez. |

Sin vibraciones nuevas: los tableros no marcan ninguna. Cambiar de vista o de periodo sigue usando `tabChange` (la del control segmentado) y deslizar la semana o el mes, `pageChange`.

Con movimiento reducido (`useMotion()` y `reduceMotion` en cada configuración) la selección salta a su día, el panel y la vista cambian sin transición, la altura cambia de golpe, las cifras aparecen con su valor final y las barras con su largo.

«Sin dato» nunca cuenta: se queda en «—», ni sale de 0 ni llega a 0. La cuenta corre en el hilo de la interfaz (un `TextInput` de solo lectura que Reanimated reescribe), y el último fotograma muestra la cifra tal como la escribe `formatKpiValue`; el lector de pantalla solo oye esa cifra final.
