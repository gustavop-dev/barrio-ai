"""Gustavo's ideas get their publishing window as soon as they arrive, and the team prepares them right away.

- A day and hour he asks for («publica esto el martes a las 12») is an order (Gustavo 14/11/2026): the post goes out
  that day at that hour as an extra post of the day, next to the daily one, outside the CONT-09 caps and outside the
  GASP structure. It is never moved to another day and never asked about later. A day without an hour goes out at
  EDITORIAL_EXTRA_TIME (capture_intent.requested). Only when the date cannot be kept (past, inside the veto notice,
  outside the window, beyond 14 days, unclear, or a day that already has two posts) does the Bandeja ask him, at once.
  Before 14/11 that idea took the next free day and Tu turno asked days later whether it could go out on his date: the
  bug this replaces (_requested and _askable, «la Bandeja te pregunta si sale también…»).
- «Cuanto antes»: the first free daily window.
- Otherwise the idea takes the first free daily window and is written for that day's GASP type; an idea that clearly is
  of one type (understanding.gasp_type) takes the nearest free day of that type, and the idea planned there is kept
  for later (estrategia.displace).
The daily post (~EDITORIAL_POST_TIME) keeps the structure on every day. Reserving never replaces a prepared idea or
bypasses a gate: verification, budget, approval and veto still apply.
"""
import os
from datetime import datetime, timedelta
from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone
from .models import Capture, ConnectorAccount, EditorialPiece, Job

CLOSED=('skipped','failed','blocked')  # pieces that never went out: their day can take one of his ideas
MAX_ATTEMPTS=2  # a reserved idea whose piece was blocked or failed twice stays on the table for the director
OPEN_STATES=('preparing','ready')
PROBLEMS={'pasada':'Esa fecha ya pasó.',
          'veto':'Esa hora queda dentro de tu plazo de veto: no daría tiempo a prepararlo y a que lo veas antes de salir.',
          'ventana':'Esa hora está fuera de la ventana de publicación.',
          'lejana':'Esa fecha está a más de 14 días.',
          'ambigua':'No entendí la fecha que pediste.',
          'llena':'Ese día ya tiene dos posts: el diario y otro que pediste.'}


def veto_window():return timedelta(minutes=max(1,int(os.environ.get('EDITORIAL_VETO_MINUTES','60'))))


def _local(when):
    from . import operador
    return when.astimezone(operador.local_tz())


def is_extra(capture):
    """His idea holds an extra post at the day and hour he asked for (not the day's structured post)."""
    return bool(capture.publish_at and capture.publish_asap_expected_slot and capture.publish_asap_expected_slot==capture.publish_at)


def _daily_jobs(day):
    return Job.objects.filter(kind='prepare_piece',state__in=['queued','running'],params__slot=day.isoformat()).exclude(params__contains={'extra':True})


def _extra_jobs(day):
    return Job.objects.filter(kind='prepare_piece',state__in=['queued','running'],params__slot=day.isoformat(),params__extra=True)


def free_slot(account,now,reserved=(),not_before=None,exclude_piece=None,at=None,closed_ok=False,gasp_type=None):
    """First free daily window from today: no daily piece (closed ones count as free with `closed_ok`), no queued
    preparation, no other idea reserved, CONT-09 capacity left, and the day's GASP type when one is asked. `at` is an
    hour he asked for; otherwise the daily post hour."""
    from . import editorial, estrategia, operador
    today=_local(now).date();daily,weekly=operador.limits()['CONT-09']
    taken={_local(r).date() for r in reserved}
    for offset in range(15):
        day=today+timedelta(days=offset)
        when=datetime.combine(day,at,tzinfo=operador.local_tz()) if at else editorial.scheduled_for(day)
        if at and not operador.within_window(when):return None
        if when<now+veto_window() or (not_before and day<not_before) or day in taken:continue
        if gasp_type and estrategia.day_type(day)!=gasp_type:continue
        # A piece stopped only for money does not take its day: the day is free once there is budget again.
        pieces=EditorialPiece.objects.filter(slot_date=day,second_of_day=False).exclude(pk=exclude_piece).exclude(editorial.budget_stopped_q())
        if closed_ok:pieces=pieces.exclude(state__in=CLOSED)
        if pieces.exists():continue
        if _daily_jobs(day).exists():continue
        if operador.capacity_left(account,'CONT-09',when)<=0:continue
        start=day-timedelta(days=day.weekday());end=start+timedelta(days=7)
        # Executed pieces are counted by capacity_left; reserve capacity for work still ahead as well.
        pending=EditorialPiece.objects.filter(slot_date__gte=start,slot_date__lt=end,state__in=['preparing','ready'],
            proposals__execution__isnull=True,second_of_day=False).exclude(pk=exclude_piece).distinct().count()
        pending+=sum(start<=_local(r).date()<end for r in reserved)
        _,week_start=operador.period_starts(when)
        executed=operador.writes(account,'CONT-09').exclude(proposal__piece__second_of_day=True).filter(
            started_at__gte=week_start,started_at__lt=week_start+timedelta(days=7)).count()
        if executed+pending>=weekly:continue
        return when
    return None


