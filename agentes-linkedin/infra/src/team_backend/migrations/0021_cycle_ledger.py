import uuid
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [
        ('team_backend', '0020_web_research'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [migrations.CreateModel(name='CycleLedger', fields=[
        ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
        ('cycle', models.CharField(max_length=60)),
        ('key', models.CharField(max_length=160)),
        ('orchestrator', models.CharField(max_length=60)),
        ('graph_version', models.CharField(max_length=40)),
        ('graph_hash', models.CharField(max_length=64)),
        ('limits', models.JSONField(default=dict)),
        ('budget_bucket', models.CharField(max_length=220, db_index=True)),
        ('task_ledger', models.JSONField(default=dict)),
        ('progress_ledger', models.JSONField(default=dict)),
        ('state', models.CharField(max_length=20, default='running', db_index=True)),
        ('stop_reason', models.CharField(max_length=80, blank=True)),
        ('needs_attention', models.BooleanField(default=False)),
        ('lease_token', models.CharField(max_length=32, blank=True)),
        ('revision', models.PositiveIntegerField(default=0)),
        ('calls', models.PositiveIntegerField(default=0)),
        ('active_seconds', models.FloatField(default=0)),
        ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
        ('updated_at', models.DateTimeField(auto_now=True)),
        ('job', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to='team_backend.job')),
        ('owner', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
    ], options={
        'ordering': ['-updated_at'],
        'constraints': [models.UniqueConstraint(fields=('cycle', 'key'), name='unique_cycle_instance')],
    })]
