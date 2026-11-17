from django.db import migrations, models


class Migration(migrations.Migration):
    """BAR-25: the line (projectapp, startup) and the segment of the three-month test a buyer entered the journey with."""

    dependencies = [
        ('team_backend', '0053_entrada_nivel_comprador'),
    ]

    operations = [
        migrations.AddField(
            model_name='buyerjourney',
            name='line',
            field=models.CharField(blank=True, db_index=True, max_length=12),
        ),
        migrations.AddField(
            model_name='buyerjourney',
            name='segment',
            field=models.CharField(blank=True, db_index=True, max_length=24),
        ),
    ]
