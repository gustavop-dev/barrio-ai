"""Outcomes of executed actions (desenlaces.py): what came after an own comment (72 h) or a network action (7 d).
New table only; nothing existing changes."""
import django.db.models.deletion
import django.utils.timezone
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('team_backend', '0041_referentes_industria'),
    ]

    operations = [
        migrations.CreateModel(
            name='ActionOutcome',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('kind', models.CharField(choices=[('72h', '72 horas'), ('7d', '7 días')], max_length=4)),
                ('captured_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('source', models.CharField(choices=[('read', 'Leído en LinkedIn'), ('derived', 'Derivado de datos propios')], max_length=10)),
                ('provider_comment_id', models.CharField(blank=True, max_length=255)),
                ('reactions', models.PositiveIntegerField(blank=True, null=True)),
                ('replies', models.PositiveIntegerField(blank=True, null=True)),
                ('author_replied', models.BooleanField(blank=True, null=True)),
                ('repliers', models.JSONField(blank=True, default=list)),
                ('signals', models.JSONField(blank=True, default=dict)),
                ('execution', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='outcomes', to='team_backend.actionexecution')),
            ],
            options={
                'ordering': ['captured_at'],
                'constraints': [models.UniqueConstraint(fields=('execution', 'kind'), name='one_outcome_per_age')],
            },
        ),
    ]
