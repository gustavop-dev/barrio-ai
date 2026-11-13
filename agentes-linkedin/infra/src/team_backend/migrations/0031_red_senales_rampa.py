"""Contact.signals, and the invitation ramp Gustavo asked for on 12/11/2026 («al menos unas 15 por día»).

The ramp stages change from 5/20, 10/50, 20/100 (start at the first) to 8/40, 16/80, 20/100 (start at the second; the
first is the step down after weak acceptance). The ramp state is an append-only audit record, so the current state
is re-recorded in the new scale instead of rewritten: first or second old stage -> 16/80, third -> 20/100."""
from django.db import migrations, models
from django.utils import timezone


def ramp_v2(apps, schema_editor):
    AuditEvent = apps.get_model('team_backend', 'AuditEvent')
    last = AuditEvent.objects.filter(action='network.ramp', target='member').order_by('-created_at', '-id').first()
    if last is None:
        return  # a new ramp starts at 16/80 by itself
    now = timezone.now()
    state = dict(last.metadata or {})
    old = int(state.get('stage') or 0)
    state.update(stage=2 if old >= 2 else 1, previous_scale_stage=old, scale='8/40,16/80,20/100',
                 stage_since=now.isoformat(), reviewed_at=now.isoformat(),
                 reason='Rampa nueva de Gustavo (12/11/2026): arranca en 16 invitaciones por día')
    AuditEvent.objects.create(action='network.ramp', target='member', metadata=state, created_at=now)


class Migration(migrations.Migration):

    dependencies = [
        ('team_backend', '0030_catalogo_biblioteca'),
    ]

    operations = [
        migrations.AddField(
            model_name='contact',
            name='signals',
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.RunPython(ramp_v2, migrations.RunPython.noop),
    ]
