"""OBS-01/02: durable monthly decisions. No LinkedIn writes, no implicit human approval."""
from copy import deepcopy
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo
import os
import re
import uuid
from urllib.parse import urlsplit

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied
from .jobs import Conflict, audit
from .models import (AuditEvent, ConnectorAccount, Notification, Referent, ReferentChange,
                     ReferentControl, ReferentNotice, ReferentReview)
from .permissions import require

TZ = ZoneInfo('America/Bogota')
TERMINAL = {'approved', 'aplicada_por_plazo', 'rejected'}


def is_gustavo(user):
    # An explicit stable installation identity, never superuser/staff/operate_linkedin as a proxy.
    username = getattr(settings, 'REFERENTS_GUSTAVO_USERNAME', os.environ.get('REFERENTS_GUSTAVO_USERNAME', 'gustavo'))
    return bool(user and user.is_authenticated and user.is_active and user.get_username() == username)


def require_gustavo(user):
    from .orquestacion import current
    require(user, 'operate_linkedin')
    if not is_gustavo(user) or current() is not None:
        raise PermissionDenied('Solo Gustavo puede decidir cambios de referentes y experimentos.')


def month_start(now):
    return now.astimezone(TZ).date().replace(day=1)


def bounds(month):
    start = datetime.combine(month, time(), TZ)
    return start, start + timedelta(days=5)


def lock(account):
    # Serialize creation of the common lock too. Every writer takes account -> control -> item.
    ConnectorAccount.objects.select_for_update().get(pk=account.pk)
    ReferentControl.objects.get_or_create(account=account, defaults={'issue': 'Identificar los cinco main iniciales.'})
    return ReferentControl.objects.select_for_update().get(account=account)


def snapshot(ref):
    return {'id': str(ref.pk), 'identifier': ref.public_identifier, 'display_name': ref.display_name,
            'profile_url': ref.profile_url, 'reason': ref.reason, 'active': ref.active, 'kind': ref.kind,
            'protected': ref.protected, 'position': ref.position, 'revision': ref.revision,
            'archived': bool(ref.archived_at)}


def occupancy(account):
    rows = Referent.objects.filter(account=account, active=True, archived_at__isnull=True)
    return {'total': rows.count(), 'main': rows.filter(protected=True).count(), 'variables': rows.filter(protected=False).count()}


def capacity(account):
    counts = occupancy(account)
    if counts['total'] > 15 or counts['variables'] > 10 or counts['main'] > 5:
        raise ValueError('Máximo 15 activos: hasta cinco main y diez variables. Libera una plaza o usa una sustitución.')
    return counts


def changed(control, actor, ref, before, source, reason):
    ref.revision += 1
    ref.save()
    control.revision += 1
    control.save(update_fields=['revision'])
    audit(actor, 'referents.changed', ref.pk, source=source, reason=reason, before=before, after=snapshot(ref))


@transaction.atomic
def manage(user, ref, *, version, changes, source='personas', replacement=None):
    require(user, 'operate_linkedin')
    if source not in ('personas', 'tu_turno'):
        raise ValueError('Origen inválido')
    control = lock(ref.account)
    ref = Referent.objects.select_for_update().get(pk=ref.pk)
    if ref.protected or 'protected' in changes or replacement:
        require_gustavo(user)
    if ref.revision != version:
        raise Conflict('La ficha cambió. Recarga antes de guardar.')
    before = snapshot(ref)
    allowed = {'active', 'protected', 'position', 'reason', 'archive'}
    if set(changes) - allowed:
        raise ValueError('Cambio de referente desconocido')
    if replacement:
        target = Referent.objects.select_for_update().filter(pk=replacement, account=ref.account, archived_at__isnull=True).first()
        if not target or target.pk == ref.pk or target.protected:
            raise ValueError('El reemplazo debe ser otro referente variable de esta cuenta.')
        target_before = snapshot(target)
        target.protected, target.position, target.active = ref.protected, ref.position, True
        ref.protected, ref.active, ref.archived_at = False, False, timezone.now()
        changed(control, user, target, target_before, source, 'Reemplazo explícito de Gustavo')
        audit(user,'referents.main_replaced',ref.pk,source=source,outgoing=str(ref.pk),incoming=str(target.pk),
              outgoing_before=before,incoming_before=target_before,incoming_after=snapshot(target))
    for field, value in changes.items():
        if field == 'archive':
            if value:
                ref.active, ref.archived_at = False, timezone.now()
        else:
            setattr(ref, field, value)
    changed(control, user, ref, before, source, 'Decisión explícita de Gustavo')
    capacity(ref.account)
    return ref


