"""Phase 4 of organizations: the content of before organizations is the first member's (docs/plan-organizaciones.md).

Every piece, weekly plan, weekly summary, monthly review, audience snapshot, team question, capture and gallery photo
without a member becomes the first member's (the oldest member, as miembros.first_member_id); a capture or a photo of
someone who is a member is hers instead (its `created_by`). The orientation of before (row 1) is marked hers too. Her
memory needs no move: the keys of before are the first member's (hechos.py), like her rhythm's audit rows (phase 2).

Safe on the production database: a handful of UPDATEs on small tables (tens to a few hundred rows), each one only on rows
without a member, in the migration's transaction. Idempotent: run again, it finds nothing to move. Without members (a fresh
installation, the CI) it does nothing; bootstrap_local's first member adopts them later (miembros.ensure_first_member).
Reversible: the reverse step empties `member` on the rows of the first member (the state before this step); 0059's reverse
then drops the columns and brings back the one-per-day and one-per-week constraints, which only fit while one member has
content."""
from django.db import migrations
from django.db.models import F

TABLES = ('EditorialPiece', 'WeeklyPlan', 'WeeklySummary', 'MonthlyReview', 'AudienceSnapshot', 'TeamQuestion')
UPLOADS = ('Capture', 'GalleryPhoto')


def forwards(apps, schema_editor):
    Member = apps.get_model('team_backend', 'Member')
    first = Member.objects.order_by('created_at', 'pk').first()
    if first is None:
        return
    for name in TABLES:
        apps.get_model('team_backend', name).objects.filter(member__isnull=True).update(member=first)
    users = dict(Member.objects.values_list('user_id', 'pk'))
    for name in UPLOADS:
        model = apps.get_model('team_backend', name)
        for user_id, member_id in users.items():
            model.objects.filter(member__isnull=True, created_by_id=user_id).update(member_id=member_id)
        model.objects.filter(member__isnull=True).update(member=first)
    # A photo of a capture is of that capture's member.
    GalleryPhoto = apps.get_model('team_backend', 'GalleryPhoto')
    for photo in GalleryPhoto.objects.filter(capture__isnull=False).exclude(member_id=F('capture__member_id')):
        photo.member_id = photo.capture.member_id
        photo.save(update_fields=['member'])
    apps.get_model('team_backend', 'Orientation').objects.filter(pk=1, member__isnull=True).update(member=first)


def backwards(apps, schema_editor):
    Member = apps.get_model('team_backend', 'Member')
    first = Member.objects.order_by('created_at', 'pk').first()
    if first is None:
        return
    for name in TABLES + UPLOADS:
        apps.get_model('team_backend', name).objects.filter(member=first).update(member=None)
    apps.get_model('team_backend', 'Orientation').objects.filter(pk=1).update(member=None)


class Migration(migrations.Migration):

    dependencies = [
        ('team_backend', '0059_contenido_por_miembro'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
