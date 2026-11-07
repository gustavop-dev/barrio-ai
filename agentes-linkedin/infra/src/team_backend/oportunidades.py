"""Business opportunities (Personas → Oportunidades; Resultados → «¿Genera negocio?»; Calendario → capa Tuyo).
Gustavo registers and moves them by hand for now; the analyst will propose them once the inbox is read.
«Cualificada» means an explicit need, a relevant modality and enough budget and dedication data."""
from django.db import transaction
from django.utils import timezone
from .exceptions import Conflict
from .jobs import audit
from .models import Contact, Opportunity
from .permissions import require

TEXT_FIELDS={'person_name':200,'company':200,'need':4000,'budget':200,'dedication':200,'next_action':300,'notes':8000}
CHOICES={'modality':Opportunity.Modality.values,'channel':Opportunity.Channel.values,'attribution':Opportunity.Attribution.values}
CLOSED=('acuerdo','sin_acuerdo')

def _note(item,event,detail=''):
    item.history=(list(item.history)+[{'at':timezone.now().isoformat(),'event':event,'detail':(detail or '')[:300]}])[-50:]

def _apply(item,data):
    for field,limit in TEXT_FIELDS.items():
        if field in data and data[field] is not None:setattr(item,field,str(data[field]).strip()[:limit])
    for field,values in CHOICES.items():
        if field in data and data[field] is not None:
            if data[field] not in values:raise ValueError(f'Valor inválido para {field}')
            setattr(item,field,data[field])
    if 'next_action_at' in data:item.next_action_at=data['next_action_at']
    if 'contact' in data:
        contact=Contact.objects.filter(id=data['contact']).first() if data['contact'] else None
        if data['contact'] and contact is None:raise ValueError('Persona inexistente')
        item.contact=contact
    if item.contact is None and not item.person_name:raise ValueError('Elige una persona del barrio o escribe el nombre de alguien fuera de la red')

def _set_stage(item,stage):
    if stage not in Opportunity.Stage.values:raise ValueError('Etapa inválida')
    if item.pk and stage==item.stage:return
    previous=item.get_stage_display() if item.pk else None
    item.stage=stage;item.stage_changed_at=timezone.now()
    item.closed_at=timezone.now() if stage in CLOSED else None
    _note(item,'stage' if previous else 'created',f'{previous} → {item.get_stage_display()}' if previous else f'Etapa inicial: {item.get_stage_display()}')

def create(user,data):
    require(user,'approve_actions')
    if data.get('modality') not in Opportunity.Modality.values:raise ValueError('Elige la modalidad')
    item=Opportunity(created_by=user,modality=data['modality'])
    _apply(item,data);_set_stage(item,data.get('stage') or 'conversacion')
    item.save();audit(user,'opportunity.created',item.id,modality=item.modality,stage=item.stage)
    return item

def update(user,opportunity_id,data):
    require(user,'approve_actions')
    with transaction.atomic():
        item=Opportunity.objects.select_for_update().get(id=opportunity_id)
        _apply(item,data)
        if data.get('stage'):_set_stage(item,data['stage'])
        item.updated_at=timezone.now();item.save()
    audit(user,'opportunity.updated',item.id,stage=item.stage)
    return item

def delete(user,opportunity_id):
    require(user,'approve_actions')
    item=Opportunity.objects.filter(id=opportunity_id).first()
    if item is None:raise Conflict('La oportunidad no existe.')
    item.delete();audit(user,'opportunity.deleted',str(opportunity_id))
