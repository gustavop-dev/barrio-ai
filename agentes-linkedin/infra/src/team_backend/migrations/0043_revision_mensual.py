"""Monthly review of analista_barrio_resultados (revision_mensual.py) and its strategy changes. New tables only; nothing
existing changes."""
import django.db.models.deletion
import django.utils.timezone
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('team_backend', '0042_desenlaces_de_acciones'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='MonthlyReview',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('month_start', models.DateField(unique=True)),
                ('stats', models.JSONField(blank=True, default=dict)),
                ('analysis', models.JSONField(blank=True, default=dict)),
                ('state', models.CharField(choices=[('nuevo', 'Nueva'), ('visto', 'Vista')], db_index=True, default='nuevo', max_length=12)),
                ('partial', models.BooleanField(default=False)),
                ('usage', models.JSONField(blank=True, default=dict)),
                ('cost_usd', models.DecimalField(blank=True, decimal_places=6, max_digits=12, null=True)),
                ('origin_job', models.CharField(blank=True, max_length=40)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ['-month_start'],
            },
        ),
        migrations.CreateModel(
            name='StrategyChange',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('position', models.PositiveSmallIntegerField(default=0)),
                ('title', models.CharField(max_length=120)),
                ('proposal', models.TextField()),
                ('reason', models.TextField(blank=True)),
                ('evidence', models.JSONField(blank=True, default=list)),
                ('expected', models.TextField(blank=True)),
                ('metric', models.CharField(max_length=40)),
                ('baseline', models.JSONField(blank=True, default=dict)),
                ('state', models.CharField(choices=[('propuesto', 'Propuesto'), ('aprobado', 'Aprobado'), ('rechazado', 'Rechazado'), ('revertido', 'Revertido')], db_index=True, default='propuesto', max_length=12)),
                ('final_text', models.TextField(blank=True)),
                ('decided_at', models.DateTimeField(blank=True, null=True)),
                ('decision_note', models.TextField(blank=True)),
                ('orientation_before', models.TextField(blank=True)),
                ('reverted_at', models.DateTimeField(blank=True, null=True)),
                ('outcome', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('decided_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
                ('review', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='changes', to='team_backend.monthlyreview')),
            ],
            options={
                'ordering': ['review', 'position'],
                'constraints': [models.UniqueConstraint(fields=('review', 'position'), name='one_strategy_change_per_position')],
            },
        ),
    ]
