from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('team_backend', '0012_notificaciones')]

    operations = [
        migrations.AddField(model_name='worker', name='lane', field=models.CharField(default='todas', max_length=20)),
        migrations.AddField(model_name='actionexecution', name='wrote', field=models.BooleanField(default=True)),
    ]