def problem(now,asked,extras=(),capture=None):
    """Why his date cannot be kept as an extra post, or None. `extras`: hours other ideas of his already hold."""
    from . import operador
    day=_local(asked).date()
    if asked<now:return 'pasada'
    if asked>now+timedelta(days=14):return 'lejana'
    if not operador.within_window(asked):return 'ventana'
    if asked<now+veto_window():return 'veto'
    others=EditorialPiece.objects.filter(slot_date=day,second_of_day=True,state__in=OPEN_STATES)
    if capture is not None and (capture.routed_to or {}).get('used_in'):others=others.exclude(pk=capture.routed_to['used_in'])
    if others.exists() or day in {_local(e).date() for e in extras}:return 'llena'
    return None


def ask(capture,code,now,asked=None):
    """His date cannot be kept: the Bandeja asks him at once (cards); the idea waits for his answer."""
    current=capture.day_request or {}
    if current.get('state')=='problem' and current.get('problem')==code:return
    capture.day_request={'state':'problem','problem':code,'asked':(asked or capture.publish_at).isoformat() if (asked or capture.publish_at) else None,
                         'evidence':(capture.publish_at_evidence or '')[:200],'at':now.isoformat()}
    capture.publish_asap_expected_slot=None;capture.publish_asap_reason='Esperando tu respuesta en la Bandeja: '+PROBLEMS[code]
    capture.save(update_fields=['day_request','publish_asap_expected_slot','publish_asap_reason'])
    from . import operador
    operador._audit(None,'capture.day_request',capture.id,decision='asked',problem=code)


def _requested(now,capture,extras):
    """His day and hour: an extra post at that hour, or a question in the Bandeja when it cannot be kept."""
    code=problem(now,capture.publish_at,extras,capture)
    if code:
        ask(capture,code,now)
        return None,capture.publish_asap_reason
    return capture.publish_at,(f'Sale a la hora que pediste («{capture.publish_at_evidence[:120]}»), además del post diario de '
                               'ese día. Sujeto a verificación, presupuesto y veto.')


def _waiting(capture):
    return (capture.day_request or {}).get('state')=='problem'


def thesis(piece):
    return ((piece.brief or {}).get('thesis') or piece.final_text or 'Publicación del día').strip()


def _day_piece(capture):
    """The ready, not yet executed piece that used this idea, or None."""
    used=(capture.routed_to or {}).get('used_in')
    if not used:return None
    piece=EditorialPiece.objects.filter(id=used,state='ready').first()
    if piece is None or piece.proposals.filter(execution__isnull=False).exists():return None
    return piece


