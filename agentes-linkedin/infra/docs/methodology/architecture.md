# Arquitectura
La continuación de assets separa revisión del contenido visible y revisión explicativa. Una arista acotada permite reparar únicamente tres campos de una sección y revisarla una vez más, dentro de los mismos límites. No se altera la identidad de las ediciones de persona ni se regeneran fotos aprobadas. Los previews acreditan sus bytes y su revisión, sin certificar la interfaz real.

Perfil conserva la edición de persona como checkpoint independiente. Las continuaciones consultan el ciclo original y los ciclos `perfil_assets` de su misma versión/propietario/presupuesto; el render local versionado produce composición y evidencia cuantitativa ligada al SHA-256 para la revisión visual. No se reinician ledgers ni presupuestos al cambiar el render.

Navegador/API → autenticación Django y permisos → serializers/servicios → biblioteca compartida o Job persistente → worker → knowledge.agents → proveedores. Las tablas históricas permanecen; Django añade tablas de autenticación, credenciales hash, trabajos y auditoría. Las unidades y evidencias son de solo lectura en Admin.

```mermaid
flowchart LR
    H[Usuario / consola] --> D[Django + DRF]
    D --> A[Auth / permisos / auditoría]
    D --> Q[(Cola PostgreSQL)]
    Q --> W[Worker con latidos]
    W --> K[Servicios knowledge]
    D --> K
    K --> L[(Biblioteca / pgvector / memoria / ledger)]
    K --> O[OpenAI embeddings]
    K --> C[Anthropic generación]
```

El grafo muestra también consultas directas de biblioteca desde DRF. Solo los trabajos de agentes van por la cola. Los proveedores siguen sujetos a LIVE_PROVIDERS, permisos, caché y reservas monetarias existentes. Cada Job pertenece a un usuario; las unidades son compartidas por el equipo. Ningún modelo de Django reescribe el contenido extraído. Los registros originales se adoptan mediante SQL idempotente y modelos unmanaged.

## Evolución planificada

El [plan maestro del equipo autónomo](../plan-equipo-autonomo.md) define ciclos,
fases y criterios de aceptación para la siguiente etapa. Es arquitectura prevista;
no implica que la coordinación multiagente esté implementada.

Diseño de coordinación pendiente de implementación: [circuitos de todos los equipos](../circuitos-equipo.md) y [datos externos necesarios](../datos-externos-por-equipo.md). Los contratos individuales no alteran la arquitectura en ejecución.
