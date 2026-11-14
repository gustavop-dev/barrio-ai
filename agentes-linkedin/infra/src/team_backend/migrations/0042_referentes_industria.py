"""Industry referents and «what worked for them» (docs/plan-referentes-industria.md). Numbered 0042 on purpose: 0036–0041
are taken by other open branches; when they land, this dependency moves to the last of them (or a merge migration).
Existing rows keep their meaning: every referent is a niche voice, every review a monthly one."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('team_backend', '0035_prueba_diaria'),
    ]

    operations = [
        migrations.AddField(
            model_name='referent',
            name='kind',
            field=models.CharField(choices=[('nicho', 'Voz del nicho'), ('industria', 'Referente de industria')], default='nicho', max_length=16),
        ),
        migrations.RemoveConstraint(
            model_name='referentreview',
            name='unique_referent_month',
        ),
        migrations.AddField(
            model_name='referentreview',
            name='kind',
            field=models.CharField(default='mensual', max_length=16),
        ),
        migrations.AddConstraint(
            model_name='referentreview',
            constraint=models.UniqueConstraint(fields=('account', 'month', 'kind'), name='unique_referent_month_kind'),
        ),
        migrations.AddField(
            model_name='observedpost',
            name='outlier',
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name='observedpost',
            name='structure',
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name='observedpost',
            name='audience',
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
