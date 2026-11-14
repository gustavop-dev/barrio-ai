"""The weekly GASP plan (docs/plan-estrategia-semanal.md, estrategia.py): one row per local ISO week. New table only;
nothing existing changes."""
import django.utils.timezone
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('team_backend', '0039_recorte_sin_ia'),
    ]

    operations = [
        migrations.CreateModel(
            name='WeeklyPlan',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('week_start', models.DateField(unique=True)),
                ('state', models.CharField(choices=[('estructura', 'Solo la estructura'), ('planeada', 'Planeada')], default='estructura', max_length=12)),
                ('slots', models.JSONField(blank=True, default=list)),
                ('summary', models.TextField(blank=True)),
                ('warnings', models.JSONField(blank=True, default=list)),
                ('signals', models.JSONField(blank=True, default=dict)),
                ('kept_ideas', models.JSONField(blank=True, default=list)),
                ('history', models.JSONField(blank=True, default=list)),
                ('usage', models.JSONField(blank=True, default=list)),
                ('cost_usd', models.DecimalField(blank=True, decimal_places=6, max_digits=12, null=True)),
                ('origin_job', models.CharField(blank=True, max_length=40)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ['-week_start'],
            },
        ),
    ]
