"""Cambiar una cuenta entre Unipile y directo (team_backend/proveedor.py): where the provider it had before is kept.
One column with an empty default; nothing existing changes."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('team_backend', '0036_conexion_desde_la_app'),
    ]

    operations = [
        migrations.AddField(
            model_name='connectoraccount',
            name='previous_provider',
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
