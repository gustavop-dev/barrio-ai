"""Phase 5. Claude must reconcile the number with the parallel phase migration."""
import uuid
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion as deletion
import django.utils.timezone


def protect_current(apps, schema_editor):
    Account = apps.get_model('team_backend', 'ConnectorAccount')
    Referent = apps.get_model('team_backend', 'Referent')
    Control = apps.get_model('team_backend', 'ReferentControl')
    Audit = apps.get_model('team_backend', 'AuditEvent')
    db = schema_editor.connection.alias
    for account in Account.objects.using(db).all():
        if account.provider in ('linkedin', 'linkedin_fake'):
            continue  # publishing-only connector: no observatory referent set
        rows = list(Referent.objects.using(db).filter(account=account, archived_at__isnull=True))
        ids = sorted(str(row.pk) for row in rows)
        ready = len(rows) == 5
        Control.objects.using(db).create(account=account, initialized=ready, initial_main=ids if ready else [],
            issue='' if ready else 'Activación pendiente: identificar los cinco IDs actuales; no se eligieron automáticamente.')
        if ready:
            Referent.objects.using(db).filter(pk__in=ids).update(protected=True)
        Audit.objects.using(db).create(action='referents.bootstrap', target=str(account.pk), metadata={
            'source': '0024_referentes_monthly', 'initialized': ready, 'main_ids': ids if ready else [],
            'observed_count': len(ids), 'before': {'protected': False}, 'after': {'protected': ready}})


class Migration(migrations.Migration):
    dependencies = [('team_backend', '0023_shared_evidence'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.AddField('referent', 'protected', models.BooleanField(default=False)),
        migrations.AddField('referent', 'position', models.PositiveIntegerField(default=0)),
        migrations.AddField('referent', 'revision', models.PositiveIntegerField(default=1)),
        migrations.CreateModel(name='ReferentControl', fields=[
            ('account', models.OneToOneField(to='team_backend.connectoraccount', on_delete=deletion.CASCADE, primary_key=True, serialize=False)),
            ('initialized', models.BooleanField(default=False)), ('initial_main', models.JSONField(default=list)),
            ('revision', models.PositiveIntegerField(default=1)), ('issue', models.TextField(blank=True)),
        ]),
        migrations.CreateModel(name='ReferentReview', fields=[
            ('id', models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
            ('account', models.ForeignKey(to='team_backend.connectoraccount', on_delete=deletion.PROTECT)),
            ('month', models.DateField()), ('state', models.CharField(max_length=24, default='preparing')),
            ('dossier', models.JSONField(default=dict)), ('expected_revision', models.PositiveIntegerField(default=1)),
            ('published_at', models.DateTimeField(null=True, blank=True)), ('deadline', models.DateTimeField()),
            ('closed_at', models.DateTimeField(null=True, blank=True)), ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
        ], options={'constraints': [models.UniqueConstraint(fields=['account', 'month'], name='unique_referent_month')]}),
        migrations.CreateModel(name='ReferentChange', fields=[
            ('id', models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
            ('review', models.ForeignKey(to='team_backend.referentreview', on_delete=deletion.CASCADE, related_name='changes')),
            ('ordinal', models.PositiveIntegerField()), ('version', models.PositiveIntegerField(default=1)),
            ('proposal', models.JSONField(default=dict)), ('history', models.JSONField(default=list)),
            ('state', models.CharField(max_length=24, default='pending')), ('responded_at', models.DateTimeField(null=True, blank=True)),
            ('applied_at', models.DateTimeField(null=True, blank=True)), ('conflict', models.TextField(blank=True)),
        ], options={'ordering': ['ordinal'], 'constraints': [models.UniqueConstraint(fields=['review', 'ordinal'], name='unique_referent_change')]}),
        migrations.CreateModel(name='ReferentNotice', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('review', models.ForeignKey(to='team_backend.referentreview', on_delete=deletion.CASCADE, related_name='notices')),
            ('event', models.CharField(max_length=24)), ('payload', models.JSONField(default=dict)),
            ('created_at', models.DateTimeField(default=django.utils.timezone.now)), ('pushed_at', models.DateTimeField(null=True, blank=True)),
        ], options={'constraints': [models.UniqueConstraint(fields=['review', 'event'], name='unique_referent_notice')]}),
        migrations.CreateModel(name='ReferentExperiment', fields=[
            ('id', models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
            ('account', models.ForeignKey(to='team_backend.connectoraccount', on_delete=deletion.PROTECT)),
            ('referent', models.ForeignKey(to='team_backend.referent', on_delete=deletion.PROTECT)),
            ('review', models.ForeignKey(to='team_backend.referentreview', on_delete=deletion.SET_NULL, null=True, blank=True)),
            ('version', models.PositiveIntegerField(default=1)), ('state', models.CharField(max_length=24, default='proposed')),
            ('plan', models.JSONField(default=dict)), ('history', models.JSONField(default=list)),
            ('approved_by', models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=deletion.SET_NULL, null=True, blank=True)),
            ('approved_at', models.DateTimeField(null=True, blank=True)), ('starts_at', models.DateTimeField()),
            ('focus_at', models.DateTimeField()), ('followup_at', models.DateTimeField()), ('ends_at', models.DateTimeField()),
            ('results', models.JSONField(default=dict)), ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
        ], options={'constraints': [models.UniqueConstraint(fields=['account'], condition=models.Q(state='approved'), name='one_referent_experiment')]}),
        migrations.AddField('actionproposal', 'referent_experiment', models.ForeignKey(to='team_backend.referentexperiment', on_delete=deletion.PROTECT, null=True, blank=True)),
        migrations.AddField('actionproposal', 'referent_experiment_version', models.PositiveIntegerField(null=True, blank=True)),
        migrations.RunPython(protect_current, migrations.RunPython.noop),
    ]
