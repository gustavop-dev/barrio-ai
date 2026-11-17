"""Phase 6 of docs/plan-outbound.md (BAR-23): the weekly reading of the buyer's funnel, deterministic (no model call).
LI-12-M001-K04's diagnosis table («Dónde se rompe, y qué tocar») and its rule: fix ONE stage at a time, starting with
the first one that breaks. The stages are read in the funnel's order; the first one under its threshold is where it
breaks, with the table's most probable cause and its one change. Under 30 invitations nothing is judged (LI-12-M001-K03,
comprador.SMALL_SAMPLE). Plus this week against the last one and the drafts pending against the ones sent.

Thresholds: acceptance under 20 % is the course's (the teacher: «20 % o 10 % sería trágico»); the course gives no number
for the others, so they are the team's and named as such: inventory (half or more of the chosen still not invited after
21 days, and at least 10), the leak between accepting and getting a message (20 % or more of those accepted more than
21 days ago never got one: phase 3 waits up to 21 days by design), replies (under 10 % of those who got a message) and
meetings (under 20 % of those who replied, with at least 5 replies).

Slack: on Mondays, inside READ_WINDOW, on the summaries channel (alertas_slack.lectura_semanal_embudo), five lines at
most.

BAR-25 (NETWORK_PROJECTAPP_BUYER_ENABLED): the same reading by line (projectapp, startup) and by segment of the ProjectApp
buyers (by the line and segment they entered with), each with its own sample rule, and one line on the three-month test:
week N of 13, invitations per segment and whether any has a sample yet; review on 17/02/2027. Off, none of it."""
from datetime import timedelta
from django.utils import timezone
from . import comprador
from .models import BuyerJourney

Step=BuyerJourney.Step
STALE=timedelta(days=21)
INVENTORY_SHARE=50;INVENTORY_MIN=10
ACCEPTANCE_MIN=20   # course: LI-12-M001-K04 (oral: «20 % o 10 % sería trágico»)
LEAK_SHARE=20
REPLY_MIN=10;REPLY_SAMPLE=10
MEETING_MIN=20;MEETING_SAMPLE=5
# (stage, what you see, most probable cause, the one change, source): LI-12-M001-K04's table, in the funnel's order.
TABLE=(('inventario','Muchos elegidos sin contactar','Inventario parado','Reactiva la campaña o limpia la lista','equipo'),
       ('aceptacion','Poca gente acepta','Lista equivocada o perfil que no convence','Afina la lista y tu perfil','curso'),
       ('fuga','Aceptaron más de los que recibieron mensaje','Fuga entre aceptar y escribir','Revisa condiciones y pasos pausados','equipo'),
       ('respuesta','Aceptan, pero no responden','Mensaje 1 genérico o que pide demasiado','Reescribe solo el mensaje 1','equipo'),
       ('reunion','Responden, pero no hay reuniones','Siguiente paso confuso o difícil','Propón algo concreto y fácil de aceptar','equipo'))
NAMES={'inventario':'el inventario','aceptacion':'la aceptación','fuga':'el paso de aceptar a recibir mensaje',
       'respuesta':'la respuesta','reunion':'la reunión'}

def _pct(n,d):
    return round(n/d*100,1) if d else None

def _checks(journeys,now):
    """Each stage of the table with its numbers: {etapa, sintoma, valor_pct, umbral_pct, n, de, rota}."""
    chosen=len(journeys)
    stale=[j for j in journeys if j.invited_at is None and j.chosen_at<=now-STALE and j.step!=Step.LEFT]
    invited=[j for j in journeys if j.invited_at];accepted=[j for j in invited if j.accepted_at]
    old=[j for j in journeys if j.accepted_at and j.accepted_at<=now-STALE]
    leaked=[j for j in old if j.first_message_at is None]
    messaged=[j for j in journeys if j.first_message_at];replied=[j for j in messaged if j.replied_at]
    met=[j for j in replied if j.meeting_at]
    rows={
        'inventario':(len(stale),chosen,_pct(len(stale),chosen),INVENTORY_SHARE,
                      len(stale)>=INVENTORY_MIN and (_pct(len(stale),chosen) or 0)>=INVENTORY_SHARE),
        'aceptacion':(len(accepted),len(invited),_pct(len(accepted),len(invited)),ACCEPTANCE_MIN,
                      bool(invited) and _pct(len(accepted),len(invited))<ACCEPTANCE_MIN),
        'fuga':(len(leaked),len(old),_pct(len(leaked),len(old)),LEAK_SHARE,bool(old) and _pct(len(leaked),len(old))>=LEAK_SHARE),
        'respuesta':(len(replied),len(messaged),_pct(len(replied),len(messaged)),REPLY_MIN,
                     len(messaged)>=REPLY_SAMPLE and _pct(len(replied),len(messaged))<REPLY_MIN),
        'reunion':(len(met),len(replied),_pct(len(met),len(replied)),MEETING_MIN,
                   len(replied)>=MEETING_SAMPLE and _pct(len(met),len(replied))<MEETING_MIN)}
    out=[]
    for stage,symptom,cause,change,source in TABLE:
        n,of,value,threshold,broken=rows[stage]
        out.append({'etapa':stage,'sintoma':symptom,'causa':cause,'cambio':change,'fuente_umbral':source,'n':n,'de':of,
                    'valor_pct':value,'umbral_pct':threshold,'umbral':'máximo' if stage in ('inventario','fuga') else 'mínimo',
                    'rota':bool(broken)})
    return out

