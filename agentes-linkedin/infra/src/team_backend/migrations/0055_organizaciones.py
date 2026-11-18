"""Organizations, phase 1 (docs/plan-organizaciones.md): Organization, Member and ConnectorAccount.member.

Data: when this database has a human to name, the organization ProjectApp gets its first member, admin, and every
existing account (today the two of Gustavo: the official API one and the `directo` one) becomes hers. Whose user:
- the user of REFERENTS_GUSTAVO_USERNAME (settings, else the environment, default 'gustavo') if it exists and is active;
- else the first active superuser by date joined that is not a technical user (barrio-autopiloto, linkedin-service) and
  has a usable password.
With neither (an empty database, the CI's, QA before seed_qa) nothing is created: accounts stay without a member and
every selector behaves as before organizations; bootstrap_local and seed_qa make the member later
(miembros.ensure_first_member applies the same rule). Reverse: the tables and the column go; nothing else changed."""
import os
import uuid

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models

ROBOTS = ('barrio-autopiloto', 'linkedin-service')


def first_member(apps, schema_editor):
    User = apps.get_model(*settings.AUTH_USER_MODEL.split('.'))
    Organization = apps.get_model('team_backend', 'Organization')
    Member = apps.get_model('team_backend', 'Member')
    ConnectorAccount = apps.get_model('team_backend', 'ConnectorAccount')
    if Member.objects.exists():
        return
    username = getattr(settings, 'REFERENTS_GUSTAVO_USERNAME', os.environ.get('REFERENTS_GUSTAVO_USERNAME', 'gustavo'))
    owner = User.objects.filter(username=username, is_active=True).exclude(username__in=ROBOTS).first()
    if owner is None:
        owner = (User.objects.filter(is_superuser=True, is_active=True).exclude(username__in=ROBOTS)
                 .exclude(password__startswith='!').order_by('date_joined', 'pk').first())
    if owner is None:
        return
    organization, _ = Organization.objects.get_or_create(slug='projectapp', defaults={'name': 'ProjectApp'})
    name = ' '.join(filter(None, [owner.first_name.strip(), owner.last_name.strip()])) or 'Gustavo'
    member = Member.objects.create(organization=organization, user=owner, display_name=name[:120], role='Fundador',
                                   is_admin=True, active=True)
    ConnectorAccount.objects.filter(member__isnull=True).update(member=member)


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('team_backend', '0054_linea_segmento_comprador'),
    ]

    operations = [
        migrations.CreateModel(
            name='Organization',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=120)),
                ('slug', models.SlugField(max_length=60, unique=True)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
            ],
        ),
        migrations.CreateModel(
            name='Member',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('display_name', models.CharField(max_length=120)),
                ('role', models.CharField(blank=True, max_length=120)),
                ('active', models.BooleanField(default=True)),
                ('is_admin', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('organization', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='members',
                                                   to='team_backend.organization')),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name='member',
                                              to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['created_at']},
        ),
        migrations.AddField(
            model_name='connectoraccount',
            name='member',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                                    related_name='accounts', to='team_backend.member'),
        ),
        migrations.RunPython(first_member, migrations.RunPython.noop),
    ]
