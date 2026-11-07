"""Agente líder: the autonomous gate that replaces Gustavo's per-action approval (oficina/PLAN-REDISENO.md, «sin aprobaciones»).

Order of the gate in autopiloto.policy_review (mode `auto`):
1. Deterministic rules first (autopiloto.content_issues, red.network_issues). Any issue discards the proposal.
2. Jev (TypeSafe System One) judges the exact proposal with narrow yes/no questions and calibrated probabilities.
3. Code applies the thresholds of the capability: every check passes clearly -> approve; otherwise -> discard,
   with the failing checks as the reason. Nothing is escalated to Gustavo: a doubtful action is simply not done
   and the team drafts something else. Gustavo steers through his orientation and the results, not per action.

If Jev is unavailable the proposal stays pending and is retried after LEAD_RETRY_MINUTES; it expires on its TTL.
Thresholds start conservative and are meant to be tuned with real outcomes."""
import os
from datetime import timedelta
from django.utils import timezone
from knowledge import memory, providers
from .models import ActionProposal, Orientation

CAP=ActionProposal.Capability
DEFAULT_CAPABILITIES='INT-03,CONT-09,RED-01,RED-02,RED-04'

from .posicionamiento import lead_criteria as _lead_criteria  # noqa: E402 (one positioning source)
CRITERIA_DEL_BARRIO=_lead_criteria()

def _noul(instructions,true=None,false=None):
    question={'type':'noul','instructions':instructions}
    if true or false:question['criteria']={'true':true or '','false':false or ''}
    return question

# (question id, minimum or maximum probability of «yes», label shown when it fails)
CHECKS={
    'text':[('aporta','min',0.7,'no aporta una idea concreta'),('pitch','max',0.2,'suena a venta o pide contacto'),
            ('inventa','max',0.2,'atribuye a Gustavo algo que no está en sus hechos'),('respeto','min',0.8,'no es del todo respetuoso'),
            ('idioma','min',0.7,'no está en el idioma de la publicación')],
    'post':[('clara','min',0.6,'no desarrolla una idea clara'),('pitch','max',0.2,'suena a venta o pide contacto'),
            ('inventa','max',0.2,'atribuye a Gustavo algo que no está en sus hechos')],
    CAP.FOLLOW:[('encaja','min',0.6,'no encaja con el barrio'),('riesgo','max',0.3,'parece vendedor, reclutador o cuenta ajena al nicho')],
    CAP.INVITE:[('encaja','min',0.7,'no encaja con el barrio'),('riesgo','max',0.2,'parece vendedor, reclutador o cuenta ajena al nicho')],
    CAP.ACCEPT:[('encaja','min',0.5,'no encaja con el barrio'),('riesgo','max',0.3,'parece vendedor, reclutador o cuenta ajena al nicho')],
}
ORIENTATION_CHECK=('orientacion','min',0.4,'contradice la orientación de Gustavo')

def enabled():
    return os.environ.get('LEAD_ENABLED','false').lower()=='true'

def capabilities():
    return [c.strip() for c in os.environ.get('LEAD_CAPABILITIES',DEFAULT_CAPABILITIES).split(',') if c.strip()]

def applies(proposal):
    return enabled() and proposal.capability in capabilities()

def waiting_retry(proposal,now=None):
    at=(proposal.review or {}).get('error_at')
    if not at:return False
    minutes=int(os.environ.get('LEAD_RETRY_MINUTES','10'))
    from datetime import datetime
    return datetime.fromisoformat(at)>(now or timezone.now())-timedelta(minutes=minutes)

def _orientation():
    return (Orientation.current().text or '').strip()

