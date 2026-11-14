"""Registry-owned tool calls, durable checkpoints and conservative crash recovery.

Only workflow code advances a cycle. Tool results are data, never delegation or
permission to write LinkedIn. Private payloads stay in the ledger/storage; audit
and office events contain identifiers and counters only.
"""
from contextlib import contextmanager
from dataclasses import asdict, is_dataclass, fields
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from typing import Literal, get_args, get_origin, get_type_hints
from decimal import Decimal
from importlib import import_module
import hashlib
import json
import math
import os
from pathlib import Path
import uuid

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models, transaction
from django.utils import timezone
from .grafo import graph_hash, load_graph
from .models import CycleLedger, UsageEntry

from knowledge.cycle_context import _current, _active_call, CycleStopped


class UndeclaredCall(CycleStopped):
    pass


class ContractError(ValueError):
    pass


def current():
    return _current.get()


def plain(value):
    return json.loads(json.dumps(value, cls=DjangoJSONEncoder, ensure_ascii=False, allow_nan=False))


def digest(value):
    return hashlib.sha256(json.dumps(plain(value), sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def resolve(binding):
    parts = binding.split('.')
    value = import_module('.'.join(parts[:2]))
    for part in parts[2:]:
        value = getattr(value, part)
    return value


def validate(value, schema, path='payload'):
    """Small strict JSON Schema subset used by the registry (no extra dependency)."""
    kind = schema.get('type')
    types = {'object': isinstance(value, dict), 'array': isinstance(value, (list, tuple)),
             'string': isinstance(value, str), 'integer': type(value) is int,
             'boolean': type(value) is bool, 'null': value is None,
             'number': type(value) in (int, float) and math.isfinite(value)}
    if kind and not types.get(kind, False):
        raise ValueError(f'{path}: tipo inválido')
    if 'enum' in schema and value not in schema['enum']:
        raise ValueError(f'{path}: opción inválida')
    if kind == 'object':
        props = schema.get('properties', {})
        if not set(schema.get('required', [])) <= value.keys():
            raise ValueError(f'{path}: faltan campos')
        if schema.get('additionalProperties') is False and value.keys() - props.keys():
            raise ValueError(f'{path}: campos desconocidos')
        for key, item in value.items():
            if key in props:
                validate(item, props[key], path + '.' + key)
    if kind == 'array':
        for item in value:
            validate(item, schema.get('items', {}), path + '[]')


def validate_dataclass(value):
    def typed(item, annotation):
        origin, args = get_origin(annotation), get_args(annotation)
        if origin is Literal:
            valid = item in args
        elif origin is tuple:
            valid = isinstance(item, tuple)
            if valid:
                for child in item:typed(child,args[0])
        elif annotation in (str, bool, int, dict):
            valid = type(item) is annotation
        elif is_dataclass(annotation):
            valid = isinstance(item,annotation)
            if valid:validate_dataclass(item)
        else:
            valid = False
        if not valid:raise ValueError('Campo de dataclass inválido')
    hints = get_type_hints(type(value))
    for field in fields(value):typed(getattr(value,field.name),hints[field.name])


def pack(value):
    if isinstance(value, models.Model):
        return {'__model__': value._meta.label, 'pk': str(value.pk)}
    if is_dataclass(value):
        return {'__dataclass__': type(value).__module__ + '.' + type(value).__name__, 'value': plain(asdict(value))}
    if isinstance(value, bytes):
        sha = hashlib.sha256(value).hexdigest()
        path = default_storage.save('cycles/' + uuid.uuid4().hex + '/' + sha, ContentFile(value))
        return {'__blob__': path, 'sha256': sha}
    if isinstance(value, tuple):
        return {'__tuple__': [pack(v) for v in value]}
    if isinstance(value, list):
        return [pack(v) for v in value]
    if isinstance(value, dict):
        return {'__dict__': {k: pack(v) for k, v in value.items()}}
    return plain(value)


def unpack(value):
    if isinstance(value, list):
        return [unpack(v) for v in value]
    if not isinstance(value, dict):
        return value
    if '__model__' in value:
        from django.apps import apps
        return apps.get_model(value['__model__']).objects.get(pk=value['pk'])
    if '__dataclass__' in value:
        cls = resolve(value['__dataclass__'])
        return cls.from_dict(value['value']) if hasattr(cls, 'from_dict') else cls(**value['value'])
    if '__blob__' in value:
        with default_storage.open(value['__blob__'], 'rb') as handle:
            raw = handle.read()
        if hashlib.sha256(raw).hexdigest() != value['sha256']:
            raise CycleStopped('Checkpoint de imagen alterado')
        return raw
    if '__tuple__' in value:
        return tuple(unpack(v) for v in value['__tuple__'])
    return {k: unpack(v) for k, v in value['__dict__'].items()}


def amount(rows):
    return sum((r.actual_usd if r.status == 'complete' and r.actual_usd is not None else r.reserved_usd
                if r.status in ('reserved', 'uncertain', 'complete') else Decimal(0) for r in rows), Decimal(0))


def effective_budget_bucket(row):
    # A monthly fan-out may straddle midnight on the last day. Charge each new
    # reservation to its actual Bogotá calendar month; never move existing usage.
    if row.limits.get('cost_period') == 'month':
        local = timezone.now().astimezone(ZoneInfo('America/Bogota'))
        return f'{row.cycle}:{local:%Y-%m}'
    return row.budget_bucket


def budget_cycle_ids(row):
    """Include legacy entries carrying only cycle_id, without rewriting durable usage."""
    return [str(pk) for pk in CycleLedger.objects.filter(budget_bucket=row.budget_bucket).values_list('pk',flat=True)]


def budget_usage(row):
    bucket=effective_budget_bucket(row)
    query=models.Q(usage__budget_bucket=bucket)
    if row.limits.get('cost_period')!='month':query|=models.Q(usage__cycle_id__in=budget_cycle_ids(row))
    return UsageEntry.objects.filter(query)


def context_version(graph):
    # Pin resolved code/contracts and non-secret model/policy overrides. A deploy
    # cannot change a running plan's schemas, model or repair policy invisibly.
    root = Path(__file__).resolve().parents[1]
    modules = {'.'.join(s['binding'].split('.')[:2]) for s in graph['schemas'].values()}
    modules.update(('knowledge.providers','team_backend.autopiloto','team_backend.orquestacion','team_backend.compuertas'))
    sources = {name:hashlib.sha256(root.joinpath(*name.split('.')).with_suffix('.py').read_bytes()).hexdigest()
               for name in modules}
    keys = ['ANTHROPIC_MODEL','ANTHROPIC_VISION_MODEL','OPENAI_IMAGE_MODEL','NETWORK_CLASSIFIER_MODEL','EDITORIAL_REPAIR',
            'LEAD_ENABLED','LEAD_CAPABILITIES','COMPUERTAS_DURAS']
    keys += ['EDITORIAL_MODEL_'+stage for stage in ('DIRECTOR','REDACTOR','LECTORES','SELECCION','VERIFICADOR','REPARACION')]
    return digest({'sources':sources,'overrides':{key:os.environ.get(key,'') for key in keys}})


def _settled(call):
    """Answered, or a known failure that Runtime.call replays as data; anything else may still be in flight."""
    return call['state']=='answered' or (call['state']=='failed' and call.get('error_type') in ('ValueError','OSError','ContractError'))


def migrate_at_gate(ledger, graph, definition):
    """Explicit migration of a finished cycle to the current graph, only to run its gate.

    The pin (graph_hash, context_version) keeps a deploy from changing a working plan's schemas, models or policy
    half way. A cycle that already finished (a ready piece waiting for its hour, an approved network action) has no plan
    left: only its gate, a fresh Jev review of the final payload, which runs under the current graph. Before this, any
    deploy that touched the graph or a pinned module stopped every ready post (10/11/2026: the 3:30 pm post never went
    out). Only a complete cycle, without a worker and with every call settled, migrates; the change is recorded in the
    task ledger and audited. The budget bucket and the spend already recorded stay as they were."""
    from .jobs import audit
    with transaction.atomic():
        row = CycleLedger.objects.select_for_update().get(pk=ledger.pk)
        if row.state != 'complete' or row.lease_token or not all(_settled(c) for c in row.progress_ledger['calls'].values()):
            return False
        before = {'graph_version': row.graph_version, 'graph_hash': row.graph_hash,
                  'context_version': row.task_ledger.get('context_version')}
        after = {'graph_version': graph['graph_version'], 'graph_hash': graph_hash(graph),
                 'context_version': context_version(graph)}
        row.task_ledger.setdefault('migrations', []).append(
            {'reason': 'gate_after_deploy', 'at': timezone.now().isoformat(), 'from': before, 'to': after})
        row.task_ledger['context_version'] = after['context_version']
        row.graph_version, row.graph_hash, row.limits = after['graph_version'], after['graph_hash'], definition['limits']
        row.revision += 1
        row.save(update_fields=['task_ledger', 'graph_version', 'graph_hash', 'limits', 'revision', 'updated_at'])
        audit(None, 'cycle.migrated', row.id, cycle=row.cycle, reason='gate_after_deploy',
              from_graph=before['graph_version'], to_graph=after['graph_version'], graph_hash=after['graph_hash'])
    return True


class Runtime:
    def __init__(self, ledger, graph):
        self.id, self.graph = ledger.pk, graph
        self.job_id = str(ledger.job_id or '')
        self.cycle = next(c for c in graph['cycles'] if c['id'] == ledger.cycle)
        self.owner = self.cycle['orchestrator']
        self.limits = ledger.limits
        self.token = uuid.uuid4().hex
        self.ordinals = {}

    @classmethod
    def open(cls, cycle, key, user, job=None, facts=None, plan=None, *, budget_parent=None, at_gate=False):
        """`at_gate`: the caller only runs the cycle's gate (review_gate). A finished cycle then survives a deploy that
        changed the graph or the pinned code (migrate_at_gate); any other open still stops with graph_changed."""
        graph = load_graph()
        definition = next((c for c in graph['cycles'] if c['id'] == cycle), None)
        if not definition or definition['status'] != 'active' or definition['ledger']['status'] != 'runtime':
            from .jobs import audit
            audit(user,'cycle.rejected',cycle,reason='inactive_cycle')
            raise UndeclaredCall('Ciclo sin runtime activo')
        limits = definition['limits']
        local = timezone.localtime(timezone.now(), ZoneInfo('America/Bogota'))
        period = limits.get('cost_period', 'cycle')
        bucket = f'{cycle}:{local:%Y-%m}' if period == 'month' else f'{cycle}:{key}'
        parent_cycle=definition.get('budget_parent_cycle')
        if parent_cycle:
            if not budget_parent or budget_parent.cycle!=parent_cycle or budget_parent.owner_id!=user.pk:
                raise UndeclaredCall('Falta el ciclo padre autorizado para compartir presupuesto')
            bucket=budget_parent.budget_bucket
        elif budget_parent is not None:
            raise UndeclaredCall('Presupuesto compartido no declarado')
        ledger, _ = CycleLedger.objects.get_or_create(cycle=cycle, key=key, defaults={
            'owner': user, 'job': job, 'orchestrator': definition['orchestrator'],
            'graph_version': graph['graph_version'], 'graph_hash': graph_hash(graph),
            'limits': limits, 'budget_bucket': bucket,
            'task_ledger': {'facts': plain(facts or {}), 'plan': plan or [], 'plan_version': 1,
                            'context_version':context_version(graph)},
            'progress_ledger': {'calls': {}, 'stall_count': 0, 'replans': 0, 'next_step': '', 'snapshots': {}},
        })
        runtime = cls(ledger, graph)
        if ledger.owner_id != user.pk:
            raise UndeclaredCall('La instancia pertenece a otro usuario')
        if ledger.budget_bucket!=bucket and parent_cycle:
            raise UndeclaredCall('El presupuesto padre de la instancia cambió')
        if ledger.graph_hash != graph_hash(graph) or ledger.task_ledger.get('context_version')!=context_version(graph):
            if at_gate and migrate_at_gate(ledger, graph, definition):
                return cls(CycleLedger.objects.get(pk=ledger.pk), graph)
            runtime.stop('graph_changed')
            raise CycleStopped('El checkpoint necesita migración explícita del grafo')
        return runtime

    @contextmanager
    def session(self):
        if current() is not None:
            self.deny('nested_cycle')
        with transaction.atomic():
            row = CycleLedger.objects.select_for_update().get(pk=self.id)
            if row.state == 'stopped':
                raise CycleStopped(row.stop_reason)
            if row.lease_token:
                raise CycleStopped('La instancia ya tiene un trabajador; conciliar antes de continuar')
            self.session_started=timezone.now()
            self.base_seconds=row.active_seconds
            row.lease_token = self.token
            row.save(update_fields=['lease_token', 'updated_at'])
        context = _current.set(self)
        try:
            yield self
        finally:
            _current.reset(context)
            with transaction.atomic():
                row=CycleLedger.objects.select_for_update().get(pk=self.id)
                if row.lease_token==self.token:
                    row.active_seconds=max(row.active_seconds,self.elapsed())
                    row.lease_token=''
                    row.save(update_fields=['lease_token','active_seconds','updated_at'])

    def elapsed(self):
        return self.base_seconds+max(0,(timezone.now()-self.session_started).total_seconds())

    def locked(self):
        row = CycleLedger.objects.select_for_update().get(pk=self.id)
        if row.lease_token != self.token or row.state == 'stopped':
            raise CycleStopped(row.stop_reason or 'Resultado de un trabajador obsoleto')
        return row

    def stop(self, reason, business=None):
        business = reason in ('cost_cap', 'stall', 'uncertain') if business is None else business
        with transaction.atomic():
            row = CycleLedger.objects.select_for_update().get(pk=self.id)
            if row.state == 'stopped':
                return
            row.state, row.stop_reason, row.needs_attention = 'stopped', reason, business
            row.save(update_fields=['state', 'stop_reason', 'needs_attention', 'updated_at'])
            self.audit('stopped', reason=reason)
            if business:
                from .notificaciones import avisar
                transaction.on_commit(lambda: avisar('cycle_stopped', 'El ciclo se ha detenido',
                    'Se conserva el progreso. Motivo: ' + reason, ref=f'cycle:{self.id}', link='/tu-turno'))

    def audit(self, event, **metadata):
        from .jobs import audit
        audit(None, 'cycle.' + event, self.id, cycle=self.cycle['id'], job_id=self.job_id,
              graph_hash=graph_hash(self.graph), **metadata)

    def deny(self, reason):
        self.audit('rejected', reason=reason)
        self.stop(reason, business=False)
        raise UndeclaredCall(reason)

    def snapshot(self, key, factory):
        # Workflow facts (including private context) are frozen once, never in public events.
        with transaction.atomic():
            row = self.locked()
            snapshots = row.progress_ledger['snapshots']
            if key not in snapshots:
                snapshots[key] = pack(factory())
                row.save(update_fields=['progress_ledger', 'updated_at'])
            return unpack(snapshots[key])

    def contract(self, name, value):
        spec = self.graph['schemas'][name]
        target = resolve(spec['binding'])
        if spec['kind'] == 'json_schema':
            validate(plain(value), target)
        elif spec['kind'] == 'model':
            if not isinstance(value, target) or not value.pk:
                raise ValueError('Modelo de contrato inválido')
        elif spec['kind'] == 'dataclass':
            if not isinstance(value, target):
                raise ValueError('Dataclass de contrato inválido')
            # ResearchResult.from_dict also validates checkpoint structure.
            validate_dataclass(value)
            if hasattr(value,'schema_version') and value.schema_version!=1:raise ValueError('Versión de contrato inválida')
        elif spec['kind'] == 'bytes':
            if not isinstance(value, bytes) or not value:
                raise ValueError('Imagen vacía')
        else:
            raise ValueError('Contrato no ejecutable: ' + name)

    def call(self, edge_id, request, operation, *, key=None):
        if _active_call.get() is not None:
            self.deny('max_depth')
        edge = next((e for e in self.graph['edges'] if e['id'] == edge_id), None)
        if (not edge or edge['status'] != 'active' or self.cycle['id'] not in edge['cycles']
                or (edge['from'] != self.owner and not (edge['request_kind']=='gate' and edge['to']=='lider_jev'
                    and any(edge_id in self.graph['gates'][g].get('runtime_edges',[]) for g in self.cycle['gates'])))
                or not edge.get('runtime')):
            self.deny('undeclared_edge')
        edges = [edge]
        if edge.get('call_group'):
            edges = [e for e in self.graph['edges'] if e.get('call_group') == edge['call_group']]
            if any(e['from'] != self.owner or self.cycle['id'] not in e['cycles'] or e['status'] != 'active' for e in edges):
                self.deny('undeclared_group')
        try:
            self.contract(edge['request_schema'], request)
        except (ValueError, TypeError, KeyError):
            self.deny('request_schema')
        self.ordinals[edge_id] = self.ordinals.get(edge_id, 0) + 1
        key = key or f'{edge_id}:{self.ordinals[edge_id]}'
        fingerprint = digest(asdict(request) if is_dataclass(request) else
                             {'id': str(request.pk), 'payload_hash':getattr(request,'payload_hash','')} if isinstance(request, models.Model) else request)
        failure = None
        with transaction.atomic():
            row = self.locked()
            calls = row.progress_ledger['calls']
            old = calls.get(key)
            if old:
                if old['request_hash'] != fingerprint or old['edge'] != edge_id:
                    failure = 'checkpoint_changed'
                elif old['state'] == 'answered':
                    return unpack(old['result'])
                elif old['state']=='failed' and old.get('error_type') in ('ValueError','OSError','ContractError'):
                    error=ContractError if old['error_type']=='ContractError' else ValueError
                    raise error(old['error'])  # A known failure is replayed as data, never paid again.
                else:
                    failure = 'uncertain'
            if not failure:
                if row.calls >= self.limits['max_calls']:
                    failure = 'max_calls'
                elif max(row.active_seconds,self.elapsed()) >= self.limits['cycle_timeout_s']:
                    failure = 'cycle_timeout'
                elif any(sum(e['id'] in c['edges'] for c in calls.values()) >= e['max_calls_per_cycle'] for e in edges):
                    failure = 'edge_limit'
            if not failure:
                started = timezone.now()
                timeout = min(edge.get('call_timeout_s', self.limits['call_timeout_s']),
                              self.limits['cycle_timeout_s'] - max(row.active_seconds,self.elapsed()))
                call = {'edge': edge_id, 'edges': [e['id'] for e in edges], 'nodes': [e['to'] for e in edges],
                        'request_hash': fingerprint, 'request':pack(request), 'state': 'pending', 'started_at': started.isoformat(),
                        'deadline': (started + timedelta(seconds=timeout)).isoformat(), 'token': self.token}
                calls[key] = call
                row.calls += 1
                row.progress_ledger['next_step'] = key
                row.save(update_fields=['calls', 'progress_ledger', 'updated_at'])
        if failure:
            self.stop(failure)
            raise CycleStopped(failure)
        from .oficina_eventos import handoff
        for e in edges:
            handoff(self.owner, e['to'], cycle=self.id, edge=e['id'], phase='request')
        self.audit('requested', edge=edge_id, call=key)
        context = _active_call.set(dict(call, key=key, runtime=edge['runtime']))
        try:
            result = operation()
            try:
                value = result[0] if edge.get('result_projection') == 'stage' else result
                if edge.get('result_projection') == 'text':value = json.loads(result['text'])
                self.contract(edge['response_schema'], value)
            except (ValueError,TypeError,KeyError,IndexError):
                self.audit('rejected', reason='response_schema', edge=edge_id)
                raise ContractError('Respuesta fuera del schema: '+edge['response_schema']) from None
            stored = pack(result)
        except CycleStopped:
            raise
        except Exception as exc:
            duration = (timezone.now()-started).total_seconds()
            with transaction.atomic():
                row = self.locked()
                row.progress_ledger['calls'][key].update(state='failed',error_type=type(exc).__name__,
                    error=str(exc)[:2000],duration_s=duration,finished_at=timezone.now().isoformat())
                row.active_seconds = max(row.active_seconds,self.elapsed())
                row.save(update_fields=['progress_ledger','active_seconds','updated_at'])
            if duration>timeout:
                self.stop('call_timeout',business=False)
                raise CycleStopped('call_timeout') from None
            self.audit('failed', edge=edge_id, call=key)
            raise
        finally:
            _active_call.reset(context)
        duration = (timezone.now() - started).total_seconds()
        if duration > timeout:
            self.stop('call_timeout', business=False)
            raise CycleStopped('call_timeout')
        with transaction.atomic():
            row = CycleLedger.objects.select_for_update().get(pk=self.id)
            if row.lease_token != self.token:raise CycleStopped('Resultado de un trabajador obsoleto')
            row.progress_ledger['calls'][key].update(state='answered', result=stored,
                finished_at=timezone.now().isoformat(), duration_s=duration)
            row.progress_ledger['next_step'] = ''
            row.active_seconds = max(row.active_seconds,self.elapsed())
            row.revision += 1
            row.save(update_fields=['progress_ledger', 'active_seconds', 'revision', 'updated_at'])
        self.audit('answered', edge=edge_id, call=key, duration_s=duration)
        self.check_cost()
        self.progress({'edge':edge_id,'result':stored})
        for e in edges:
            handoff(e['to'], self.owner, cycle=self.id, edge=e['id'], phase='response')
        return result

    def check_cost(self):
        row = CycleLedger.objects.get(pk=self.id)
        spent = amount(UsageEntry.objects.filter(usage__cycle_id=str(self.id)))
        if spent >= Decimal(str(self.limits['cost_cap_usd'])):
            self.stop('cost_cap')
            raise CycleStopped('cost_cap')
        spent = amount(budget_usage(row))
        if spent >= Decimal(str(self.limits['cost_cap_usd'])):
            self.stop('cost_cap')
            raise CycleStopped('cost_cap')

        if self.limits.get('daily_cost_cap_usd') is not None:
            day=timezone.localtime(timezone.now(),ZoneInfo('America/Bogota')).replace(hour=0,minute=0,second=0,microsecond=0)
            rows=UsageEntry.objects.filter(created_at__gte=day).filter(
                models.Q(usage__cycle=self.cycle['id'])|models.Q(purpose__startswith='editorial-')|models.Q(purpose__startswith='image-'))
            if amount(rows)>=Decimal(str(self.limits['daily_cost_cap_usd'])):
                self.stop('cost_cap')
                raise CycleStopped('cost_cap')

    def progress(self, evidence, *, waiting=False, replan=None, key=None):
        if waiting:
            return  # A legitimate human/gate wait is not a stall.
        failure = False
        with transaction.atomic():
            row = self.locked()
            progress = row.progress_ledger
            if key:
                if key in progress.get('progress_keys',[]):return
                progress.setdefault('progress_keys',[]).append(key)
            marker = digest(evidence)
            progress['stall_count'] = progress['stall_count'] + 1 if marker == progress.get('evidence') else 0
            progress['evidence'] = marker
            if progress['stall_count'] >= self.limits['max_stalls']:
                if replan and progress['replans'] < self.limits['max_replans']:
                    row.task_ledger['plan'] = plain(replan)
                    row.task_ledger['plan_version'] += 1
                    progress['replans'] += 1
                    progress['stall_count'] = 0
                    self.audit('replanned', plan_version=row.task_ledger['plan_version'])
                else:
                    failure = True
            row.save(update_fields=['progress_ledger', 'task_ledger', 'updated_at'])
        if failure:
            self.stop('stall')
            raise CycleStopped('stall')

    def finish(self, result, *, allow_stopped=False):
        """Checkpoint a terminal workflow result without clearing a runtime stop.

        Editorial repair can close as blocked after a budget stop. It may save
        that outcome, but it cannot mark the cycle complete or authorize a call.
        """
        if self.elapsed()>=self.limits['cycle_timeout_s']:
            self.stop('cycle_timeout',business=False)
            raise CycleStopped('cycle_timeout')
        with transaction.atomic():
            row = CycleLedger.objects.select_for_update().get(pk=self.id)
            if row.lease_token != self.token:
                raise CycleStopped('Resultado de un trabajador obsoleto')
            if row.state == 'stopped':
                if not allow_stopped:raise CycleStopped(row.stop_reason)
            else:
                row.state = 'complete'
            row.progress_ledger['result'] = pack(result)
            row.save(update_fields=['state', 'progress_ledger', 'updated_at'])


def call(edge, request, operation, *, key=None):
    runtime = current()
    return runtime.call(edge, request, operation, key=key) if runtime else operation()


def provider_metadata(provider, purpose, amount_usd, connection):
    """Called under the usage ledger's global reservation lock, BEFORE INSERT/send."""
    runtime, call = current(), _active_call.get()
    if runtime is None:
        return {}
    declared = call['runtime'].get('purposes', {}) if call else {}
    # OpenAI is Claude's fallback (providers.openai_text): a purpose declared for anthropic is declared for it too.
    allowed = declared.get(provider, []) + (declared.get('anthropic', []) if provider == 'openai' else [])
    if not call or purpose not in allowed:
        runtime.deny('undeclared_provider')
    if timezone.now() >= datetime.fromisoformat(call['deadline']):
        runtime.stop('call_timeout', business=False)
        raise CycleStopped('call_timeout')
    row = CycleLedger.objects.get(pk=runtime.id)
    budget_bucket = effective_budget_bucket(row)
    if row.state == 'stopped' or row.lease_token != runtime.token:
        raise CycleStopped('Trabajador obsoleto')
    # A Claude refusal answered by OpenAI is one call, not two: its rejected row carries usage.fallback.
    used = connection.execute("""SELECT coalesce(sum(CASE WHEN status='complete' THEN coalesce(actual_usd,reserved_usd)
        WHEN status IN ('reserved','uncertain') THEN reserved_usd ELSE 0 END),0) AS spent,
        count(*) FILTER (WHERE NOT (status='rejected' AND usage ? 'fallback')) AS calls
        FROM usage_ledger WHERE usage->>'cycle_id'=%s""", (str(runtime.id),)).fetchone()
    if used['calls'] >= runtime.limits['max_provider_calls']:
        runtime.stop('provider_calls', business=False)
        raise CycleStopped('provider_calls')
    spent = used['spent']
    family=[] if runtime.limits.get('cost_period')=='month' else budget_cycle_ids(row)
    spent = connection.execute("""SELECT coalesce(sum(CASE WHEN status='complete' THEN coalesce(actual_usd,reserved_usd)
        WHEN status IN ('reserved','uncertain') THEN reserved_usd ELSE 0 END),0) AS spent
        FROM usage_ledger WHERE usage->>'budget_bucket'=%s OR usage->>'cycle_id'=ANY(%s)""",
        (budget_bucket,family)).fetchone()['spent']
    if spent + amount_usd > Decimal(str(runtime.limits['cost_cap_usd'])):
        runtime.stop('cost_cap')
        raise CycleStopped('cost_cap')
    if runtime.limits.get('daily_cost_cap_usd') is not None:
        day = timezone.localtime(timezone.now(),ZoneInfo('America/Bogota')).replace(hour=0,minute=0,second=0,microsecond=0)
        daily_spent = connection.execute("""SELECT coalesce(sum(CASE WHEN status='complete' THEN coalesce(actual_usd,reserved_usd)
            WHEN status IN ('reserved','uncertain') THEN reserved_usd ELSE 0 END),0) AS spent
            FROM usage_ledger WHERE created_at>=%s AND (usage->>'cycle'=%s OR purpose LIKE 'editorial-%%' OR purpose LIKE 'image-%%')""", (day,runtime.cycle['id'])).fetchone()['spent']
        if daily_spent + amount_usd > Decimal(str(runtime.limits['daily_cost_cap_usd'])):
            runtime.stop('cost_cap')
            raise CycleStopped('cost_cap')
    return {'cycle_id': str(runtime.id), 'cycle': runtime.cycle['id'], 'budget_bucket': budget_bucket,
            'edge': call['edge'], 'call': call['key'], 'node': call['nodes'][0],
            'graph_hash': row.graph_hash, 'job_id': str(row.job_id or '')}


def timeout(default):
    call = _active_call.get()
    if call is None:
        return default
    remaining = (datetime.fromisoformat(call['deadline']) - timezone.now()).total_seconds()
    if remaining <= 0:
        current().stop('call_timeout', business=False)
        raise CycleStopped('call_timeout')
    return min(default, remaining)


def recover_job(job):
    """Only confirmed checkpoints resume automatically. Never replay an in-flight call."""
    row = CycleLedger.objects.select_for_update().filter(job=job).first()
    if row is None:
        return False
    row.lease_token = ''  # fence the old worker before considering a continuation
    pending = any(c['state'] == 'pending' for c in row.progress_ledger['calls'].values())
    if pending:
        row.state, row.stop_reason, row.needs_attention = 'stopped', 'uncertain', True
    row.save(update_fields=['lease_token', 'state', 'stop_reason', 'needs_attention', 'updated_at'])
    if pending:
        from .jobs import audit
        audit(None,'cycle.stopped',row.id,reason='uncertain',job_id=str(job.id))
        from .notificaciones import avisar
        transaction.on_commit(lambda:avisar('cycle_stopped','Ciclo interrumpido',REASONS['uncertain'],ref=f'cycle:{row.id}'))
    return not pending and row.state != 'stopped'


REASONS = {
    'cost_cap': 'Se alcanzó el presupuesto del ciclo. Se conserva el trabajo parcial y no se amplía el gasto.',
    'stall': 'El ciclo no obtiene avances. Revisa el objetivo antes de continuar.',
    'uncertain': 'Hay una llamada sin resultado confirmado. Hay que conciliarla antes de repetirla.',
}


def attention_cards(user, card):
    rows = CycleLedger.objects.filter(needs_attention=True)
    if not user.has_perm('team_backend.manage_jobs'):
        rows = rows.filter(owner=user)
    return [card(f'cycle:{row.id}', 'aviso', 'Ciclo detenido: ' + row.cycle,
        REASONS.get(row.stop_reason, row.stop_reason),
        [{'label': 'Ver equipo', 'href': '/equipo'}]+([{'label':'Entendido',
          'endpoint':f'/api/v1/equipo/ciclos/{row.id}/decision','body':{'action':'acknowledge'}}]
          if user.has_perm('team_backend.manage_jobs') else []), priority='importante',
        agent=row.orchestrator, created_at=row.updated_at) for row in rows[:20]]


def after_settle():
    runtime = current()
    if runtime:
        try:runtime.check_cost()
        except CycleStopped:pass  # Notify now; the dispatcher retains the result then stops the workflow.


def review_gate(proposal, operation):
    """The deterministic policy invokes Jev; this never grants gate authority to a tool."""
    rows = CycleLedger.objects.all()
    row = rows.filter(cycle='pieza_diaria',key=str(proposal.piece_id)).first() if proposal.piece_id else (
        rows.filter(cycle='red',key=proposal.origin_job).first() if proposal.origin_job else None)
    if row is None:return operation()  # Legacy and human-created proposals retain their existing policy.
    edge = 'pieza_diaria_gate_0' if row.cycle=='pieza_diaria' else 'politica_red'
    attempt = proposal.review.get('error_at','initial') if proposal.review else 'initial'
    try:
        runtime = Runtime.open(row.cycle,row.key,row.owner,row.job,at_gate=True)
        with runtime.session():
            return runtime.call(edge,proposal,operation,key=f'gate:{proposal.pk}:{proposal.payload_hash}:{attempt}')
    except CycleStopped as exc:
        return {'decision':'retry','reasons':['Ciclo detenido: '+str(exc)],'at':timezone.now().isoformat(),
                'error_at':timezone.now().isoformat()}


def human_decision(user, cycle_id, action, plan=None):
    """Acknowledge a stop, or replan a stalled cycle without replenishing anything."""
    from .permissions import require
    from .exceptions import Conflict
    from .jobs import audit
    require(user,'manage_jobs')
    with transaction.atomic():
        row=CycleLedger.objects.select_for_update().get(pk=cycle_id)
        if action=='acknowledge':
            row.needs_attention=False
        elif action=='resume':
            if row.state!='stopped' or row.stop_reason!='stall' or row.lease_token:
                raise Conflict('Solo un atasco conciliado puede reanudarse; no se reinician límites ni llamadas inciertas.')
            if not isinstance(plan,list) or not plan or len(plan)>20 or not all(isinstance(s,str) and 0<len(s)<=300 for s in plan):
                raise Conflict('Indica un plan concreto de hasta veinte pasos.')
            if any(c['state']!='answered' for c in row.progress_ledger['calls'].values()):
                raise Conflict('Hay llamadas pendientes de conciliación.')
            if row.calls>=row.limits['max_calls'] or row.active_seconds>=row.limits['cycle_timeout_s']:
                raise Conflict('El ciclo ya consumió su límite técnico.')
            if amount(UsageEntry.objects.filter(usage__cycle_id=str(row.id)))>=Decimal(str(row.limits['cost_cap_usd'])):
                raise Conflict('El ciclo ya consumió su presupuesto.')
            if row.job_id is None:raise Conflict('La instancia no tiene un trabajo reanudable.')
            from .models import Job, EditorialPiece
            job=Job.objects.select_for_update().get(pk=row.job_id)
            if job.state not in ('failed','interrupted','complete'):
                raise Conflict('El trabajo ya está activo.')
            row.state='running';row.stop_reason='';row.needs_attention=False
            row.task_ledger['plan']=plan;row.task_ledger['plan_version']+=1
            row.progress_ledger['stall_count']=0
            job.state='queued';job.worker=None;job.finished_at=None;job.error='';job.save()
            if row.cycle=='pieza_diaria':
                EditorialPiece.objects.filter(pk=row.key,state='blocked',proposals__isnull=True).update(state='preparing')
        else:
            raise Conflict('Decisión desconocida.')
        row.task_ledger.setdefault('decisions',[]).append({'actor':user.pk,'action':action,'at':timezone.now().isoformat()})
        row.revision+=1
        row.save()
        audit(user,'cycle.human_decision',row.id,decision=action,revision=row.revision)
    return row


def cycle_issues(proposal):
    """Read-only final guard, including when Jev is disabled or approval is manual."""
    if proposal.piece_id:
        row=CycleLedger.objects.filter(cycle='pieza_diaria',key=str(proposal.piece_id)).first()
    elif proposal.origin_job:
        row=CycleLedger.objects.filter(cycle='red',key=proposal.origin_job).first()
    else:row=None
    return ['Ciclo detenido: '+row.stop_reason] if row and row.state=='stopped' else []


def ensure_current():
    runtime=current()
    if runtime:
        row=CycleLedger.objects.get(pk=runtime.id)
        if row.lease_token!=runtime.token or (row.state=='stopped' and row.stop_reason!='cost_cap'):
            raise CycleStopped(row.stop_reason or 'Resultado de un trabajador obsoleto')
