"""OBS-03/BAR-14. Local, deterministic evidence shared through the orchestrators.

No connector/model calls, identity guessing, inbox text or outreach side effects.
Dates describe observations unless an actual event timestamp was supplied.
"""
from collections import Counter, defaultdict
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
import hashlib
import json
import math
import re

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .models import (ActionExecution, Contact, EvidenceCoverage, EvidencePerson, FitClassification,
                     ObservedPost, PersonEvidence, PostMetric, Referent, ReferentAttribution)

CRITERION_VERSION = 'network-fit-v1'
REPORT_VERSION = 1
KINDS = {'referent_comment', 'own_comment', 'reactor', 'invitation', 'connection',
         'manual', 'follower', 'discovery'}
OWN_KINDS = {'own_comment', 'reactor'}
PARTIAL = {'status': 'partial', 'limit': 50, 'paginated': False}


@dataclass(frozen=True)
class EvidenceRequest:
    account: str
    start: str
    end: str
    as_of: str


@dataclass(frozen=True)
class EvidenceResult:
    schema_version: int
    window: dict
    coverage: dict
    people: tuple[dict, ...]
    referents: tuple[dict, ...]
    aggregates: dict

    @classmethod
    def from_dict(cls, value):
        return cls(**dict(value, people=tuple(value['people']), referents=tuple(value['referents'])))


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, default=str,
                                     allow_nan=False).encode()).hexdigest()


def moment(value):
    """Invalid/unknown provider dates stay unknown, never replaced by now()."""
    if isinstance(value, str):
        try:
            value = parse_datetime(value)
        except ValueError:
            return None
    return value if isinstance(value, datetime) and timezone.is_aware(value) else None


def iso(value):
    return value.isoformat() if value else None


def person(account, provider_user_id, name=''):
    if not isinstance(provider_user_id, str) or not provider_user_id.strip() or len(provider_user_id) > 200:
        raise ValueError('Identidad opaca ausente o inválida; no se deduplica por nombre.')
    row, _ = EvidencePerson.objects.get_or_create(account=account, provider_user_id=provider_user_id,
                                                  defaults={'display_name': name[:200]})
    return row


@transaction.atomic
def observe(who, *, kind, source, source_id, observed_at, referent=None, post_id='', interaction_id='',
            source_url='', event_at=None, coverage=None, details=None, experiment_id=''):
    if kind not in KINDS or not source_id or not moment(observed_at):
        raise ValueError('Observación sin tipo, fuente o fecha verificable.')
    if referent and referent.account_id != who.account_id:
        raise ValueError('Referente de otra cuenta.')
    if kind == 'reactor':
        # No current adapter provides reactor identities. A caller cannot enable this with a flag.
        raise ValueError('Reactores: sin identidad; falta un adaptador de identidades validado.')
    if kind == 'follower' and source != 'manual':
        raise ValueError('Seguidores identificados requieren evidencia manual específica.')
    allowed = {'substantive', 'comments_in_cut', 'direction', 'origin', 'evidence_ref', 'access',
               'legacy', 'event_time_unknown'}
    clean = {k: v for k, v in (details or {}).items() if k in allowed}
    if source == 'manual' and (not re.fullmatch(r'(capture|manual):[0-9a-f-]{36}', str(clean.get('evidence_ref', '')))
                               or clean.get('access') != 'private'):
        raise ValueError('La evidencia manual necesita un localizador privado, nunca el texto de un mensaje.')
    if source != 'manual' and clean.get('origin') == 'declared':
        raise ValueError('Un cruce automático no acredita origen declarado.')
    key = digest([kind, source, source_id, str(referent.pk) if referent else '', post_id, interaction_id])
    row, created = PersonEvidence.objects.get_or_create(person=who, key=key, defaults={
        'kind': kind, 'source': source, 'source_id': source_id, 'referent': referent,
        'post_id': post_id, 'interaction_id': interaction_id, 'source_url': source_url,
        'event_at': moment(event_at), 'observed_at': observed_at, 'coverage': coverage or PARTIAL,
        'details': clean, 'experiment_id': experiment_id})
    if not created:
        row = PersonEvidence.objects.select_for_update().get(pk=row.pk)
        if observed_at < row.observed_at:
            row.observed_at = observed_at
            row.save(update_fields=['observed_at'])
    return row