def _honor_legacy(capture,now):
    """A question of the old flow (state pending: his post waited on the next free day for a «sí»): his date is an
    order now, so the post moves to it as that day's extra when it still can; otherwise the question expires."""
    from . import operador
    piece=_day_piece(capture);asked=capture.publish_at;day=_local(asked).date()
    with transaction.atomic():
        operador.policy_lock()
        others=EditorialPiece.objects.select_for_update().filter(slot_date=day,second_of_day=True,state__in=OPEN_STATES)
        if piece is not None:others=others.exclude(pk=piece.pk)
        if piece is None or asked<now+veto_window() or not operador.within_window(asked) or others.exists():
            capture.day_request=dict(capture.day_request,state='expired',answered_at=now.isoformat())
            capture.save(update_fields=['day_request'])
            operador._audit(None,'capture.day_request',capture.id,decision='expired')
            return False
        before=piece.scheduled_for
        piece.scheduled_for,piece.slot_date,piece.second_of_day=asked,day,True
        piece.save(update_fields=['scheduled_for','slot_date','second_of_day','updated_at'])
        piece.gallery_photos.update(chosen_for=day)
        capture.publish_asap_expected_slot=asked;capture.publish_asap_reason='A la hora que pediste.'
        capture.day_request=dict(capture.day_request,state='same_day',answered_at=now.isoformat())
        capture.save(update_fields=['publish_asap_expected_slot','publish_asap_reason','day_request'])
        operador._audit(None,'editorial.piece_moved',piece.id,before=before.isoformat(),after=asked.isoformat(),reason='fecha pedida')
    return True


def problems(now=None):
    """Ideas of his whose date waits for his answer, oldest first."""
    return list(Capture.objects.filter(state=Capture.State.IDEA,day_request__state='problem').order_by('created_at'))


def tick_day_requests(now=None):
    """Autopilot: each new question about a date pushes once; questions of the old flow are settled by the new rule."""
    from .notificaciones import avisar
    now=now or timezone.now();count=0
    for capture in Capture.objects.filter(publish_at__isnull=False,day_request__state='pending'):_honor_legacy(capture,now)
    for capture in problems(now):
        if capture.day_request.get('notified'):continue
        capture.day_request=dict(capture.day_request,notified=now.isoformat());capture.save(update_fields=['day_request'])
        avisar('day_request','No puedo publicarlo cuando pediste',PROBLEMS.get(capture.day_request.get('problem'),'')+' ¿Qué hacemos?',
               link='/tu-turno',ref=f'day_request:{capture.id}')
        count+=1
    return count


def confirm_day(user,capture_id,decision):
    """His answer to a date that cannot be kept: `siguiente` publishes the idea on the first free day (written for that
    day's type), `descartar` drops it."""
    from . import operador
    from .exceptions import Conflict
    from .permissions import require
    require(user,'approve_actions')
    if decision not in ('siguiente','descartar'):raise ValueError('decision debe ser siguiente o descartar')
    now=timezone.now()
    with transaction.atomic():
        operador.policy_lock()
        capture=Capture.objects.select_for_update().get(id=capture_id)
        request=dict(capture.day_request or {})
        if request.get('state')!='problem' or capture.state!=Capture.State.IDEA:raise Conflict('Esta pregunta ya se respondió.')
        capture.day_request=dict(request,state='next_free' if decision=='siguiente' else 'discarded',answered_at=now.isoformat())
        fields=['day_request']
        if decision=='siguiente':
            capture.publish_at=None;fields.append('publish_at')  # an idea without a date from now on
        else:
            from .capturas import _outcome
            capture.state=Capture.State.UNUSED;capture.publish_asap_expected_slot=None
            capture.outcome=_outcome('sin_usar','La descartaste: la fecha que pediste no se podía cumplir.')
            fields+=['state','publish_asap_expected_slot','outcome']
        capture.save(update_fields=fields)
        operador._audit(user,'capture.day_request',capture.id,decision=capture.day_request['state'])
    if decision=='siguiente':assign_slots(now)
    capture.refresh_from_db()
    return capture,None


def _eligible(capture):
    routed=capture.routed_to or {}
    return not routed.get('declined_in') and routed.get('intentos',0)<MAX_ATTEMPTS


def _count_failed_attempt(capture):
    """The piece prepared for this idea's reserved window ended without it (blocked or failed, not for money): one
    attempt, counted once. Without this, the idea moved to the next free day and was prepared again at once, day after
    day. A piece that used the idea is counted when capturas.release_ideas gives it back."""
    from . import editorial
    old=capture.publish_asap_expected_slot
    if not old:return False
    routed=dict(capture.routed_to or {});seen=routed.get('intentos_en',[])
    piece=EditorialPiece.objects.filter(slot_date=_local(old).date(),scheduled_for=old,state__in=('blocked','failed'),
        created_at__gte=capture.created_at).exclude(editorial.budget_stopped_q()).exclude(id__in=seen).order_by('created_at').first()
    if piece is None:return False
    routed.update(intentos=routed.get('intentos',0)+1,intentos_en=seen+[str(piece.id)])
    capture.routed_to=routed;capture.save(update_fields=['routed_to'])
    return True


