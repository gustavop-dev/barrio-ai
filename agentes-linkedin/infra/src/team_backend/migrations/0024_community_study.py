"""LEC-01–03 only. Reconcile numbering with phase 5 before merging; no data rewrite."""
import uuid
from django.db import migrations, models
from django.utils import timezone


class Migration(migrations.Migration):
    dependencies = [('team_backend', '0023_shared_evidence')]
    operations = [
        migrations.CreateModel(name='CommunityStudy', fields=[
            ('id', models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
            ('account', models.ForeignKey(to='team_backend.connectoraccount', on_delete=models.PROTECT)),
            ('period', models.DateField()), ('version', models.PositiveIntegerField(default=1)),
            ('window_start', models.DateTimeField()), ('window_end', models.DateTimeField()),
            ('created_at', models.DateTimeField(default=timezone.now)),
            ('completed_at', models.DateTimeField(null=True, blank=True)), ('expires_at', models.DateTimeField()),
            ('state', models.CharField(max_length=24, default='building')),
            ('positioning_version', models.CharField(max_length=100)),
            ('selection', models.JSONField(default=list)), ('coverage', models.JSONField(default=dict)),
            ('summary', models.JSONField(default=dict)),
        ], options={'constraints': [models.UniqueConstraint(fields=['account', 'period', 'version'], name='unique_community_version')]}),
        migrations.CreateModel(name='CommunitySource', fields=[
            ('id', models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
            ('study', models.ForeignKey(to='team_backend.communitystudy', on_delete=models.CASCADE, related_name='sources')),
            ('person', models.ForeignKey(to='team_backend.evidenceperson', on_delete=models.PROTECT)),
            ('key', models.CharField(max_length=64)), ('target', models.CharField(max_length=64)),
            ('kind', models.CharField(max_length=24)), ('url', models.TextField(blank=True)), ('text', models.TextField(blank=True)),
            ('event_at', models.DateTimeField(null=True, blank=True)),
            ('observed_at', models.DateTimeField(default=timezone.now)), ('expires_at', models.DateTimeField()),
            ('retired_at', models.DateTimeField(null=True, blank=True)), ('analysis', models.JSONField(default=dict)),
        ], options={'constraints': [models.UniqueConstraint(fields=['study', 'person', 'key'], name='unique_community_source')]}),
        migrations.CreateModel(name='CommunityWithdrawal', fields=[
            ('id', models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
            ('account', models.ForeignKey(to='team_backend.connectoraccount', on_delete=models.PROTECT)),
            ('key', models.CharField(max_length=64)), ('created_at', models.DateTimeField(default=timezone.now)),
            ('reason', models.CharField(max_length=24)),
        ], options={'constraints': [models.UniqueConstraint(fields=['account', 'key'], name='unique_community_withdrawal')]}),
    ]
