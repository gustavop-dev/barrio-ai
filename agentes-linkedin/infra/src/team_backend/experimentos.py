"""OBS-04. Positive approval freezes a 14/28/7-day plan; only observed quality decides."""
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, timedelta

from django.db import transaction
from django.utils import timezone
from . import evidencia, operador, orientacion, orquestacion, posicionamiento
from .jobs import Conflict, audit
from .models import (ActionExecution, ActionProposal, Notification, Referent, ReferentExperiment,
                     ReferentReview, ReferentAttribution)
from .referentes import TZ, bounds, lock, require_gustavo

SIGNAL_REQUEST = {'type': 'object', 'properties': {'post': {'type': 'string'}}, 'required': ['post'], 'additionalProperties': False}
RESULT_SCHEMA = {'type': 'object'}
EVALUATION_REQUEST = {'type': 'object', 'properties': {'plan': {'type': 'object'}, 'base': {'type': 'object'},
    'focus': {'type': 'object'}, 'followup': {'type': 'object'}, 'control': {'type': 'object'}}, 'required': ['plan', 'base', 'focus', 'followup'], 'additionalProperties': False}
DEFAULTS = {'base_days': 14, 'focus_days': 28, 'followup_days': 7, 'comments_week': 2,
    'min_classified': 10, 'min_coverage': 0.7, 'min_fit_week': 2, 'min_exposure': 4,
    'control_referent': '',
    'confounders': 'Publicaciones propias, otras acciones de red, cambios de orientación y exposición real; no estima causalidad.',
    'metric': 'Personas únicas con nueva interacción propia observable y encaje suficiente',
    'denominator': 'Personas con nueva interacción propia asociada observacionalmente al referente',
    'stop_rule': 'Pausa, restricción del proveedor o cambio de público/criterio detienen el foco.',
    'budget': 'Dentro de BAR-15 y el presupuesto existente de comentarios; revisión mensual ≤5 USD.',
    'limitations': 'Muestra parcial, asociaciones compartidas, sin causalidad ni identidades de todos los seguidores.'}


def propose(review, data):
    ref = Referent.objects.filter(pk=data.get('referent'), account=review.account, active=True, archived_at__isnull=True).first()
    if not ref:
        return None
    plan = dict(DEFAULTS, hypothesis=data['hypothesis'], audience=data['audience'], comparison=data['comparison'],
                fit_criterion=posicionamiento.network_criteria(), positioning_version=posicionamiento.VERSION,
                orientation_version=orquestacion.digest(orientacion.text()))
    if data.get('control_referent'):
        control = Referent.objects.filter(account=review.account, pk=data['control_referent'], active=True, archived_at__isnull=True).exclude(pk=ref.pk).first()
        if control:plan['control_referent']=str(control.pk)
    start = max(bounds(review.month)[1], timezone.now() + timedelta(days=1))
    experiment, _ = ReferentExperiment.objects.get_or_create(review=review, defaults={
        'account': review.account, 'referent': ref, 'plan': plan, 'starts_at': start,
        'focus_at': start+timedelta(days=14), 'followup_at': start+timedelta(days=42), 'ends_at': start+timedelta(days=49)})
    return experiment


def validate_plan(plan):
    required = set(DEFAULTS) | {'hypothesis', 'audience', 'comparison', 'fit_criterion', 'positioning_version', 'orientation_version'}
    if not isinstance(plan, dict) or set(plan) != required:
        raise ValueError('El plan debe conservar hipótesis, público, comparación, criterio, umbrales y límites.')
    for key, value in {'base_days': 14, 'focus_days': 28, 'followup_days': 7, 'comments_week': 2}.items():
        if type(plan[key]) is not int or plan[key] != value:
            raise ValueError('Esta fase usa base 14, foco 28, seguimiento 7 y hasta dos comentarios por semana.')
    for key in ('min_classified', 'min_exposure'):
        if type(plan[key]) is not int or plan[key] < 1:
            raise ValueError('La muestra y exposición mínimas deben ser positivas.')
    if type(plan['min_coverage']) not in (int, float) or not 0 < plan['min_coverage'] <= 1:
        raise ValueError('Cobertura mínima entre 0 y 1.')
    if type(plan['min_fit_week']) not in (int, float) or not 0 < plan['min_fit_week'] <= 100:
        raise ValueError('Umbral semanal inválido.')
    if any(not isinstance(plan[key], str) or not plan[key].strip() for key in required - set(DEFAULTS)):
        raise ValueError('Faltan criterios de la prueba.')


