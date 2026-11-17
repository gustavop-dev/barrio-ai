"""«Qué les funciona y qué no» to the industry referents (analisis_referentes.py, docs/plan-referentes-industria.md).

ObservedPost keeps the shares LinkedIn counts, the media type the connector recognized and the cached decomposition of
the post (labels and numbers, never its text). Existing rows: shares unknown (null), media unknown (''), no analysis
yet (computed on the first read)."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('team_backend', '0046_referentes_industria_intentos'),
    ]

    operations = [
        migrations.AddField(
            model_name='observedpost',
            name='reposts_count',
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='observedpost',
            name='media',
            field=models.CharField(blank=True, default='', max_length=20),
        ),
        migrations.AddField(
            model_name='observedpost',
            name='analysis',
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
