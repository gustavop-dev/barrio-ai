# Entrega fase 5: referentes mensuales y experimentos

Implementación en `feat/fase5-referentes`, sobre fases 3b/4. Solo se editaron archivos: sin red, instalaciones, suites, typecheck, builds, commit ni push. Se regeneró `docs/arquitectura/grafo.md` con el generador de documentación de stdlib. Esto no equivale a ejecutar CI ni validar el comportamiento desplegado.

## Comportamiento

- La revisión se prepara el último día del mes y se publica el día 1. El plazo es exclusivo a las 00:00 del día 6 en **America/Bogota**, independiente de la zona configurada para el operador. Avisos persistidos/deduplicados el día 1, recordatorio el día 4 desde las 09:00 y resumen al cerrar. El push espera la ventana del operador; el aviso y el lote se guardan en la misma transacción.
- `ReferentControl` serializa la lista, el lote y las decisiones. Los cinco main quedan protegidos; el resto tiene hasta diez plazas, con máximo quince activos. Alta, baja y pareja son decisiones distintas; un swap se aplica en una transacción. Rechazo, edición guardada, ajuste o aplazamiento impiden la aplicación por silencio. Lotes tardíos, avisos ausentes, protección/lista modificada y capacidad incompatible quedan para decisión explícita. Historial y auditoría sobreviven a bajas y reemplazos.
- Solo la identidad configurada de Gustavo, mediante sesión CSRF o token humano de dispositivo, puede modificar protegidos. Un superusuario diferente o una credencial técnica no equivale a Gustavo. Personas muestra protección, posición, reemplazo, efecto antes/después e historial; Tu turno enlaza esa gestión. Ninguna operación de lista hace unfollow ni escribe en LinkedIn.
- `referentes_mensuales` usa tres ramas web paralelas de fase 1, contexto privado solo en la selección local al modelo, curso curado de fase 2 y evidencia de fase 4. El dispatcher valida las aristas, contratos, checkpoints, reservas y cap de **5 USD por mes natural**, compartido entre cuentas y reintentos. No hay replay de llamadas inciertas. Una investigación sin fuentes o curso queda incompleta, sin propuestas inventadas.
- Experimentos con aprobación positiva: **14 días de base, 28 de foco y 7 de seguimiento**, uno aprobado por cuenta a la vez. Umbrales y criterio se congelan al aprobar. Hasta **dos comentarios útiles por semana** para el referente del foco, incluyendo comentarios ordinarios y reservas inciertas; las guardas y BAR-15 siguen prevaleciendo. El comentario retiene ID y versión del experimento usado al redactar, aunque se detenga durante la llamada al modelo. Se revalida antes de ejecutar y antes de escribir.
- Los resultados comparan personas únicas con nueva interacción propia y encaje suficiente, tasas por semana, cobertura y exposición confirmada. Conservan la referencia a cortes, control comparable si fue propuesto, otras acciones y limitaciones. Una muestra/base/exposición insuficiente termina «inconcluso». No cambia referentes ni orientación por el resultado. El siguiente dossier consume los resultados disponibles.
- App/PWA comparten contratos, consultas, edición y lógica de plazo; los componentes nativos solo usan JS/TS y dependencias existentes. Historial y resultados quedan en Personas › Referentes después de resolver las tarjetas.

## Migración y configuración

**Nueva: `0024_referentes_monthly.py`, depende de `0023_shared_evidence`. Claude debe reconciliar el número con la fase paralela antes de fusionar.** No se editaron migraciones anteriores. Añade protección/posición/revisión, control por cuenta, lote, cambios, avisos, experimento y vínculo/versionado del foco en `ActionProposal`.

La migración registra exactamente los cinco referentes actuales **no archivados**, sin descartar antes los inactivos ni elegir por orden/popularidad. Los protege y audita con actor de migración. Si no hay exactamente cinco, conserva la lista y bloquea la gestión automática. Omite conectores oficiales dedicados a publicación. No borra evidencia, ledger ni presupuesto.

Configurar **`REFERENTS_GUSTAVO_USERNAME`** con el username Django real de Gustavo (default `gustavo`). QA usa explícitamente `qa` solo en `settings_qa`. Verificar identidad e IDs existentes en la instalación; no asignar esa identidad al usuario técnico del autopiloto. Si hubo conflicto factual en la migración, la recuperación exige a Gustavo: `POST /api/v1/referentes/main-inicial` con `{account, ids: [cinco UUIDs comprobados]}`. No se eligen automáticamente.

Los presupuestos de proveedores y los topes web de fase 1 pueden detener una revisión antes de 5 USD; no se aumentaron. Selección y ramas usan `WEB_RESEARCH_MODEL`. El único ajuste de 3b fuera de los puntos de integración calcula el bucket mensual en el momento de reservar, para llamadas que cruzan medianoche del último día; no mueve ni reinicia reservas anteriores. Revisar ese cambio con la CI final de 3b.

## Verificaciones que debe ejecutar Claude

