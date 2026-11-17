"""Soft weekly shares of the invitations by role (BAR-24, Gustavo 17/11/2026), and by audience with the ProjectApp buyer
(BAR-25, Gustavo 17/11/2026).

Gustavo: the distribution of roles «debería ser construido», but «estamos cortando con una misma tijera a todos; ...no
ser tan rígidos». Measured in production on 17/11/2026: par 53 %, aliado 26 %, comprador 9 %, divulgador 6 %,
recomendador 6 % of the invitations. The shares follow the course's neighborhood table (red.BARRIO_TABLE, LI-03-V021-K03:
20 buyers, 15 recommenders, 20 spreaders, 25 peers of 80; the 10 leaders get comments, never invitations).

With NETWORK_PROJECTAPP_BUYER_ENABLED the default is Gustavo's split of the 80 a week by audience (PROJECTAPP_SHARE):
28 ProjectApp buyers, 12 startup buyers, 12 partners, 8 recommenders and allies, 10 peers and 10 spreaders; leaders
still only get comments. A buyer counts in the share of her line (`comprador_projectapp`, `comprador_startup`) or, when
the configuration names plain `comprador`, in the buyers' one. Inside the ProjectApp buyers' share the turn alternates
softly between technology leaders and owners (projectapp.PAPEL_SHARE, about 60/40); a buyer whose papel is unknown waits
in the owners' turn (LI-08-M004-K04: in a small company, the CEO).

They are soft: they decide whose turn it is, never how many go out. The ramp, the daily and weekly caps and the reading
window stay where they are (red.ramp_limits, operador.capacity_left); the weekly target of each role is its share of
what the ramp allows this week, so it grows and shrinks with the ramp. Each turn goes to the role with candidates that is
furthest below its share (invited this week plus open proposals, divided by its share): buyers first on a tie. A role
without candidates leaves its turn to the others (overflow) and nobody is held back to keep a percentage; a role above
its share waits while another with candidates is below its own. Inside a role the order of red.plan stays (whoever
answered a follow first, then red.prioritized: market tier and buyer score).

`aliado` shares the recommenders' turn: the table looks for recommenders among «clientes, aliados y socios», and an ally
(who sells services to founders) is who recommends Gustavo to them. NETWORK_ROLE_SHARE='' turns the shares off: the order
of red.plan as it was."""
import os

from django.utils import timezone

from . import projectapp

DEFAULT_SHARE='comprador=20,recomendador+aliado=15,divulgador=20,par=25'
PROJECTAPP_SHARE='comprador_projectapp=28,comprador_startup=12,partner=12,recomendador+aliado=8,par=10,divulgador=10'
INVITED_ROLES=('comprador','recomendador','aliado','divulgador','par')
LINE_KEYS=tuple(f'comprador_{line}' for line in projectapp.LINES)


def default_share():
    return PROJECTAPP_SHARE if projectapp.enabled() else DEFAULT_SHARE


def invited_keys():
    """What a share may name: the invited roles and, with the ProjectApp buyer on, the partner and the buyers' lines."""
    return INVITED_ROLES+(('partner',)+LINE_KEYS if projectapp.enabled() else ())


def shares():
    """[(keys, share)] in configuration order; [] when NETWORK_ROLE_SHARE is empty. A bad value is a configuration
    error (ValueError), never a silent default: leaders are not invited, every key appears once, shares are > 0 and
    plain `comprador` never goes with a line of buyers."""
    raw=os.environ.get('NETWORK_ROLE_SHARE',default_share()).strip()
    groups=[];seen=set();known=invited_keys()
    for item in filter(None,(x.strip() for x in raw.split(','))):
        key,sep,value=item.partition('=')
        roles=tuple(role.strip() for role in key.split('+') if role.strip())
        if not sep or not roles or not value.strip().isdigit() or int(value)<=0:
            raise ValueError(f'NETWORK_ROLE_SHARE inválido en «{item}»: usa papel=número (papel+papel=número para compartir).')
        for role in roles:
            if role=='lider':raise ValueError('NETWORK_ROLE_SHARE: a los líderes no se les invita; reciben comentarios.')
            if role not in known:raise ValueError(f'NETWORK_ROLE_SHARE: papel desconocido «{role}».')
            if role in seen:raise ValueError(f'NETWORK_ROLE_SHARE: «{role}» aparece dos veces.')
            seen.add(role)
        groups.append((roles,int(value)))
    if 'comprador' in seen and seen&set(LINE_KEYS):
        raise ValueError('NETWORK_ROLE_SHARE: usa «comprador» o sus líneas (comprador_projectapp, comprador_startup), no ambos.')
    return groups


def _role(contact):
    return (contact.classification or {}).get('role')