def cancel_pending(experiment):
    ActionProposal.objects.filter(referent_experiment=experiment, state__in=['proposed', 'approved']).update(
        state='rejected', decision_note='Foco detenido o revisado; no ejecutar la asignación anterior.')


@transaction.atomic
def decide(user, experiment_id, version, decision, plan=None, starts_at=None):
    require_gustavo(user)
    experiment = ReferentExperiment.objects.select_related('account').get(pk=experiment_id)
    operador.policy_lock()
    lock(experiment.account)
    experiment = ReferentExperiment.objects.select_for_update().get(pk=experiment_id)
    now = timezone.now()
    if experiment.version != version or experiment.state in ('completed', 'discarded', 'stopped'):
        raise Conflict('El experimento cambió o ya terminó; recarga la tarjeta.')
    if decision not in ('approve', 'edit', 'adjust', 'later', 'discard', 'stop'):
        raise ValueError('Decisión desconocida')
    if experiment.state == 'approved' and decision not in ('stop', 'edit'):
        raise Conflict('El plan aprobado solo se puede detener o revisar con nueva aprobación.')
    before = {'plan': deepcopy(experiment.plan), 'version': experiment.version, 'state': experiment.state,
              'starts_at': experiment.starts_at.isoformat(), 'actor': str(user.pk), 'at': now.isoformat(), 'decision': decision}
    if decision == 'edit':
        if isinstance(plan,dict):
            plan=dict(plan,fit_criterion=posicionamiento.network_criteria(),positioning_version=posicionamiento.VERSION,
                      orientation_version=orquestacion.digest(orientacion.text()))
        validate_plan(plan)
        start = datetime.fromisoformat(starts_at)
        if timezone.is_naive(start) or start <= now:
            raise ValueError('La nueva base debe empezar en el futuro, con zona horaria.')
        cancel_pending(experiment)
        experiment.plan, experiment.starts_at = plan, start
        experiment.focus_at = start+timedelta(days=14)
        experiment.followup_at = start+timedelta(days=42)
        experiment.ends_at = start+timedelta(days=49)
        experiment.state = 'proposed'
        experiment.approved_at = experiment.approved_by = None
    elif decision == 'approve':
        validate_plan(experiment.plan)
        if experiment.starts_at <= now:
            raise Conflict('La base aprobable ya pasó. Edita las fechas; no se inicia retroactivamente.')
        if not experiment.referent.active or experiment.referent.archived_at:
            raise ValueError('El referente debe estar activo.')
        comparator=experiment.plan['control_referent']
        if comparator and not Referent.objects.filter(account=experiment.account,pk=comparator,active=True,archived_at__isnull=True).exclude(pk=experiment.referent_id).exists():
            raise ValueError('El referente de comparación debe estar activo en esta cuenta.')
        if ReferentExperiment.objects.filter(account=experiment.account, state='approved').exclude(pk=experiment.pk).exists():
            raise Conflict('Ya hay un experimento aprobado en esta cuenta.')
        if material_change(experiment):
            raise Conflict('Cambió el criterio de encaje; revisa el plan antes de aprobar.')
        experiment.state, experiment.approved_at, experiment.approved_by = 'approved', now, user
    else:
        experiment.state = {'adjust': 'adjustment', 'later': 'postponed', 'discard': 'discarded', 'stop': 'stopped'}[decision]
        cancel_pending(experiment)
    experiment.history.append(before)
    experiment.version += 1
    experiment.save()
    audit(user, 'referents.experiment_decision', experiment.pk, decision=decision, version=experiment.version,
          before=before, after={'plan': experiment.plan, 'starts_at': experiment.starts_at.isoformat(), 'state': experiment.state})
    return experiment


def material_change(experiment):
    return (experiment.plan['positioning_version'] != posicionamiento.VERSION
            or experiment.plan['orientation_version'] != orquestacion.digest(orientacion.text()))


def active_focus(account, now=None):
    now = now or timezone.now()
    return ReferentExperiment.objects.filter(account=account, state='approved', focus_at__lte=now,
        followup_at__gt=now, referent__active=True, referent__archived_at__isnull=True).first()


