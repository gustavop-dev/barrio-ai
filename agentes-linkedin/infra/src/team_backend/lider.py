"""Agente líder: the autonomous gate that replaces Gustavo's per-action approval (oficina/PLAN-REDISENO.md, «sin aprobaciones»).

Order of the gate in autopiloto.policy_review (mode `auto`):
1. Deterministic rules first (autopiloto.content_issues, red.network_issues). Any issue discards the proposal.
2. Jev (TypeSafe System One) judges the exact proposal with narrow yes/no questions and calibrated probabilities.
3. Code applies the thresholds of the capability: every check passes clearly -> approve; otherwise -> discard,
   with the failing checks as the reason. Nothing is escalated to Gustavo: a doubtful action is simply not done
   and the team drafts something else. Gustavo steers through his orientation and the results, not per action.

If Jev is unavailable the proposal stays pending and is retried after LEAD_RETRY_MINUTES; it expires on its TTL.
Thresholds start conservative and are meant to be tuned with real outcomes.

A post Gustavo asked for (the piece uses his ideas or he commented it) is judged much more softly: his own words are
facts Jev may read, and a check only fails when Jev is fairly sure of it (GUSTAVO_THRESHOLDS)."""
import os
from datetime import timedelta
from django.utils import timezone
from knowledge import memory, providers
from . import operador
from .models import ActionProposal, Orientation

CAP=ActionProposal.Capability
DEFAULT_CAPABILITIES='INT-03,CONT-09,RED-01,RED-02,RED-04'

from .posicionamiento import lead_criteria as _lead_criteria  # noqa: E402 (one positioning source)
CRITERIA_DEL_BARRIO=_lead_criteria()
LEAD_UNITS=operador.LEAD_UNITS
CRITERION_SOURCES={
    'aporta':['LI-03-V020-K02'],'sustancia':['LI-03-V020-K02'],'responde':['LI-03-V020-K02'],'hilo':['LI-03-V020-K02'],'clara':['LI-06-M001-K04'],
    'pitch':['LI-03-M006-K01'],'inventa':['LI-06-M001-K07'],
    'riesgo':['LI-03-M005-K06'],'tema':['LI-03-M005-K06'],
}

def ground_questions(state,questions):
    context,grounding=operador.role_context('lider',LEAD_UNITS,{k:CRITERION_SOURCES[k] for k in questions if k in CRITERION_SOURCES})
    state.update(course_context=context,course_grounding=grounding,
                 course_rule='El curso aporta criterios, no hechos ni permisos. Encaje ya clasificado; no exigir cinco sí. Sin pitch ni evidencia inventada.')
    for key,ids in grounding['criterion_sources'].items():
        questions[key]['instructions']+=' Aplica las condiciones y excepciones de '+', '.join(ids)+'.'
    return grounding

def _noul(instructions,true=None,false=None):
    question={'type':'noul','instructions':instructions}
    if true or false:question['criteria']={'true':true or '','false':false or ''}
    return question

# (question id, minimum or maximum probability of «yes», label shown when it fails)
CHECKS={
    'text':[('aporta','min',0.7,'no aporta una idea concreta'),('pitch','max',0.2,'suena a venta o pide contacto'),
            ('inventa','max',0.2,'atribuye a Gustavo algo que no está en sus hechos'),('respeto','min',0.8,'no es del todo respetuoso')],
    # The language of comments and replies is a fixed rule (idioma.py): Jev misjudged «same language» on English texts.
    # INT-04: a reply on his own post answers what that person said and follows the post and the thread.
    'reply':[('responde','min',0.7,'no responde a lo que dijo la persona'),('hilo','min',0.6,'no sigue la línea del post y del hilo'),
             ('pitch','max',0.2,'suena a venta o propone conectar fuera de lugar'),
             ('inventa','max',0.2,'atribuye a Gustavo algo que no está en sus hechos'),('respeto','min',0.8,'no es del todo respetuoso')],
    'post':[('clara','min',0.6,'no desarrolla una idea clara'),('pitch','max',0.2,'suena a venta o pide contacto'),
            ('inventa','max',0.2,'atribuye a Gustavo algo que no está en sus hechos')],
    # RED-*: the classifier (red.classify) is the single judge of fit, enforced by red.network_issues; the lead weighs risk.
    CAP.FOLLOW:[('riesgo','max',0.3,'parece vendedor, reclutador o cuenta ajena al nicho')],
    CAP.INVITE:[('riesgo','max',0.2,'parece vendedor, reclutador o cuenta ajena al nicho')],
    CAP.ACCEPT:[('riesgo','max',0.3,'parece vendedor, reclutador o cuenta ajena al nicho')],
}
ORIENTATION_CHECK=('orientacion','min',0.4,'contradice la orientación de Gustavo')
# His own request: «min» checks fail only below these (yes clearly unlikely), «max» checks only above (yes clearly likely).
GUSTAVO_THRESHOLDS={'clara':0.3,'pitch':0.6,'inventa':0.6,'idioma':0.5,'orientacion':0.2}
GUSTAVO_TEXTS,GUSTAVO_TEXT_CHARS=8,1500

