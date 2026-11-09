# Observatorio: dependencia web de fase 1 (`OBS`)

El catálogo de `plan-equipos` reserva estos IDs para fases posteriores:

| ID | Función | Estado |
| --- | --- | --- |
| OBS-01 | Investigación mensual de altas, continuidad y bajas | no implementado |
| OBS-02 | Cinco main protegidos y ventana mensual para diez plazas | no implementado |
| OBS-03 | Evidencia de audiencia y encaje por referente | no implementado |
| OBS-04 | Experimentos de participación con resultado medible | no implementado |

La dependencia de acceso web ya tiene implementación en [CAP-17/18](captura.md#cap-17) y [EDI-03/07/17](motor-editorial.md#edi-03), con estado `funciona` y CI pendiente. No sustituye la investigación mensual ni activa altas, bajas, cambios de protección o experimentos. Las reglas del catálogo completo de `plan-equipos` siguen siendo la especificación de esas fases.

El futuro orquestador podrá llamar `research(ResearchRequest) -> ResearchResult` con una clave estable por ciclo/paso, una pregunta pública y enlaces acotados. Recibirá hallazgos, citas, fechas, costes y limitaciones. El investigador no llama agentes ni escribe en LinkedIn. Los contratos y límites del dispatcher de ARQ-01–09 se implementarán en fase 3.

Contrato, configuración y entrega a Claude: [acceso web del equipo](../../agentes-linkedin/infra/docs/acceso-web-equipo.md).