def _undated(account,now,capture,reserved):
    """An idea without a date: the nearest free day of its type when it clearly has one, else the first free day; it is
    written for that day's GASP type."""
    from . import estrategia
    kind=(capture.understanding or {}).get('gasp_type') if estrategia.enabled() else None
    when=free_slot(account,now,reserved,gasp_type=kind) if kind in estrategia.TYPES else None
    if when:
        return when,(f'El día de {estrategia.LABELS[kind].lower()} más cercano: tu idea encaja en ese tipo. Las piezas ya preparadas '
                     'conservan su sitio. Sujeto a verificación, presupuesto, aprobación y veto.')
    when=free_slot(account,now,reserved)
    reason=('Siguiente día libre de la cola; las piezas ya preparadas conservan su sitio. El equipo empieza a prepararla ya. '
            'Sujeto a verificación, presupuesto, aprobación y veto.')
    kind=estrategia.day_type(_local(when).date()) if when else None
    if kind:reason=f'Se escribe como post de {estrategia.LABELS[kind].lower()}, el tipo de ese día. '+reason
    return when,reason


def assign_slots(now=None):
    from . import editorial, estrategia, operador, autopiloto, oficina_eventos
    from .notificaciones import avisar
    now=now or timezone.now();account=editorial.publishing_account()
    from .capturas import expire_ideas
    expire_ideas(now)
    changes=[]
    if account is None:
        reason='Conecta LinkedIn para asignar el primer hueco de publicación'
        for capture in Capture.objects.filter(state='idea').exclude(publish_asap_reason=reason):
            if not _eligible(capture) or _waiting(capture):continue
            capture.publish_asap_expected_slot=None;capture.publish_asap_reason=reason
            capture.save(update_fields=['publish_asap_expected_slot','publish_asap_reason'])
            avisar('capture_scheduled','Tu idea espera fecha',reason,link='/?enviado=1',ref=f'capture_slot:{capture.id}:no_account')
            oficina_eventos.emit('entrega','director_editorial','operador_cuenta',reason)
        return
    with transaction.atomic():
        ConnectorAccount.objects.select_for_update().get(pk=account.pk)
        reserved=[];extras=[]
        # His explicit day/hour first, then «cuanto antes», then the queue in the order he sent them.
        ideas=Capture.objects.select_for_update().filter(state='idea').order_by(
            F('publish_at').asc(nulls_last=True),'-publish_asap','created_at','id')
        for capture in ideas:
            _count_failed_attempt(capture)
            if not _eligible(capture):
                if capture.publish_asap_expected_slot:
                    # Two attempts did not go out: it stays on the table for the director's daily post, without a date.
                    capture.publish_asap_expected_slot=None
                    capture.publish_asap_reason=('Se intentó preparar dos veces y no salió; sigue en la mesa del director '
                                                 'para un día normal.')
                    capture.save(update_fields=['publish_asap_expected_slot','publish_asap_reason']);changes.append(capture)
                continue
            if _waiting(capture):continue  # his answer in the Bandeja decides
            old=capture.publish_asap_expected_slot;extra=is_extra(capture)
            if operador.globally_paused() or not editorial.can_publish(account) or autopiloto.autonomy('CONT-09')=='off':
                when=None;reason='Publicación en pausa; se asignará el hueco al reanudar'
            else:
                # A queued or running preparation already owns this capture's reservation.
                day=_local(old).date() if old else None
                queued=old and old>now and (_extra_jobs(day) if extra else _daily_jobs(day)).exists()
                preparing=old and EditorialPiece.objects.filter(scheduled_for=old,state='preparing',second_of_day=extra).exists()
                if (queued or preparing) and old not in (extras if extra else reserved):
                    when,reason=old,capture.publish_asap_reason
                elif capture.publish_at:
                    when,reason=_requested(now,capture,extras)
                    if when is None:changes.append(capture);continue
                    extra=True
                elif capture.publish_asap:
                    when=free_slot(account,now,reserved,capture.publish_asap_not_before)
                    reason='Primer hueco libre; las piezas preparadas conservan su sitio. Sujeto a verificación, presupuesto, aprobación y veto.'
                else:
                    when,reason=_undated(account,now,capture,reserved)
                if not when:reason='Sin hueco disponible en 14 días; tu idea sigue en la mesa'
                if not editorial.can_afford_preparation(now):reason+=' Preparación pendiente de presupuesto de IA.'
            if when:(extras if extra else reserved).append(when)
            if when and not extra and when!=old:estrategia.displace(_local(when).date(),capture)
            if when!=old or reason!=capture.publish_asap_reason:
                capture.publish_asap_expected_slot=when;capture.publish_asap_reason=reason
                capture.save(update_fields=['publish_asap_expected_slot','publish_asap_reason']);changes.append(capture)
    for capture in changes:
        when=capture.publish_asap_expected_slot
        if _waiting(capture):continue  # the Bandeja card and its push tell him (tick_day_requests)
        detail=(f'Previsto para {_local(when):%d/%m %H:%M}. ' if when else '')+capture.publish_asap_reason
        title='Tu idea tiene prioridad' if capture.publish_asap else ('Tu idea ya tiene fecha' if when else 'Tu idea espera fecha')
        avisar('capture_scheduled',title,detail,link='/?enviado=1',
               ref=f'capture_slot:{capture.id}:{when.isoformat() if when else "pending"}')
        oficina_eventos.emit('entrega','director_editorial','operador_cuenta',detail)
        operador._audit(None,'capture.priority_slot',capture.id,expected_slot=when.isoformat() if when else None,decision=capture.publish_asap_reason)


