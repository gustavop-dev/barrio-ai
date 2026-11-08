# Ajustes › Notificaciones: the push types Gustavo turns on although their default is off (OfficePreference.push_enabled).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('team_backend', '0017_app_errores_cliente'),
    ]

    operations = [
        migrations.AddField(
            model_name='officepreference',
            name='push_enabled',
            field=models.JSONField(blank=True, default=list),
        ),
    ]
