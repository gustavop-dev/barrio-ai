# Despliegue de fase 2: curso y participación

Cambios preparados en `feat/fase2-curso`. No se desplegó ni se leyó el entorno privado. No hubo instalaciones, red, ejecución de tests, builds, commit o push. Los ejemplos públicos de configuración se actualizaron; los overrides del servidor siguen pendientes de reconciliar con BAR-15.

Claves del servidor que Claude debe reconciliar, **solo nombres**:

- `OPERATOR_DAILY_LIMITS`
- `OPERATOR_WEEKLY_LIMITS`
- `OPERATOR_WINDOW`
- `OPERATOR_TIMEZONE`
- `OPERATOR_MIN_SPACING_SECONDS`
- `OPERATOR_MAX_SPACING_SECONDS`
- `OPERATOR_WEEKEND_FACTOR`
- `OPERATOR_PROFILE_READ_DAILY_LIMIT`
- `OPERATOR_INVITE_RAMP_ENABLED`
- `OPERATOR_INVITE_RAMP_STAGES`
- `OPERATOR_INVITE_RAMP_MIN_DAYS`
- `OPERATOR_INVITE_ACCEPTANCE_MIN`
- `OPERATOR_INVITE_ACCEPTANCE_PAUSE`
- `OPERATOR_INVITE_ACCEPTANCE_DROP_PP`
- `OPERATOR_INVITE_SAMPLE_MIN`
- `OPERATOR_INVITE_MATURITY_DAYS`
- `OPERATOR_INVITE_COHORT_DAYS`
- `OPERATOR_EXTERNAL_OUTREACH_ACTIVE`
- `NETWORK_READ_CAPS`
- `LINKEDIN_ACCOUNT_TIER`
- `LINKEDIN_INVITE_NOTE_MONTHLY_LIMIT`

Comprobar, conservando sus decisiones y pausas: `OPERATOR_AUTOPILOT`, `OPERATOR_AUTONOMY`, `OPERATOR_PAUSED`, `OPERATOR_AUTHOR_COOLDOWN_HOURS`, `NETWORK_ENABLED`, `NETWORK_INVITE_AFTER_HOURS`, `LEAD_ENABLED`, `LEAD_CAPABILITIES`. No copiar valores privados a logs, PR o documentación.

La rampa empieza en su primera etapa al crear su primer registro persistente. Cambiar env, reiniciar procesos o cambiar tier no reinicia estado, reservas ni consumos. Se usa el singleton existente `OperatorControl` para serializar reservas entre conectores y `AuditEvent` para historial durable; no hay cambios de esquema. Conservar estos registros al desplegar. Los topes generales nuevos no autorizan saltar la rampa. No levantar pausas existentes.

No ejecutar lemlist ni otra automatización de outreach junto al operador. La configuración declara la automatización externa conocida; no constituye una comprobación por API de su ausencia. Un tier pagado no habilita por sí solo más invitaciones, notas ilimitadas o mayor longitud. Las capacidades verificadas pueden registrarse mediante los eventos internos `network.note_capability` y `network.notes_reset_verified`, con evidencia del proveedor; no fabricarlos para quitar bloqueos. Una cuota de notas rechazada permanece bloqueada hasta un reinicio acreditado, aunque cambie el mes local.

Claude debe verificar en CI:

- Ejecutar `team_backend.tests.test_fase2_curso` y las regresiones de operador, red, auditoría de red/líder, conversaciones, métricas, resumen semanal y evaluaciones, con PostgreSQL temporal, corpus sintético y conectores/proveedores falsos. Nada contra LinkedIn ni modelos pagados.
- Confirmar bloqueo en fin de semana y fuera de ventana aun con aprobación previa; máximos diarios/semanales, reservas concurrentes entre conectores, jitter persistente y agenda distinta tras reiniciar/cambiar de día. Mantener veto, hash aprobado, espera por persona y pausas.
- Confirmar cohortes únicas maduras, desconocidas separadas, falta de muestra, ascenso por etapa, caída de tasa, pausa por salud, destinatario bloqueado por 422 y pausa tras repetición/restricción. No reducir dos veces por el mismo corte.
- Confirmar el contador compartido de perfiles: investigación, observación, métricas, preflight y conciliación; el agotamiento previo deja la aprobación pendiente. Un fallo después de escribir conserva envío/reserva para conciliar.
- Confirmar notas sin texto por defecto, selección por encaje, inglés/sin pitch, reserva mensual concurrente, cambio de tier y continuidad sin nota. Solo un rechazo inequívoco de cuota de notas genera un intento posterior vinculado a la misma intención y sujeto a todos los gates. Timeout, 429, `cannot_resend_yet` y cuota genérica nunca hacen fallback.
- **Contrato pendiente de verificar con fixture redactada del proveedor:** `send_invitation` usa el campo opcional `message`. El adaptador conservador solo tipa cuota de notas ante alcance explícito de nota, motivo mensual y certeza de que no se creó invitación. Estos campos son un contrato de adaptación, no una afirmación de que la respuesta real de Unipile los contenga. Comparar con una respuesta capturada y añadir su mapeo comprobado antes de activar notas excepcionales; el flujo sin nota sigue disponible.
- Confirmar todos los IDs curados en la base desplegada mediante `retrieval.unit`, originales completos, fuentes con clase, hashes, exclusión de clase 07 y citas de unidades realmente cargadas. Sin biblioteca, clasificación/inbox/líder esperan; el semanal guarda cifras y aprendizaje pendiente.
- Revisar los siete casos BIB-09 y los constructores de evaluación frente a las peticiones de producción. El informe de ensayo enumera fixtures; no declara haber ejecutado ni aprobado sus evaluaciones. Las evaluaciones pagadas conservan sus opt-ins y presupuesto.
- Ejecutar las comprobaciones Django habituales y la detección de migraciones pendientes en CI. No se hicieron comprobaciones de runtime en esta sesión; solo revisión de archivos y `git diff --check`.

Límites de esta entrega: fundamento del Observatorio existente, sin crear el ciclo mensual de referentes ni modificar main; cifras y contexto del analista, sin convertir el recolector determinista en un nuevo agente. Perfil/visual y los ciclos futuros mantienen sus fases. Jev recibe el bloque estable dentro de `state` porque su contrato actual no tiene un campo separado de caché; Claude recibe `context` cacheable. No se cambió `knowledge/providers.py`.
