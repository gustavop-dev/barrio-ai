"""Cambiar de proveedor traduciendo los ids guardados (team_backend/proveedor.py): the originals a switch rewrote, and
the mark a switched conversation carries until its next read. New table and one column with an empty default."""
import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('team_backend', '0037_cambio_de_proveedor'),
    ]

    operations = [
        migrations.AddField(
            model_name='conversation',
            name='carry',
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.CreateModel(
            name='ProviderIdOriginal',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('provider', models.CharField(max_length=20)),
                ('model', models.CharField(max_length=40)),
                ('object_id', models.CharField(max_length=64)),
                ('field', models.CharField(max_length=60)),
                ('original', models.TextField()),
                ('translated', models.TextField()),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('account', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                              related_name='provider_id_originals', to='team_backend.connectoraccount')),
            ],
            options={
                'constraints': [models.UniqueConstraint(fields=('account', 'provider', 'model', 'object_id', 'field'),
                                                        name='unique_provider_id_original')],
            },
        ),
    ]
