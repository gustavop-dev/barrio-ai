# Catálogo de funcionalidades de 0ff1ce

Este catálogo dice qué hace 0ff1ce, función por función, y cómo se comprueba que funciona. Es la fuente única contra la que prueba el agente de QA: «funciona» deja de depender de lo que Gustavo se acuerde de probar.

Cada función se escribió leyendo el código (`agentes-linkedin/infra/`, `oficina/`, `movil/` y `compartido/`) y sus documentos. Cuando el código y la documentación no coinciden, la ficha describe lo que hace **el código** y deja la diferencia anotada en «Brechas código/docs».

**Verificado contra:** `main` en el commit `486a23d` (7 de noviembre de 2026).

## Áreas

| Archivo | Prefijo | Qué cubre |
| --- | --- | --- |
| [acceso.md](acceso.md) | `ACC` | Login de la PWA y de la app, sesión, cierre de sesión y dispositivos |
| [oficina.md](oficina.md) | `OFI` | La escena pixel art, sus paneles y la tarjeta de Tu turno en la Oficina |
| [tu-turno.md](tu-turno.md) | `TUR` | Tarjetas que solo Gustavo puede resolver, preguntas y «Lo que el equipo sabe de ti» |
| [notificaciones.md](notificaciones.md) | `NOT` | La bandeja de Notificaciones dentro de la PWA y de la app |
| [captura.md](captura.md) | `CAP` | El botón de captura: nota, voz, fotos, contexto, «Lo que enviaste» y «Deshacer» |
| [galeria.md](galeria.md) | `GAL` | Fotos, notas y permiso de edición para posts; categoría Perfil privada para foto y banner |
| [calendario-piezas.md](calendario-piezas.md) | `CAL` | Calendario (Mes, Semana, Lista), panel del día y detalle de una pieza con su veto |
| [resultados.md](resultados.md) | `RES` | Indicadores, gráficos y tabla de posts |
| [personas-oportunidades.md](personas-oportunidades.md) | `PRS` | El barrio, la ficha de una persona, las oportunidades y los referentes |
| [ajustes.md](ajustes.md) | `AJU` | Máquina, autonomía, gasto, LinkedIn, notificaciones, orientación y sesión |
| [motor-editorial.md](motor-editorial.md) | `EDI` | El circuito que prepara, verifica y publica la pieza diaria |
| [observatorio-referentes.md](observatorio-referentes.md) | `OBS` | Evidencia compartida OBS-03 disponible; investigación mensual y experimentos en siguientes fases |
| [red.md](red.md) | `BAR` | Descubrir, clasificar, seguir, invitar y aceptar personas del barrio |
| [comentarios-y-lider.md](comentarios-y-lider.md) | `COM` | Comentarios en posts de referentes y el agente líder que aprueba o descarta |
| [inbox.md](inbox.md) | `INB` | Lectura del inbox de LinkedIn y conversaciones que le tocan a Gustavo |
| [resumen-semanal.md](resumen-semanal.md) | `SEM` | El resumen de la semana del analista y su orientación propuesta |
| [notificaciones-push.md](notificaciones-push.md) | `PUS` | Web Push de la PWA, push nativa de la app y sus interruptores |
| [app-movil-instalacion.md](app-movil-instalacion.md) | `APP` | Compilar e instalar la app, a qué servidor apunta, sus permisos y sus actualizaciones OTA |
| [imagenes-en-publicaciones.md](imagenes-en-publicaciones.md) | `IMG`, `IMG-INF` | La imagen de cada post: foto de la Galería, infografía o carrusel, hasta LinkedIn (no implementado) |
| [observatorio-referentes.md](observatorio-referentes.md) | `OBS` | Cinco main protegidos, diez plazas variables, altas/bajas/swaps con ventana días 1–5 y experimentos con evidencia |
| [comunidad-lectores.md](comunidad-lectores.md) | `LEC` | Estudio de la comunidad, sus límites de privacidad y su uso por los cinco lectores |
| [estrategia-perfil.md](estrategia-perfil.md) | `EST` | Propuestas semestrales/mensuales y desde captura: assets de Perfil, previews, Markdown fundamentado y checklist manual |
| [biblioteca-equipos.md](biblioteca-equipos.md) | `BIB` | Unidades curadas para Observatorio, red, inbox, líder y resumen semanal; política de invitaciones y evaluaciones. Capturas no necesita biblioteca |
| [arquitectura-agentes.md](arquitectura-agentes.md) | `ARQ` | Registro único ejecutable, orquestadores, especialistas como herramientas, bucles, ledgers, límites, Mermaid y Mapa del equipo |

