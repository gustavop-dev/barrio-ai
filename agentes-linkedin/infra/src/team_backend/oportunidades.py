"""Business opportunities (Resultados: «¿Genera negocio?»; Personas: mark a person as an opportunity).
Gustavo registers and moves them by hand for now; the analyst will propose them once the inbox is read."""
from django.db import transaction
from django.utils import timezone
from .exceptions import Conflict
from .jobs import audit
from .models import Contact, Opportunity
from .permissions import require

FIELDS=('title','modality','origin','notes')

def _note(item,event,detail=''):
    item.history=(list(item.history)+[{'at':timezone.now().isoformat(),'event':event,'detail':(detail or '')[:300]}])[-50:]

def create(user,title,modality,origin='outbound',contact_id=None,notes='',stage='conversacion'):
    require(user,'approve_actions')
    if not (title or '').strip():raise ValueError('La oportunidad necesita un título')
    if modality not in Opportunity.Modality.values:raise ValueError('Modalidad inválida')
    if origin not in Opportunity.Origin.values or stage not in Opportunity.Stage.values:raise ValueError('Origen o etapa inválidos')
    contact=Contact.objects.filter(id=contact_id).first() if contact_id else None
    if contact_id and contact is None:raise ValueError('Persona inexistente')
    item=Opportunity(title=title.strip()[:200],modality=modality,origin=origin,stage=stage,notes=(notes or '').strip(),contact=contact,created_by=user)
    _note(item,'created',f'Etapa inicial: {item.get_stage_display()}')
    if stage in ('acuerdo','perdida'):item.closed_at=timezone.now()
    item.save();audit(user,'opportunity.created',item.id,modality=modality,stage=stage)
    return item

def update(user,opportunity_id,**changes):
    require(user,'approve_actions')
    with transaction.atomic():
        item=Opportunity.objects.select_for_update().get(id=opportunity_id)
        stage=changes.pop('stage',None)
        for field in FIELDS:
            if field in changes and changes[field] is not None:
                value=changes[field].strip() if isinstance(changes[field],str) else changes[field]
                if field=='modality' and value not in Opportunity.Modality.values:raise ValueError('Modalidad inválida')
                if field=='origin' and value not in Opportunity.Origin.values:raise ValueError('Origen inválido')
                if field=='title' and not value:raise ValueError('La oportunidad necesita un título')
                setattr(item,field,value)
        if stage and stage!=item.stage:
            if stage not in Opportunity.Stage.values:raise ValueError('Etapa inválida')
            previous=item.get_stage_display();item.stage=stage
            _note(item,'stage',f'{previous} → {item.get_stage_display()}')
            item.closed_at=timezone.now() if stage in ('acuerdo','perdida') else None
        item.updated_at=timezone.now();item.save()
    audit(user,'opportunity.updated',item.id,stage=item.stage)
    return item
