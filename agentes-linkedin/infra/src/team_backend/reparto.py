"""Soft weekly shares of the invitations by role (BAR-24, Gustavo 17/11/2026).

Gustavo: the distribution of roles «debería ser construido», but «estamos cortando con una misma tijera a todos; ...no
ser tan rígidos». Measured in production on 17/11/2026: par 53 %, aliado 26 %, comprador 9 %, divulgador 6 %,
recomendador 6 % of the invitations. The shares follow the course's neighborhood table (red.BARRIO_TABLE, LI-03-V021-K03:
20 buyers, 15 recommenders, 20 spreaders, 25 peers of 80; the 10 leaders get comments, never invitations).

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

DEFAULT_SHARE='comprador=20,recomendador+aliado=15,divulgador=20,par=25'
INVITED_ROLES=('comprador','recomendador','aliado','divulgador','par')


def shares():
    """[(roles, share)] in configuration order; [] when NETWORK_ROLE_SHARE is empty. A bad value is a configuration
    error (ValueError), never a silent default: leaders are not invited, every role appears once and shares are > 0."""
    raw=os.environ.get('NETWORK_ROLE_SHARE',DEFAULT_SHARE).strip()
    groups=[];seen=set()
    for item in filter(None,(x.strip() for x in raw.split(','))):
        key,sep,value=item.partition('=')
        roles=tuple(role.strip() for role in key.split('+') if role.strip())
        if not sep or not roles or not value.strip().isdigit() or int(value)<=0:
            raise ValueError(f'NETWORK_ROLE_SHARE inválido en «{item}»: usa papel=número (papel+papel=número para compartir).')
        for role in roles:
            if role=='lider':raise ValueError('NETWORK_ROLE_SHARE: a los líderes no se les invita; reciben comentarios.')
            if role not in INVITED_ROLES:raise ValueError(f'NETWORK_ROLE_SHARE: papel desconocido «{role}».')
            if role in seen:raise ValueError(f'NETWORK_ROLE_SHARE: «{role}» aparece dos veces.')
            seen.add(role)
        groups.append((roles,int(value)))
    return groups


def _role(contact):
    return (contact.classification or {}).get('role')


def week_counts(account,now=None):
    """{role: invitations this week}: the ones that went out (wrote, what the caps count) plus the open proposals."""
    from . import operador
    from .models import ActionExecution, ActionProposal
    _,week=operador.period_starts(now)
    counts={}
    sent=(ActionExecution.objects.filter(proposal__account=account,proposal__capability='RED-02',wrote=True,started_at__gte=week)
          .values_list('proposal__contact__classification',flat=True))
    open_=(ActionProposal.objects.filter(account=account,capability='RED-02',state__in=['proposed','approved'])
           .values_list('contact__classification',flat=True))
    for classification in [*sent,*open_]:
        role=(classification or {}).get('role')
        if role:counts[role]=counts.get(role,0)+1
    return counts


def weekly_invitations(account,now=None):
    """What the invitations may reach this week: the weekly cap within the ramp."""
    from . import operador, red
    _,weekly=operador.limits(now)['RED-02']
    _,ramp=red.ramp_limits(account,now)
    return min(weekly,ramp)


def order(candidates,account,now=None):
    """(candidates in the order of the shares, report). The report has one row per share: roles, share, weekly target,
    invited this week, deficit, ready (candidates now) and planned (filled by planned())."""
    groups=shares()
    if not groups:return list(candidates),[]
    now=now or timezone.now()
    counts=week_counts(account,now);weekly=weekly_invitations(account,now);total=sum(share for _,share in groups)
    group_of={role:n for n,(roles,_) in enumerate(groups) for role in roles}
    queues=[[] for _ in groups];rest=[]
    for contact in candidates:
        n=group_of.get(_role(contact))
        (queues[n] if n is not None else rest).append(contact)
    filled=[sum(counts.get(role,0) for role in roles) for roles,_ in groups]
    report=[{'roles':list(roles),'share':share,'weekly_target':round(weekly*share/total),'invited':filled[n],
             'deficit':max(0,round(weekly*share/total)-filled[n]),'ready':len(queues[n]),'planned':0}
            for n,(roles,share) in enumerate(groups)]
    ordered=[];taken=[0]*len(groups)
    while True:
        ready=[n for n in range(len(groups)) if taken[n]<len(queues[n])]
        if not ready:break
        n=min(ready,key=lambda n:(filled[n]/groups[n][1],'comprador' not in groups[n][0],n))
        ordered.append(queues[n][taken[n]]);taken[n]+=1;filled[n]+=1
    # A role outside the shares (configured out) goes after everyone, never in place of a role with a share.
    return ordered+rest,report


def planned(report,contacts):
    """Fill `planned` with the invitations this plan proposed, by share."""
    for row in report:
        row['planned']=sum(_role(contact) in row['roles'] for contact in contacts)
    return report