def record_coverage(account, source, source_id, at, status, details, referent=None):
    return EvidenceCoverage.objects.get_or_create(account=account, source=source, source_id=source_id,
        defaults={'observed_at': at, 'status': status, 'details': details, 'referent': referent})[0]


@transaction.atomic
def referent_comments(post, comments, observed_at):
    """Called with the already-fetched page, including known people and short comments."""
    if not post.referent_id or not post.referent.active:
        return
    read_id = f'{post.pk}:{observed_at.isoformat()}'
    record_coverage(post.account, 'referent_comments', read_id, observed_at,
                    'missing' if comments is None else 'partial',
                    dict(PARTIAL, status='missing' if comments is None else 'partial',
                         returned=None if comments is None else len(comments),
                         without_identity=None if comments is None else sum(not (c.get('author') or {}).get('id') for c in comments)), post.referent)
    for index, comment in enumerate(comments or []):
        author = comment.get('author') or {}
        uid = author.get('id')
        if (comment.get('is_sender') or not uid or uid == post.author_provider_id
                or author.get('type') not in (None, '', 'individual')):
            continue
        who = person(post.account, uid, author.get('display_name') or '')
        interaction = comment.get('id') or ''
        observe(who, kind='referent_comment', source='list_comments',
                source_id=interaction or f'{read_id}:{index}', observed_at=observed_at, referent=post.referent,
                post_id=post.provider_post_id, interaction_id=interaction, source_url=post.share_url,
                event_at=comment.get('created_at'), coverage=PARTIAL,
                details={'substantive': len(' '.join((comment.get('text') or '').split())) >= 80})


@transaction.atomic
def ingest_metric(metric):
    """Reuse compact PostMetric.commenters; no second comment read or fabricated event ids."""
    account = metric.piece.account
    commenters = metric.commenters
    record_coverage(account, 'post_metric', str(metric.pk), metric.captured_at,
                    'missing' if commenters is None else 'partial',
                    dict(PARTIAL, status='missing' if commenters is None else 'partial',
                         piece=str(metric.piece_id), kind=metric.kind,
                         comments=metric.comments, reactions=metric.reactions,
                         reactions_identity='sin identidad', published_at=iso(metric.published_at),
                         returned=None if commenters is None else len(commenters)))
    grouped = defaultdict(list)
    for entry in commenters or []:
        if entry.get('provider_user_id'):
            grouped[entry['provider_user_id']].append(entry)
    for uid, entries in grouped.items():
        who = person(account, uid, entries[0].get('name') or '')
        observe(who, kind='own_comment', source='post_metric', source_id=str(metric.pk),
                observed_at=metric.captured_at, post_id=metric.provider_post_id,
                source_url=metric.share_url, coverage=dict(PARTIAL, event_ids=False, event_dates=False),
                details={'comments_in_cut': len(entries), 'substantive': any(c.get('substantive') for c in entries)})


def ingest_audience(account, snapshot):
    record_coverage(account, 'audience_snapshot', str(snapshot.pk), snapshot.captured_at, 'aggregate',
                    {'followers': snapshot.followers, 'connections': snapshot.connections,
                     'profile_views': snapshot.profile_views, 'profile_views_days': snapshot.profile_views_days,
                     'identity': 'sin identidad'})


def record_classification(contact, *, version=None, threshold=None, observed_at=None):
    data = contact.classification or {}
    if not data:
        return None
    version = version or data.get('criterion_version') or 'legacy-unknown'
    threshold = threshold if threshold is not None else data.get('minimum_confidence')
    confidence = data.get('confidence')
    classified_at = moment(data.get('classified_at'))
    public_evidence = bool(contact.headline or (contact.evidence or {}).get('comment'))
    sufficient = (version != 'legacy-unknown' and classified_at is not None and public_evidence
                  and type(data.get('fit')) is bool and bool(data.get('reason'))
                  and type(confidence) in (int, float) and math.isfinite(confidence)
                  and type(threshold) in (int, float) and 0 <= threshold <= confidence <= 1)
    clean = {k: data.get(k) for k in ('role', 'confidence', 'model', 'course_citations', 'missing_data')}
    clean.update(minimum_confidence=threshold, public_evidence=public_evidence)
    who = person(contact.account, contact.provider_user_id, contact.display_name)
    # Never copy Contact.evidence: it may contain private invitation messages.
    # New profile data cannot retroactively make an unchanged classification sufficient.
    key = digest([version, classified_at, data.get('fit'),
                  {k: v for k, v in clean.items() if k != 'public_evidence'}, digest(data.get('reason') or '')])
    return FitClassification.objects.get_or_create(person=who, key=key, defaults={
        'criterion_version': version, 'classified_at': classified_at,
        'recorded_at': observed_at or timezone.now(), 'sufficient': sufficient,
        'fit': data['fit'] if sufficient else None, 'details': clean})[0]


