from pathlib import Path
from django.db import migrations

class Migration(migrations.Migration):
    dependencies = [('team_backend', '0001_initial')]
    operations = [migrations.RunSQL(
        Path(__file__).with_name('legacy_schema.sql').read_text(),
        reverse_sql=migrations.RunSQL.noop,
    )]
