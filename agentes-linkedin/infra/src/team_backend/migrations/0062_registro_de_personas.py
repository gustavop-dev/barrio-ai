"""Phase 6 of organizations: the organization's shared register of people (docs/plan-organizaciones.md «Fase 6: lo
construido»; team_backend/registro.py). Schema only: Person (one card per LinkedIn person in an organization, with the
member who attends her), Contact.person (the card of each member's contact), PostClaim (a referent's post admits one
member's comment) and ConnectorAccount.linkedin_ids (the account's own profile ids: a colleague is never a prospect).
New tables and two nullable/empty columns: nothing is rewritten. Reversible (the columns and tables go)."""
import django.db.models.deletion
import django.utils.timezone
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('team_backend', '0061_avisos_y_preferencias_por_miembro'),
    ]

    operations = [
        migrations.AddField(
            model_name='connectoraccount',
            name='linkedin_ids',
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.CreateModel(
            name='Person',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('provider_user_id', models.CharField(max_length=200)),
                ('public_identifier', models.CharField(blank=True, max_length=100)),
                ('display_name', models.CharField(blank=True, max_length=200)),
                ('headline', models.TextField(blank=True)),
                ('company', models.CharField(blank=True, max_length=120)),
                ('classification', models.JSONField(blank=True, default=dict)),
                ('stage', models.CharField(choices=[('candidata', 'Candidata'), ('seguida', 'Seguida'), ('invitada', 'Invitada'), ('conectada', 'Conectada'), ('descartada', 'Descartada'), ('descanso', 'En descanso')], default='candidata', max_length=12)),
                ('excluded', models.CharField(blank=True, choices=[('no_contactar', 'Pidió no ser contactada'), ('rechazo_linkedin', 'LinkedIn rechazó la invitación'), ('descarte', 'Descartada para toda la organización')], max_length=20)),
                ('excluded_reason', models.TextField(blank=True)),
                ('excluded_at', models.DateTimeField(blank=True, null=True)),
                ('owned_since', models.DateTimeField(blank=True, null=True)),
                ('touch', models.CharField(blank=True, max_length=10)),
                ('touch_proposal', models.UUIDField(blank=True, null=True)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('updated_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('assigned_to', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='+', to='team_backend.member')),
                ('excluded_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='+', to='team_backend.member')),
                ('organization', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='people', to='team_backend.organization')),
                ('owner', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='people', to='team_backend.member')),
            ],
            options={
                'ordering': ['-updated_at'],
            },
        ),
        migrations.AddField(
            model_name='contact',
            name='person',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='contacts', to='team_backend.person'),
        ),
        migrations.CreateModel(
            name='PostClaim',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('provider_post_id', models.CharField(max_length=200)),
                ('proposal', models.UUIDField(blank=True, null=True)),
                ('claimed_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('member', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='post_claims', to='team_backend.member')),
                ('organization', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='post_claims', to='team_backend.organization')),
            ],
        ),
        migrations.AddConstraint(
            model_name='person',
            constraint=models.UniqueConstraint(fields=('organization', 'provider_user_id'), name='one_person_per_organization'),
        ),
        migrations.AddConstraint(
            model_name='postclaim',
            constraint=models.UniqueConstraint(fields=('organization', 'provider_post_id'), name='one_comment_claim_per_post'),
        ),
    ]
