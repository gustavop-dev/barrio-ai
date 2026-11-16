# Barrio AI

Equipo de agentes de IA para construir posicionamiento, contenido y una comunidad relevante en LinkedIn, con una oficina visual en pixel art y una biblioteca de conocimiento compartida.

## Estado

El backend Django/PostgreSQL y la oficina visual ya existen. El diseño de cinco equipos y trece agentes está documentado y revisado; los ciclos completos todavía no están implementados. Los contratos JSON son especificaciones, no activaciones de agentes. La extracción original del curso no se repite al clonar este repositorio.

## Estructura

- `apartamento-agentes/`: oficina visual e integración existente con Sites.
- `agentes-linkedin/infra/`: backend Django, PostgreSQL/pgvector, recuperación de conocimiento, proveedores, caché, memoria y registro de consumo.
- `agentes-linkedin/arquitectura/`: estructura del equipo, plantilla, índice de contratos y registros de validación.
- `agentes-linkedin/equipos/`: contratos individuales y asignaciones de conocimiento.

Se conservan las rutas actuales para mantener las referencias entre documentación y componentes.

## Por dónde empezar

**Recorrido completo del proyecto:** [cómo construimos Barrio AI, desde los videos hasta la arquitectura de agentes](docs/como-construimos-barrio-ai.md).

**Diseño más reciente:** [72 acciones para operar el LinkedIn de Gustavo](agentes-linkedin/infra/docs/catalogo-acciones-linkedin.md): descubrir referentes, construir el barrio, interactuar, publicar, conversar, mantener el perfil y aprender. Primero se define el alcance; después se repartirán responsabilidades y se elegirán herramientas.

**Herramientas de LinkedIn:** la cuenta opera con LinkedIn directo, un conector propio que hace cada llamada desde la página de LinkedIn con la sesión abierta ([plan](docs/plan-linkedin-directo.md), [servicio navegador](agentes-linkedin/navegador/README.md)), y publica los posts con la API oficial de LinkedIn. La selección del 6/11/2026 queda como registro histórico: [selección revisada y huecos de cobertura](agentes-linkedin/infra/docs/herramientas-linkedin-v2.md), con la v1 como historial.

**Búsqueda de prospectos (registro histórico):** [lemlist frente al proveedor de entonces y Sales Navigator](agentes-linkedin/infra/docs/comparacion-lemlist-unipile.md). Diferencias entre base B2B, búsqueda de la cuenta, cobertura operativa y costes, del 6/11/2026.

1. [Plan del proyecto](agentes-linkedin/infra/docs/plan-equipo-autonomo.md) (registro histórico de noviembre de 2026).
2. [Ciclos de los cinco equipos](agentes-linkedin/infra/docs/circuitos-equipo.md).
3. [Datos externos necesarios](agentes-linkedin/infra/docs/datos-externos-por-equipo.md).
4. [Índice de los trece agentes](agentes-linkedin/arquitectura/indice-agentes-v1.json).
5. [Recorrido de mesa y QA](agentes-linkedin/infra/docs/recorrido-mesa-equipo-completo.md).
6. [Operación del backend](agentes-linkedin/infra/LEEME.txt) y [oficina conectada](apartamento-agentes/README.md).

## Datos y configuración locales

El repositorio es privado. No contiene claves de API, archivos `.env`/`.dev.vars`, bases de datos, copias de seguridad, cachés de ejecución ni las carpetas originales del curso. Los archivos de conocimiento incluidos en contratos y documentos no sustituyen el corpus privado necesario para importar y verificar la biblioteca.

Una instalación nueva requiere configurar el entorno privado y `SOURCE_ROOT`, aportar el corpus autorizado y seguir la documentación de cada componente. Clonar el repositorio no conecta proveedores, no modifica presupuestos y no inicia publicaciones. El entorno operativo actual permanece en su ubicación original.

Las pruebas del backend que requieren el corpus deben ejecutarse en un entorno que lo tenga disponible. Los workflows existentes del backend se conservan en su subcarpeta; no hay un workflow raíz habilitado para este monorepo todavía.

## Procedencia

Este primer commit reúne una copia del estado actual de los dos proyectos locales y los diseños del equipo; no importa sus historiales Git. Los proyectos originales y sus historiales se conservan. [Registro de importación](docs/importacion-inicial.json).

Los presets de desarrollo proceden de [ai_skills_project](https://github.com/gustavop-dev/ai_skills_project), con revisión fijada en [su registro](agentes-linkedin/infra/docs/stack/source.json).

El arte usado por la oficina pertenece a LimeZu — Modern Interiors; se mantienen [los créditos](apartamento-agentes/public/assets/CREDITS.txt). Este repositorio no distribuye la biblioteca original de assets ni concede una licencia nueva sobre recursos de terceros o materiales del curso.