def keys_of(classification):
    """The keys a classification counts under: its role, the line of a buyer (only with the ProjectApp buyer on) and,
    for a ProjectApp buyer, `papel:<papel>` (owners' turn when unknown)."""
    c=classification or {};role=c.get('role')
    if not role:return []
    keys=[role]
    if role=='comprador' and projectapp.enabled():
        line=projectapp.line_in(c)
        keys.insert(0,f'comprador_{line}')
        if line=='projectapp':keys.append('papel:'+((c.get('buyer') or {}).get('papel') or 'dueno'))
    return keys


def week_counts(account,now=None):
    """{key: invitations this week}: the ones that went out (wrote, what the caps count) plus the open proposals, by
    role, by buyer line and by papel (keys_of)."""
    from . import operador
    from .models import ActionExecution, ActionProposal
    _,week=operador.period_starts(now)
    counts={}
    sent=(ActionExecution.objects.filter(proposal__account=account,proposal__capability='RED-02',wrote=True,started_at__gte=week)
          .values_list('proposal__contact__classification',flat=True))
    open_=(ActionProposal.objects.filter(account=account,capability='RED-02',state__in=['proposed','approved'])
           .values_list('contact__classification',flat=True))
    for classification in [*sent,*open_]:
        for key in keys_of(classification):counts[key]=counts.get(key,0)+1
    return counts


def weekly_invitations(account,now=None):
    """What the invitations may reach this week: the weekly cap within the ramp."""
    from . import operador, red
    _,weekly=operador.limits(now)['RED-02']
    _,ramp=red.ramp_limits(account,now)
    return min(weekly,ramp)


def _papel(contact):
    return projectapp.papel_of(contact) or 'dueno'


def _mix(queue,counts):
    """The ProjectApp buyers' queue with the turn alternating softly between papeles (projectapp.PAPEL_SHARE): the
    papel furthest below its share goes next (technology leaders on a tie); one without buyers leaves its turn. The
    order inside each papel stays."""
    share=projectapp.PAPEL_SHARE
    buckets={papel:[c for c in queue if _papel(c)==papel] for papel in share}
    filled={papel:counts.get('papel:'+papel,0) for papel in share};taken={papel:0 for papel in share};out=[]
    while True:
        ready=[p for p in share if taken[p]<len(buckets[p])]
        if not ready:return out
        papel=min(ready,key=lambda p:(filled[p]/share[p],list(share).index(p)))
        out.append(buckets[papel][taken[papel]]);taken[papel]+=1;filled[papel]+=1


def order(candidates,account,now=None):
    """(candidates in the order of the shares, report). The report has one row per share: roles, share, weekly target,
    invited this week, deficit, ready (candidates now) and planned (filled by planned()); the ProjectApp buyers' row
    also has `papel`: each papel's soft share and invitations this week."""
    groups=shares()
    if not groups:return list(candidates),[]
    now=now or timezone.now()
    counts=week_counts(account,now);weekly=weekly_invitations(account,now);total=sum(share for _,share in groups)
    group_of={key:n for n,(roles,_) in enumerate(groups) for key in roles}
    queues=[[] for _ in groups];rest=[]
    for contact in candidates:
        n=next((group_of[key] for key in keys_of(contact.classification) if key in group_of),None)
        (queues[n] if n is not None else rest).append(contact)
    filled=[sum(counts.get(role,0) for role in roles) for roles,_ in groups]
    report=[{'roles':list(roles),'share':share,'weekly_target':round(weekly*share/total),'invited':filled[n],
             'deficit':max(0,round(weekly*share/total)-filled[n]),'ready':len(queues[n]),'planned':0}
            for n,(roles,share) in enumerate(groups)]
    for n,(roles,_) in enumerate(groups):
        if 'comprador_projectapp' in roles:
            queues[n]=_mix(queues[n],counts)
            report[n]['papel']={papel:{'share':share,'invited':counts.get('papel:'+papel,0)} for papel,share in projectapp.PAPEL_SHARE.items()}
    ordered=[];taken=[0]*len(groups)
    buyers=[any(role.startswith('comprador') for role in roles) for roles,_ in groups]
    while True:
        ready=[n for n in range(len(groups)) if taken[n]<len(queues[n])]
        if not ready:break
        n=min(ready,key=lambda n:(filled[n]/groups[n][1],not buyers[n],n))
        ordered.append(queues[n][taken[n]]);taken[n]+=1;filled[n]+=1
    # A role outside the shares (configured out) goes after everyone, never in place of a role with a share.
    return ordered+rest,report


def planned(report,contacts):
    """Fill `planned` with the invitations this plan proposed, by share."""
    for row in report:
        row['planned']=sum(any(key in row['roles'] for key in keys_of(contact.classification)) for contact in contacts)
    return report
