"""Unipile is gone: the account has operated through LinkedIn directo since 2026-11-14, and what only existed to move
it there (and back) goes with it.
- ConnectorAccount.provider loses the `unipile` choice.
- ConnectorAccount.previous_provider ({provider, external_account_id, until, by}) becomes ids_since, its `until`: the
  moment the account's stored LinkedIn ids changed scheme. Audit events before it keep ids of the scheme before and
  are never reused (metricas._known_id, red.search_location).
- EditorialPiece.metrics: the key `unipile_post_id` becomes `provider_post_id` and the source `unipile`, `linkedin`.
- ProviderIdOriginal (each id as it was before the move, kept only to move back) and Conversation.carry (the mark a
  moved conversation carried until its next read) are dropped.
Backwards puts the columns, the table and the names back; the dropped originals and marks do not come back."""
import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models
from django.utils.dateparse import parse_datetime

RENAMES = (('unipile_post_id', 'provider_post_id'),)
SOURCES = (('unipile', 'linkedin'),)


def _metrics(apps, keys, sources):
    piece = apps.get_model('team_backend', 'EditorialPiece')
    for pk, metrics in piece.objects.exclude(metrics={}).values_list('pk', 'metrics').iterator():
        if not isinstance(metrics, dict):
            continue
        new = dict(metrics)
        for old, name in keys:
            if old in new:
                new.setdefault(name, new[old])
                del new[old]
        for old, name in sources:
            if new.get('source') == old:
                new['source'] = name
        if new != metrics:
            piece.objects.filter(pk=pk).update(metrics=new)


def forwards(apps, schema_editor):
    account = apps.get_model('team_backend', 'ConnectorAccount')
    for row in account.objects.exclude(previous_provider={}):
        until = parse_datetime(str((row.previous_provider or {}).get('until') or ''))
        if until:
            account.objects.filter(pk=row.pk).update(ids_since=until)
    _metrics(apps, RENAMES, SOURCES)


def backwards(apps, schema_editor):
    account = apps.get_model('team_backend', 'ConnectorAccount')
    for row in account.objects.exclude(ids_since=None):
        account.objects.filter(pk=row.pk).update(previous_provider={'until': row.ids_since.isoformat()})
    _metrics(apps, [(b, a) for a, b in RENAMES], [(b, a) for a, b in SOURCES])


class Migration(migrations.Migration):

    dependencies = [
        ('team_backend', '0043_revision_mensual'),
    ]

    operations = [
        migrations.AddField(
            model_name='connectoraccount',
            name='ids_since',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunPython(forwards, backwards),
        migrations.RemoveField(model_name='connectoraccount', name='previous_provider'),
        migrations.RemoveField(model_name='conversation', name='carry'),
        migrations.DeleteModel(name='ProviderIdOriginal'),
        migrations.AlterField(
            model_name='connectoraccount',
            name='provider',
            field=models.CharField(choices=[('fake', 'Simulado (pruebas)'), ('directo', 'LinkedIn directo (navegador)'),
                                            ('linkedin', 'API oficial de LinkedIn'),
                                            ('linkedin_fake', 'API oficial simulada (pruebas)')], max_length=20),
        ),
    ]
