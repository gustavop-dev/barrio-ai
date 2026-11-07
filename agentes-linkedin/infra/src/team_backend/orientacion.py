"""Gustavo's orientation: the high-level direction he gives the team from the results (PLAN-REDISENO).
Writers, the network classifier and the agente líder read it. Like private guidance, it orients decisions and
never appears or is paraphrased in public text."""
from django.utils import timezone
from .models import Orientation
from .permissions import require

MAX_CHARS=4000

def text():
    return (Orientation.current().text or '').strip()

def update(user,value):
    require(user,'approve_actions')
    value=(value or '').strip()
    if len(value)>MAX_CHARS:raise ValueError(f'La orientación supera {MAX_CHARS} caracteres')
    current=Orientation.current()
    current.text=value;current.updated_by=user;current.updated_at=timezone.now();current.save()
    from .jobs import audit
    audit(user,'orientation.updated','orientation',chars=len(value))
    return current
