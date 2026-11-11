"""Typed adapters for the two migrated workflows; existing output schemas stay canonical."""
STRING = {'type': 'string'}
OBJECT = {'type': 'object'}
ARRAY = {'type': 'array'}
INTEGER = {'type': 'integer'}


def obj(required=(), **properties):
    return {'type': 'object', 'properties': properties, 'required': list(required), 'additionalProperties': False}


def stage(name, required, **props):
    return obj(('piece', 'stage', 'payload', 'units'), piece=STRING,
        stage={'type': 'string', 'enum': [name]}, units={'type': 'array', 'items': STRING},
        payload={'type': 'object', 'properties': props, 'required': list(required)})


BRIEF_INPUT = stage('director', ('slot', 'public_facts', 'private_guidance'), slot=OBJECT,
                    public_facts=ARRAY, private_guidance=ARRAY)
WRITER_INPUT = stage('redactor', ('brief', 'sources'), brief=OBJECT, sources=ARRAY)
PANEL_INPUT = stage('lectores', ('brief', 'drafts'), brief=OBJECT, drafts=obj(('A', 'B'), A=STRING, B=STRING),
                    community=obj(('status', 'study_id', 'version', 'findings'), status=STRING, study_id=STRING,
                                  version=INTEGER, findings={'type':'array','items':STRING}))
SELECTION_INPUT = stage('seleccion', ('brief', 'variants', 'panel'), brief=OBJECT, variants=OBJECT, panel=OBJECT)
VERIFIER_INPUT = stage('verificador', ('text', 'brief', 'claims'), text=STRING, brief=OBJECT, claims=ARRAY)
REPAIR_INPUT = stage('reparacion', ('text', 'brief', 'findings'), text=STRING, brief=OBJECT, findings=ARRAY)
REWORK_INPUT = stage('retoque', ('comment', 'text', 'brief', 'image'), comment=STRING, text=STRING, brief=OBJECT,
                     image=OBJECT, claims=ARRAY)
NETWORK_INPUT = obj(('job', 'kind', 'params'), job=STRING, kind=STRING, params=OBJECT)
READ_RESULT = {'type': 'object', 'properties': {
    'new_posts': INTEGER, 'seen_posts': INTEGER, 'new': INTEGER, 'classified': INTEGER, 'fit': INTEGER,
    'follow': INTEGER, 'invite': INTEGER, 'accept': INTEGER, 'received': INTEGER, 'connected': INTEGER,
    'errors': ARRAY, 'stopped': STRING}, 'additionalProperties': True}
IMAGE_INPUT = obj(('piece', 'payload'), piece=STRING, payload=OBJECT)
EDIT_INPUT = obj(('piece', 'photo', 'sha256', 'instruction'), piece=STRING, photo=STRING, sha256=STRING, instruction=STRING)
CHECK_INPUT = obj(('piece', 'sha256', 'context', 'instruction', 'original'), piece=STRING,
    sha256={'type': 'array', 'items': STRING}, context=OBJECT, instruction=STRING, original=STRING)
# ImageConnector.check adds hashes and rule metadata after validating the provider's CHECK_SCHEMA.
CHECK_RESULT = {'type': 'object', 'required': ['ok', 'sha256'], 'properties': {
    'ok': {'type': 'boolean'}, 'sha256': {'type': 'array', 'items': STRING}, 'reasons': ARRAY}}

LEAD_RESULT = {'type': 'object', 'required': ['decision','reasons','at'], 'properties': {
    'decision': {'type':'string','enum':['approve','discard','retry']},
    'reasons': {'type':'array','items':STRING}, 'at': STRING}}
OBSERVE_RESULT = dict(READ_RESULT,required=['new_posts','seen_posts','errors'])
DISCOVER_RESULT = dict(READ_RESULT,required=['new'])
CLASSIFY_RESULT = dict(READ_RESULT,required=['classified','fit'])
PLAN_RESULT = dict(READ_RESULT,required=['follow','invite','accept'])
SYNC_RESULT = dict(READ_RESULT,required=['received','connected'])