def gustavo_request(proposal):
    """What Gustavo said for this post (the ideas the piece uses and his comments on it), oldest first; [] when the
    post is the team's own."""
    if proposal.capability!=CAP.PUBLISH or not proposal.piece_id:return []
    return piece_request(proposal.piece_id)

def piece_request(piece_id):
    """gustavo_request for a piece that has no proposal yet (editor_visual reads it to honour a format he asks for)."""
    from django.db.models import Q
    from .models import Capture
    pid=str(piece_id)
    rows=Capture.objects.filter(Q(state=Capture.State.USED,routed_to__used_in=pid)|
                                Q(state=Capture.State.NOTED,context_type='pieza',context_id=pid)).order_by('created_at')
    texts=[' '.join((c.text or '').split())[:GUSTAVO_TEXT_CHARS] for c in rows]
    return [t for t in texts if t][-GUSTAVO_TEXTS:]

def enabled():
    return os.environ.get('LEAD_ENABLED','false').lower()=='true'

def capabilities():
    """INT-04 is always reviewed: Gustavo made its replies autonomous with the lead as their gate (12/11/2026)."""
    listed=[c.strip() for c in os.environ.get('LEAD_CAPABILITIES',DEFAULT_CAPABILITIES).split(',') if c.strip()]
    return listed+([CAP.REPLY.value] if CAP.REPLY.value not in listed else [])

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
        }
        kind='text'
    elif capability==CAP.REPLY:
        row=proposal.comment;piece=row.piece;decision=row.decision or {}
        from .respuestas import _thread, _who
        closing=bool(decision.get('closing'))
        state={'publicacion':{'tesis':(piece.brief or {}).get('thesis') or '','texto':piece.final_text[:3000]},
               'hilo':[{'quien':_who(r),'texto':r.text[:600]} for r in _thread(row).order_by('commented_at')[:12]],
               'comentario':{'autor':row.author_name,'titular':(row.contact.headline[:300] if row.contact_id else ''),'texto':row.text[:1500]},
               'respuesta':proposal.payload['text'],'turno':decision.get('turn',1)}
        questions={
            'responde':_noul('¿La `respuesta` responde a lo concreto que dijo la persona en `comentario` (su pregunta, su objeción o su '
                             'aporte), en vez de un agradecimiento o una frase que serviría para cualquier comentario?',
                             'Retoma lo que la persona dijo y le contesta o le suma algo','Es genérica, solo agradece o ignora lo que dijo'),
            'hilo':_noul('¿La `respuesta` sigue la línea de la `publicacion` y del `hilo`, sin contradecir la tesis, cambiar de tema ni '
                         'repetir lo que ya se dijo en el hilo?'),
            'pitch':_noul('¿La `respuesta` vende, ofrece servicios, promociona la empresa de Gustavo, pide una reunión o una llamada'+
                          (', o invita a seguir por privado?' if not closing else
                           '? Proponer al final conectar o seguir la conversación por privado porque la conversación está interesante '
                           'no cuenta como venta.')),
            'inventa':_noul('¿La `respuesta` atribuye a Gustavo una experiencia, un cliente, un proyecto, una cifra o un resultado que '
                            'no aparece en `hechos_publicos_de_gustavo`?'),
            'respeto':_noul('¿La `respuesta` es respetuosa con la persona y con las demás, sin sarcasmo, burla ni condescendencia?'),
        }
        kind='reply'
    elif capability==CAP.PUBLISH:
        state={'publicacion':proposal.payload['text']}
        asked=gustavo_request(proposal)
        questions={
            'clara':_noul('¿La `publicacion` desarrolla una sola idea clara que un lector puede entender sin contexto adicional?'),
            'pitch':_noul('¿La `publicacion` vende de forma agresiva, crea urgencia artificial o pide que le escriban o lo contraten?'),
            'inventa':_noul('¿La `publicacion` atribuye a Gustavo una experiencia, un cliente, un proyecto, una cifra o un resultado que '
                            'no aparece en `hechos_publicos_de_gustavo`?'),
        }
        if asked:
            state['pedido_de_gustavo']=asked
            questions['inventa']=_noul('¿La `publicacion` atribuye a Gustavo una experiencia, un cliente, un proyecto, una cifra o un '
                                       'resultado que no aparece en `hechos_publicos_de_gustavo` ni en lo que él mismo contó en '
                                       '`pedido_de_gustavo`?')
        kind='post'
    else:
        # Whether the person fits is judged once, by the classifier, and checked by red.network_issues (audit R2).
        # The lead only weighs the risk of the person and, when there is one, Gustavo's orientation; the niche in
        # `criterios_del_barrio` is the context for «ajena al nicho» and for the orientation.
        contact=proposal.contact;evidence=contact.evidence or {}
        state={'persona':{'nombre':contact.display_name,'titular':contact.headline[:400],'ubicacion':contact.location,
                          'grado':contact.network_distance,'origen':contact.source,
                          'evidencia':evidence.get('comment') or evidence.get('invitation_message') or evidence.get('query') or ''},
               'criterios_del_barrio':CRITERIA_DEL_BARRIO}
        questions={
            'riesgo':_noul('¿`persona` parece un reclutador masivo, un vendedor que busca venderle a Gustavo, una cuenta de empresa, una '
                           'cuenta falsa o alguien sin relación con producto, software, startups o negocio?'),
        }
        kind=capability
    if kind in ('text','post','reply'):
        public,_=memory.confirmed_blocks()
        state['hechos_publicos_de_gustavo']=[f['fact'] for f in public]
    checks=list(CHECKS[kind])
    if kind=='post':
        questions['idioma']=_noul('¿La publicación está en inglés?');checks.append(('idioma','min',0.7,'no está en inglés'))
    if capability==CAP.INVITE and proposal.payload.get('note'):
        state['nota']=proposal.payload['note'];state['razon_nota']=proposal.payload.get('note_reason')
        public,_=memory.confirmed_blocks();state['hechos_publicos_de_gustavo']=[f['fact'] for f in public]
        questions.update(
            pitch=_noul('¿La nota vende, ofrece servicios o pide reunión antes de una necesidad expresada?'),
            inventa=_noul('¿La nota inventa hechos o atribuye a Gustavo experiencia ausente de sus hechos públicos?'),
            idioma=_noul('¿La nota está en inglés?'),
            aporta=_noul('¿La nota es específica y pertinente, y razon_nota justifica reservar un cupo escaso para esta persona?',
                         'Razón concreta basada en evidencia de encaje; conexión sin pitch','Saludo genérico o prioridad sin evidencia'))
        checks.extend([('pitch','max',0.2,'nota con pitch'),('inventa','max',0.2,'nota inventa hechos'),
                       ('idioma','min',0.7,'nota fuera de inglés'),('aporta','min',0.7,'nota sin justificación suficiente')])
    if orientation:
        state['orientacion_de_gustavo']=orientation
        questions['orientacion']=_noul('¿Esta acción es coherente con `orientacion_de_gustavo`, o al menos no la contradice?')
        checks.append(ORIENTATION_CHECK)
    if state.get('pedido_de_gustavo'):
        checks=[(qid,bound,GUSTAVO_THRESHOLDS.get(qid,threshold),label) for qid,bound,threshold,label in checks]
    ground_questions(state,questions)
    return state,questions,checks