Los prefijos no coinciden con los códigos del [catálogo de acciones de LinkedIn](../../agentes-linkedin/infra/docs/catalogo-acciones-linkedin.md) (`ADM`, `APRE`, `CHAT`, `CONT`, `DESC`, `INT`, `LI`, `PERF`, `RED`). Por eso la red usa `BAR` (barrio) y Personas usa `PRS`. Cuando una ficha cita `CONT-09` o `RED-02`, habla de una capacidad de LinkedIn, no de otra ficha de este catálogo.

## Imágenes en las publicaciones

Gustavo quiere que cada post salga con al menos una imagen. El equipo decide por contexto entre una foto de la Galería, una infografía y un carrusel. La opción de edición de Gustavo decide si puede editarse una foto y su nota indica cómo ([IMG-07](imagenes-en-publicaciones.md#img-07), [IMG-16](imagenes-en-publicaciones.md#img-16)); las ediciones permitidas se muestran para veto según IMG-08. Las infografías y los carruseles los dibuja código con su manual «Infografías hechas con IA · reglas», nunca un modelo de imagen. El flujo completo está en [imagenes-en-publicaciones.md](imagenes-en-publicaciones.md) (`IMG-01` a `IMG-16` e `IMG-INF-01` a `IMG-INF-08`), en estado `no implementado` en este catálogo. Su implementación está en curso en `feat/imagenes-backend`; este trabajo no la verifica ni la duplica.

Captura, Galería, Calendario, Ajustes y el motor editorial enlazan a las fichas `IMG` que les tocan.

## Ampliación de equipos de Gustavo

El diseño inicial sobre `1ba4e43` (8 de noviembre de 2026, sin red) reservó OBS, LEC, EST, BIB, EDI-21, OFI-10, GAL-08, BAR-14, COM-11, TUR-20/21 y la ampliación de TUR-18. Las fichas individuales reflejan ahora las entregas del [plan de equipos](../plan-equipos.md). La fase 4 marca **funciona** a [OBS-03](observatorio-referentes.md#obs-03) y [BAR-14](red.md#bar-14): evidencia compartida tipada, procedencias, cobertura y atribución observacional; CI/QA pendientes de Claude. La fase 5 marca **funciona** a OBS-01/02/04, TUR-20/21 y COM-11: revisión mensual, main protegidos, pares, ventana Bogotá, experimentos y señales para Relaciones. CI/QA por Claude; las capacidades posteriores conservan su estado planificado.

Los addenda incorporan [listas curadas y política de red](biblioteca-equipos.md#unidades-por-rol) y la [arquitectura declarativa](arquitectura-agentes.md), también **no implementado**. BIB-06 se retira por decisión de Gustavo, con su ID reservado. Primero se migrará el pipeline real al registro; después se conectarán las capacidades nuevas. Los especialistas proponen y sus orquestadores deciden dentro de las compuertas existentes.

El tercer addendum incorpora la [marca ya entregada](estrategia-perfil.md#marca), el banner con recorte propio (excepción a «sin fotos»), fotos solo de la categoría Perfil, edición/revisión obligatorias y entregables exactos con citas por recomendación. EST-05 añade la petición desde captura. El punto de partida de Observatorio es de cinco referentes, confirmado por Gustavo: no exige bajas antes de activar la revisión mensual.

El cuarto fija dos opciones obligatorias de retrato —A grises, B color— para elección de Gustavo, y banner con figura de cintura arriba y micrófono como estilo, sin afirmar charlas no confirmadas. [EST/GAL-08](estrategia-perfil.md#referencias-privadas) asignan 01 a pose, 02 a cuerpo y 03 a identidad, con carga privada futura por Claude. Ninguna referencia se incorpora al repo público; Diandra solo se describe en palabras. Fotos/derivados de Perfil quedan excluidos de posts y sus notas son instrucciones de Perfil.

El quinto hace vinculantes: sonrisa de 01 y transitions claras de 03 en A/B/banner; cinco main protegidos; cierre autorizado de propuestas variables sin respuesta al terminar el día 5 America/Bogota, recordatorios 1/4; [ritmo diario y rampa/configuración BAR-15](red.md#bar-15); reparto literal del curso BIB-08; estudio mensual público de hasta 50 personas/90 días; todo texto público en inglés; fallback de datos sin inventar identidades y prueba social verificable. Caps [ARQ-05](arquitectura-agentes.md#arq-05): pieza 2 USD, referentes 5 USD/mes, Perfil 10 USD/ciclo; parar y avisar al agotarse (desde el 10/11/2026: presupuesto general, ver `knowledge/presupuesto.py`; la pieza tiene 8 USD por ciclo y sin tope diario propio). El quinto reemplaza las reglas anteriores que exigían aprobación positiva de todo cambio de referente o dejaban reparto/presupuesto abiertos.

El sexto confirma [cuenta gratuita y notas excepcionales BAR-16](red.md#bar-16), tier configurable y ninguna automatización de outreach paralela. Reserva solo a Gustavo mover/reemplazar/desproteger main, con `protected` y auditoría en [OBS-02](observatorio-referentes.md#obs-02), desde Personas › Referentes o Tu turno. Perfil propone la frase inglesa del banner con curso/posicionamiento; la frase de prueba es solo fallback. [EST-01](estrategia-perfil.md#est-01) consulta memoria/lecturas antes de preguntar y crea una pregunta por hecho imprescindible faltante, sin inventar. No quedan decisiones de producto abiertas.

El [plan de equipos](../plan-equipos.md) ordena las fases y decisiones pendientes. La fase de acceso web ya prevista (`web_search`, `web_fetch` para el equipo y enlaces en capturas) es dependencia previa, no otra implementación de este catálogo. [EDI-21](motor-editorial.md#edi-21) formaliza el agente visual sobre IMG. Revisión conserva su función y Relaciones sus flujos; [COM-11](comentarios-y-lider.md#com-11) y [BAR-14](red.md#bar-14) precisan el uso de información de referentes. Los límites reales de seguidores, comentaristas y reactores están en la [matriz de conectores](observatorio-referentes.md#datos-conectores).

Estas fichas de diseño añaden a la plantilla **Responsable**, **Cadencia**, **Tu turno** (qué decide Gustavo, o ninguna aprobación adicional) y **Datos necesarios y disponibilidad**. Un campo de «Código» identifica referencias existentes y lo que falta; no acredita que la ampliación esté implementada.

## Cómo leer una ficha

```markdown
### CAP-04 · Enviar una captura con nota de voz <a id="cap-04"></a>

- **Dónde:** PWA · app · backend
- **Estado:** con fallo conocido
- **Qué hace para Gustavo:** una o dos frases desde su punto de vista.
- **Código:** los archivos y funciones que la implementan.
- **El fallo:** solo en `con fallo conocido` (o «Lo que falta» en algunas `parcial`): qué falla, dónde y por qué.
- **Criterios de aceptación:**
  1. **Dado** … **cuando** … **entonces** …
- **Brechas código/docs:** lo que difiere entre el código y la documentación, o «—».
- **Cobertura QA:** pendiente
```

### Identificador

`<PREFIJO>-<NN>`, por ejemplo `CAP-04`. Un grupo dentro de un área puede llevar un subprefijo, como `IMG-INF-01` para las infografías dentro de `IMG`. Es estable:
- nunca se reutiliza ni se renumera;
- una función nueva toma el siguiente número libre de su área;
- si una función se parte en dos, la original conserva su número y la nueva toma uno libre;
- si una función desaparece, su ficha se mueve a la sección «Retiradas» del final de su archivo, con la fecha y el motivo, y su número queda reservado.

El ancla HTML (`<a id="cap-04"></a>`) permite enlazar una ficha desde un informe de QA o desde un PR.

### Dónde

`PWA` es `oficina/`, la oficina web instalable. `app` es `movil/`, la app nativa de Expo. `backend` es Django en `agentes-linkedin/infra/`: la API, el autopiloto y los workers. Una función de interfaz que existe en una sola de las dos lo dice en su ficha.

### Estado

| Estado | Significa |
| --- | --- |
| `funciona` | El código hace lo que dicen los criterios en todas las plataformas de «Dónde». Nada en el código contradice un criterio. |
| `parcial` | Una parte de los criterios está implementada y otra no, o funciona en una plataforma y no en la otra. La ficha dice qué falta. |
| `no implementado` | No hay código que lo haga. Los criterios describen lo que se espera cuando exista. |
| `con fallo conocido` | El código existe, pero hay un fallo comprobado o reportado. La ficha describe el fallo y los criterios describen el comportamiento correcto. |

El estado se decide leyendo el código, nunca por memoria ni por lo que diga un documento. `funciona` significa «el código lo implementa»: la prueba de que se comporta así en producción es la cobertura de QA. Un estado solo cambia con evidencia: un commit que lo implementa o lo arregla, o un informe de QA que demuestra un fallo.

Algunas funciones dependen de una configuración que hoy está apagada (por ejemplo `INBOX_ENABLED=false` o `LIVE_LINKEDIN_OFFICIAL=false`). Su estado describe el código; la ficha anota de qué interruptor depende para que QA prepare el entorno.

### Criterios de aceptación

Cada criterio es una comprobación que un tester puede ejecutar: **Dado** un estado de partida, **cuando** Gustavo hace algo o pasa algo, **entonces** un resultado observable (un texto en pantalla, una respuesta HTTP, una fila en la base, una push). Cada ficha incluye, cuando aplica:
- el camino feliz;
- el estado vacío;
- el estado de error, con el mensaje que debe ver Gustavo;
- los límites (tamaños, plazos, permisos).

Los textos entre comillas («…») son los que muestra la interfaz o devuelve la API. Si un criterio no se cumple, la función no funciona, aunque el resto sí. Un criterio que hoy no se cumple lo dice al final: «**Hoy falla:** …». Así QA sabe qué prueba debe fallar hasta que llegue el arreglo.

## Cómo lo usa QA

1. **Elegir qué probar.** El agente de QA recorre las fichas en estado `funciona`, `parcial` y `con fallo conocido`. Las `no implementado` solo se prueban cuando un PR dice que las implementa.
2. **Una prueba por criterio.** Cada prueba (automática o guion manual) cita el ID y el número de criterio en su nombre, por ejemplo `CAP-04.2`. Así un fallo apunta a una sola frase de este catálogo.
3. **Rellenar «Cobertura QA».** El agente de QA sustituye `pendiente` por una línea con este formato:

   ```markdown
   - **Cobertura QA:** CAP-04.1–7 en `qa/movil/captura.spec.ts` · 2026-11-10 · pasa
   ```

   Si algún criterio falla: `· falla CAP-04.2 (informe: <enlace>)`. Un criterio sin prueba se nombra aparte: `· sin prueba: CAP-04.5`.
4. **Un fallo nuevo no cambia el catálogo solo.** QA abre el informe con el ID. Quien lo confirme en el código cambia el estado a `con fallo conocido` y describe el fallo en la ficha. Cuando el arreglo se fusiona, vuelve a `funciona` y QA repite la prueba.
5. **Entorno.** Las pruebas nunca llaman a proveedores de pago ni publican en LinkedIn de verdad. Usan el conector simulado (`OPERATOR_ALLOW_FAKE=true`, cuentas `linkedin_fake` y `fake`) y los proveedores parcheados de los tests del backend. En el servidor de producción, QA solo lee o usa el modo ensayo.

## Cómo añadir o cambiar una función

1. Busca el área. Si no encaja en ninguna, propón un archivo nuevo con su prefijo de tres letras y añádelo a la tabla de arriba.
2. Toma el siguiente número libre del área y copia la plantilla.
3. Escribe «Qué hace para Gustavo» como lo diría él, sin nombres de funciones.
4. Escribe los criterios con datos concretos: rutas, textos, códigos HTTP, límites. Incluye el vacío y el error.
5. Pon el estado según el código del commit que lo implementa, y su ruta en «Código».
6. Añade la fila a la tabla de resumen del archivo.
7. Deja «Cobertura QA: pendiente». Solo QA lo rellena.

Un PR que cambia el comportamiento de una función actualiza su ficha en el mismo PR: los criterios, el estado y las brechas.

## Brechas generales entre el código y la documentación

Las brechas de cada función van en su ficha. Estas afectan a varias.

**Fallos que comparten causa:**
- **`expo/fetch` en la app.** Expo SDK 58 sustituye el `fetch` global por `expo/fetch` (`EXPO_PUBLIC_USE_RN_FETCH` no está definido en el repositorio). Eso explica tres fallos a la vez:
  - las subidas con audio o fotos no salen del teléfono (`Unsupported FormDataPart implementation`): [CAP-04](captura.md#cap-04), [CAP-05](captura.md#cap-05), [GAL-02](galeria.md#gal-02), [CAL-11](calendario-piezas.md#cal-11), [PRS-05](personas-oportunidades.md#prs-05), [TUR-10](tu-turno.md#tur-10);
  - los errores de red salían en inglés (`fetch failed: …`): [APP-08](app-movil-instalacion.md#app-08), [ACC-02](acceso.md#acc-02), [CAP-06](captura.md#cap-06). **Arreglado** en el PR #52: el transporte de la app convierte el `FetchError` en un `NetworkError` (un `TypeError`);
  - abrir la app sin conexión, o con el servidor dando un 5xx, cerraba la sesión: [ACC-06](acceso.md#acc-06). **Arreglado** en el PR #52: solo un 401 o `authenticated:false` cierran la sesión al arrancar.

  Las pruebas de Jest de la app sustituyen `fetch` por un simulacro (`movil/src/test/server.ts`), así que ninguna los detecta.
- **El inbox existe, pero varias partes siguen como si no.** La escena mostraba al agente de inbox «en diseño» ([OFI-01](oficina.md#ofi-01), arreglado en el PR #52), `red/summary.stages.conversation` es siempre `null` ([BAR-11](red.md#bar-11)) y la capa Conversaciones del calendario sigue «parcial» sin conversaciones ([CAL-02](calendario-piezas.md#cal-02)).

**Documentos desfasados:**
- **Pantallas que ya no existen.** `CONTRATO-API.md` sigue describiendo `/acciones`, `/red` y `/maquina` como pantallas vivas; la PWA las redirige ([CAL-16](calendario-piezas.md#cal-16)).
- **Diseño original fuera de `main`.** `oficina/PLAN-REDISENO.md` y `oficina/DISENO-VISTAS.md`, que citan `CONTRATO-API.md`, `rediseno-backend.md` y varios docstrings, solo existen en la rama `feat/rediseno-oficina`. `FUNCIONES-NUEVAS.md`, que citan `capturas.py` y `docs/capturas-galeria.md`, no existe en ninguna rama.
- **`movil/README.md`.** Dice que Oficina, Resultados, Personas y la ficha de una persona salen «En construcción», que Skia no está instalado y que no hay proyecto ni builds de EAS, y manda usar un perfil `development` que `eas.json` no tiene. El código ya tiene esas pantallas, Skia, perfiles `preview` y `production` y el `projectId` de EAS. El README tampoco menciona que las push en el APK necesitan `android.googleServicesFile` ([PUS-07](notificaciones-push.md#pus-07)).
- **`oficina/README.md` describe la PWA de antes del rediseño.** Nombra páginas que ya no existen como tales (Máquina, Acciones, Contenido, Referentes, Red, Conocimiento, Memoria), un `scene/simulation.ts` que no está en el código y los botones «Activar ambiente» y «Luz de tarde». Las rutas actuales son Oficina, Tu turno, Notificaciones, Calendario, Resultados, Personas, Galería y Ajustes.
- **La fase de imagen.** `capturas-galeria.md`, `publicacion-diaria.md` y `CONTRATO-API.md` la anuncian, pero ningún código la implementa: ver [imagenes-en-publicaciones.md](imagenes-en-publicaciones.md). El tablero de reglas de infografías solo está en el canvas de Gustavo, no en el repositorio.
- **CI y documentación.** El filtro de rutas de `.github/workflows/barrio-ai.yml` no incluye `docs/`, así que un PR que solo cambia este catálogo no dispara CI.

## No verificado

Todo el catálogo sale de leer el código; no se ejecutó nada. Quedan sin comprobar en un dispositivo o en el servidor:
- que la app falle exactamente con `Unsupported FormDataPart implementation` en el teléfono (deducido del código instalado de `expo@58.0.23`);
- que abrir la app sin conexión cierre la sesión;
- que la push del APK falle por la falta de `googleServicesFile`;
- si el reproductor de audio de la app envía la cabecera `Authorization` en Android;
- el manifiesto final de Android (`CAMERA`, `POST_NOTIFICATIONS`);
- la conexión de LinkedIn desde la app de principio a fin;
- la forma real de los datos de Unipile en el inbox (ids de hilo y de remitente), que `conversaciones-inbox.md` deja «por comprobar».