def relationship(contact, kind, source_id, at, *, event_at=None, direction=''):
    who = person(contact.account, contact.provider_user_id, contact.display_name)
    return observe(who, kind=kind, source='relationship', source_id=source_id, observed_at=at,
                   event_at=event_at, coverage={'status': 'partial', 'basis': 'confirmed_relationship'},
                   details={'direction': direction})


def ingest_contact(contact):
    """Conservative legacy import: exact post FK only; no name matching or historical reconstruction."""
    who = person(contact.account, contact.provider_user_id, contact.display_name)
    evidence = contact.evidence or {}
    post = None
    if evidence.get('post_id'):
        try:
            post = ObservedPost.objects.filter(pk=evidence['post_id'], account=contact.account).first()
        except (ValueError, ValidationError):
            pass
    # The initial contact may predate every later comment. Preserve it as discovery,
    # never as an additional reconstructed comment event.
    observe(who, kind='discovery', source='contact_legacy', source_id=str(contact.pk),
            observed_at=contact.discovered_at, referent=post.referent if post else None,
            post_id=post.provider_post_id if post else '', source_url=post.share_url if post else '',
            coverage={'status': 'partial', 'legacy': True}, details={'legacy': True})
    record_classification(contact)
    for kind, at in (('invitation', contact.invited_at), ('connection', contact.connected_at)):
        if at and not who.observations.filter(kind=kind).exists():
            relationship(contact, kind, f'legacy:{contact.pk}:{kind}', at)
    if contact.source == 'incoming' and not who.observations.filter(kind='invitation').exists():
        relationship(contact, 'invitation', f'legacy:{contact.pk}:incoming', contact.discovered_at, direction='received')


def sync_stored(account, as_of):
    for contact in Contact.objects.filter(account=account, discovered_at__lte=as_of).select_related('account').iterator():
        ingest_contact(contact)
    captured = set(EvidenceCoverage.objects.filter(account=account, source='post_metric').values_list('source_id', flat=True))
    for metric in PostMetric.objects.filter(piece__account=account, captured_at__lte=as_of).select_related('piece__account').iterator():
        if str(metric.pk) not in captured:
            ingest_metric(metric)


def add_manual(user, account, *, provider_user_id, source_id, observed_at, evidence_ref,
               kind='manual', referent=None, event_at=None, origin='unknown', experiment_id=''):
    """Private capture locator only; callers must not pass its contents or an inbox excerpt."""
    from .permissions import require
    require(user, 'operate_linkedin')
    if kind not in ('manual', 'follower', 'invitation', 'connection') or origin not in ('unknown', 'declared'):
        raise ValueError('Tipo u origen manual inválido.')
    if not evidence_ref or (origin == 'declared' and referent is None):
        raise ValueError('Hace falta una fuente privada y el referente para un origen declarado.')
    with transaction.atomic():
        row = observe(person(account, provider_user_id), kind=kind, source='manual', source_id=source_id,
            observed_at=observed_at, event_at=event_at, referent=referent, experiment_id=experiment_id,
            coverage={'status': 'partial', 'manual': True},
            details={'evidence_ref': evidence_ref, 'access': 'private', 'origin': origin})
        from .models import AuditEvent
        AuditEvent.objects.get_or_create(action='evidence.manual', target=str(row.pk),
                                         defaults={'actor': user, 'metadata': {'kind': kind}})
    return row


def contact_context(contact):
    """Identifiers and dates for a decision, no private sources or excerpts."""
    rows = PersonEvidence.objects.filter(person__account=contact.account,
                                         person__provider_user_id=contact.provider_user_id).order_by('observed_at', 'key')
    return [{'evidence': str(e.pk), 'kind': e.kind, 'source': e.source, 'referent': str(e.referent_id) if e.referent_id else None,
             'post_id': e.post_id, 'interaction_id': e.interaction_id, 'source_url': e.source_url,
             'event_at': iso(e.event_at), 'observed_at': iso(e.observed_at), 'coverage': e.coverage,
             'experiment_id': e.experiment_id} for e in rows]