def _split(journeys,now):
    """One audience's reading: its invitations, whether the sample is small and where it breaks first (None while small)."""
    invited=sum(1 for j in journeys if j.invited_at);small=invited<comprador.SMALL_SAMPLE
    broken=None if small else next((row for row in _checks(journeys,now) if row['rota']),None)
    return {'personas':len(journeys),'invitaciones':invited,'muestra_chica':small,'se_rompe':broken['etapa'] if broken else None,
            'cambio':broken['cambio'] if broken else None}

def test_line(progress):
    """The three-month test in one line for Slack."""
    from . import projectapp
    segments=' · '.join(f'{projectapp.SEGMENT_LABELS[s].lower()} {row["invitaciones"]}' for s,row in progress['por_segmento'].items())
    ready=[projectapp.SEGMENT_LABELS[s].lower() for s,row in progress['por_segmento'].items() if row['muestra']]
    sample=('con muestra: '+', '.join(ready)) if ready else f'ningún segmento tiene muestra todavía ({comprador.SMALL_SAMPLE} invitaciones)'
    week=('antes de empezar' if progress['semana']==0 else 'terminó, toca revisarla' if progress['semana']>progress['de']
          else f'semana {progress["semana"]} de {progress["de"]}')
    return (f'Prueba ProjectApp, {week}: invitaciones a compradores por segmento: {segments}; partners '
            f'{progress["partner"]["invitaciones"]}. {sample.capitalize()}. Revisión el {projectapp.REVIEW}.')

def read(now=None,account=None):
    """The week's reading: the table, where it breaks first (or the small sample), its cause and ONE change, this week
    against the last one, drafts pending against sent, and `lineas` (five at most) for Slack."""
    now=now or timezone.now()
    rows=BuyerJourney.objects.filter(entry=BuyerJourney.Entry.OUTBOUND)
    if account is not None:rows=rows.filter(contact__account=account)
    journeys=list(rows)
    funnel=comprador.funnel(weeks=2,now=now,account=account)
    invitations=funnel['acumulado']['invitaciones'];small=invitations<comprador.SMALL_SAMPLE
    table=_checks(journeys,now)
    broken=None if small else next((row for row in table if row['rota']),None)
    this,last=(funnel['semanas'][0]['actividad'],funnel['semanas'][1]['actividad'])
    drafts=funnel['borradores'];replies=(drafts.get('respuestas') or {})
    pending=drafts['pendientes']+replies.get('pendientes',0)+replies.get('sin_borrador',0)
    sent=drafts['enviados']+replies.get('enviados',0)
    week=funnel['semanas'][0]['semana']
    def pair(key):
        return f'{this.get(key,0)} ({last.get(key,0)})'
    lines=[f'Barrio · Embudo del comprador, semana del {week[8:10]}/{week[5:7]} (entre paréntesis, la anterior): '
           f'{pair("invitados")} invitados · {pair("aceptaron")} aceptaron · {pair("recibieron_mensaje")} recibieron mensaje · '
           f'{pair("respondieron")} respondieron · {pair("reunion")} reuniones.']
    if small:
        lines.append(f'Muestra chica: {invitations} invitaciones en total, menos de {comprador.SMALL_SAMPLE}; no se juzga ninguna etapa.')
    elif broken:
        value=broken['valor_pct']
        lines.append(f'Se rompe primero en {NAMES[broken["etapa"]]}: {broken["sintoma"].lower()} ({broken["n"]} de {broken["de"]}, '
                     f'{value} %; umbral {broken["umbral"]} {broken["umbral_pct"]} %, del {broken["fuente_umbral"]}).')
        lines.append(f'Lo más probable: {broken["causa"].lower()}. Un solo cambio esta semana: {broken["cambio"].lower()}.')
    else:
        lines.append('Ninguna etapa bajo su umbral: no se cambia nada esta semana.')
    from . import projectapp
    split={}
    if projectapp.enabled():
        split={'por_linea':{line:_split([j for j in journeys if (j.line or 'startup')==line],now) for line in projectapp.LINES},
               'por_segmento':{s:_split([j for j in journeys if j.line=='projectapp' and j.segment==s],now) for s in projectapp.SEGMENTS},
               'prueba_projectapp':funnel['prueba_projectapp']}
        lines.append(test_line(funnel['prueba_projectapp']))
    lines.append(f'Borradores: {pending} esperan en Tu turno; {sent} enviados en total.')
    return {**split,'generado':now.isoformat(),'semana':week,'muestra_chica':small,'invitaciones':invitations,'tabla':table,
            'se_rompe':broken['etapa'] if broken else None,'causa':broken['causa'] if broken else None,
            'cambio':broken['cambio'] if broken else None,
            'semana_actual':this,'semana_anterior':last,'borradores':{'pendientes':pending,'enviados':sent},
            'regla':'Arregla una etapa a la vez, empezando por la primera que se rompe (LI-12-M001-K04).',
            'lineas':lines[:5]}

def text(now=None,account=None):
    return '\n'.join(read(now,account)['lineas'])
