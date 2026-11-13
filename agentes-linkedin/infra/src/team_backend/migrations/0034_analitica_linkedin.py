"""Creator analytics of a `directo` account (docs/plan-linkedin-directo.md, «Analítica»): days, posts, captures, ranges and
the import log. New tables only; nothing existing changes."""
import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('team_backend', '0033_proveedor_directo'),
    ]

    operations = [
        migrations.CreateModel(
            name='AnalyticsDay',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('day', models.DateField()),
                ('impressions', models.IntegerField(blank=True, null=True)),
                ('engagements', models.IntegerField(blank=True, null=True)),
                ('new_followers', models.IntegerField(blank=True, null=True)),
                ('updated_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('account', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='analytics_days', to='team_backend.connectoraccount')),
            ],
            options={
                'ordering': ['account', 'day'],
                'constraints': [models.UniqueConstraint(fields=('account', 'day'), name='one_analytics_day')],
            },
        ),
        migrations.CreateModel(
            name='AnalyticsImport',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('start', models.DateField()),
                ('end', models.DateField()),
                ('trigger', models.CharField(choices=[('diaria', 'Importación diaria'), ('manual', 'A mano'), ('carga_inicial', 'Carga inicial')], default='manual', max_length=16)),
                ('state', models.CharField(choices=[('running', 'En curso'), ('ok', 'Importada'), ('error', 'Fallida')], db_index=True, default='running', max_length=10)),
                ('error_kind', models.CharField(blank=True, max_length=40)),
                ('error', models.TextField(blank=True)),
                ('rows', models.JSONField(blank=True, default=dict)),
                ('sheets', models.JSONField(blank=True, default=list)),
                ('started_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('finished_at', models.DateTimeField(blank=True, null=True)),
                ('account', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='analytics_imports', to='team_backend.connectoraccount')),
            ],
            options={
                'ordering': ['-started_at'],
                'indexes': [models.Index(fields=['account', 'state', 'started_at'], name='analytics_import_last')],
            },
        ),
        migrations.CreateModel(
            name='AnalyticsPost',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('post_urn', models.CharField(max_length=60)),
                ('url', models.TextField(blank=True)),
                ('published', models.DateField(blank=True, null=True)),
                ('kind', models.CharField(blank=True, max_length=60)),
                ('impressions', models.IntegerField(blank=True, null=True)),
                ('network_pct', models.FloatField(blank=True, null=True)),
                ('outside_pct', models.FloatField(blank=True, null=True)),
                ('members_reached', models.IntegerField(blank=True, null=True)),
                ('followers_gained', models.IntegerField(blank=True, null=True)),
                ('profile_views', models.IntegerField(blank=True, null=True)),
                ('reactions', models.IntegerField(blank=True, null=True)),
                ('comments', models.IntegerField(blank=True, null=True)),
                ('shares', models.IntegerField(blank=True, null=True)),
                ('saves', models.IntegerField(blank=True, null=True)),
                ('sends', models.IntegerField(blank=True, null=True)),
                ('button_clicks', models.IntegerField(blank=True, null=True)),
                ('first_seen_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('last_seen_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('account', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='analytics_posts', to='team_backend.connectoraccount')),
                ('piece', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='analytics_posts', to='team_backend.editorialpiece')),
            ],
            options={
                'ordering': ['account', '-published'],
                'constraints': [models.UniqueConstraint(fields=('account', 'post_urn'), name='one_analytics_post')],
            },
        ),
        migrations.CreateModel(
            name='AnalyticsRange',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('start', models.DateField()),
                ('end', models.DateField()),
                ('impressions', models.IntegerField(blank=True, null=True)),
                ('members_reached', models.IntegerField(blank=True, null=True)),
                ('top_by_engagements', models.JSONField(blank=True, default=list)),
                ('top_by_impressions', models.JSONField(blank=True, default=list)),
                ('content', models.JSONField(blank=True, null=True)),
                ('captured_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('account', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='analytics_ranges', to='team_backend.connectoraccount')),
            ],
            options={
                'ordering': ['account', '-captured_at'],
                'constraints': [models.UniqueConstraint(fields=('account', 'start', 'end'), name='one_analytics_range')],
            },
        ),
        migrations.CreateModel(
            name='AnalyticsSnapshot',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('day', models.DateField()),
                ('followers', models.IntegerField(blank=True, null=True)),
                ('audience', models.JSONField(blank=True, default=list)),
                ('captured_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('account', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='analytics_snapshots', to='team_backend.connectoraccount')),
            ],
            options={
                'ordering': ['account', '-day'],
                'constraints': [models.UniqueConstraint(fields=('account', 'day'), name='one_analytics_snapshot')],
            },
        ),
    ]