@transaction.atomic
def initialize(user, account, ids):
    """Recovery only after an ambiguous migration; never pick five by order/popularity."""
    require_gustavo(user)
    control = lock(account)
    if control.initialized:
        raise Conflict('Los main iniciales ya están registrados; usa la gestión de protegidos.')
    rows = list(Referent.objects.filter(account=account, pk__in=ids, archived_at__isnull=True))
    if len(set(ids)) != 5 or len(rows) != 5:
        raise ValueError('Identifica exactamente los cinco referentes actuales de esta cuenta.')
    for ref in rows:
        before = snapshot(ref)
        ref.protected = True
        changed(control, user, ref, before, 'personas', 'Identificación de los cinco main iniciales')
    capacity(account)
    control.initialized, control.initial_main, control.issue = True, sorted(str(r.pk) for r in rows), ''
    control.save()


def validate_proposal(account, data, *, evidence=None):
    from .operador import public_identifier
    if not isinstance(data, dict) or set(data) - {'kind', 'outgoing', 'incoming', 'reason', 'evidence', 'experiment'}:
        raise ValueError('Formato de propuesta inválido')
    kind = data.get('kind')
    if kind not in ('add', 'remove', 'swap') or not isinstance(data.get('reason'),str) or not data['reason'].strip() or len(data['reason'])>2000:
        raise ValueError('Indica alta, baja o sustitución y su motivo.')
    out, incoming = data.get('outgoing'), data.get('incoming')
    if bool(out) != (kind in ('remove', 'swap')) or bool(incoming) != (kind in ('add', 'swap')):
        raise ValueError('Una sustitución exige sale y entra en la misma propuesta.')
    if out:
        try:uuid.UUID(str(out))
        except (ValueError, TypeError, AttributeError):raise ValueError('Saliente inválido') from None
        ref = Referent.objects.filter(account=account, pk=out, active=True, archived_at__isnull=True).first()
        if not ref or ref.protected:
            raise ValueError('El saliente debe ser un referente variable activo; main está protegido.')
        # A failed/empty reading never justifies removing a referent for performance.
        if evidence is not None:
            report = next((r for r in evidence.get('referents', []) if r['referent'] == str(out)), {})
            if not report.get('exposure_count') or not report.get('coverage', {}).get('classified'):
                raise ValueError('Baja sin muestra clasificada y exposición: seguir midiendo.')
    if incoming:
        if not isinstance(incoming, dict) or set(incoming) - {'identifier', 'display_name', 'profile_url', 'niche', 'audience', 'contribution', 'top_voice', 'sources', 'industria'}:
            raise ValueError('Candidato inválido')
        for field in ('identifier', 'display_name', 'profile_url', 'niche', 'audience', 'contribution'):
            if not isinstance(incoming.get(field), str) or not incoming[field].strip():
                raise ValueError('Falta identidad, nicho, audiencia o aporte del candidato.')
        slug = public_identifier(incoming['profile_url'])
        url = urlsplit(incoming['profile_url'])
        if (url.scheme != 'https' or not re.fullmatch(r'(?:(?:www|[a-z]{2})\.)?linkedin\.com',url.hostname or '')
                or url.username or url.password or url.port not in (None,443) or not re.fullmatch(r'/in/[^/]+/?',url.path)
                or slug != public_identifier(incoming['identifier'])):
            raise ValueError('El enlace debe identificar el perfil propuesto.')
        # referentes_industria: the evaluation belongs to one profile; an edit that changes the profile must drop it.
        industry = incoming.get('industria')
        if industry is not None and (not isinstance(industry, dict) or industry.get('slug', slug) != slug):
            raise ValueError('La evaluación de industria corresponde a otro perfil; quítala al cambiar el perfil.')
        if Referent.objects.filter(account=account, public_identifier=slug, active=True, archived_at__isnull=True).exists():
            raise ValueError('El candidato ya está activo.')
        if Referent.objects.filter(account=account, public_identifier=slug, protected=True).exists():
            raise ValueError('El agente no puede restaurar ni mover un protegido.')
        if (not isinstance(incoming.get('sources'),list) or not incoming['sources']
                or any(not isinstance(x,str) or not x for x in incoming['sources'])
                or not isinstance(incoming.get('top_voice'), bool)):
            raise ValueError('El candidato necesita fuentes fechadas; Top Voice debe verificarse.')
    if not isinstance(data.get('evidence'), list) or not data['evidence'] or any(not isinstance(x,str) or not x for x in data['evidence']):
        raise ValueError('La propuesta necesita evidencia.')
    return deepcopy(data)


