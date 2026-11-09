"""Read-only team map. No provider calls and no mutation of jobs or audit data."""
from django.db.models import CharField, Q, Value
from django.db.models.functions import Cast, Concat
from django.db.models.fields.json import KeyTextTransform
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView
from .grafo import graph_hash, load_graph
from .jobs import visible_jobs
from .models import AuditEvent, Capture, EditorialPiece, WebResearchRun
from .permissions import require


def recent_activity(graph, user):
    """Bounded metadata only. Job ownership is identical to the jobs endpoint.

    Office handoffs are the existing shared office feed, not evidence that an
    agent invoked another agent. Missing attribution stays empty rather than
    assigning a whole prepare_piece job to stages that never ran.
    """
    result = {}
    jobs_cache, events_cache = {}, {}
    visible = visible_jobs(user)
    for node in graph['nodes']:
        activity = node['activity']
        jobs, handoffs, records = [], [], []
        if node['status'] == 'active':
            kinds = tuple(activity['job_kinds'])
            stage, agent = activity.get('stage'), activity.get('agent')
            evidence = activity.get('piece_evidence')
            capture_evidence = activity.get('capture_evidence')
            key = kinds, stage, agent, evidence, capture_evidence
            if kinds:
                if key not in jobs_cache:
                    rows = visible.filter(kind__in=kinds)
                    if agent:
                        rows = rows.filter(agent=agent)
                    if stage or evidence:
                        pieces = EditorialPiece.objects.all()
                        if stage:
                            pieces = pieces.filter(Q(usage__contains=[{'stage': stage}]) | Q(stage=stage))
                        elif evidence == 'design':
                            pieces = pieces.exclude(image_spec={})
                        elif evidence == 'edited':
                            pieces = pieces.filter(images__edited=True)
                        elif evidence == 'review':
                            pieces = pieces.filter(Q(image_review__has_key='attempts') | Q(images__review__has_key='ok'))
                        rows = rows.annotate(graph_job_id=Cast('id', CharField())).filter(
                            graph_job_id__in=pieces.exclude(origin_job='').values('origin_job'))
                    if capture_evidence:
                        captures = Capture.objects.all()
                        if capture_evidence == 'route':
                            captures = captures.filter(understanding__has_key='destino')
                        elif capture_evidence == 'intent':
                            captures = captures.filter(understanding__method='jev')
                        elif capture_evidence == 'transcript':
                            captures = captures.exclude(transcript_provider_id='')
                        captures = captures.annotate(graph_capture_id=Cast('id', CharField()))
                        rows = rows.annotate(graph_capture_id=KeyTextTransform('capture', 'params')).filter(
                            graph_capture_id__in=captures.values('graph_capture_id'))
                    jobs_cache[key] = [
                        {'id': str(j.id), 'kind': j.kind, 'state': j.state,
                         'at': j.finished_at or j.started_at or j.created_at, 'stage': stage}
                        for j in rows.only('id', 'kind', 'state', 'created_at', 'started_at', 'finished_at')
                        .order_by('-created_at', '-id')[:5]]
                jobs = jobs_cache[key]
            roles = tuple(activity['event_roles'])
            if roles:
                if roles not in events_cache:
                    rows = AuditEvent.objects.filter(action='office.event', metadata__tipo='entrega').filter(
                        Q(metadata__rol__in=roles) | Q(metadata__destino__in=roles)).order_by('-created_at', '-id')[:5]
                    events_cache[roles] = [
                        {'id': str(e.id), 'at': e.created_at, 'from': e.metadata.get('rol', ''),
                         'to': e.metadata.get('destino', ''), 'detail': e.metadata.get('detalle', '')}
                        for e in rows]
                handoffs = events_cache[roles]
            actions = activity.get('audit_actions', [])
            if actions:
                rows = AuditEvent.objects.filter(action__in=actions).order_by('-created_at', '-id')[:5]
                records += [{'id': str(e.id), 'at': e.created_at,
                             'label': 'Propuesta revisada por Jev' if e.action == 'operator.lead_reviewed' else 'Veto registrado'}
                            for e in rows]
            if activity.get('research'):
                rows = WebResearchRun.objects.all()
                if not user.has_perm('team_backend.manage_jobs'):
                    keys = lambda qs, prefix: qs.annotate(graph_key=Concat(Value(prefix), Cast('id', CharField()))).values('graph_key')
                    rows = rows.filter(Q(key__in=keys(Capture.objects.filter(created_by=user), 'capture:')) |
                                       Q(key__in=keys(EditorialPiece.objects.filter(created_by=user), 'piece:')))
                records += [{'id': r.key, 'at': r.created_at, 'label': 'Investigación: ' + r.state}
                            for r in rows.only('key', 'created_at', 'state').order_by('-created_at', '-key')[:5]]
        result[node['id']] = {'jobs': jobs, 'handoffs': handoffs, 'records': records}
    return result


class EquipoGrafo(APIView):
    def get(self, request):
        require(request.user, 'operate_linkedin')
        graph = load_graph()
        activity = recent_activity(graph, request.user)
        return Response({
            'schema_version': graph['schema_version'], 'graph_version': graph['graph_version'],
            'graph_hash': graph_hash(graph), 'scope': graph['scope'], 'updated_at': timezone.now(),
            'groups': graph['groups'], 'nodes': [dict(n, recent_activity=activity[n['id']]) for n in graph['nodes']],
            'edges': graph['edges'], 'cycles': graph['cycles'], 'gates': graph['gates'],
        })