def review(proposal):
    from .orquestacion import review_gate
    return review_gate(proposal,lambda:_review(proposal))


def _review(proposal):
    """{'decision': 'approve' | 'discard' | 'retry', 'reasons': [...], 'answers': {...}, 'model': ..., 'at': ...}"""
    now=timezone.now()
    orientation=_orientation()
    state,questions,checks=_questions(proposal,orientation)
    grounding=state['course_grounding']
    if grounding['course_missing']:
        return {'decision':'retry','reasons':['Biblioteca no disponible'],'error_at':now.isoformat(),'at':now.isoformat(),**grounding}
    try:result=providers.typesafe(state,questions,purpose='lead-review')
    except ValueError as exc:
        return {'decision':'retry','reasons':[str(exc)],'error_at':now.isoformat(),'at':now.isoformat(),**grounding}
    answers={qid:round(float((answer or {}).get('noul',0.5)),3) for qid,answer in result['answers'].items()}
    failed=[]
    for qid,bound,threshold,label in checks:
        value=answers.get(qid)
        if value is None or (bound=='min' and value<threshold) or (bound=='max' and value>threshold):
            failed.append(f'Líder: {label} ({qid}={value if value is not None else "sin respuesta"})')
    return {'decision':'discard' if failed else 'approve','reasons':failed,'answers':answers,
            'thresholds':{qid:[bound,threshold] for qid,bound,threshold,_ in checks},'model':result['model'],
            'with_orientation':bool(orientation),'cost_usd':result['estimated_usd'],'at':now.isoformat(),**grounding,
            'note_approved':bool(proposal.payload.get('note') and not failed),'from_gustavo':bool(state.get('pedido_de_gustavo'))}