def _questions(proposal,orientation):
    capability=proposal.capability
    if capability==CAP.COMMENT:
        post=proposal.post
        state={'publicacion':{'autor':post.author_name,'texto':post.text[:3000]},'comentario':proposal.payload['text']}
        questions={
            'aporta':_noul('¿El `comentario` aporta algo concreto a la conversación de la `publicacion`: una opinión con fundamento, '
                           'un matiz o una pregunta específica?','Aporta una idea concreta relacionada con el tema de la publicación',
                           'Es un elogio genérico, repite la publicación o no tiene relación con ella'),
            'pitch':_noul('¿El `comentario` vende, ofrece servicios, promociona la empresa de Gustavo o invita a escribirle por privado?'),
            'inventa':_noul('¿El `comentario` atribuye a Gustavo una experiencia, un cliente, un proyecto, una cifra o un resultado que '
                            'no aparece en `hechos_publicos_de_gustavo`?'),
            'respeto':_noul('¿El `comentario` es respetuoso con el autor y con las demás personas, sin sarcasmo, burla ni ataque?'),
            'idioma':_noul('¿El `comentario` está escrito en el mismo idioma que `publicacion.texto`?'),
        }
        kind='text'
    elif capability==CAP.PUBLISH:
        state={'publicacion':proposal.payload['text']}
        questions={
            'clara':_noul('¿La `publicacion` desarrolla una sola idea clara que un lector puede entender sin contexto adicional?'),
            'pitch':_noul('¿La `publicacion` vende de forma agresiva, crea urgencia artificial o pide que le escriban o lo contraten?'),
            'inventa':_noul('¿La `publicacion` atribuye a Gustavo una experiencia, un cliente, un proyecto, una cifra o un resultado que '
                            'no aparece en `hechos_publicos_de_gustavo`?'),
        }
        kind='post'
    else:
        contact=proposal.contact;evidence=contact.evidence or {}
        state={'persona':{'nombre':contact.display_name,'titular':contact.headline[:400],'ubicacion':contact.location,
                          'grado':contact.network_distance,'origen':contact.source,
                          'evidencia':evidence.get('comment') or evidence.get('invitation_message') or evidence.get('query') or ''},
               'criterios_del_barrio':CRITERIA_DEL_BARRIO}
        questions={
            'encaja':_noul('Según `persona.titular`, `persona.ubicacion` y `persona.evidencia`, ¿esta persona encaja en el barrio de '
                           'Gustavo descrito en `criterios_del_barrio`?'),
            'riesgo':_noul('¿`persona` parece un reclutador masivo, un vendedor que busca venderle a Gustavo, una cuenta de empresa, una '
                           'cuenta falsa o alguien sin relación con producto, software, startups o negocio?'),
        }
        kind=capability
    if kind in ('text','post'):
        public,_=memory.confirmed_blocks()
        state['hechos_publicos_de_gustavo']=[f['fact'] for f in public]
    checks=list(CHECKS[kind])
    if orientation:
        state['orientacion_de_gustavo']=orientation
        questions['orientacion']=_noul('¿Esta acción es coherente con `orientacion_de_gustavo`, o al menos no la contradice?')
        checks.append(ORIENTATION_CHECK)
    return state,questions,checks

def review(proposal):
    """{'decision': 'approve' | 'discard' | 'retry', 'reasons': [...], 'answers': {...}, 'model': ..., 'at': ...}"""
    now=timezone.now()
    orientation=_orientation()
    state,questions,checks=_questions(proposal,orientation)
    try:result=providers.typesafe(state,questions,purpose='lead-review')
    except ValueError as exc:
        return {'decision':'retry','reasons':[str(exc)],'error_at':now.isoformat(),'at':now.isoformat()}
    answers={qid:round(float((answer or {}).get('noul',0.5)),3) for qid,answer in result['answers'].items()}
    failed=[]
    for qid,bound,threshold,label in checks:
        value=answers.get(qid)
        if value is None or (bound=='min' and value<threshold) or (bound=='max' and value>threshold):
            failed.append(f'Líder: {label} ({qid}={value if value is not None else "sin respuesta"})')
    return {'decision':'discard' if failed else 'approve','reasons':failed,'answers':answers,
            'thresholds':{qid:[bound,threshold] for qid,bound,threshold,_ in checks},'model':result['model'],
            'with_orientation':bool(orientation),'cost_usd':result['estimated_usd'],'at':now.isoformat()}
