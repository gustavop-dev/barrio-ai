"""The navegador service (docs/plan-linkedin-directo.md, phase 2): one Chromium per LinkedIn account, each with its
own persistent profile, that makes every call the backend's `directo` connector asks for from inside the account's
logged-in page, and returns LinkedIn's answer as it came. Wire contract: agentes-linkedin/infra/docs/
navegador-contrato.md. What may leave and how an answer is judged come from the backend's own linkedin_directo package
(never duplicated here).

- ajustes: settings from the environment (token, data folder, pause, budgets).
- almacen: what is kept per account on disk (profile, stop flag, budget use, writes by request_id).
- pagina: the real browser page (patchright), the in-page fetch and the live GraphQL query ids.
- cuenta: one account's guards, in order, around each call.
- servidor: the HTTP API (aiohttp).
- canario: the daily read-only check, through the running service.
"""