def reserved_at(day):
    """The window an idea of his reserved on `day` for the day's post (its own hour), or None for the daily post hour."""
    rows=[c.publish_asap_expected_slot for c in Capture.objects.filter(state='idea',publish_asap_expected_slot__isnull=False)
          if _local(c.publish_asap_expected_slot).date()==day and not is_extra(c)]
    return min(rows) if rows else None


def extra_at(day):
    """The hour of the extra post he asked for on `day`, or None."""
    rows=[c.publish_asap_expected_slot for c in Capture.objects.filter(state='idea',publish_at__isnull=False,publish_asap_expected_slot__isnull=False)
          if is_extra(c) and _local(c.publish_asap_expected_slot).date()==day]
    return min(rows) if rows else None


def next_slot(now=None,manual=False):
    """The day of the earliest idea reserved for a day's post still without a piece: prepared right away, not
    EDITORIAL_LEAD_HOURS ahead."""
    from . import editorial
    now=now or timezone.now();assign_slots(now)
    # Starting a preparation the budget cannot finish only leaves a stopped piece behind; it waits for budget.
    if not editorial.can_afford_preparation(now):return None
    for capture in Capture.objects.filter(state='idea',publish_asap_expected_slot__gt=now).order_by('publish_asap_expected_slot'):
        if is_extra(capture):continue
        day=_local(capture.publish_asap_expected_slot).date()
        if EditorialPiece.objects.filter(slot_date=day,second_of_day=False).exclude(state__in=CLOSED).exists():continue
        if _daily_jobs(day).exists():continue
        return day
    return None


def next_extra(now=None):
    """The day of the earliest extra post he asked for that has no piece yet: prepared right away."""
    from . import editorial
    now=now or timezone.now();assign_slots(now)
    if not editorial.can_afford_preparation(now):return None
    for capture in Capture.objects.filter(state='idea',publish_at__isnull=False,publish_asap_expected_slot__gt=now).order_by('publish_asap_expected_slot'):
        if not is_extra(capture):continue
        day=_local(capture.publish_asap_expected_slot).date()
        if EditorialPiece.objects.filter(slot_date=day,second_of_day=True).exclude(state__in=CLOSED).exists():continue
        if _extra_jobs(day).exists():continue
        return day
    return None