def notice(review, event, title, detail, now):
    """Unlike best-effort avisar, recording the initial notice is part of publication's transaction."""
    payload = {'title': title, 'detail': detail, 'deadline': review.deadline.isoformat()}
    row, created = ReferentNotice.objects.get_or_create(review=review, event=event, defaults={'payload': payload, 'created_at': now})
    if created:
        Notification.objects.create(kind='referents_review', layer='conversaciones', title=title, detail=detail,
            link='/personas?pestana=referentes' if event=='closed' else '/tu-turno', ref=f'referents:{review.pk}:{event}', created_at=now)
    return row


@transaction.atomic
def publish(review, now=None):
    now = now or timezone.now()
    control = lock(review.account)
    review = ReferentReview.objects.select_for_update().get(pk=review.pk)
    if review.published_at or review.state == 'preparing':
        return review
    if now < bounds(review.month)[0]:
        return review
    review.published_at = now
    # Late batches stay explicit-only, including after a failed initial publication transaction. An industry search
    # (referentes_industria) is never applied by silence, whatever day it lands.
    review.state = 'published' if now.astimezone(TZ).date() == review.month and review.kind == 'mensual' else 'late'
    if control.revision != review.expected_revision or not control.initialized:
        review.state = 'conflict'
    review.save()
    if review.kind == 'industria':
        n = review.changes.count()
        notice(review, 'day1', 'Referentes de industria por decidir',
            (f'{n} {"voz grande" if n == 1 else "voces grandes"} de tu industria en EE. UU., con los criterios que cumple cada una. '
             if n else 'Ningún candidato cumplió todos los criterios; el detalle queda en Personas. ')
            + f'Decide hasta el {review.deadline.astimezone(TZ):%d/%m}; nada se aplica sin tu decisión.', now)
        return review
    if (review.dossier or {}).get('extraordinaria'):
        notice(review, 'day1', 'Revisión extraordinaria de referentes',
            f'Voces con audiencia en EE. UU. para los cupos variables. Decide cada propuesta hasta el '
            f'{review.deadline.astimezone(TZ):%d/%m}; nada se aplica sin tu decisión.', now)
        return review
    notice(review, 'day1', 'Revisión mensual de referentes',
        'Decide hasta terminar el día 5, America/Bogota. Sin respuesta se aplican solo las propuestas variables elegibles. '
        + ('Este lote requiere decisión explícita.' if review.state != 'published' else ''), now)
    return review


def extraordinary(user, account, now=None):
    """Gustavo, 12/11/2026: the ten variable slots are empty and his five main voices are local to Colombia («toca
    buscar más»). A review now, outside the monthly calendar, looks for voices with an audience in the United States.
    It is a late batch: every proposal needs his explicit decision, within a week."""
    from .jobs import enqueue_operation
    now = now or timezone.now()
    month = month_start(now)
    if not ReferentControl.objects.filter(account=account, initialized=True).exists():
        raise ValueError('Primero identifica los cinco main de la cuenta.')
    if ReferentReview.objects.filter(account=account, month=month, kind='mensual').exists():
        raise Conflict('Ya hay una revisión de referentes este mes; decide esa en la Bandeja.')
    job, _ = enqueue_operation(user, 'review_referents',
        {'account': str(account.pk), 'month': month.isoformat(), 'extraordinaria': True},
        request_id=uuid.uuid5(uuid.NAMESPACE_URL, f'referents:{account.pk}:{month}:extraordinaria'))
    return job


