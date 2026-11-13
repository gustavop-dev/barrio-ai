"""Gustavo's ideas get their publishing window as soon as they arrive, and the team prepares them right away.

- A day/hour he asked for («publícalo mañana a las 10») is kept. A post the team prepared on its own for that day
  moves to the next free window (one post a day). When that day already has a post of his own ideas, his post is
  prepared for the next free day at his hour, and Tu turno asks him whether it goes out on the day he asked for too:
  a second post that day, which only he can authorize (confirm_day, Gustavo 12/11/2026).
- «Cuanto antes»: the first free window.
- Otherwise the idea queues behind what is already scheduled: the next free daily window.
The autopilot still prepares its own daily post (EDITORIAL_LEAD_HOURS ahead) on the days no idea reserved.
Reserving never replaces a prepared idea or bypasses a gate: verification, budget, approval and veto still apply.
"""
import os
from datetime import datetime, timedelta
from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone
from .models import Capture, ConnectorAccount, EditorialPiece, Job

CLOSED=('skipped','failed','blocked')  # pieces that never went out: their day can take one of his ideas
MAX_ATTEMPTS=2  # a reserved idea whose piece was blocked or failed twice stays on the table for the director


def veto_window():return timedelta(minutes=max(1,int(os.environ.get('EDITORIAL_VETO_MINUTES','60'))))


def _local(when):
    from . import operador
    return when.astimezone(operador.local_tz())


def free_slot(account,now,reserved=(),not_before=None,exclude_piece=None,at=None,closed_ok=False):
    """First free window from today: no piece (closed ones count as free with `closed_ok`), no queued preparation,
    no other idea reserved, CONT-09 capacity left. `at` is the hour he asked for; otherwise the daily post hour."""
    from . import editorial, operador
    today=_local(now).date();daily,weekly=operador.limits()['CONT-09']
    taken={_local(r).date() for r in reserved}
    for offset in range(15):
        day=today+timedelta(days=offset)
        when=datetime.combine(day,at,tzinfo=operador.local_tz()) if at else editorial.scheduled_for(day)
        if at and not operador.within_window(when):return None
        if when<now+veto_window() or (not_before and day<not_before) or day in taken:continue
        # A piece stopped only for money does not take its day: the day is free once there is budget again.
        pieces=EditorialPiece.objects.filter(slot_date=day).exclude(pk=exclude_piece).exclude(editorial.budget_stopped_q())
        if closed_ok:pieces=pieces.exclude(state__in=CLOSED)
        if pieces.exists():continue
        if Job.objects.filter(kind='prepare_piece',state__in=['queued','running'],params__slot=day.isoformat()).exists():continue
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


def team_piece(day):
    """The ready piece of `day` the team prepared on its own (no idea of Gustavo) and not executed yet, or None."""
    piece=EditorialPiece.objects.filter(slot_date=day,state='ready').first()
    if piece is None or (piece.brief or {}).get('reserved_capture'):return None
    if Capture.objects.filter(routed_to__used_in=str(piece.id)).exists():return None
    if piece.proposals.filter(execution__isnull=False).exists():return None
    return piece


