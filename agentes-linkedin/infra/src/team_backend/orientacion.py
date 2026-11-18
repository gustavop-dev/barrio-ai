"""Her orientation: the high-level direction a member gives the team from her results (PLAN-REDISENO).
Writers, the network classifier and the agente líder read it. Like private guidance, it orients decisions and
never appears or is paraphrased in public text.

Each member has her own (organizaciones, phase 4), by the rule of miembros.policy_key: row 1 (the singleton of before
organizations) is the first member's and an installation's without members, untouched; any other member gets her own
row, created empty the first time. One member's orientation never reaches another's texts or decisions."""
from django.db import IntegrityError, transaction
from django.db.models import Max
from django.utils import timezone
from . import miembros
from .models import Orientation
from .permissions import require

MAX_CHARS=4000
LEGACY_PK=1

def row(member=None):
    """Her Orientation row. `member=None`: the default member (MiembroRequerido among several active ones)."""
    member=miembros.resolve(member)
    if miembros.is_first(member):
        return Orientation.objects.get_or_create(pk=LEGACY_PK)[0]
    found=Orientation.objects.filter(member=member).first()
    if found:return found
    for _ in range(3):  # another request may take the same free number: try the next one
        number=(Orientation.objects.aggregate(top=Max('pk'))['top'] or LEGACY_PK)+1
        try:
            with transaction.atomic():
                return Orientation.objects.create(pk=number,member=member)
        except IntegrityError:
            found=Orientation.objects.filter(member=member).first()
            if found:return found
    raise IntegrityError('No se pudo crear la orientación del miembro.')

def text(member=None):
    return (row(member).text or '').strip()

def update(user,value,member=None):
    """Her orientation changed by a person: `member` (the summary's or the review's), else the person's own member."""
    require(user,'approve_actions')
    value=(value or '').strip()
    if len(value)>MAX_CHARS:raise ValueError(f'La orientación supera {MAX_CHARS} caracteres')
    current=row(member if member is not None else miembros.member_for(user))
    current.text=value;current.updated_by=user;current.updated_at=timezone.now();current.save()
    from .jobs import audit
    audit(user,'orientation.updated','orientation' if current.pk==LEGACY_PK else f'orientation:{current.member_id}',chars=len(value))
    return current