1. Reconciliar migraciones y ejecutar checks de Django/migraciones y suites backend, con PostgreSQL temporal y proveedores/conectores falsos. Incluir `test_referentes_mensuales`, `test_grafo`, `test_orquestacion`, `test_evidencia`, `test_operador`, `test_autopiloto`, `test_evaluaciones`, `test_rediseno`, `test_seed_qa` y regresiones de fase 4. No se ejecutaron aquí.
2. Comprobar migración con cinco, con inactivos, con lista distinta y con conector oficial; permisos de sesión/dispositivo/servicio y usuario técnico; auditoría, restauración y reemplazo. Verificar límite de 10 variables/15 activos por todas las rutas CRUD.
3. Con reloj falso: último día, día 1, día 4 antes/después de las 09:00, día 5 23:59 y día 6 00:00 Bogotá; reintento, fallo del aviso, lote tardío, lista/protección cambiada, rechazo concurrente con cierre y atomicidad del swap. Verificar que no se etiqueta la aplicación por plazo como aprobación humana.
4. Verificar fan-out real con fakes y tres conexiones DB, gather antes de liberar lease, un intento por rama, fuentes/insignia verificadas, biblioteca ausente, cap y reservas compartidas, y cambio de bucket en medianoche Bogotá. Confirmar grafo empaquetado y `python3 scripts/grafo/mermaid.py --check` en CI.
5. Experimentos: aprobación futura/versionada, un foco simultáneo, revisión con nueva aprobación, parada durante un borrador/preflight, etiqueta de versión antigua rechazada, 14/28/7, dos comentarios semanales dentro de BAR-15, resultados con cobertura insuficiente y con encaje suficiente, sin causalidad ni cambio automático de lista. Revisar cortes semanales y resultado final de extremo a extremo.
6. Ejecutar Jest/Vitest, lint/typecheck y los builds en CI. Revisar tarjeta de pareja, cuenta atrás, edición/guardar/aplicar, conflicto 409 sin falso éxito, «Más tarde», ausencia de controles para otra identidad, badge main y gestión auditada; asegurar que aprobar experimento conserva la tarjeta activa con «Detener». Validar UI estrecha, enlaces y retorno desde Personas.
7. Sesión QA: **`[qa: 03 04 09-personas 13-referentes 17-mapa-equipo 19-referentes-mensual]`**. El runner usa `seed_qa --referentes-mensual` únicamente para el flujo 19, conservando el escenario de los demás flujos. La fecha del lote sembrado es canónica: fuera de días 1–5 se verá «Plazo terminado»; backend/Jest prueban la ventana activa con reloj falso. La base experimental sembrada empieza en el futuro en cualquier fecha de CI. Confirmar que el seed no toca proveedores y que todos los cambios móviles siguen siendo OTA.

## Archivos cambiados

Inventario completo respecto de la base del worktree, incluyendo archivos nuevos; sin commit.
<!-- inventory -->