def _requested(account,now,capture,reserved,moves):
    """The hour he asked for. His request wins over a post the team prepared on its own that day."""
    from . import operador
    asked=capture.publish_at;day=_local(asked).date()
    if asked>=now+veto_window() and operador.within_window(asked) and day not in {_local(r).date() for r in reserved}:
        when=free_slot(account,now,reserved,not_before=day,at=_local(asked).time(),closed_ok=True)
        if when==asked:return when,'A la hora que pediste («'+capture.publish_at_evidence[:120]+'»).'
        team=team_piece(day)
        others=EditorialPiece.objects.filter(slot_date=day).exclude(state__in=CLOSED)
        if team and others.count()==1:
            later=free_slot(account,now,list(reserved)+[asked],exclude_piece=team.id)
            if later:
                moves.append((team,team.scheduled_for,later))
                team.scheduled_for=later;team.slot_date=_local(later).date()
                team.save(update_fields=['scheduled_for','slot_date','updated_at'])
                team.gallery_photos.update(chosen_for=team.slot_date)
                return asked,('A la hora que pediste («'+capture.publish_at_evidence[:120]+'»). El post que el equipo '
                              f'tenía para ese día pasa al {_local(later):%d/%m %H:%M}.')
    hour=_local(asked).time() if operador.within_window(asked) else None
    when=free_slot(account,now,reserved,not_before=day,at=hour,closed_ok=True) or free_slot(account,now,reserved,not_before=day)
    reason=('Ese día ya tiene un post tuyo o no tiene hueco; va al siguiente día libre'
            +(' a la hora que pediste.' if hour and when and _local(when).time()==hour else '.'))
    if when and _askable(capture,asked,now,reserved):
        state=(capture.day_request or {}).get('state')
        if state!='next_free':
            if state!='pending':
                capture.day_request={'state':'pending','asked':asked.isoformat(),'at':now.isoformat()}
                capture.save(update_fields=['day_request'])
            reason+=(' Cuando esté lista, Tu turno te pregunta si sale también el '
                     f'{_local(asked):%d/%m a las %H:%M}: serían dos posts ese día.')
    return when,reason


def _askable(capture,asked,now,reserved=()):
    """His hour is valid and its day already holds a post (or another idea of his reserved it), with room for one more:
    he may authorize a second post that day."""
    from . import operador
    if asked<now+veto_window() or not operador.within_window(asked):return False
    day=_local(asked).date()
    pieces=EditorialPiece.objects.filter(slot_date=day,state__in=OPEN_STATES)
    if pieces.filter(second_of_day=True).exists():return False
    return pieces.exists() or day in {_local(r).date() for r in reserved}


OPEN_STATES=('preparing','ready')


def _day_piece(capture):
    """The ready, not yet executed piece that used this idea, or None."""
    used=(capture.routed_to or {}).get('used_in')
    if not used:return None
    piece=EditorialPiece.objects.filter(id=used,state='ready').first()
    if piece is None or piece.proposals.filter(execution__isnull=False).exists():return None
    return piece


def day_requests(now=None):
    """(capture, piece, others) for each idea of his whose ready piece waits for his answer: it is on the next free day
    because the day he asked for already had a post. `others`: the open pieces of that day."""
    now=now or timezone.now();out=[]
    for capture in Capture.objects.filter(state=Capture.State.USED,publish_at__isnull=False,day_request__state='pending').order_by('created_at'):
        piece=_day_piece(capture)
        asked=capture.publish_at
        if piece is None or piece.scheduled_for==asked or asked<now+veto_window():continue
        others=list(EditorialPiece.objects.filter(slot_date=_local(asked).date(),state__in=OPEN_STATES).exclude(pk=piece.pk).order_by('scheduled_for'))
        if any(o.second_of_day for o in others):continue  # never a third post
        out.append((capture,piece,others))
    return out


def tick_day_requests(now=None):
    """Autopilot: an unanswered question expires when his hour comes within the veto period (the post keeps the next
    free day); a new one pushes once."""
    from .notificaciones import avisar
    from . import operador
    now=now or timezone.now();count=0
    for capture in Capture.objects.filter(publish_at__isnull=False,day_request__state='pending'):
        if capture.publish_at<now+veto_window():
            capture.day_request=dict(capture.day_request,state='expired',answered_at=now.isoformat())
            capture.save(update_fields=['day_request'])
            operador._audit(None,'capture.day_request',capture.id,decision='expired')
    for capture,piece,others in day_requests(now):
        if capture.day_request.get('notified'):continue
        capture.day_request=dict(capture.day_request,notified=now.isoformat());capture.save(update_fields=['day_request'])
        avisar('day_request',f'¿Dos posts el {_local(capture.publish_at):%d/%m}?',
               f'Tu post está listo para el {_local(piece.scheduled_for):%d/%m %H:%M}. Pediste el '
               f'{_local(capture.publish_at):%d/%m a las %H:%M}, pero ese día ya sale otro.',link='/tu-turno',ref=f'day_request:{capture.id}')
        count+=1
    return count


