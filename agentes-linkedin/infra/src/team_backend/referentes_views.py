from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView
from . import referentes, experimentos
from .models import ConnectorAccount, Referent, ReferentChange, ReferentExperiment, ReferentReview, ReferentControl
from .operador_views import get_or_404, human_session, valid
from .permissions import require


class DecisionInput(serializers.Serializer):
    version = serializers.IntegerField(min_value=1)
    decision = serializers.CharField(max_length=20)
    proposal = serializers.JSONField(required=False)
    plan = serializers.JSONField(required=False)
    starts_at = serializers.CharField(required=False)
    note = serializers.CharField(required=False, allow_blank=True)


class ChangeDecision(APIView):
    def post(self, request, cid):
        human_session(request)
        data = valid(DecisionInput, request)
        get_or_404(ReferentChange, pk=cid)
        try:
            item = referentes.decide(request.user, cid, data['version'], data['decision'], data.get('proposal'))
        except (ValueError, TypeError) as exc:
            return Response({'detail': str(exc)}, status=400)
        return Response({'id': str(item.pk), 'state': item.state, 'version': item.version})


class ExperimentDecision(APIView):
    def post(self, request, eid):
        human_session(request)
        data = valid(DecisionInput, request)
        get_or_404(ReferentExperiment, pk=eid)
        try:
            item = experimentos.decide(request.user, eid, data['version'], data['decision'], data.get('plan'), data.get('starts_at'))
        except (ValueError, TypeError) as exc:
            return Response({'detail': str(exc)}, status=400)
        return Response({'id': str(item.pk), 'state': item.state, 'version': item.version})


class InitialMainInput(serializers.Serializer):
    account = serializers.UUIDField()
    ids = serializers.ListField(child=serializers.UUIDField(), min_length=5, max_length=5)


class InitialMain(APIView):
    def post(self, request):
        human_session(request)
        data = valid(InitialMainInput, request)
        try:
            referentes.initialize(request.user, get_or_404(ConnectorAccount, pk=data['account']), [str(x) for x in data['ids']])
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=400)
        return Response({'initialized': True})


class Reviews(APIView):
    def get(self, request):
        require(request.user, 'operate_linkedin')
        rows = ReferentReview.objects.order_by('-month')
        if request.query_params.get('account'):
            rows = rows.filter(account_id=request.query_params['account'])
        return Response([{'id': str(r.pk), 'month': r.month, 'state': r.state, 'deadline': r.deadline,
            'dossier': r.dossier, 'changes': list(r.changes.values('id', 'version', 'state', 'proposal', 'history', 'conflict')),
            'experiments': list(ReferentExperiment.objects.filter(review=r).values('id', 'state', 'plan', 'results', 'history'))} for r in rows[:12]])


def cards(user, card, now):
    out = []
    human = referentes.is_gustavo(user)
    for control in ReferentControl.objects.filter(initialized=False).exclude(account__provider__in=['linkedin','linkedin_fake']).select_related('account'):
        out.append(card(f'referents_setup:{control.account_id}', 'aviso', 'Identificar los cinco referentes main',
            control.issue, [{'label': 'Gestionar protegidos', 'href': '/personas?pestana=referentes'}], agent='investigador_lider'))
    for item in ReferentChange.objects.select_related('review__account').exclude(state__in=referentes.TERMINAL).filter(review__published_at__isnull=False):
        p, review = item.proposal, item.review
        outgoing = Referent.objects.filter(pk=p.get('outgoing')).first() if p.get('outgoing') else None
        incoming = p.get('incoming')
        title = (f'sale {outgoing.display_name if outgoing else "referente"} · entra {incoming["display_name"]}' if p['kind'] == 'swap'
                 else f'Alta: {incoming["display_name"]}' if p['kind'] == 'add' else f'Baja: {outgoing.display_name if outgoing else "referente"}')
        endpoint = f'/api/v1/referentes/cambios/{item.pk}/decidir'
        auto = review.state == 'published' and item.state == 'pending' and not item.responded_at
        actions = [{'label': {'add': 'Aprobar alta', 'remove': 'Aprobar baja', 'swap': 'Aprobar sustitución'}[p['kind']],
                    'endpoint': endpoint, 'body': {'version': item.version, 'decision': 'approve'}, 'primary': True},
                   *[{'label': label, 'endpoint': endpoint, 'body': {'version': item.version, 'decision': decision}}
                     for label, decision in [('Rechazar', 'reject'), ('Pedir ajuste', 'adjust'), ('Más tarde', 'later')]]] if human else []
        sources = review.dossier.get('sources', [])
        current = Referent.objects.filter(account=review.account, active=True, archived_at__isnull=True)
        total, main = current.count(), current.filter(protected=True).count()
        body = p['reason'] + (' Si no respondes, se aplicará al terminar el día 5 (America/Bogota).' if auto else 'Requiere decisión explícita; esta versión no se aplicará por silencio.')
        out.append(card(f'referent_change:{item.pk}', 'referente', title, body, actions, agent='investigador_lider',
            deadline=review.deadline, created_at=review.published_at,
            state_override='pospuesta' if item.state == 'postponed' else None,
            referent_change={'id': str(item.pk), 'account': str(review.account_id), 'version': item.version, 'state': item.state,
                'proposal': p, 'outgoing': referentes.snapshot(outgoing) if outgoing else None, 'sources': sources,
                'evidence': review.dossier.get('evidence', {}), 'limitations': review.dossier.get('limitations', []),
                'occupancy': {'before': total, 'after': total + (1 if p['kind'] == 'add' else -1 if p['kind'] == 'remove' else 0), 'main': main, 'variables': total-main},
                'can_decide': human, 'conflict': item.conflict, 'endpoint': endpoint}))
    for exp in ReferentExperiment.objects.select_related('referent').filter(state__in=['proposed', 'postponed', 'adjustment', 'approved']):
        endpoint = f'/api/v1/referentes/experimentos/{exp.pk}/decidir'
        choices = [('Detener', 'stop')] if exp.state == 'approved' else [('Aprobar experimento', 'approve'), ('Pedir ajuste', 'adjust'), ('Descartar', 'discard'), ('Más tarde', 'later')]
        actions = [{'label': label, 'endpoint': endpoint, 'body': {'version': exp.version, 'decision': decision}, 'primary': n == 0} for n, (label, decision) in enumerate(choices)] if human else []
        out.append(card(f'referent_experiment:{exp.pk}', 'experimento', f'Experimento: {exp.referent.display_name}',
            exp.plan['hypothesis'], actions, agent='investigador_lider', created_at=exp.created_at,
            state_override='pospuesta' if exp.state == 'postponed' else None,
            referent_experiment={'id': str(exp.pk), 'version': exp.version, 'state': exp.state, 'plan': exp.plan,
                'starts_at': exp.starts_at, 'focus_at': exp.focus_at, 'followup_at': exp.followup_at, 'ends_at': exp.ends_at,
                'can_decide': human, 'endpoint': endpoint, 'results': exp.results}))
    return out
