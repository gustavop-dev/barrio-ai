from django.core.management import call_command
from django.db import migrations


def create_cache_table(apps, schema_editor):
    # settings.CACHES uses the database so that the login lockout counter (ACC-03) is shared by every gunicorn process.
    call_command('createcachetable', database=schema_editor.connection.alias, verbosity=0)


class Migration(migrations.Migration):
    dependencies = [('team_backend', '0027_capture_publish_at')]

    operations = [migrations.RunPython(create_cache_table, migrations.RunPython.noop)]