def thesis(piece):
    return ((piece.brief or {}).get('thesis') or piece.final_text or 'Publicación del día').strip()


def confirm_day(user,capture_id,decision):
    """Gustavo's answer: `mismo_dia` moves the ready piece to the day and hour he asked for, as that day's second post
    when it already has one (outside the CONT-09 caps); `siguiente` keeps it on the next free day."""
    from . import operador
    from .exceptions import Conflict
    from .permissions import require
    require(user,'approve_actions')
    if decision not in ('mismo_dia','siguiente'):raise ValueError('decision debe ser mismo_dia o siguiente')
    now=timezone.now()
    with transaction.atomic():
        operador.policy_lock()
        capture=Capture.objects.select_for_update().get(id=capture_id)
        request=dict(capture.day_request or {})
        if request.get('state')!='pending':raise Conflict('Esta pregunta ya se respondió o caducó.')
        if decision=='siguiente':
            capture.day_request=dict(request,state='next_free',answered_at=now.isoformat())
            capture.save(update_fields=['day_request'])
            operador._audit(user,'capture.day_request',capture.id,decision='next_free')
            return capture,None
        asked=capture.publish_at
        if asked<now+veto_window():raise Conflict('Tu hora ya está dentro del plazo de veto; el post se queda en el siguiente día libre.')
        if not operador.within_window(asked):raise Conflict('Tu hora está fuera de la ventana de publicación.')
        piece=_day_piece(capture)
        if piece is None:raise Conflict('El post ya no está listo para moverlo.')
        piece=EditorialPiece.objects.select_for_update().get(pk=piece.pk)
        day=_local(asked).date()
        others=EditorialPiece.objects.select_for_update().filter(slot_date=day,state__in=OPEN_STATES).exclude(pk=piece.pk)
        if others.filter(second_of_day=True).exists():raise Conflict('Ese día ya tiene dos posts.')
        before=piece.scheduled_for
        piece.scheduled_for,piece.slot_date,piece.second_of_day=asked,day,others.exists()
        piece.save(update_fields=['scheduled_for','slot_date','second_of_day','updated_at'])
        piece.gallery_photos.update(chosen_for=day)
        capture.publish_asap_expected_slot=asked
        capture.publish_asap_reason=('A la hora que pediste: autorizaste un segundo post ese día.' if piece.second_of_day
                                     else 'A la hora que pediste.')
        capture.day_request=dict(request,state='same_day',answered_at=now.isoformat())
        capture.save(update_fields=['publish_asap_expected_slot','publish_asap_reason','day_request'])
        operador._audit(user,'editorial.piece_moved',piece.id,before=before.isoformat(),after=asked.isoformat(),
                        reason='fecha pedida autorizada',second_of_day=piece.second_of_day)
        operador._audit(user,'capture.day_request',capture.id,decision='same_day',piece=str(piece.id))
    return capture,piece


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