def _apply(item, control, user, automatic, now):
    review = item.review
    data = validate_proposal(review.account, item.proposal)
    out = Referent.objects.select_for_update().get(pk=data['outgoing']) if data.get('outgoing') else None
    before_count = capacity(review.account)
    if out:
        before = snapshot(out)
        out.active, out.archived_at = False, now
        changed(control, user, out, before, 'monthly_deadline' if automatic else 'tu_turno', data['reason'])
    if data.get('incoming'):
        from .operador import public_identifier
        candidate = data['incoming']
        incoming, _ = Referent.objects.get_or_create(account=review.account,
            public_identifier=public_identifier(candidate['identifier']), defaults={'active': False, 'reason': data['reason']})
        before = snapshot(incoming)
        incoming.active, incoming.archived_at, incoming.reason = True, None, data['reason']
        incoming.display_name, incoming.profile_url = candidate['display_name'], candidate['profile_url']
        if review.kind == 'industria':
            incoming.kind = Referent.Kind.INDUSTRIA
        changed(control, user, incoming, before, 'monthly_deadline' if automatic else 'tu_turno', data['reason'])
    after_count = capacity(review.account)
    item.state = 'aplicada_por_plazo' if automatic else 'approved'
    item.applied_at, item.conflict = now, ''
    item.save()
    # Only an otherwise compatible review can advance its expected list revision.
    review.expected_revision = control.revision
    review.save(update_fields=['expected_revision'])
    audit(user, 'referents.applied', item.pk, version=item.version, state=item.state,
          before=before_count, after=after_count, proposal=data)


@transaction.atomic
def decide(user, item_id, version, decision, proposal=None, now=None, note=''):
    """`note`: Gustavo's why, kept in the history; a rejected industry candidate's note is shown to the next search."""
    require_gustavo(user)
    now = now or timezone.now()
    item = ReferentChange.objects.select_related('review__account').get(pk=item_id)
    control = lock(item.review.account)
    item = ReferentChange.objects.select_for_update().select_related('review').get(pk=item_id)
    if item.version != version or item.state in TERMINAL:
        raise Conflict('La propuesta cambió o ya se aplicó. Recarga; una corrección requiere otra decisión.')
    if not item.review.published_at:
        raise Conflict('El lote todavía no se ha publicado.')
    if decision not in ('approve', 'reject', 'edit', 'edit_apply', 'adjust', 'later'):
        raise ValueError('Decisión desconocida')
    item.history.append({'version': item.version, 'proposal': item.proposal, 'state': item.state,
                         'decision': decision, 'actor': str(user.pk), 'at': now.isoformat(),
                         **({'note': str(note).strip()[:500]} if note and str(note).strip() else {})})
    if decision in ('edit', 'edit_apply'):
        item.proposal = validate_proposal(item.review.account, proposal)
    item.version += 1
    item.responded_at, item.conflict = now, ''
    item.state = {'reject': 'rejected', 'edit': 'edited', 'adjust': 'adjustment', 'later': 'postponed'}.get(decision, 'pending')
    if decision in ('approve', 'edit_apply'):
        compatible = item.review.expected_revision == control.revision
        _apply(item, control, user, False, now)
        if not compatible:
            item.review.state = 'conflict'
            item.review.save(update_fields=['state'])
    else:
        item.save()
    audit(user, 'referents.decision', item.pk, version=item.version, decision=decision, source='tu_turno')
    return item


