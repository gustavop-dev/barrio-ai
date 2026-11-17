from django.db import migrations, models


class Migration(migrations.Migration):
    """BAR-24: the level and score a buyer entered the journey with (nivel_comprador), kept once."""

    dependencies = [
        ('team_backend', '0052_respuesta_comprador'),
    ]

    operations = [
        migrations.AddField(
            model_name='buyerjourney',
            name='entry_level',
            field=models.CharField(blank=True, max_length=14),
        ),
        migrations.AddField(
            model_name='buyerjourney',
            name='entry_score',
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='buyerjourney',
            name='entry_score_version',
            field=models.CharField(blank=True, max_length=20),
        ),
    ]