def ensure_veto(piece):
    """If preparation consumed the notice period, move to a later free window, never publish immediately. An hour he
    asked for himself is kept while it is still ahead."""
    ideas=Capture.objects.filter(Q(publish_asap_expected_slot__isnull=False)|Q(publish_asap=True),state='usado',routed_to__used_in=str(piece.id))
    if not ideas.exists() or piece.scheduled_for>=timezone.now()+veto_window():return
    if ideas.filter(publish_at=piece.scheduled_for).exists() and piece.scheduled_for>timezone.now():return
    with transaction.atomic():
        ConnectorAccount.objects.select_for_update().get(pk=piece.account_id)
        when=free_slot(piece.account,timezone.now(),exclude_piece=piece.id)
        if when is None:raise ValueError('Sin hueco posterior que respete el plazo de veto')
        piece.scheduled_for=when;piece.slot_date=_local(when).date();piece.second_of_day=False  # alone on a free day
        piece.save(update_fields=['scheduled_for','slot_date','second_of_day'])
        ideas.update(publish_asap_expected_slot=when,publish_asap_reason='Se movió para conservar el plazo de veto tras la preparación')
        piece.gallery_photos.update(chosen_for=piece.slot_date)
    from .notificaciones import avisar
    avisar('capture_scheduled','Tu idea cambió de hora',f'Previsto para {_local(when):%d/%m %H:%M}; conserva tu plazo de veto.',
           link=f'/calendario/pieza/{piece.id}',ref=f'priority_moved:{piece.id}:{when.isoformat()}')


WEEKDAYS=['lunes','martes','miércoles','jueves','viernes','sábado','domingo']


def _when(value):
    local=_local(value);return f'{WEEKDAYS[local.weekday()]} {local:%d/%m} a las {local:%H:%M}'


def cards(card,now=None):
    """Bandeja: «No puedo publicarlo cuando pediste» for each idea of his whose date cannot be kept, at once."""
    now=now or timezone.now();out=[]
    for capture in problems(now):
        request=capture.day_request;code=request.get('problem');endpoint=f'/api/v1/capturas/{capture.id}/fecha'
        asked=datetime.fromisoformat(request['asked']) if request.get('asked') else None
        quote=request.get('evidence') or capture.publish_at_evidence
        body=PROBLEMS.get(code,'')+(f' Pediste «{quote[:120]}».' if quote else '')+' Mientras decides, la idea espera.'
        actions=[{'label':'Al primer día libre','endpoint':endpoint,'body':{'decision':'siguiente'},'primary':True},
                 {'label':'Descartarla','endpoint':endpoint,'body':{'decision':'descartar'}}]
        out.append(card(f'day_request:{capture.id}','fecha','No puedo publicarlo cuando pediste',body,actions,
                        agent='director_editorial',priority='importante',
                        created_at=datetime.fromisoformat(request['at']) if request.get('at') else capture.created_at,
                        day_request={'capture_id':str(capture.id),'asked_at':asked.isoformat() if asked else None,'evidence':(quote or '')[:200],
                                     'problem':code,'problem_label':PROBLEMS.get(code,''),'idea':' '.join(capture.text.split())[:280],
                                     'piece':None,'others':[]}))
    return out


def recently_resolved(days=7):
    """Tu turno «Hecho»: what happened with a date he asked for that needed his answer."""
    since=timezone.now()-timedelta(days=days);out=[]
    how={'next_free':'Va al primer día libre','discarded':'La descartaste','same_day':'Sale el día que pediste',
         'expired':'Se quedó en el siguiente día libre'}
    for capture in Capture.objects.filter(day_request__state__in=list(how)).order_by('-created_at')[:20]:
        at=capture.day_request.get('answered_at')
        if not at or datetime.fromisoformat(at)<since:continue
        asked=capture.day_request.get('asked')
        title=f'Tu post del {_when(datetime.fromisoformat(asked))}' if asked else 'Tu idea con fecha'
        out.append({'kind':'day_request','id':f'day_request:{capture.id}','title':title,'at':at,'how':how[capture.day_request['state']]})
    return out