@transaction.atomic
def close(review, now=None):
    now = now or timezone.now()
    control = lock(review.account)
    review = ReferentReview.objects.select_for_update().get(pk=review.pk)
    if now < review.deadline or review.closed_at:
        return
    eligible = (control.initialized and review.kind == 'mensual' and review.state == 'published' and review.published_at
                and review.published_at.astimezone(TZ).date() == review.month
                and review.notices.filter(event='day1').exists()
                and review.expected_revision == control.revision)
    for item in review.changes.select_for_update().filter(state='pending', responded_at__isnull=True).order_by('ordinal'):
        item.review = review
        if eligible:
            try:
                # Savepoint: a full-capacity swap is atomic, including its audit and revisions.
                with transaction.atomic():
                    _apply(item, control, None, True, now)
                continue
            except (ValueError, Conflict) as exc:
                control.refresh_from_db(); review.refresh_from_db(); item.refresh_from_db()
                item.conflict = str(exc)
        else:
            item.conflict = ('Referente de industria: solo entra con tu decisión explícita.' if review.kind == 'industria'
                             else 'Lote tardío, aviso ausente o lista modificada: requiere decisión explícita.')
        item.state = 'conflict'
        item.save(update_fields=['state', 'conflict'])
    review.closed_at = now
    review.save(update_fields=['closed_at'])
    states = list(review.changes.values('id', 'state', 'conflict'))
    if review.kind == 'industria':
        result_notice = notice(review, 'closed', 'Cierre de referentes de industria',
            f'Sin decisión: {sum(x["state"] == "conflict" for x in states)}; siguen en la Bandeja y no se aplicaron.', now)
    else:
        result_notice=notice(review, 'closed', 'Cierre de referentes',
           f'Aplicadas por plazo autorizado: {sum(x["state"] == "aplicada_por_plazo" for x in states)}. '
           f'Conflictos: {sum(x["state"] == "conflict" for x in states)}. Protegidos conservados.', now)
    result_notice.payload['changes']=[{'id':str(item.pk),'state':item.state,'proposal':item.proposal,'conflict':item.conflict}
                                      for item in review.changes.all()]
    result_notice.payload['occupancy']=occupancy(review.account)
    result_notice.save(update_fields=['payload'])


def tick(user, now=None):
    from . import experimentos, operador
    from .jobs import enqueue_operation
    now = now or timezone.now()
    local = now.astimezone(TZ)
    # The closing mandate is local data work and remains available outside write hours / during pause.
    for review in ReferentReview.objects.filter(closed_at__isnull=True).select_related('account'):
        publish(review, now)
        review.refresh_from_db()
        # The day-4 reminder promises an application by silence: only the monthly batch has one.
        if (local.day == 4 and local.hour >= 9 and review.month == local.date().replace(day=1) and review.published_at
                and review.kind == 'mensual'):
            if review.changes.filter(state='pending', responded_at__isnull=True).exists():
                with transaction.atomic():
                    lock(review.account)
                    notice(review, 'day4', 'Queda poco para decidir referentes',
                           'Sin respuesta, las propuestas elegibles se aplicarán al terminar el día 5, America/Bogota.', now)
        close(review, now)
    from .models import ReferentExperiment
    if ReferentExperiment.objects.filter(state='approved').exists():
        enqueue_operation(user,'advance_experiments',{},request_id=uuid.uuid5(uuid.NAMESPACE_URL,f'experiments:{local:%Y-%m-%d-%H}'))
    if operador.within_window(now):
        from .alerts import notify
        from .notificaciones import push_enabled
        for pending in ReferentNotice.objects.filter(pushed_at__isnull=True).select_related('review'):
            if pending.event == 'day1' and now < bounds(pending.review.month)[0] + timedelta(hours=9):
                continue
            with transaction.atomic():
                pending = ReferentNotice.objects.select_for_update().get(pk=pending.pk)
                if pending.pushed_at:
                    continue
                if push_enabled('referents_review'):
                    notify(pending.payload['title'], pending.payload['detail'][:200],
                           url='/personas?pestana=referentes' if pending.event=='closed' else '/tu-turno', tag=f'referents-{pending.pk}')
                pending.pushed_at = now
                pending.save(update_fields=['pushed_at'])
    tomorrow = (local + timedelta(days=1)).date()
    if local.day != 1 and tomorrow.day != 1:
        return
    period = tomorrow if tomorrow.day == 1 else local.date().replace(day=1)
    for control in ReferentControl.objects.filter(initialized=True).select_related('account'):
        if control.account.provider in ('linkedin', 'linkedin_fake'):
            continue  # official publishing account has no observatory reads
        enqueue_operation(user, 'review_referents', {'account': str(control.account_id), 'month': period.isoformat()},
            request_id=uuid.uuid5(uuid.NAMESPACE_URL, f'referents:{control.account_id}:{period}'))


def history(ref):
    return list(AuditEvent.objects.filter(target=str(ref.pk), action='referents.changed').values('actor__username', 'created_at', 'metadata')[:10])
