import uuid
import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models

CHOICES=[('no','No editar'),('auto','Que decida el equipo'),('si','Editar')]


def forwards(apps,schema_editor):
    apps.get_model('team_backend','GalleryPhoto').objects.filter(allow_ai_edit=False).update(ai_edit='no')
    apps.get_model('team_backend','OfficePreference').objects.filter(gallery_ai_edit_default=False).update(gallery_ai_edit='no')


def backwards(apps,schema_editor):
    for model,old,new in [('GalleryPhoto','allow_ai_edit','ai_edit'),('OfficePreference','gallery_ai_edit_default','gallery_ai_edit')]:
        rows=apps.get_model('team_backend',model).objects
        rows.update(**{old:True})
        rows.filter(**{new:'no'}).update(**{old:False})


class Migration(migrations.Migration):
    dependencies=[('team_backend','0018_push_enabled')]
    operations=[
        migrations.AddField('galleryphoto','ai_edit',models.CharField(max_length=4,choices=CHOICES,default='auto')),
        migrations.AddField('officepreference','gallery_ai_edit',models.CharField(max_length=4,choices=CHOICES,default='auto')),
        migrations.RunPython(forwards,backwards),
        migrations.RemoveField('galleryphoto','allow_ai_edit'),
        migrations.RemoveField('officepreference','gallery_ai_edit_default'),
        migrations.AddField('galleryphoto','instruction',models.TextField(blank=True)),
        migrations.AddField('galleryphoto','instruction_kind',models.CharField(max_length=12,blank=True)),
        migrations.AlterField('capture','purpose',models.CharField(max_length=12,blank=True,choices=[('post','Idea para un post'),('propuesta','Propuesta de post'),('dato','Dato sobre mí'),('respuesta','Responde una pregunta'),('galeria','Foto para la galería')])),
        migrations.AddField('capture','ai_edit',models.CharField(max_length=4,choices=CHOICES,default='auto')),
        migrations.AddField('capture','publish_asap',models.BooleanField(default=False,db_index=True)),
        migrations.AddField('capture','publish_asap_evidence',models.TextField(blank=True)),
        migrations.AddField('capture','publish_asap_not_before',models.DateField(null=True,blank=True)),
        migrations.AddField('capture','publish_asap_expected_slot',models.DateTimeField(null=True,blank=True)),
        migrations.AddField('capture','publish_asap_reason',models.TextField(blank=True)),
        migrations.AddField('capture','understanding',models.JSONField(default=dict,blank=True)),
        migrations.AddField('editorialpiece','image_kind',models.CharField(max_length=16,blank=True)),
        migrations.AddField('editorialpiece','image_reason',models.TextField(blank=True)),
        migrations.AddField('editorialpiece','image_spec',models.JSONField(default=dict,blank=True)),
        migrations.AddField('editorialpiece','image_review',models.JSONField(default=dict,blank=True)),
        migrations.AddField('editorialpiece','image_document',models.FileField(upload_to='piezas/documentos',max_length=200,blank=True)),
        migrations.AddField('editorialpiece','image_document_sha256',models.CharField(max_length=64,blank=True)),
        migrations.CreateModel(name='PieceImage',fields=[
            ('id',models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False,serialize=False)),
            ('position',models.PositiveSmallIntegerField(default=1)),
            ('kind',models.CharField(max_length=16)),
            ('image',models.FileField(upload_to='piezas/imagenes',max_length=200)),
            ('mime',models.CharField(max_length=40,default='image/png')),
            ('width',models.PositiveIntegerField()),('height',models.PositiveIntegerField()),
            ('sha256',models.CharField(max_length=64)),('alt',models.TextField()),
            ('edited',models.BooleanField(default=False)),
            ('ai_edit',models.CharField(max_length=4,choices=CHOICES,default='no')),
            ('reason',models.TextField(blank=True)),('template',models.CharField(max_length=20,blank=True)),
            ('data',models.JSONField(default=dict,blank=True)),('review',models.JSONField(default=dict,blank=True)),
            ('created_at',models.DateTimeField(default=django.utils.timezone.now)),
            ('piece',models.ForeignKey(to='team_backend.editorialpiece',related_name='images',on_delete=django.db.models.deletion.CASCADE)),
            ('source_photo',models.ForeignKey(to='team_backend.galleryphoto',related_name='uses',on_delete=django.db.models.deletion.CASCADE,null=True,blank=True)),
        ],options={'ordering':['position'],'constraints':[models.UniqueConstraint(fields=['piece','position'],name='one_image_per_piece_position')]}),
    ]