def assign_slots(now=None):
    from . import editorial, operador, autopiloto, oficina_eventos
    from .notificaciones import avisar
    now=now or timezone.now();account=editorial.publishing_account()
    from .capturas import expire_ideas
    expire_ideas(now)
    changes=[];moves=[]
    if account is None:
        reason='Conecta LinkedIn para asignar el primer hueco de publicación'
        for capture in Capture.objects.filter(state='idea').exclude(publish_asap_reason=reason):
            if not _eligible(capture):continue
            capture.publish_asap_expected_slot=None;capture.publish_asap_reason=reason
            capture.save(update_fields=['publish_asap_expected_slot','publish_asap_reason'])
            avisar('capture_scheduled','Tu idea espera fecha',reason,link='/?enviado=1',ref=f'capture_slot:{capture.id}:no_account')
            oficina_eventos.emit('entrega','director_editorial','operador_cuenta',reason)
        return
    with transaction.atomic():
        ConnectorAccount.objects.select_for_update().get(pk=account.pk)
        reserved=[]
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
            old=capture.publish_asap_expected_slot
            if operador.globally_paused() or not editorial.can_publish(account) or autopiloto.autonomy('CONT-09')=='off':
                when=None;reason='Publicación en pausa; se asignará el hueco al reanudar'
            else:
                # A queued or running preparation already owns this capture's reservation.
                queued=old and old>now and Job.objects.filter(kind='prepare_piece',state__in=['queued','running'],
                    params__slot=_local(old).date().isoformat()).exists()
                preparing=old and EditorialPiece.objects.filter(scheduled_for=old,state='preparing').exists()
                if (queued or preparing) and old not in reserved:
                    when,reason=old,capture.publish_asap_reason
                elif capture.publish_at:
                    when,reason=_requested(account,now,capture,reserved,moves)
                elif capture.publish_asap:
                    when=free_slot(account,now,reserved,capture.publish_asap_not_before)
                    reason='Primer hueco libre; las piezas preparadas conservan su sitio. Sujeto a verificación, presupuesto, aprobación y veto.'
                else:
                    when=free_slot(account,now,reserved)
                    reason=('Siguiente día libre de la cola; las piezas ya preparadas conservan su sitio. El equipo empieza '
                            'a prepararla ya. Sujeto a verificación, presupuesto, aprobación y veto.')
                    if (capture.understanding or {}).get('publish_when'):
                        reason='No pude usar el día u hora que pediste (fuera de 07:00–21:00 o de los próximos 14 días). '+reason
                if not when:reason='Sin hueco disponible en 14 días; tu idea sigue en la mesa'
                if not editorial.can_afford_preparation(now):reason+=' Preparación pendiente de presupuesto de IA.'
            if when:reserved.append(when)
            if when!=old or reason!=capture.publish_asap_reason:
                capture.publish_asap_expected_slot=when;capture.publish_asap_reason=reason
                capture.save(update_fields=['publish_asap_expected_slot','publish_asap_reason']);changes.append(capture)
    for capture in changes:
        when=capture.publish_asap_expected_slot
        detail=(f'Previsto para {_local(when):%d/%m %H:%M}. ' if when else '')+capture.publish_asap_reason
        title='Tu idea tiene prioridad' if capture.publish_asap else ('Tu idea ya tiene fecha' if when else 'Tu idea espera fecha')
        avisar('capture_scheduled',title,detail,link='/?enviado=1',
               ref=f'capture_slot:{capture.id}:{when.isoformat() if when else "pending"}')
        oficina_eventos.emit('entrega','director_editorial','operador_cuenta',detail)
        operador._audit(None,'capture.priority_slot',capture.id,expected_slot=when.isoformat() if when else None,decision=capture.publish_asap_reason)
    for piece,before,after in moves:
        avisar('capture_scheduled','Movimos un post para darle tu hora',
               f'El post del {_local(before):%d/%m %H:%M} pasa al {_local(after):%d/%m %H:%M}.',
               link=f'/calendario/pieza/{piece.id}',ref=f'team_piece_moved:{piece.id}:{after.isoformat()}')
        operador._audit(None,'editorial.piece_moved',piece.id,before=before.isoformat(),after=after.isoformat(),reason='idea con hora pedida')


def reserved_at(day):
    """The window an idea of his reserved on `day` (its own hour), or None for the daily post hour."""
    rows=[c.publish_asap_expected_slot for c in Capture.objects.filter(state='idea',publish_asap_expected_slot__isnull=False)
          if _local(c.publish_asap_expected_slot).date()==day]
    return min(rows) if rows else None


