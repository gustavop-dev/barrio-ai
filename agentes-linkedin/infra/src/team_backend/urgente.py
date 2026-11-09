"""ASAP reserves a normal publishing window; it never replaces a prepared piece or bypasses a gate."""
import os
from datetime import timedelta
from django.db import transaction
from django.utils import timezone
from .models import Capture, ConnectorAccount, EditorialPiece, Job


def veto_window():return timedelta(minutes=max(1,int(os.environ.get('EDITORIAL_VETO_MINUTES','60'))))


def free_slot(account,now,reserved=(),not_before=None,exclude_piece=None):
    from . import editorial, operador
    today=now.astimezone(operador.local_tz()).date();daily,weekly=operador.limits()['CONT-09']
    for offset in range(15):
        day=today+timedelta(days=offset);when=editorial.scheduled_for(day)
        if when<now+veto_window() or (not_before and day<not_before) or when in reserved:continue
        if EditorialPiece.objects.filter(slot_date=day).exclude(pk=exclude_piece).exists():continue
        if Job.objects.filter(kind='prepare_piece',state__in=['queued','running'],params__slot=day.isoformat()).exists():continue
        if operador.capacity_left(account,'CONT-09',when)<=0:continue
        start=day-timedelta(days=day.weekday());end=start+timedelta(days=7)
        # Executed pieces are counted by capacity_left; reserve capacity for work still ahead as well.
        pending=EditorialPiece.objects.filter(slot_date__gte=start,slot_date__lt=end,state__in=['preparing','ready'],
            proposals__execution__isnull=True).exclude(pk=exclude_piece).distinct().count()
        pending+=sum(start<=r.astimezone(operador.local_tz()).date()<end for r in reserved)
        _,week_start=operador.period_starts(when)
        executed=operador.writes(account,'CONT-09').filter(started_at__gte=week_start,started_at__lt=week_start+timedelta(days=7)).count()
        if executed+pending>=weekly:continue
        return when
    return None


def assign_slots(now=None):
    from . import editorial, operador, autopiloto, oficina_eventos
    from .notificaciones import avisar
    now=now or timezone.now();account=editorial.publishing_account()
    from .capturas import expire_ideas
    expire_ideas(now)
    changes=[]
    if account is None:
        reason='Conecta LinkedIn para asignar el primer hueco de publicación'
        for capture in Capture.objects.filter(state='idea',publish_asap=True).exclude(publish_asap_reason=reason):
            capture.publish_asap_expected_slot=None;capture.publish_asap_reason=reason
            capture.save(update_fields=['publish_asap_expected_slot','publish_asap_reason'])
            avisar('capture_scheduled','Tu idea tiene prioridad',reason,link='/?enviado=1',ref=f'capture_slot:{capture.id}:no_account')
            oficina_eventos.emit('entrega','director_editorial','operador_cuenta',reason)
        return
    with transaction.atomic():
        ConnectorAccount.objects.select_for_update().get(pk=account.pk)
        reserved=[]
        for capture in Capture.objects.select_for_update().filter(state='idea',publish_asap=True).order_by('created_at','id'):
            old=capture.publish_asap_expected_slot
            if operador.globally_paused() or not editorial.can_publish(account) or autopiloto.autonomy('CONT-09')=='off':
                when=None;reason='Publicación en pausa; se asignará el primer hueco al reanudar'
            else:
                # A queued preparation already owns this capture's reservation.
                queued=old and old>now and Job.objects.filter(kind='prepare_piece',state__in=['queued','running'],
                    params__slot=old.astimezone(operador.local_tz()).date().isoformat()).exists()
                preparing=old and EditorialPiece.objects.filter(scheduled_for=old,state='preparing').exists()
                when=old if (queued or preparing) and old not in reserved else free_slot(account,now,reserved,capture.publish_asap_not_before)
                reason=('Primer hueco libre; las piezas preparadas conservan su sitio. Sujeto a verificación, presupuesto, '
                        'aprobación y veto.') if when else 'Sin hueco disponible en 14 días; se conserva la prioridad'
                if editorial.spent_today(now)>=editorial.daily_budget():reason+=' Preparación pendiente de presupuesto editorial.'
            if when:reserved.append(when)
            if when!=old or reason!=capture.publish_asap_reason:
                capture.publish_asap_expected_slot=when;capture.publish_asap_reason=reason
                capture.save(update_fields=['publish_asap_expected_slot','publish_asap_reason']);changes.append(capture)
    for capture in changes:
        when=capture.publish_asap_expected_slot
        detail=(f'Previsto para {when.astimezone(operador.local_tz()):%d/%m %H:%M}. ' if when else '')+capture.publish_asap_reason
        avisar('capture_scheduled','Tu idea tiene prioridad',detail,link='/?enviado=1',
               ref=f'capture_slot:{capture.id}:{when.isoformat() if when else "pending"}')
        oficina_eventos.emit('entrega','director_editorial','operador_cuenta',detail)
        operador._audit(None,'capture.priority_slot',capture.id,expected_slot=when.isoformat() if when else None,decision=capture.publish_asap_reason)


def next_slot(now=None,manual=False):
    from . import editorial, operador
    now=now or timezone.now();assign_slots(now)
    for capture in Capture.objects.filter(state='idea',publish_asap=True,publish_asap_expected_slot__gt=now).order_by('publish_asap_expected_slot'):
        when=capture.publish_asap_expected_slot
        day=when.astimezone(operador.local_tz()).date()
        if EditorialPiece.objects.filter(slot_date=day).exists():continue
        if Job.objects.filter(kind='prepare_piece',state__in=['queued','running'],params__slot=day.isoformat()).exists():continue
        if manual or now>=when-editorial.lead_time():return day
    return None


def ensure_veto(piece):
    """If preparation consumed the notice period, move to a later free window, never publish immediately."""
    from . import operador
    urgent=Capture.objects.filter(state='usado',publish_asap=True,routed_to__used_in=str(piece.id))
    if not urgent.exists() or piece.scheduled_for>=timezone.now()+veto_window():return
    with transaction.atomic():
        ConnectorAccount.objects.select_for_update().get(pk=piece.account_id)
        when=free_slot(piece.account,timezone.now(),exclude_piece=piece.id)
        if when is None:raise ValueError('Sin hueco posterior que respete el plazo de veto')
        piece.scheduled_for=when;piece.slot_date=when.astimezone(operador.local_tz()).date()
        piece.save(update_fields=['scheduled_for','slot_date'])
        urgent.update(publish_asap_expected_slot=when,publish_asap_reason='Se movió para conservar el plazo de veto tras la preparación')
        piece.gallery_photos.update(chosen_for=piece.slot_date)
    from .notificaciones import avisar
    avisar('capture_scheduled','Tu idea cambió de hora',f'Previsto para {when:%d/%m %H:%M}; conserva tu plazo de veto.',
           link=f'/calendario/pieza/{piece.id}',ref=f'priority_moved:{piece.id}:{when.isoformat()}')
