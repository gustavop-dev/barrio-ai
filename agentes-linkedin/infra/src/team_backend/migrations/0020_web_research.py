import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies=[('team_backend','0019_imagenes_y_urgencia')]
    operations=[
        migrations.AddField('capture','investigation',models.JSONField(default=dict,blank=True)),
        migrations.AddField('editorialpiece','research',models.JSONField(default=list,blank=True)),
        migrations.CreateModel(name='WebResearchRun',fields=[
            ('key',models.CharField(max_length=160,primary_key=True,serialize=False)),
            ('request_hash',models.CharField(max_length=64)),
            ('created_at',models.DateTimeField(default=django.utils.timezone.now,db_index=True)),
            ('state',models.CharField(max_length=20,default='running')),
            ('result',models.JSONField(default=dict,blank=True)),
        ]),
    ]