def week_start(now):
    local = now.astimezone(TZ)
    return (local-timedelta(days=local.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)


def used_comments(experiment, now, exclude=None, pending=True):
    # Count all comments to this referent, not just those tagged as focus. Reservations/uncertain writes consume slots.
    start = max(week_start(now), experiment.focus_at)
    executions = ActionExecution.objects.filter(proposal__account=experiment.account,
        proposal__post__referent=experiment.referent, proposal__capability='INT-03', started_at__gte=start)
    if exclude:
        executions = executions.exclude(proposal_id=exclude)
    used = executions.exclude(state='failed', wrote=False).count()
    if pending:
        proposals = ActionProposal.objects.filter(account=experiment.account, post__referent=experiment.referent,
            capability='INT-03', state__in=['proposed', 'approved'], execution__isnull=True)
        if exclude:
            proposals = proposals.exclude(pk=exclude)
        used += proposals.count()
    return used


def eligible(post, now=None):
    now = now or timezone.now()
    focus = active_focus(post.account, now)
    return not focus or post.referent_id != focus.referent_id or (not material_change(focus) and used_comments(focus, now) < 2)


def execution_issues(proposal, now=None):
    if proposal.capability != 'INT-03':
        return []
    now = now or timezone.now()
    if proposal.post_id and not proposal.post.text.strip():
        return ['No hay contenido base verificable para comentar.']
    if proposal.post_id and proposal.post.referent_id and not Referent.objects.filter(pk=proposal.post.referent_id, active=True, archived_at__isnull=True).exists():
        return ['El referente ya no está activo.']
    if proposal.referent_experiment_id:
        exp = ReferentExperiment.objects.get(pk=proposal.referent_experiment_id)
        if (exp.state != 'approved' or exp.version != proposal.referent_experiment_version
                or not exp.focus_at <= now < exp.followup_at or material_change(exp)):
            return ['El foco aprobado se detuvo, cambió o terminó.']
    focus = active_focus(proposal.account, now)
    if focus and proposal.post_id and proposal.post.referent_id == focus.referent_id:
        if material_change(focus) or used_comments(focus, now, exclude=proposal.pk, pending=False) >= 2:
            return ['El foco admite hasta dos comentarios útiles por semana; criterio y límites vigentes.']
    return []


def signals(post):
    """COM-11: bounded public evidence only; no private messages, person targeting or invented followers."""
    if not post.referent_id:
        return {'limitations': ['Sin referente asociado.']}
    review = ReferentReview.objects.filter(account=post.account, published_at__isnull=False, kind='mensual').order_by('-month').first()
    attribution = ReferentAttribution.objects.filter(referent=post.referent).order_by('-as_of').first()
    focus = active_focus(post.account)
    report = attribution.report if attribution else {}
    return {'referent': {'id': str(post.referent_id), 'reason': post.referent.reason},
        'dossier': {'id': str(review.pk), 'summary': review.dossier.get('summary'), 'sources': review.dossier.get('sources', [])[:10]} if review else None,
        'audience': {k: report.get(k) for k in ('coverage', 'new_own_observations', 'exposure_count', 'comparison')},
        'experiment': {'id': str(focus.pk), 'version': focus.version, 'hypothesis': focus.plan['hypothesis'],
                       'audience': focus.plan['audience'], 'comments_week': 2} if focus and focus.referent_id == post.referent_id else None,
        'limitations': ['Procedencia y coincidencia no prueban seguimiento ni causalidad.',
                       'No insertar datos privados ni mencionar personas para atraerlas.',
                       'Sin dossier o muestra suficiente, usar solo el contenido legible.']}


def measure(report, referent):
    linked = next((r for r in report['referents'] if r['referent'] == referent), {})
    associated = {a['person'] for a in linked.get('associations', []) if a['own_after_referent']}
    people = [p for p in report['people'] if p['person'] in associated and p['new_own_observation']]
    classified = [p for p in people if p['classification']['sufficient']]
    fits = sum(p['classification']['fit'] is True for p in classified)
    return {'observed': len(people), 'classified': len(classified), 'fit': fits,
        'coverage': len(classified)/len(people) if people else 0,
        'fit_ratio': fits/len(classified) if classified else None,
        'criterion_versions': sorted({p['classification']['criterion_version'] for p in classified}),
        'exposure': len([e for e in linked.get('exposure', []) if e['capability'] == 'INT-03']),
        'sources': linked.get('associations', []), 'report_id': linked.get('record_id'), 'aggregates': report['aggregates'],
        'coverage_details': report['coverage']}


def evaluate(request):
    p, base, focus = request['plan'], request['base'], request['focus']
    base_rate, focus_rate = base['fit'] / (p['base_days']/7), focus['fit'] / (p['focus_days']/7)
    sufficient = (base['classified'] > 0 and base['coverage'] >= p['min_coverage']
        and focus['classified'] >= p['min_classified'] and focus['coverage'] >= p['min_coverage']
        and focus['exposure'] >= p['min_exposure'] and base['criterion_versions'] == focus['criterion_versions'])
    outcome = ('señal favorable' if focus_rate >= p['min_fit_week'] and focus_rate > base_rate else 'sin mejora observada') if sufficient else 'inconcluso'
    return {'outcome': outcome, 'base_fit_week': base_rate, 'focus_fit_week': focus_rate,
            'base': base, 'focus': focus, 'followup': request['followup'], 'plan': p,
            'control': request.get('control', {}), 'confounders': p['confounders'],
            'limitations': p['limitations'], 'causal_claim': False,
            'recommendation': 'Mantener o seguir midiendo; cualquier cambio variable exige otro lote mensual.'}


def result(experiment, end):
    runtime = orquestacion.Runtime.open('experimentos_referentes', f'{experiment.pk}:{experiment.version}:{end.isoformat()}',
        experiment.approved_by, facts={'experiment': str(experiment.pk), 'version': experiment.version},
        plan=['evidencia_experimento', 'evaluar_experimento'])
    measurements = {}
    control_measurements = {}
    with runtime.session():
        for key, start, stop in [('base', experiment.starts_at, experiment.focus_at),
                                 ('focus', experiment.focus_at, experiment.followup_at),
                                 ('followup', experiment.followup_at, experiment.ends_at)]:
            if end <= start:
                measurements[key] = {'pending': True}
                continue
            request = evidencia.EvidenceRequest(str(experiment.account_id), start.isoformat(), min(end, stop).isoformat(), end.isoformat())
            report = runtime.call('evidencia_experimento', request, lambda: evidencia.report(request), key=key)
            measurements[key] = measure(asdict(report), str(experiment.referent_id))
            measurements[key]['other_actions'] = ActionExecution.objects.filter(proposal__account=experiment.account,
                state='confirmed',wrote=True,finished_at__gte=start,finished_at__lt=min(end,stop)).exclude(
                proposal__post__referent=experiment.referent).count()
            if experiment.plan['control_referent']:
                control_measurements[key]=measure(asdict(report),experiment.plan['control_referent'])
        if end >= experiment.ends_at:
            request = dict(measurements, plan=experiment.plan, control=control_measurements)
            output = runtime.call('evaluar_experimento', request, lambda: evaluate(request), key='evaluation')
        else:
            output = dict(measurements, outcome='seguimiento', limitations=experiment.plan['limitations'])
        runtime.finish(output)
    return output


def tick(now=None):
    now = now or timezone.now()
    for experiment in ReferentExperiment.objects.filter(state='approved').select_related('account', 'referent', 'approved_by'):
        with transaction.atomic():
            operador.policy_lock()
            lock(experiment.account)
            experiment.refresh_from_db()
            if experiment.state != 'approved':
                continue
            if (not experiment.approved_by_id or operador.globally_paused() or experiment.account.paused or material_change(experiment)
                    or not experiment.referent.active or experiment.referent.archived_at):
                experiment.state = 'stopped'
                experiment.results['stop'] = {'at': now.isoformat(), 'reason': 'Pausa, referente inactivo o cambio material; comparación interrumpida.'}
                cancel_pending(experiment)
                experiment.save()
                audit(None, 'referents.experiment_stopped', experiment.pk, reason=experiment.results['stop']['reason'])
                continue
            days = (now-experiment.starts_at).days
            if days < 7:
                continue
            key = 'final' if now >= experiment.ends_at else f'week:{days//7}'
            if key in experiment.results:
                continue
            end = experiment.ends_at if key == 'final' else experiment.starts_at+timedelta(days=7*(days//7))
            output = result(experiment, end)
            experiment.results[key] = output
            if key == 'final':
                experiment.state = 'completed'
                cancel_pending(experiment)
            experiment.save()
            Notification.objects.get_or_create(ref=f'experiment:{experiment.pk}:{key}', defaults={
                'kind': 'referents_review', 'layer': 'conversaciones', 'title': 'Experimento de referentes: '+output['outcome'],
                'detail': 'La decisión depende del encaje y la cobertura de personas observadas. '+experiment.plan['limitations'], 'link': '/personas?pestana=referentes'})
