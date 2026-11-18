"""Business opportunities (Personas → Oportunidades; Resultados → «¿Genera negocio?»; Calendario → capa Tuyo).
Gustavo registers and moves them by hand for now; the analyst will propose them once the inbox is read.
«Cualificada» means an explicit need, a relevant modality and enough budget and dedication data.

The organization's one funnel (organizaciones, phase 5): every member sees and moves every opportunity. Each says who
registered it (`member`) and whose person it came from (`origin_member`, the owner of its person's account); a member
can only link a person of her own (another member's is «Persona inexistente», as one that does not exist)."""
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from . import alcance, miembros
from .exceptions import Conflict
from .jobs import audit
from .models import Contact, Opportunity
from .permissions import require

TEXT_FIELDS={'person_name':200,'company':200,'need':4000,'budget':200,'dedication':200,'next_action':300,'notes':8000}
CHOICES={'modality':Opportunity.Modality.values,'channel':Opportunity.Channel.values,'attribution':Opportunity.Attribution.values}
CLOSED=('acuerdo','sin_acuerdo')

def _note(item,event,detail='',stage=None):
    entry={'at':timezone.now().isoformat(),'event':event,'detail':(detail or '')[:300]}
    if stage:entry['stage']=stage  # lets Resultados count when each stage was reached
    item.history=(list(item.history)+[entry])[-50:]

def hers(rows,member):
    """The opportunities she brought or registered: the next steps of her calendar. Every one without members."""
    if alcance._require(member) is None:return rows
    own=Q(origin_member=member)|Q(member=member)
    if miembros.is_first(member):own|=Q(origin_member__isnull=True,member__isnull=True)
    return rows.filter(own)

def _origin(item):
    """Whose person it is: the owner of its contact's account; without a person, whoever registered it."""
    if item.contact_id is not None and item.contact.account_id:
        owner=miembros.member_of_account(item.contact.account)
        if owner is not None:return owner
    return item.member

def _apply(item,data,user=None):
    for field,limit in TEXT_FIELDS.items():
        if field in data and data[field] is not None:setattr(item,field,str(data[field]).strip()[:limit])
    for field,values in CHOICES.items():
        if field in data and data[field] is not None:
            if data[field] not in values:raise ValueError(f'Valor inválido para {field}')
            setattr(item,field,data[field])
    if 'next_action_at' in data:item.next_action_at=data['next_action_at']
    if 'contact' in data:
        people=Contact.objects.all() if user is None else alcance.de(Contact.objects.all(),miembros.member_for(user))  # hers
        contact=people.filter(id=data['contact']).first() if data['contact'] else None
        if data['contact'] and contact is None:raise ValueError('Persona inexistente')
        item.contact=contact
    if item.contact is None and not item.person_name:raise ValueError('Elige una persona del barrio o escribe el nombre de alguien fuera de la red')

def _set_stage(item,stage):
    if stage not in Opportunity.Stage.values:raise ValueError('Etapa inválida')
    if item.pk and stage==item.stage:return
    previous=item.get_stage_display() if item.pk else None
    item.stage=stage;item.stage_changed_at=timezone.now()
    item.closed_at=timezone.now() if stage in CLOSED else None
    _note(item,'stage' if previous else 'created',f'{previous} → {item.get_stage_display()}' if previous else f'Etapa inicial: {item.get_stage_display()}',stage)

def create(user,data):
    require(user,'approve_actions')
    if data.get('modality') not in Opportunity.Modality.values:raise ValueError('Elige la modalidad')
    item=Opportunity(created_by=user,modality=data['modality'],member=miembros.member_of_user(user))
    _apply(item,data,user);_set_stage(item,data.get('stage') or 'conversacion')
    item.origin_member=_origin(item)
    item.save();audit(user,'opportunity.created',item.id,modality=item.modality,stage=item.stage)
    if item.contact_id:
        from . import comprador, entrega_lead
        entrega_lead.on_opportunity(item)  # phase 6: a lead waiting for this person is handed over to it (PRS-09: he created it)
        comprador.on_contact(item.contact,'oportunidad')
    _notify(item)
    return item

def _notify(item):
    from .notificaciones import avisar
    name=item.contact.display_name if item.contact else item.person_name
    detail=f'Siguiente paso: {item.next_action}' if item.next_action else item.get_modality_display()
    # The funnel is everyone's; the notice goes to whoever brought the person (else who registered it).
    avisar('opportunity',f'Oportunidad con {name}: {item.get_stage_display().lower()}',detail,
           link=f'/personas/{item.contact_id}' if item.contact_id else '/personas?pestana=oportunidades',ref=f'opportunity:{item.id}:{item.stage}',
           member=item.origin_member or item.member)

def update(user,opportunity_id,data):
    require(user,'approve_actions')
    with transaction.atomic():
        item=Opportunity.objects.select_for_update().get(id=opportunity_id)
        _apply(item,data,user)
        if 'contact' in data:item.origin_member=_origin(item)
        if data.get('stage'):_set_stage(item,data['stage'])
        moved=bool(data.get('stage'))
        item.updated_at=timezone.now();item.save()
    audit(user,'opportunity.updated',item.id,stage=item.stage)
    if item.contact_id:
        from . import comprador
        comprador.on_contact(item.contact,'oportunidad')
    if moved:_notify(item)
    return item

def delete(user,opportunity_id):
    require(user,'approve_actions')
    item=Opportunity.objects.filter(id=opportunity_id).first()
    if item is None:raise Conflict('La oportunidad no existe.')
    item.delete();audit(user,'opportunity.deleted',str(opportunity_id))
