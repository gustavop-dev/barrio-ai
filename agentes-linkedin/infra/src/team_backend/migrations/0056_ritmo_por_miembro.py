"""Organizations, phase 2 (docs/plan-organizaciones.md): one LinkedIn rhythm per member.

Schema only: Member.settings, the variables of her rhythm she sets apart from the .env (miembros.MEMBER_SETTINGS), empty
for every existing member, so everything keeps the .env's values.

No data moves. The rhythm already lived on audit events with target 'member' (the schedule, the ramp, the notes' tier
and block, the provider limits, the profile reads); that key stays the first member's (miembros.policy_key, the oldest
member: Gustavo in production), so his ramp, his month's notes, his day's schedule and today's reads continue exactly
where they are, also if this migration is reverted or the previous code is deployed again. A later member writes under
'member:<id>'. Reverse: the column goes; nothing else changed."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('team_backend', '0055_organizaciones'),
    ]

    operations = [
        migrations.AddField(
            model_name='member',
            name='settings',
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
