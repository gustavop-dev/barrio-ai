"""Another industry search in the same month when every earlier one ended without proposals (docs/plan-referentes-industria.md).

Each attempt is its own ReferentReview (its dossier, notices, ledger key and research keys); the earlier one is closed by
referentes_industria.supersede. Existing rows are attempt 1, so the monthly batch and the first search of a month keep
their meaning. The new constraint is created before the old one is dropped: the table is never without one."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('team_backend', '0045_biblioteca_clases_01_12'),
    ]

    operations = [
        migrations.AddField(
            model_name='referentreview',
            name='attempt',
            field=models.PositiveSmallIntegerField(default=1),
        ),
        migrations.AddConstraint(
            model_name='referentreview',
            constraint=models.UniqueConstraint(fields=('account', 'month', 'kind', 'attempt'), name='unique_referent_month_kind_attempt'),
        ),
        migrations.RemoveConstraint(
            model_name='referentreview',
            name='unique_referent_month_kind',
        ),
    ]
