"""La biblioteca admite las clases 01–12 (units y evidence). Antes, CHECK(session BETWEEN 1 AND 6).

legacy_schema.sql queda congelado; este cambio vive aquí y en knowledge/schema.sql para instalaciones nuevas. El
número va escrito: una migración no sigue a knowledge.clases.CLASES_BIBLIOTECA. Qué clases leen los agentes no es
cosa de la base: lo decide knowledge.clases.CLASES_AGENTES.

Se quita cualquier CHECK sobre session sin depender de su nombre (la base de la laptop y la restaurada en el
servidor vienen de SQL anterior a Django). Volver atrás falla mientras haya filas de las clases 07–12: hay que
retirarlas antes, a propósito, en vez de perderlas en silencio."""
from django.db import migrations

DROP_SESSION_CHECKS = '''DO $$
DECLARE r record;
BEGIN
  FOR r IN SELECT conrelid::regclass::text AS tabla, conname FROM pg_constraint
      WHERE contype = 'c' AND conrelid IN ('units'::regclass, 'evidence'::regclass)
        AND position('session' IN pg_get_constraintdef(oid)) > 0
  LOOP
    EXECUTE format('ALTER TABLE %s DROP CONSTRAINT %I', r.tabla, r.conname);
  END LOOP;
END $$'''


def session_checks(last):
    return [DROP_SESSION_CHECKS] + [
        f'ALTER TABLE {table} ADD CONSTRAINT {table}_session_check CHECK (session BETWEEN 1 AND {last})'
        for table in ('units', 'evidence')]


class Migration(migrations.Migration):

    dependencies = [('team_backend', '0044_sin_unipile')]

    operations = [migrations.RunSQL(session_checks(12), reverse_sql=session_checks(6))]
