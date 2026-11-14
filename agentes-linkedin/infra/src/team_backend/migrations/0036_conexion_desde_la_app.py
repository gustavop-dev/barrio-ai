"""Conectar LinkedIn desde la app (team_backend/conexion.py): one row per login into a `directo` account's browser.
New table only; nothing existing changes."""
import uuid

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('team_backend', '0035_prueba_diaria'),
    ]

    operations = [
        migrations.CreateModel(
            name='BrowserLogin',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('session', models.CharField(max_length=64)),
                ('state', models.CharField(choices=[('abriendo', 'Abriendo'), ('esperando', 'Esperando'), ('conectada', 'Conectada'), ('vencida', 'Vencida'), ('cancelada', 'Cancelada'), ('fallida', 'Fallida')], default='abriendo', max_length=12)),
                ('reason', models.TextField(blank=True)),
                ('still_stopped', models.BooleanField(default=False)),
                ('started_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('expires_at', models.DateTimeField()),
                ('finished_at', models.DateTimeField(blank=True, null=True)),
                ('ticket_hash', models.CharField(blank=True, db_index=True, max_length=64)),
                ('ticket_expires_at', models.DateTimeField(blank=True, null=True)),
                ('cookie_hash', models.CharField(blank=True, db_index=True, max_length=64)),
                ('account', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='browser_logins', to='team_backend.connectoraccount')),
                ('user', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-started_at'],
                'indexes': [models.Index(fields=['account', 'started_at'], name='browser_login_last')],
            },
        ),
    ]
