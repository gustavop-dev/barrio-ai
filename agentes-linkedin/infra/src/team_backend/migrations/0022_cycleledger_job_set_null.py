from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('team_backend', '0021_cycle_ledger')]

    operations = [migrations.AlterField(
        model_name='cycleledger',
        name='job',
        field=models.ForeignKey(blank=True, null=True,
                                on_delete=django.db.models.deletion.SET_NULL,
                                to='team_backend.job'),
    )]