def next_slot(now=None,manual=False):
    """The day of the earliest reserved idea still without a piece: prepared right away, not EDITORIAL_LEAD_HOURS ahead."""
    from . import editorial
    now=now or timezone.now();assign_slots(now)
    # Starting a preparation the budget cannot finish only leaves a stopped piece behind; it waits for budget.
    if not editorial.can_afford_preparation(now):return None
    for capture in Capture.objects.filter(state='idea',publish_asap_expected_slot__gt=now).order_by('publish_asap_expected_slot'):
        day=_local(capture.publish_asap_expected_slot).date()
        if EditorialPiece.objects.filter(slot_date=day).exclude(state__in=CLOSED).exists():continue
        if Job.objects.filter(kind='prepare_piece',state__in=['queued','running'],params__slot=day.isoformat()).exists():continue
        return day
    return None


def ensure_veto(piece):
    """If preparation consumed the notice period, move to a later free window, never publish immediately. An hour he
    asked for himself is kept while it is still ahead."""
    from . import operador
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
    """Tu turno: «¿Seguro que lo quieres ese día?» for each idea of his whose day already had a post."""
    now=now or timezone.now();out=[]
    for capture,piece,others in day_requests(now):
        asked=capture.publish_at;endpoint=f'/api/v1/capturas/{capture.id}/fecha'
        if others:
            other=others[0]
            body=(f'Ese día ya sale «{thesis(other)[:140]}» a las {_local(other.scheduled_for):%H:%M}: serían dos posts '
                  f'ese día. Mientras decides, el tuyo queda el {_when(piece.scheduled_for)}, el siguiente día libre.')
        else:
            body=(f'Ese día ya no tiene otro post. Mientras decides, el tuyo queda el {_when(piece.scheduled_for)}, el '
                  'siguiente día libre.')
        local=_local(asked);current=_local(piece.scheduled_for)
        actions=[{'label':f'Sí, el {WEEKDAYS[local.weekday()]} {local:%d/%m} a las {local:%H:%M}','endpoint':endpoint,
                  'body':{'decision':'mismo_dia'},'primary':True},
                 {'label':f'Dejarlo el {WEEKDAYS[current.weekday()]} {current:%d/%m}','endpoint':endpoint,'body':{'decision':'siguiente'}},
                 {'label':'Ver el post','href':f'/calendario/pieza/{piece.id}'}]
        out.append(card(f'day_request:{capture.id}','fecha',f'¿Seguro que lo quieres el {_when(asked)}?',body,actions,
                        agent='director_editorial',priority='importante',deadline=(asked-veto_window()).isoformat(),
                        created_at=datetime.fromisoformat(capture.day_request['notified']) if capture.day_request.get('notified') else capture.created_at,
                        day_request={'capture_id':str(capture.id),'asked_at':asked.isoformat(),'evidence':capture.publish_at_evidence[:200],
                                     'piece':{'id':str(piece.id),'thesis':thesis(piece)[:280],'scheduled_for':piece.scheduled_for.isoformat()},
                                     'others':[{'id':str(o.id),'thesis':thesis(o)[:280],'scheduled_for':o.scheduled_for.isoformat()} for o in others]}))
    return out


def recently_resolved(days=7):
    """Tu turno «Hecho»: what he answered (or let expire) about a day he asked for."""
    since=timezone.now()-timedelta(days=days);out=[]
    how={'same_day':'Sale el día que pediste','next_free':'Se queda en el siguiente día libre','expired':'Sin respuesta: siguiente día libre'}
    for capture in Capture.objects.filter(publish_at__isnull=False,day_request__state__in=list(how)).order_by('-created_at')[:20]:
        at=capture.day_request.get('answered_at')
        if not at or datetime.fromisoformat(at)<since:continue
        out.append({'kind':'day_request','id':f'day_request:{capture.id}','title':f'Tu post del {_when(capture.publish_at)}',
                    'at':at,'how':how[capture.day_request['state']]})
    return out