def _fit(who, at):
    versions = [v for v in who.fit_versions.all() if v.classified_at and v.classified_at < at]
    latest = max(versions, key=lambda v: (v.classified_at, v.recorded_at, v.key), default=None)
    return {'fit': latest.fit if latest and latest.sufficient else None,
            'sufficient': bool(latest and latest.sufficient),
            'criterion_version': latest.criterion_version if latest else None,
            'minimum_confidence': latest.details.get('minimum_confidence') if latest else None,
            'classified_at': iso(latest.classified_at) if latest else None,
            'version_id': str(latest.pk) if latest else None}


def _coverage(people):
    total = len(people)
    classified = sum(p['classification']['sufficient'] for p in people)
    fits = sum(p['classification']['fit'] is True for p in people)
    versions = sorted({p['classification']['criterion_version'] for p in people if p['classification']['sufficient']})
    return {'observed': total, 'classified': classified, 'unknown': total-classified,
            'fit': fits if classified else None, 'fit_pct': round(100*fits/classified, 2) if classified else None,
            'classification_coverage': f'{classified}/{total}', 'criterion_versions': versions,
            'status': 'partial' if classified else 'Sin datos suficientes', 'population': 'personas observadas'}


def _aggregates(account, start, end):
    latest = {}
    for cut in EvidenceCoverage.objects.filter(account=account, source='post_metric', observed_at__gte=start,
                                                observed_at__lt=end).order_by('observed_at', 'source_id'):
        latest[cut.details['piece']] = cut
    reactions = [c.details.get('reactions') for c in latest.values()]
    known = [v for v in reactions if v is not None]
    audience = list(EvidenceCoverage.objects.filter(account=account, source='audience_snapshot',
                        observed_at__gte=start, observed_at__lt=end).order_by('observed_at', 'source_id'))
    first, last = (audience[0], audience[-1]) if len(audience) >= 2 else (None, None)
    def delta(field):
        a, b = (first.details.get(field), last.details.get(field)) if first else (None, None)
        return b-a if a is not None and b is not None else None
    return {'reactions': {'value': sum(known) if known else None, 'identity': 'sin identidad',
                          'coverage': f'{len(known)}/{len(reactions)}', 'basis': 'último corte por pieza en la ventana'},
            'followers_net': {'value': delta('followers'), 'identity': 'sin identidad',
                              'first': iso(first.observed_at) if first else None,
                              'last': iso(last.observed_at) if last else None,
                              'meaning': 'variación neta agregada; no altas ni atribución por referente'}}


