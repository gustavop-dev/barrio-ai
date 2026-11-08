# Client error reports of the mobile app (POST /api/v1/app/errores).

import django.db.models.deletion
import django.utils.timezone
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('team_backend', '0016_app_movil'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='AppClientError',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now, editable=False)),
                ('kind', models.CharField(max_length=40)),
                ('name', models.CharField(blank=True, max_length=80)),
                ('message', models.CharField(blank=True, max_length=500)),
                ('status', models.PositiveSmallIntegerField(blank=True, null=True)),
                ('detail', models.CharField(blank=True, max_length=500)),
                ('parts', models.JSONField(blank=True, default=list)),
                ('platform', models.CharField(blank=True, max_length=20)),
                ('os_version', models.CharField(blank=True, max_length=40)),
                ('app_version', models.CharField(blank=True, max_length=40)),
                ('device', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='client_errors', to='team_backend.devicetoken')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='app_client_errors', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]
