# LinkedIn Team backend

User-approved stack: Django + PostgreSQL/pgvector. Project presets come from
https://github.com/gustavop-dev/ai_skills_project.git at the commit in
docs/stack/source.json. Apply relevant local skills, not unrelated fleet workflows.

- Original classes 01–06 are immutable. Class07 is excluded. Never rewrite units.
- Keep provider keys in ignored .env; never log them or copy into frontend/code.
- Existing cache, runs, memory and ledger are durable data; never reset budgets.
- Tests default to LIVE_PROVIDERS=false and use temporary PostgreSQL data.
- Product repository has no origin. The presets repository is not a push target.
- OPS_ROOT/fleet helpers are unavailable here. Report that limit instead of
  inventing a profile or claiming formal fleet validation. Local measurements
  and standalone tests remain required.
- Local checks: uv run pytest -q (requires private corpus),
  uv run python manage.py test team_backend.tests --noinput,
  uv run python manage.py check, migrations --check --dry-run.
- Use Django migrations for schema changes. Do not edit the frozen legacy SQL.
- Retain the single-workspace shared knowledge model and job ownership checks.