def report(request):
    """Typed local tool. Windows are half-open and classifications are frozen at the observation cutoff."""
    from .models import ConnectorAccount
    account = ConnectorAccount.objects.get(pk=request.account)
    start, end, as_of = (moment(v) for v in (request.start, request.end, request.as_of))
    if not all((start, end, as_of)) or not start < end <= as_of or end-start > timedelta(days=366):
        raise ValueError('Ventana incompatible: fechas conscientes, inicio < fin <= corte, máximo 366 días.')
    sync_stored(account, as_of)
    people, histories = [], {}
    for who in EvidencePerson.objects.filter(account=account).prefetch_related('observations', 'fit_versions').order_by('provider_user_id'):
        history = sorted((e for e in who.observations.all() if e.observed_at < end), key=lambda e: (e.observed_at, e.key))
        if not history:
            continue
        histories[str(who.pk)] = history
        in_window = [e for e in history if start <= e.observed_at]
        if not in_window:
            continue
        first_own = next((e for e in history if e.kind in OWN_KINDS), None)
        refs = sorted({str(e.referent_id) for e in history if e.referent_id})
        people.append({'person': str(who.pk), 'provider_user_id': who.provider_user_id,
            'first_observed_at': iso(history[0].observed_at), 'arrival_at': None,
            'classification': _fit(who, min(end, as_of)), 'referents': refs,
            'sources': sorted({e.kind for e in in_window}),
            'first_own_observation': iso(first_own.observed_at) if first_own else None,
            'new_own_observation': bool(first_own and first_own.observed_at >= start),
            'connection_observed': any(e.kind == 'connection' for e in in_window),
            'follower_identified': any(e.kind == 'follower' for e in in_window)})
    reads = list(EvidenceCoverage.objects.filter(account=account, observed_at__gte=start, observed_at__lt=end))
    referents = []
    for ref in Referent.objects.filter(account=account).order_by('id'):
        cohort = [p for p in people if str(ref.pk) in p['referents']]
        executions = ActionExecution.objects.filter(proposal__post__referent=ref, state='confirmed', wrote=True,
                         proposal__capability__in=['INT-03', 'INT-02'], started_at__lt=end).order_by('started_at')
        exposures, undated_exposures = [], []
        for execution in executions.select_related('proposal'):
            confirmed_at = execution.reconciled_at or execution.finished_at
            if not confirmed_at:
                undated_exposures.append(str(execution.pk))
            elif start <= confirmed_at < end:
                exposures.append({'execution': str(execution.pk), 'confirmed_at': iso(confirmed_at),
                                  'started_at': iso(execution.started_at), 'capability': execution.proposal.capability})
        baseline = {pid for pid, rows in histories.items() if any(e.observed_at < start and e.referent_id == ref.pk for e in rows)}
        associations = []
        for p in cohort:
            rows = histories[p['person']]
            declared = [e for e in rows if e.referent_id == ref.pk and e.details.get('origin') == 'declared']
            first_ref = next(e for e in rows if e.referent_id == ref.pk)
            first_own = next((e for e in rows if e.kind in OWN_KINDS), None)
            associations.append({'person': p['person'], 'first_observed_at': iso(first_ref.observed_at),
                'event_at': iso(first_ref.event_at), 'evidence': str(first_ref.pk),
                'own_after_referent': bool(first_own and first_own.observed_at > first_ref.observed_at),
                'shared_with': [r for r in p['referents'] if r != str(ref.pk)],
                'origin': 'declarado_por_persona' if declared else 'coincidencia_observable' if first_own else 'desconocido',
                'declared_evidence': [str(e.pk) for e in declared], 'causal_claim': False})
        ref_reads = [r for r in reads if r.referent_id == ref.pk]
        result = {'referent': str(ref.pk), 'active': ref.active, 'coverage': _coverage(cohort),
            'baseline': {'observed_before_window': len(baseline) if baseline else None,
                         'own_observed_before_window': sum(any(e.kind in OWN_KINDS and e.observed_at < start
                             for e in histories[p['person']]) for p in cohort) or None,
                         'status': 'partial' if baseline else 'sin dato'},
            'exposure': exposures, 'exposure_without_date': undated_exposures,
            'exposure_count': len(exposures) if exposures else None,
            'discovered': (sum(moment(a['first_observed_at']) >= start for a in associations)
                if cohort or any(r.status == 'partial' for r in ref_reads) else None),
            'new_own_observations': (sum(p['new_own_observation'] for p in cohort)
                if any(r.source == 'post_metric' and r.status == 'partial' for r in reads) else None),
            'connections_confirmed': sum(p['connection_observed'] for p in cohort) or None,
            'associations': associations, 'reads': dict(Counter(r.status for r in ref_reads)),
            'causal_claim': False, 'comparison': 'Sin datos suficientes: cobertura parcial; no estima efecto causal.'}
        key = digest([REPORT_VERSION, request.start, request.end, request.as_of, result])
        saved, _ = ReferentAttribution.objects.get_or_create(referent=ref, key=key, defaults={
            'window_start': start, 'window_end': end, 'as_of': as_of, 'report': result})
        referents.append(dict(result, record_id=str(saved.pk)))
    coverage = dict(_coverage(people), reads=dict(Counter(r.status for r in reads)),
                    missing='sin dato', limits=['Comentarios: hasta 50, sin paginación.',
                    'Primera observación no equivale a llegada.', 'No hay identidades automáticas de seguidores/reactores.'])
    return EvidenceResult(REPORT_VERSION, asdict(request), coverage, tuple(people), tuple(referents), _aggregates(account, start, end))


def consult(user, request, *, runtime=None):
    """Orchestrator entry point; specialists receive the result, never call each other."""
    from .permissions import require
    from . import orquestacion
    require(user, 'operate_linkedin')
    if runtime is not None:
        return runtime.call('evidencia_red', request, lambda: report(request), key='evidencia')
    run = orquestacion.Runtime.open('consulta_evidencia', digest([str(user.pk), asdict(request)]), user,
                                   facts={'account': request.account}, plan=['evidencia_analista'])
    with run.session():
        result = run.call('evidencia_analista', request, lambda: report(request), key='evidencia')
        run.finish({'schema_version': result.schema_version})
        return result
