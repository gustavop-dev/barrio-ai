import uuid
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
import team_backend.models


class Migration(migrations.Migration):
    dependencies=[('team_backend','0023_shared_evidence'),migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations=[
        migrations.AddField('galleryphoto','category',models.CharField(max_length=12,default='posts',choices=[('posts','Posts'),('perfil','Perfil')],db_index=True)),
        migrations.AddField('galleryphoto','profile_edit',models.BooleanField(default=False)),
        migrations.AddField('galleryphoto','profile_role',models.CharField(max_length=2,blank=True,choices=[('','Sin asignar'),('01','Pose y sonrisa'),('02','Cuerpo'),('03','Identidad')])),
        migrations.AddField('galleryphoto','profile_version',models.PositiveIntegerField(default=1)),
        migrations.AddField('galleryphoto','profile_consent',models.JSONField(default=dict,blank=True)),
        migrations.AddField('pieceimage','profile_exclusive',models.BooleanField(default=False)),
        migrations.CreateModel(name='ProfileSchedule',fields=[
            ('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),
            ('anchor',models.DateField()),('full_period',models.CharField(max_length=10,blank=True)),
            ('monthly_period',models.CharField(max_length=7,blank=True)),
            ('owner',models.OneToOneField(to=settings.AUTH_USER_MODEL,on_delete=django.db.models.deletion.PROTECT)),
        ]),
        migrations.CreateModel(name='ProfileProposal',fields=[
            ('id',models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False,serialize=False)),
            ('key',models.CharField(max_length=160,unique=True)),('mode',models.CharField(max_length=12,default='full')),
            ('triggers',models.JSONField(default=list,blank=True)),('version',models.PositiveIntegerField(default=1)),
            ('revision',models.PositiveIntegerField(default=1)),('state',models.CharField(max_length=16,default='queued',db_index=True)),
            ('sections',models.JSONField(default=list,blank=True)),('context',models.JSONField(default=dict,blank=True)),
            ('references',models.JSONField(default=list,blank=True)),('history',models.JSONField(default=list,blank=True)),
            ('findings',models.JSONField(default=list,blank=True)),('download_tickets',models.JSONField(default=dict,blank=True)),
            ('photo_choice',models.CharField(max_length=1,blank=True)),
            ('postponed_until',models.DateTimeField(null=True,blank=True)),
            ('created_at',models.DateTimeField(default=django.utils.timezone.now)),('updated_at',models.DateTimeField(auto_now=True)),
            ('owner',models.ForeignKey(to=settings.AUTH_USER_MODEL,on_delete=django.db.models.deletion.PROTECT)),
            ('cycle',models.ForeignKey(to='team_backend.cycleledger',on_delete=django.db.models.deletion.PROTECT,null=True,blank=True)),
        ],options={'ordering':['-created_at']}),
        migrations.CreateModel(name='ProfileAsset',fields=[
            ('id',models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False,serialize=False)),
            ('version',models.PositiveIntegerField()),('kind',models.CharField(max_length=24)),
            ('image',models.FileField(upload_to=team_backend.models.profile_asset_path,max_length=200)),
            ('sha256',models.CharField(max_length=64)),('width',models.PositiveIntegerField()),('height',models.PositiveIntegerField()),
            ('review',models.JSONField(default=dict,blank=True)),('provenance',models.JSONField(default=dict,blank=True)),
            ('proposal',models.ForeignKey(to='team_backend.profileproposal',on_delete=django.db.models.deletion.CASCADE,related_name='assets')),
        ],options={'constraints':[models.UniqueConstraint(fields=('proposal','version','kind'),name='profile_asset_version_kind')]}),
    ]
