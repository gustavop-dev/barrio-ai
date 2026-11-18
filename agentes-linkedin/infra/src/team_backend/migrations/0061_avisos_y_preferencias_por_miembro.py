"""Phase 5 of organizations: notices, preferences and «Vista» are each person's; opportunities say whose they are
(docs/plan-organizaciones.md «Fase 5: lo construido»).

- Notification.member: whose notice it is. The rows of before (kept 7 days) become the first member's.
- OfficePreference.user: whose preferences they are. Row 1 (Gustavo's configuration of before: the pushes he turned off
  or on, his gallery's AI edit) becomes the first member's user's, untouched; anyone else gets her own row later.
- InboxSeen.item_id up to 200 characters: another user's «Vista» carries «u:<user id>:» before the card id; the rows of
  before stay as they are (the first member's user's).
- Opportunity.member (who registered it) and Opportunity.origin_member (whose person it came from): the rows of before
  get the member of the user who created them, else the first member; their origin, the owner of their person's
  account, else the same member.

Safe on the production database: a few columns on small tables and UPDATEs of tens of rows, in the migration's
transaction. Idempotent. Without members (a fresh installation, the CI) the data step does nothing; bootstrap_local's
first member adopts them later (miembros.adopt_content). Reversible: the reverse data step empties what it filled, then
the columns go."""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def forwards(apps, schema_editor):
    Member = apps.get_model('team_backend', 'Member')
    first = Member.objects.order_by('created_at', 'pk').first()
    if first is None:
        return
    apps.get_model('team_backend', 'Notification').objects.filter(member__isnull=True).update(member=first)
    apps.get_model('team_backend', 'OfficePreference').objects.filter(pk=1, user__isnull=True).update(user_id=first.user_id)
    members = dict(Member.objects.values_list('user_id', 'pk'))
    Opportunity = apps.get_model('team_backend', 'Opportunity')
    for item in Opportunity.objects.filter(models.Q(member__isnull=True) | models.Q(origin_member__isnull=True)).select_related('contact__account'):
        member_id = item.member_id or members.get(item.created_by_id) or first.pk
        account = item.contact.account if item.contact_id else None
        origin_id = item.origin_member_id or (account.member_id if account is not None and account.member_id else member_id)
        Opportunity.objects.filter(pk=item.pk).update(member_id=member_id, origin_member_id=origin_id)


def backwards(apps, schema_editor):
    apps.get_model('team_backend', 'Notification').objects.update(member=None)
    apps.get_model('team_backend', 'OfficePreference').objects.filter(pk=1).update(user=None)
    apps.get_model('team_backend', 'OfficePreference').objects.exclude(pk=1).delete()
    apps.get_model('team_backend', 'Opportunity').objects.update(member=None, origin_member=None)


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('team_backend', '0060_contenido_del_primer_miembro'),
    ]

    operations = [
        migrations.AddField(
            model_name='notification',
            name='member',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE,
                                    related_name='notifications', to='team_backend.member'),
        ),
        migrations.AddField(
            model_name='officepreference',
            name='user',
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE,
                                       related_name='office_preference', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name='inboxseen',
            name='item_id',
            field=models.CharField(max_length=200, primary_key=True, serialize=False),
        ),
        migrations.AddField(
            model_name='opportunity',
            name='member',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                    related_name='registered_opportunities', to='team_backend.member'),
        ),
        migrations.AddField(
            model_name='opportunity',
            name='origin_member',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                    related_name='brought_opportunities', to='team_backend.member'),
        ),
        migrations.RunPython(forwards, backwards),
    ]