- [agentes-linkedin/equipos/grafo.yaml](../../../agentes-linkedin/equipos/grafo.yaml)
- [agentes-linkedin/infra/docs/referentes-mensuales.md](../../../agentes-linkedin/infra/docs/referentes-mensuales.md)
- [agentes-linkedin/infra/src/linkedin_backend/settings_qa.py](../../../agentes-linkedin/infra/src/linkedin_backend/settings_qa.py)
- [agentes-linkedin/infra/src/team_backend/autopiloto.py](../../../agentes-linkedin/infra/src/team_backend/autopiloto.py)
- [agentes-linkedin/infra/src/team_backend/evaluaciones.py](../../../agentes-linkedin/infra/src/team_backend/evaluaciones.py)
- [agentes-linkedin/infra/src/team_backend/experimentos.py](../../../agentes-linkedin/infra/src/team_backend/experimentos.py)
- [agentes-linkedin/infra/src/team_backend/jobs.py](../../../agentes-linkedin/infra/src/team_backend/jobs.py)
- [agentes-linkedin/infra/src/team_backend/management/commands/seed_qa.py](../../../agentes-linkedin/infra/src/team_backend/management/commands/seed_qa.py)
- [agentes-linkedin/infra/src/team_backend/migrations/0024_referentes_monthly.py](../../../agentes-linkedin/infra/src/team_backend/migrations/0024_referentes_monthly.py)
- [agentes-linkedin/infra/src/team_backend/models.py](../../../agentes-linkedin/infra/src/team_backend/models.py)
- [agentes-linkedin/infra/src/team_backend/notificaciones.py](../../../agentes-linkedin/infra/src/team_backend/notificaciones.py)
- [agentes-linkedin/infra/src/team_backend/oficina_views.py](../../../agentes-linkedin/infra/src/team_backend/oficina_views.py)
- [agentes-linkedin/infra/src/team_backend/operador.py](../../../agentes-linkedin/infra/src/team_backend/operador.py)
- [agentes-linkedin/infra/src/team_backend/operador_views.py](../../../agentes-linkedin/infra/src/team_backend/operador_views.py)
- [agentes-linkedin/infra/src/team_backend/orquestacion.py](../../../agentes-linkedin/infra/src/team_backend/orquestacion.py)
- [agentes-linkedin/infra/src/team_backend/rediseno_views.py](../../../agentes-linkedin/infra/src/team_backend/rediseno_views.py)
- [agentes-linkedin/infra/src/team_backend/referentes.py](../../../agentes-linkedin/infra/src/team_backend/referentes.py)
- [agentes-linkedin/infra/src/team_backend/referentes_research.py](../../../agentes-linkedin/infra/src/team_backend/referentes_research.py)
- [agentes-linkedin/infra/src/team_backend/referentes_views.py](../../../agentes-linkedin/infra/src/team_backend/referentes_views.py)
- [agentes-linkedin/infra/src/team_backend/research.py](../../../agentes-linkedin/infra/src/team_backend/research.py)
- [agentes-linkedin/infra/src/team_backend/seed_referentes_qa.py](../../../agentes-linkedin/infra/src/team_backend/seed_referentes_qa.py)
- [agentes-linkedin/infra/src/team_backend/serializers.py](../../../agentes-linkedin/infra/src/team_backend/serializers.py)
- [agentes-linkedin/infra/src/team_backend/tests/test_orquestacion.py](../../../agentes-linkedin/infra/src/team_backend/tests/test_orquestacion.py)
- [agentes-linkedin/infra/src/team_backend/tests/test_referentes_mensuales.py](../../../agentes-linkedin/infra/src/team_backend/tests/test_referentes_mensuales.py)
- [agentes-linkedin/infra/src/team_backend/urls.py](../../../agentes-linkedin/infra/src/team_backend/urls.py)
- [compartido/src/api/hooks.ts](../../../compartido/src/api/hooks.ts)
- [compartido/src/api/referentes.ts](../../../compartido/src/api/referentes.ts)
- [compartido/src/api/types.ts](../../../compartido/src/api/types.ts)
- [compartido/src/fixtures/referentes.ts](../../../compartido/src/fixtures/referentes.ts)
- [compartido/src/logic/referentes.ts](../../../compartido/src/logic/referentes.ts)
- [compartido/src/logic/turno.ts](../../../compartido/src/logic/turno.ts)
- [docs/arquitectura/anadir-agente.md](../../../docs/arquitectura/anadir-agente.md)
- [docs/arquitectura/grafo.md](../../../docs/arquitectura/grafo.md)
- [docs/funcionalidades/README.md](../../../docs/funcionalidades/README.md)
- [docs/funcionalidades/comentarios-y-lider.md](../../../docs/funcionalidades/comentarios-y-lider.md)
- [docs/funcionalidades/observatorio-referentes.md](../../../docs/funcionalidades/observatorio-referentes.md)
- [docs/funcionalidades/tu-turno.md](../../../docs/funcionalidades/tu-turno.md)
- [docs/plan-equipos.md](../../../docs/plan-equipos.md)
- [movil/.maestro/19-referentes-mensual.yaml](../../../movil/.maestro/19-referentes-mensual.yaml)
- [movil/src/personas/ProtectedReferent.tsx](../../../movil/src/personas/ProtectedReferent.tsx)
- [movil/src/personas/ReferentHistory.tsx](../../../movil/src/personas/ReferentHistory.tsx)
- [movil/src/personas/Referentes.tsx](../../../movil/src/personas/Referentes.tsx)
- [movil/src/test/server.ts](../../../movil/src/test/server.ts)
- [movil/src/turno/ReferentDecision.test.tsx](../../../movil/src/turno/ReferentDecision.test.tsx)
- [movil/src/turno/ReferentDecision.tsx](../../../movil/src/turno/ReferentDecision.tsx)
- [movil/src/turno/TurnoCard.tsx](../../../movil/src/turno/TurnoCard.tsx)
- [movil/src/turno/actions.ts](../../../movil/src/turno/actions.ts)
- [oficina/src/pages/personas/ProtectedReferent.tsx](../../../oficina/src/pages/personas/ProtectedReferent.tsx)
- [oficina/src/pages/personas/ReferentHistory.tsx](../../../oficina/src/pages/personas/ReferentHistory.tsx)
- [oficina/src/pages/personas/Referentes.tsx](../../../oficina/src/pages/personas/Referentes.tsx)
- [oficina/src/pages/turno/ReferentDecision.test.tsx](../../../oficina/src/pages/turno/ReferentDecision.test.tsx)
- [oficina/src/pages/turno/ReferentDecision.tsx](../../../oficina/src/pages/turno/ReferentDecision.tsx)
- [oficina/src/pages/turno/TurnoCardView.tsx](../../../oficina/src/pages/turno/TurnoCardView.tsx)
- [oficina/src/test/fakeServer.ts](../../../oficina/src/test/fakeServer.ts)
- [scripts/grafo/mermaid.py](../../../scripts/grafo/mermaid.py)
- [scripts/qa/correr-maestro.sh](../../../scripts/qa/correr-maestro.sh)
- [scripts/qa/seleccion.json](../../../scripts/qa/seleccion.json)
