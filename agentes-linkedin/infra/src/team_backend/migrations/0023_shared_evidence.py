"""Schema only. Historical data is imported idempotently by evidencia.sync_stored.

Keep existing contacts, cuts, ledgers and budgets intact. No connector calls.
"""
import uuid
from django.db import migrations, models
from django.utils import timezone


class Migration(migrations.Migration):
    dependencies = [('team_backend', '0022_cycleledger_job_set_null')]
    operations = [
        migrations.AddField(model_name='referent', name='archived_at', field=models.DateTimeField(null=True, blank=True)),
        migrations.CreateModel(name='EvidencePerson', fields=[
            ('id', models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
            ('provider_user_id', models.CharField(max_length=200)),
            ('display_name', models.CharField(max_length=200, blank=True)),
            ('account', models.ForeignKey(to='team_backend.connectoraccount', on_delete=models.PROTECT, related_name='evidence_people')),
        ], options={'constraints': [models.UniqueConstraint(fields=['account', 'provider_user_id'], name='unique_evidence_person')]}),
        migrations.CreateModel(name='PersonEvidence', fields=[
            ('id', models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
            ('key', models.CharField(max_length=64)),
            ('kind', models.CharField(max_length=32)),
            ('source', models.CharField(max_length=40)),
            ('source_id', models.CharField(max_length=200)),
            ('post_id', models.CharField(max_length=200, blank=True)),
            ('interaction_id', models.CharField(max_length=200, blank=True)),
            ('source_url', models.TextField(blank=True)),
            ('event_at', models.DateTimeField(null=True, blank=True)),
            ('observed_at', models.DateTimeField(db_index=True)),
            ('recorded_at', models.DateTimeField(default=timezone.now)),
            ('coverage', models.JSONField(default=dict)),
            ('details', models.JSONField(default=dict)),
            ('experiment_id', models.CharField(max_length=200, blank=True)),
            ('person', models.ForeignKey(to='team_backend.evidenceperson', on_delete=models.PROTECT, related_name='observations')),
            ('referent', models.ForeignKey(to='team_backend.referent', on_delete=models.PROTECT, null=True, blank=True, related_name='person_evidence')),
        ], options={'constraints': [models.UniqueConstraint(fields=['person', 'key'], name='unique_person_evidence')]}),
        migrations.CreateModel(name='EvidenceCoverage', fields=[
            ('id', models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
            ('source', models.CharField(max_length=40)),
            ('source_id', models.CharField(max_length=200)),
            ('observed_at', models.DateTimeField(db_index=True)),
            ('status', models.CharField(max_length=20)),
            ('details', models.JSONField(default=dict)),
            ('account', models.ForeignKey(to='team_backend.connectoraccount', on_delete=models.PROTECT, related_name='evidence_coverage')),
            ('referent', models.ForeignKey(to='team_backend.referent', on_delete=models.PROTECT, null=True, blank=True)),
        ], options={'constraints': [models.UniqueConstraint(fields=['account', 'source', 'source_id'], name='unique_evidence_coverage')]}),
        migrations.CreateModel(name='FitClassification', fields=[
            ('id', models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
            ('key', models.CharField(max_length=64)),
            ('criterion_version', models.CharField(max_length=100)),
            ('classified_at', models.DateTimeField(null=True, blank=True)),
            ('recorded_at', models.DateTimeField(default=timezone.now)),
            ('sufficient', models.BooleanField(default=False)),
            ('fit', models.BooleanField(null=True, blank=True)),
            ('details', models.JSONField(default=dict)),
            ('person', models.ForeignKey(to='team_backend.evidenceperson', on_delete=models.PROTECT, related_name='fit_versions')),
        ], options={'constraints': [models.UniqueConstraint(fields=['person', 'key'], name='unique_fit_version')]}),
        migrations.CreateModel(name='ReferentAttribution', fields=[
            ('id', models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
            ('key', models.CharField(max_length=64)),
            ('window_start', models.DateTimeField()),
            ('window_end', models.DateTimeField()),
            ('as_of', models.DateTimeField()),
            ('created_at', models.DateTimeField(default=timezone.now)),
            ('report', models.JSONField(default=dict)),
            ('referent', models.ForeignKey(to='team_backend.referent', on_delete=models.PROTECT, related_name='attribution_reports')),
        ], options={'constraints': [models.UniqueConstraint(fields=['referent', 'key'], name='unique_referent_attribution')]}),
    ]
