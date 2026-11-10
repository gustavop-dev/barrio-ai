from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('team_backend', '0026_profile_strategy')]

    operations = [
        migrations.AddField('capture', 'publish_at', models.DateTimeField(blank=True, null=True)),
        migrations.AddField('capture', 'publish_at_evidence', models.TextField(blank=True)),
    ]