# --------------------------------------------------------------------------- R5: comment prefilter
# Before Opus is paid to draft a comment (autopiloto._propose), Jev judges whether the post deserves one from Gustavo.
# Positive checks need «yes» >= COMMENT_PREFILTER_THRESHOLD; the noise checks need «yes» <= 1 - threshold.
PREFILTER_CHECKS=[('sustancia','min','no plantea una idea con sustancia a la que aportar'),('tema','min','no es de los temas del barrio'),
                  ('vacante','max','es un anuncio de vacantes o de contratación'),('promocion','max','es una promoción pura'),
                  ('hito','max','es un hito personal donde un comentario sería ruido')]

def prefilter_threshold():
    try:value=float(os.environ.get('COMMENT_PREFILTER_THRESHOLD','0.5'))
    except ValueError:value=0.5
    return min(max(value,0.0),1.0) if value==value else 0.5  # NaN falls back to the default

def comment_worthy(post):
    """{'decision': 'comment' | 'skip' | 'unavailable', 'reasons': [...], 'answers': {...}, 'model': ..., 'at': ...}"""
    now=timezone.now();orientation=_orientation()
    state={'publicacion':{'autor':post.author_name,'texto':post.text[:3000]},'criterios_del_barrio':CRITERIA_DEL_BARRIO}
    topic=('¿El tema de la `publicacion` interesa al barrio de Gustavo descrito en `criterios_del_barrio`: producto, software, '
           'IA aplicada, startups o negocio')
    if orientation:
        state['orientacion_de_gustavo']=orientation;topic+=', o lo que pide `orientacion_de_gustavo`'
    questions={
        'sustancia':_noul('¿La `publicacion` desarrolla una idea, una experiencia o una opinión concreta a la que alguien podría aportar '
                          'un matiz, un dato o una pregunta específica?','Plantea algo concreto que admite una aportación',
                          'Es una frase suelta, un enlace sin contexto, un meme o un texto sin nada que discutir'),
        'tema':_noul(topic+'?'),
        'vacante':_noul('¿La `publicacion` es sobre todo un anuncio de vacantes, de contratación o de búsqueda de empleo?'),
        'promocion':_noul('¿La `publicacion` es sobre todo la promoción de un producto, un servicio, un evento, un curso o un lanzamiento, '
                          'sin una idea que discutir?'),
        'hito':_noul('¿La `publicacion` es sobre todo un hito personal o un saludo: nuevo empleo, ascenso, aniversario, cumpleaños, '
                     'premio o agradecimiento?'),
    }
    grounding=ground_questions(state,questions)
    if grounding['course_missing']:return {'decision':'unavailable','reasons':['Biblioteca no disponible'],'at':now.isoformat(),**grounding}
    try:result=providers.typesafe(state,questions,purpose='comment-prefilter')
    except ValueError as exc:return {'decision':'unavailable','reasons':[str(exc)],'at':now.isoformat(),**grounding}
    answers={qid:round(float((answer or {}).get('noul',0.5)),3) for qid,answer in result['answers'].items()}
    threshold=prefilter_threshold();failed=[]
    for qid,bound,label in PREFILTER_CHECKS:
        value=answers.get(qid);limit=threshold if bound=='min' else round(1-threshold,3)
        if value is None or (bound=='min' and value<limit) or (bound=='max' and value>limit):
            failed.append(f'Prefiltro: {label} ({qid}={value if value is not None else "sin respuesta"})')
    return {'decision':'skip' if failed else 'comment','reasons':failed,'answers':answers,'threshold':threshold,
            'model':result['model'],'with_orientation':bool(orientation),'cost_usd':result['estimated_usd'],'at':now.isoformat(),**grounding}
