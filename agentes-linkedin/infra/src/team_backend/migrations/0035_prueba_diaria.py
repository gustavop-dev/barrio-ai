"""The daily canary of a `directo` account (docs/plan-linkedin-directo.md, «Prueba diaria»): one row per run, the last
few kept. New table only; nothing existing changes."""
import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('team_backend', '0034_analitica_linkedin'),
    ]

    operations = [
        migrations.CreateModel(
            name='CanaryRun',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('state', models.CharField(choices=[('running', 'En curso'), ('ok', 'Todo bien'), ('roto', 'Algo cambió en LinkedIn'), ('alto', 'Cuenta detenida'), ('no_corrio', 'No pudo correr')], default='running', max_length=10)),
                ('operations', models.JSONField(blank=True, default=list)),
                ('calls', models.PositiveIntegerField(default=0)),
                ('error_kind', models.CharField(blank=True, max_length=40)),
                ('error', models.TextField(blank=True)),
                ('started_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('finished_at', models.DateTimeField(blank=True, null=True)),
                ('account', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='canary_runs', to='team_backend.connectoraccount')),
            ],
            options={
                'ordering': ['-started_at'],
                'indexes': [models.Index(fields=['account', 'started_at'], name='canary_run_last')],
            },
        ),
    ]
