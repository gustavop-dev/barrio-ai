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
FIRST_MESSAGE_UNITS=operador.FIRST_MESSAGE_UNITS  # loaded only when the review has a first message to judge
WARMUP_COMMENT_UNITS=operador.WARMUP_COMMENT_UNITS  # loaded only when the review judges a warm-up comment on a buyer's post
INVITE_NOTE_UNITS=operador.INVITE_NOTE_UNITS  # loaded only when the lead reviews a buyer's invitation note (phase 3)
SEQUENCE_UNITS=operador.SEQUENCE_UNITS  # loaded only when the lead reviews a follow-up 2–4 of the sequence (phase 4)
BUYER_REPLY_UNITS=operador.BUYER_REPLY_UNITS  # loaded only when the lead reviews the reply to what a buyer wrote (phase 6)
CRITERION_SOURCES={
    'aporta':['LI-03-V020-K02'],'sustancia':['LI-03-V020-K02'],'responde':['LI-03-V020-K02'],'hilo':['LI-03-V020-K02'],'clara':['LI-06-M001-K04'],
    'pitch':['LI-03-M006-K01'],'inventa':['LI-06-M001-K07'],
    'falsa':['LI-03-M005-K06'],'empresa':['LI-03-M005-K06'],'reclutador':['LI-03-M005-K06'],'prospector':['LI-03-M005-K06'],
    'proveedor':['LI-03-M005-K06'],'tema':['LI-03-M005-K06'],
    # BIB-09-primer-mensaje: the class 09 criterion behind each question about the first message.
    'dm_toque':['LI-09-M003-K02','LI-09-V011-K01'],'dm_puente':['LI-09-M003-K02','LI-09-M003-K04'],
    'dm_pregunta':['LI-09-M003-K03'],'dm_un_tema':['LI-09-M003-K04'],'dm_en_persona':['LI-09-M004-K02'],
    'dm_pitch':['LI-09-M002-K04','LI-03-M006-K01'],
    # BIB-09-comentario-calentamiento: the class 07 criterion behind each question about a warm-up comment.
    'cal_aporte':['LI-07-M005-K05','LI-07-M001-K04'],'cal_pregunta':['LI-07-M005-K05'],'cal_aplauso':['LI-07-M001-K04','LI-07-M005-K05'],
    # BIB-09-nota-invitacion: the class 09 criterion behind each question about a buyer's invitation note.
    'nota_hecho':['LI-09-M002-K06','LI-09-V008-K04'],'nota_aceptar':['LI-09-V008-K04'],'nota_generica':['LI-09-M002-K06','LI-09-V008-K04'],
    'nota_pitch':['LI-09-M002-K06','LI-03-M006-K01'],'nota_inventa':['LI-06-M001-K07'],
    # BIB-11-respuesta-comprador: the class 11, 08 and 12 criterion behind each question about the reply to a buyer.
    'resp_responde':['LI-11-M006-K01'],'resp_pitch':['LI-11-M006-K01','LI-08-M003-K05'],'resp_presiona':['LI-08-M003-K05'],
    'resp_inventa':['LI-11-M006-K01'],'resp_paso_facil':['LI-12-M001-K04'],'resp_insiste':['LI-11-M006-K03','LI-08-M003-K05'],
    'resp_agradece':['LI-11-M006-K02'],
}

def ground_questions(state,questions):
    """Load the lead's units (and, with a first message to judge, the activated class 09 units; with a warm-up comment,
    the activated class 07/10 units) and point each question at its criterion. If the class 09 units are missing, the
    first message is not judged (no card) and the rest of the review goes on as before. If the warm-up units are missing,
    course_missing says so and the review waits (lider._review: retry): a buyer is never commented without them."""
    def ground(units,metodologia=None):
        return operador.role_context('lider',units,{k:CRITERION_SOURCES[k] for k in questions if k in CRITERION_SOURCES},
                                     metodologia=metodologia)
    if 'calentamiento' in state:
        context,grounding=ground(LEAD_UNITS+[u for u in WARMUP_COMMENT_UNITS if u not in LEAD_UNITS],metodologia='comentario_calentamiento')
    elif 'primer_mensaje' in state:
        context,grounding=ground(LEAD_UNITS+[u for u in FIRST_MESSAGE_UNITS if u not in LEAD_UNITS],metodologia='primer_mensaje')
        if grounding['course_missing'] and set(grounding['course_missing'])<=set(FIRST_MESSAGE_UNITS):
            state.pop('primer_mensaje')
            for qid in DM_IDS:questions.pop(qid,None)
            context,grounding=ground(LEAD_UNITS)
    else:context,grounding=ground(LEAD_UNITS)
    state.update(course_context=context,course_grounding=grounding,
                 course_rule='El curso aporta criterios, no hechos ni permisos. Encaje ya clasificado; no exigir cinco sí. Sin pitch ni evidencia inventada.')
    for key,ids in grounding['criterion_sources'].items():
        if ids:questions[key]['instructions']+=' Aplica las condiciones y excepciones de '+', '.join(ids)+'.'
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
}
# BIB-09-primer-mensaje: the first message drafted with a closing reply (dm_opener) is judged in the same review, with
# questions 1–5 of the class 09 guide (LI-09-M004-K02) and selling; question 6 (no links, no asking for a meeting) is a
# fixed rule (respuestas.dm_text_issues). A failing check only sets dm_approved=False: it never discards the public reply.
DM_CHECKS=[('dm_toque','min',0.7,'el primer mensaje no retoma algo concreto que dijo la persona'),
           ('dm_puente','min',0.6,'el primer mensaje no dice con honestidad por qué le escribe'),
           ('dm_pregunta','min',0.6,'el primer mensaje no cierra con una pregunta fácil de contestar'),
           ('dm_un_tema','min',0.7,'el primer mensaje trata más de un tema'),
           ('dm_en_persona','min',0.6,'el primer mensaje no suena a lo que le diría en persona'),
           ('dm_pitch','max',0.2,'el primer mensaje vende o pide una reunión')]
DM_IDS=frozenset(qid for qid,*_ in DM_CHECKS)
# BIB-09-comentario-calentamiento: a comment on a warming buyer's post is also judged as a warm-up comment (LI-07-M005-K05,
# LI-07-M001-K04): an own concrete contribution, one open question about their experience, no applause. Length, the
# question mark and applause or selling words are fixed rules first (autopiloto.warmup_text_issues). A failing check
# discards the comment, like the other checks of a comment.
CAL_CHECKS=[('cal_aporte','min',0.7,'el comentario de calentamiento no aporta algo propio y concreto'),
            ('cal_pregunta','min',0.6,'el comentario de calentamiento no termina en una pregunta abierta sobre su experiencia'),
            ('cal_aplauso','max',0.2,'el comentario de calentamiento aplaude o felicita en vez de aportar')]
CAL_IDS=frozenset(qid for qid,*_ in CAL_CHECKS)

def warmup_questions():
    return {
        'cal_aporte':_noul('¿El `comentario` aporta algo propio y concreto que la `publicacion` no dice (un mecanismo, una práctica, '
                           'un matiz o un hecho de `hechos_publicos_de_gustavo`), en vez de repetirla, resumirla o elogiarla?',
                           'Suma una idea concreta propia sobre lo que cuenta el autor',
                           'Repite o resume la publicación, felicita, o es una opinión genérica que serviría para cualquier post'),
        'cal_pregunta':_noul('¿El `comentario` termina con una sola pregunta abierta y concreta sobre la experiencia, la decisión o el '
                             'aprendizaje del autor, que puede contestar en el hilo?',
                             'Una pregunta acotada sobre qué hizo, qué eligió o qué cambiaría',
                             'Ninguna pregunta, varias, una retórica o una genérica («¿qué opinas?», «¿cómo lo ves?»)'),
        'cal_aplauso':_noul('¿El `comentario` es sobre todo un aplauso o una felicitación («gran post», «felicidades», emojis de '
                            'aplauso) en vez de un aporte?'),
    }
DM_UNAVAILABLE='Líder: el primer mensaje no se juzgó (Biblioteca no disponible para la clase 09)'

def drafted_message(proposal):
    """The first message drafted with a closing reply, or '' (only INT-04 with closing carries one)."""
    if proposal.capability!=CAP.REPLY or not proposal.comment_id:return ''
    decision=proposal.comment.decision or {}
    return (decision.get('dm_opener') or '').strip() if decision.get('closing') else ''

def dm_questions(source='conversacion'):
    """The six questions about a first message. `conversacion`: RSP-07, the message after a conversation on his post
    (unchanged). `recorrido` (phase 3): the buyer's journey, whose facts are `hechos` (an interaction, a post of hers the
    team commented, a buying signal); same ids and thresholds (DM_CHECKS)."""
    if source=='recorrido':
        toque=_noul('¿La primera frase de `primer_mensaje.texto` retoma con precisión uno de `hechos` (lo que la persona publicó, '
                    'respondió o comentó, o la señal citada), de modo que no serviría para otra persona?',
                    'Nombra de qué trataba su post, qué respondió o qué señal, en concreto',
                    'Saluda, agradece la conexión o alude a «tu post» o «tu trabajo» sin decir de qué')
        puente=_noul('¿`primer_mensaje.texto` dice con honestidad por qué Gustavo le escribe: ese tema de `hechos` que les interesa a '
                     'los dos, y no sus servicios ni a quién ayuda?')
        return dict(dm_questions(),dm_toque=toque,dm_puente=puente)
    return {
        'dm_toque':_noul('¿La primera frase de `primer_mensaje.texto` retoma algo concreto que la persona dijo en `comentario` o en '
                         'el `hilo`, de modo que no serviría para otra persona?',
                         'Nombra una idea, un dato o una pregunta concreta de la persona en esta conversación',
                         'Saluda, agradece o alude a «la conversación» o a «tu post» sin decir de qué'),
        'dm_puente':_noul('¿`primer_mensaje.texto` dice con honestidad por qué Gustavo le escribe: lo que quedó abierto o les interesa '
                          'a los dos de esa conversación, y no sus servicios ni a quién ayuda?'),
        'dm_pregunta':_noul('¿`primer_mensaje.texto` termina con una sola pregunta concreta sobre ese tema que la persona puede contestar '
                            'en una o dos líneas sin pensarlo mucho?',
                            'Pregunta acotada: qué hizo, cuál eligió o cómo resolvió algo puntual de lo que hablaron',
                            'Pregunta filosófica o abierta («¿cómo ves…?», «¿qué opinas de…?»), varias preguntas o ninguna'),
        'dm_un_tema':_noul('¿`primer_mensaje.texto` trata un solo tema, el de la conversación, sin enumerar varios problemas, servicios o '
                           'propuestas?'),
        'dm_en_persona':_noul('¿`primer_mensaje.texto` suena a lo que Gustavo le diría en persona a alguien con quien acaba de '
                              'conversar, y no a una plantilla de prospección?'),
        'dm_pitch':_noul('¿`primer_mensaje.texto` vende, ofrece servicios, presenta la empresa de Gustavo, pide una reunión, una llamada '
                         'o minutos, o lleva un enlace?'),
    }
# RED-*: the classifier (red.classify) is the single judge of fit, enforced by red.network_issues. The lead only looks for
# concrete risks of the person, reads the classifier's role and reason, and asks about selling services only for the
# buyer hypothesis (measured 14/11/2026: the single compound question sat at 0.3–0.6 for people who fit).
# An invitation is scarcer than a follow or an acceptance, so it gets the stricter threshold.
NETWORK_THRESHOLD={CAP.FOLLOW:0.6,CAP.INVITE:0.5,CAP.ACCEPT:0.6}
PERSON_CHECKS=[('falsa','el perfil parece falso o de relleno'),('empresa','es la cuenta de una organización, no una persona'),
               ('reclutador','se dedica a reclutar'),('prospector','se dedica a prospectar en frío para otros')]
BUYER_CHECK=('proveedor','vende sus propios servicios; no parece comprador')
NETWORK_RISKS=tuple(qid for qid,_ in PERSON_CHECKS+[BUYER_CHECK])
# What each role of the classifier (red.ROLES) means, as the lead reads it in `clasificacion.papel`.
ROLE_MEANING={
    'par':'par: construye producto o software, o funda una startup de tecnología, como Gustavo',
    'comprador':'comprador (hipótesis): dirige una empresa con producto u operación propia y podría contratar ingeniería de producto',
    'recomendador':'recomendador: trabaja cerca de founders (inversor, asesor, ejecutivo fraccional, aceleradora) y puede recomendar proveedores',
    'aliado':'aliado: ofrece a startups un servicio complementario al de Gustavo, no competidor',
    'divulgador':'divulgador: crea contenido con audiencia sobre los temas del barrio',
    'lider':'líder: dirige una empresa, una comunidad o un equipo en tecnología o negocio',
    # Phase 5 (sin_posts.py): not a role of the classifier's table; a rule of Gustavo's route sets it.
    'puente':'puente: colega, en la misma empresa, de un posible comprador que no publica; el equipo lo calienta para llegar a él',
}

def network_checks(capability,role=None):
    """The lead's checks on a person: the concrete risks for every role, plus selling services for a buyer."""
    threshold=NETWORK_THRESHOLD[capability]
    return [(qid,'max',threshold,label) for qid,label in PERSON_CHECKS+([BUYER_CHECK] if role=='comprador' else [])]

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
        from . import calentamiento
        warm=calentamiento.warmup_post(post)
        questions={
            'aporta':_noul('¿El `comentario` aporta algo concreto a la conversación de la `publicacion`: una opinión con fundamento, '
                           'un matiz o una pregunta específica?','Aporta una idea concreta relacionada con el tema de la publicación',
                           'Es un elogio genérico, repite la publicación o no tiene relación con ella'),
            'pitch':_noul('¿El `comentario` vende, ofrece servicios, promociona la empresa de Gustavo o invita a escribirle por privado?'),
            'inventa':_noul('¿El `comentario` atribuye a Gustavo una experiencia, un cliente, un proyecto, una cifra o un resultado que '
                            'no aparece en `hechos_publicos_de_gustavo`?'),
            'respeto':_noul('¿El `comentario` es respetuoso con el autor y con las demás personas, sin sarcasmo, burla ni ataque?'),
        }
        if warm:
            state['calentamiento']={'autor':post.author_name,
                                    'que_es':'Comentario en el post de un posible cliente al que Gustavo calienta antes de invitarlo: '
                                             'un aporte propio y concreto más una pregunta, 25 a 40 palabras, sin vender ni aplaudir.'}
            questions.update(warmup_questions())
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
        dm=drafted_message(proposal)
        if dm:
            state['primer_mensaje']={'texto':dm,'para':row.author_name,
                                     'momento':'Gustavo se lo enviaría él mismo por privado si conectan, después de esta conversación en su post.'}
            questions.update(dm_questions())
        kind='reply'
    elif capability==CAP.PUBLISH:
        state={'publicacion':proposal.payload['text']}
        asked=gustavo_request(proposal)
        # A Sales post of the weekly strategy may carry ONE invitation to talk (compuertas.gate_policy): the rules and the
        # verifier already let it through, so the lead must not discard it for exactly that.
        from . import compuertas
        sales=compuertas.gate_policy(proposal.piece if proposal.piece_id else None).get('cta_max')
        questions={
            'clara':_noul('¿La `publicacion` desarrolla una sola idea clara que un lector puede entender sin contexto adicional?'),
            'pitch':_noul('¿La `publicacion` vende de forma agresiva, crea urgencia artificial o pide que le escriban o lo contraten?'
                          if not sales else
                          '¿La `publicacion` vende de forma agresiva, crea urgencia artificial, pide que lo contraten o trae más de '
                          'una invitación a escribirle o a comentar? Es un post de venta: una sola invitación a conversar es lo que '
                          'debe llevar y no cuenta como venta.'),
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
        # The lead only looks for concrete risks of the person, reads the classifier's role and reason, and asks about
        # selling services only for the buyer hypothesis (measured 14/11/2026: the single compound question sat at
        # 0.3–0.6 for people who fit). `criterios_del_barrio` is the context for the risks and for the orientation.
        contact=proposal.contact;evidence=contact.evidence or {};classification=contact.classification or {};signals=contact.signals or {}
        role=classification.get('role')
        state={'persona':{'nombre':contact.display_name,'titular':contact.headline[:400],'bio':(signals.get('bio') or '')[:600],
                          'ubicacion':contact.location,'seguidores':signals.get('followers'),'grado':contact.network_distance,'origen':contact.source,
                          'evidencia':evidence.get('comment') or evidence.get('invitation_message') or evidence.get('query') or ''},
               'clasificacion':{'papel':ROLE_MEANING.get(role,role or ''),'razon':classification.get('reason') or ''},
               'criterios_del_barrio':CRITERIA_DEL_BARRIO}
        questions={
            'falsa':_noul('¿El perfil de `persona` parece falso, automatizado o de relleno: sin cargo ni actividad reconocible, o con '
                          'promesas de dinero fácil?','Titular vacío o incoherente, o promesas de ingresos, cripto u «oportunidades» por mensaje',
                          'Muestra un cargo, una empresa o una actividad profesional reconocible, aunque el perfil sea breve'),
            'empresa':_noul('¿`persona` es la cuenta de una empresa, una marca, un medio o una comunidad, y no una persona individual?',
                            'El nombre y el titular describen una organización','Es una persona, aunque nombre la empresa donde trabaja o que fundó'),
            'reclutador':_noul('¿La actividad principal de `persona` es reclutar, seleccionar personal o colocar talento para otras empresas?',
                               'Reclutador, headhunter, talent acquisition, staffing o bolsa de empleo',
                               'Cualquier otra actividad, aunque su empresa esté contratando o lidere equipos'),
            'prospector':_noul('¿`persona` se dedica sobre todo a conseguir citas o clientes para otros con prospección en frío: generación de '
                               'leads, agendamiento de llamadas o envíos masivos de mensajes?',
                               'Vende lead generation, appointment setting, cold email u outreach hecho para otros',
                               'Vende otra cosa o no vende; hacer marketing, ventas, RevOps o contenido para su propio negocio no cuenta'),
        }
        if role=='comprador':
            questions['proveedor']=_noul('¿`persona` vive de vender sus propios servicios profesionales (consultoría, agencia, freelance, '
                                         'coaching) en vez de dirigir una empresa con producto u operación propia?',
                                         'Es consultor, freelancer, coach o dueño de una agencia de servicios',
                                         'Dirige o fundó una empresa con producto, clientes u operación propia, aunque también asesore')
        kind=capability
    if kind in ('text','post','reply'):
        public,_=memory.confirmed_blocks()
        state['hechos_publicos_de_gustavo']=[f['fact'] for f in public]
    checks=list(CHECKS[kind]) if kind in CHECKS else network_checks(capability,role)
    if kind=='post':
        questions['idioma']=_noul('¿La publicación está en inglés?');checks.append(('idioma','min',0.7,'no está en inglés'))
    # A buyer's note (phase 3) was already judged with its own methodology (review_buyer_draft): only the person is
    # reviewed here, and note_approved follows from that review.
    from .mensajes_comprador import approved_note
    if capability==CAP.INVITE and proposal.payload.get('note') and not approved_note(proposal):
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
    if 'primer_mensaje' in state:checks.extend(DM_CHECKS)  # still there: its class 09 units were loaded
    if 'calentamiento' in state:checks.extend(CAL_CHECKS)
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
    failed=[];dm_failed=[]
    for qid,bound,threshold,label in checks:
        value=answers.get(qid)
        if value is None or (bound=='min' and value<threshold) or (bound=='max' and value>threshold):
            (dm_failed if qid in DM_IDS else failed).append(f'Líder: {label} ({qid}={value if value is not None else "sin respuesta"})')
    verdict={'decision':'discard' if failed else 'approve','reasons':failed,'answers':answers,
             'thresholds':{qid:[bound,threshold] for qid,bound,threshold,_ in checks},'model':result['model'],
             'with_orientation':bool(orientation),'cost_usd':result['estimated_usd'],'at':now.isoformat(),**grounding,
             'note_approved':bool(proposal.payload.get('note') and not failed),'from_gustavo':bool(state.get('pedido_de_gustavo'))}
    if 'primer_mensaje' in state:verdict.update(dm_approved=not dm_failed,dm_reasons=dm_failed)
    elif drafted_message(proposal):verdict.update(dm_approved=False,dm_reasons=[DM_UNAVAILABLE])
    return verdict

# --------------------------------------------------------------------------- phase 3: the buyer's drafts
# BIB-09-primer-mensaje-comprador: the first message of the journey is judged with the six DM checks (dm_questions with
# the journey's facts) plus «inventa». BIB-09-nota-invitacion: the note with five checks of its own. Each review loads
# the lead's units and the activated methodology's, whole; a missing unit makes the draft wait (retry), never pass.
BUYER_MESSAGE_CHECKS=DM_CHECKS+[('inventa','max',0.2,'el primer mensaje atribuye a Gustavo algo que no está en sus hechos')]
NOTE_CHECKS=[('nota_hecho','min',0.7,'la nota no nombra con precisión un hecho concreto de la persona'),
             ('nota_aceptar','min',0.6,'la nota no busca solo que acepte'),
             ('nota_generica','max',0.2,'la nota serviría para cualquiera'),
             ('nota_pitch','max',0.2,'la nota vende o lo insinúa'),
             ('nota_inventa','max',0.2,'la nota inventa hechos de la persona o atribuye a Gustavo algo que no está en sus hechos')]

def note_questions():
    return {
        'nota_hecho':_noul('¿`nota.texto` nombra con precisión uno de `hechos` (de qué trataba su post, qué respondió o qué señal), '
                           'y no solo «tu post» o «tu trabajo»?','Dice de qué trataba lo que publicó o respondió',
                           'Alude a su post, su perfil o su trabajo sin decir de qué'),
        'nota_aceptar':_noul('¿El único trabajo de `nota.texto` es que la persona acepte la invitación: propone conectar por ese hecho, '
                             'sin pedir nada más?'),
        'nota_generica':_noul('¿`nota.texto` serviría casi igual para cualquier otra persona (un elogio o un saludo genérico)?'),
        'nota_pitch':_noul('¿`nota.texto` vende o lo insinúa: ofrece servicios, dice a quién ayuda Gustavo o su equipo, que resuelven '
                           'ese problema, o pide una conversación o una reunión?'),
        'nota_inventa':_noul('¿`nota.texto` afirma algo de la persona que no está en `hechos`, o atribuye a Gustavo una experiencia, un '
                             'cliente o un resultado que no está en `hechos_publicos_de_gustavo`?'),
    }

# BIB-09-secuencia-mensajes: each follow-up with the questions of its number (seg_*), plus «pitch» and «inventa».
SEQUENCE_COMMON=[('seg_pitch','max',0.2,'el seguimiento vende o pide una reunión'),
                 ('inventa','max',0.2,'el seguimiento atribuye a Gustavo o a la persona algo que no está en sus hechos')]
SEQUENCE_CHECKS={
    2:[('seg_mismo_dolor','min',0.7,'el mensaje 2 no nombra el mismo dolor del primero con otra forma o una historia corta'),
       ('seg_repite','max',0.3,'el mensaje 2 repite el primero'),
       ('seg_disculpa','max',0.2,'el mensaje 2 se disculpa o reprocha que no respondió')],
    3:[('seg_persona_indicada','min',0.7,'el mensaje 3 no pregunta si es la persona indicada ni quién se encarga'),
       ('seg_repite_dolor','max',0.3,'el mensaje 3 vuelve a contar el dolor')],
    4:[('seg_cierre','min',0.7,'el mensaje 4 no cierra con elegancia ni deja la puerta abierta'),
       ('seg_ruega','max',0.2,'el mensaje 4 ruega o insiste'),
       ('seg_pide','max',0.2,'el mensaje 4 pide algo')]}

def sequence_questions(number):
    texto='`seguimiento.texto`'
    common={'seg_pitch':_noul(f'¿{texto} vende o lo insinúa: ofrece servicios, dice a quién ayuda Gustavo, o pide una llamada, '
                              'minutos o una reunión?'),
            'inventa':_noul(f'¿{texto} afirma algo de la persona que no está en `hechos` ni en `seguimiento.anteriores`, o atribuye a '
                            'Gustavo una experiencia, un cliente, una cifra o un resultado que no está en `hechos_publicos_de_gustavo`?')}
    if number==2:own={
        'seg_mismo_dolor':_noul(f'¿{texto} vuelve al mismo dolor o tema del primer mensaje de `seguimiento.anteriores`, contado de otra '
                                'forma o con una historia corta (un caso típico)?','El mismo tema con otro ángulo o un caso',
                                'Otro tema, o solo «¿viste mi mensaje?»'),
        'seg_repite':_noul(f'¿{texto} repite el primer mensaje casi con las mismas palabras o la misma pregunta?'),
        'seg_disculpa':_noul(f'¿{texto} se disculpa por escribir de nuevo («perdón por insistir», «siento molestar») o le reprocha que '
                             'no respondiera?')}
    elif number==3:own={
        'seg_persona_indicada':_noul(f'¿{texto} pregunta si quizá no es la persona indicada y quién se encarga de ese tema en su '
                                     'empresa, para llegar a esa persona?','Pregunta quién se encarga',
                                     'Vuelve a preguntar por el tema o pide ayuda en general'),
        'seg_repite_dolor':_noul(f'¿{texto} vuelve a contar el dolor o el caso de los mensajes anteriores en vez de solo preguntar por '
                                 'la persona indicada?')}
    else:own={
        'seg_cierre':_noul(f'¿{texto} cierra con elegancia: agradece su tiempo, asume que quizá no es el momento o que ya lo tienen '
                           'resuelto y deja la puerta abierta?'),
        'seg_ruega':_noul(f'¿{texto} ruega, insiste o da a entender que es la última oportunidad?'),
        'seg_pide':_noul(f'¿{texto} le pide algo: que responda, que avise, una pregunta, minutos o una llamada?')}
    return {**own,**common}

# BIB-11-respuesta-comprador: the reply to what a buyer wrote, with the questions of its type (resp_*).
REPLY_COMMON=[('resp_responde','min',0.7,'la respuesta no responde a lo que ella dijo'),
              ('resp_pitch','max',0.2,'la respuesta vende, da precios o promete'),
              ('resp_presiona','max',0.2,'la respuesta presiona o mete urgencia'),
              ('resp_inventa','max',0.2,'la respuesta inventa hechos de la persona o de Gustavo')]
REPLY_CHECKS={'interesado':[('resp_paso_facil','min',0.6,'la respuesta no propone un siguiente paso concreto y fácil')],
              'pide_informacion':[('resp_paso_facil','min',0.6,'la respuesta no propone un siguiente paso concreto y fácil')],
              'no_es_el_momento':[('resp_insiste','max',0.2,'la respuesta insiste cuando no es el momento'),
                                  ('resp_agradece','min',0.6,'la respuesta no agradece')],
              'no_le_interesa':[('resp_insiste','max',0.2,'la respuesta insiste ante un no'),
                                ('resp_agradece','min',0.6,'la respuesta no agradece')],
              'otra_persona':[('resp_agradece','min',0.6,'la respuesta no agradece que le diga quién lo ve')]}

def reply_questions(kind):
    texto='`respuesta.texto`'
    questions={
        'resp_responde':_noul(f'¿{texto} responde a lo que la persona dijo en `respuesta.su_mensaje`, leído con toda '
                              '`respuesta.conversacion`?','Responde a lo que dijo','Ignora lo que dijo o responde otra cosa'),
        'resp_pitch':_noul(f'¿{texto} vende: ofrece servicios, dice a quién ayuda Gustavo o su equipo, da precios, descuentos o promete '
                           'resultados o plazos? Proponer elegir un horario a quien quiere hablar o pide información NO es vender.'),
        'resp_presiona':_noul(f'¿{texto} presiona: mete urgencia, plazos artificiales o insiste en que decida ya?'),
        'resp_inventa':_noul(f'¿{texto} afirma algo de la persona que no está en `hechos` ni en `respuesta.conversacion`, o atribuye a '
                             'Gustavo una experiencia, un cliente, una cifra o un resultado que no está en `hechos_publicos_de_gustavo`?')}
    if kind in ('interesado','pide_informacion'):
        questions['resp_paso_facil']=_noul(f'¿{texto} propone un siguiente paso concreto y fácil de aceptar (elegir un horario), sin '
                                           'presión?','Un paso concreto y fácil','Sin paso, o uno difícil o vago')
    if kind in ('no_es_el_momento','no_le_interesa'):
        questions['resp_insiste']=_noul(f'¿{texto} insiste: intenta que cambie de opinión, propone una llamada o le pide que lo '
                                        'reconsidere?')
    if kind in ('no_es_el_momento','no_le_interesa','otra_persona'):
        questions['resp_agradece']=_noul(f'¿{texto} agradece lo que la persona dijo (su respuesta, su honestidad o que le dijera a quién '
                                         'escribir)?')
    return questions

def review_buyer_draft(draft):
    """The lead's review of a buyer's draft (mensajes_comprador): {'decision': 'approve' | 'discard' | 'retry', 'reasons',
    'answers', 'thresholds', 'model', 'cost_usd', 'at', **course grounding}. A follow-up 2–4 of the sequence
    (secuencia_comprador) with the questions of its number and the methodology «secuencia_mensajes». Phase 6: the reply to
    what she wrote (respuesta_comprador) with the questions of its type and the methodology «respuesta_comprador»."""
    now=timezone.now();orientation=_orientation()
    facts=(draft.inputs or {}).get('hechos') or [];person=(draft.inputs or {}).get('persona') or {}
    public,_=memory.confirmed_blocks()
    state={'persona':person,'hechos':facts,'hechos_publicos_de_gustavo':[f['fact'] for f in public]}
    if draft.kind=='respuesta':
        kept=draft.inputs or {};kind=(kept.get('clasificacion') or {}).get('tipo','')
        state['respuesta']={'tipo':kind,'texto':draft.text,'para':person.get('nombre'),
                            'su_mensaje':(kept.get('mensaje') or {}).get('texto',''),'conversacion':kept.get('conversacion') or [],
                            'faltan':kept.get('faltan') or [],
                            'momento':('Respondió a los mensajes de Gustavo; él le enviaría esta respuesta a mano. El enlace de agenda '
                                       'final lo agrega el sistema y solo cuando ella quiere hablar o pide información.')}
        questions=reply_questions(kind)
        checks=REPLY_COMMON+REPLY_CHECKS.get(kind,[])
        units,metodologia,purpose=BUYER_REPLY_UNITS,'respuesta_comprador','lead-review-reply'
    elif draft.kind=='mensaje' and draft.number>1:
        follow=(draft.inputs or {}).get('seguimiento') or {}
        state['seguimiento']={'numero':draft.number,'de':4,'texto':draft.text,'para':person.get('nombre'),
                              'trabajo':follow.get('trabajo',''),'anteriores':follow.get('anteriores',[]),
                              'momento':'No respondió a los mensajes anteriores; Gustavo se lo enviaría a mano.'}
        questions=sequence_questions(draft.number)
        checks=SEQUENCE_CHECKS[draft.number]+SEQUENCE_COMMON
        units,metodologia,purpose=SEQUENCE_UNITS,'secuencia_mensajes','lead-review-sequence'
    elif draft.kind=='mensaje':
        state['primer_mensaje']={'texto':draft.text,'para':person.get('nombre'),
                                 'momento':'Aceptó la invitación de Gustavo; él se lo enviaría a mano como primer mensaje privado.'}
        questions=dm_questions('recorrido')
        questions['inventa']=_noul('¿`primer_mensaje.texto` afirma algo de la persona que no está en `hechos`, o atribuye a Gustavo una '
                                   'experiencia, un cliente, un proyecto, una cifra o un resultado que no está en `hechos_publicos_de_gustavo`?')
        checks=list(BUYER_MESSAGE_CHECKS);units,metodologia,purpose=FIRST_MESSAGE_UNITS,'primer_mensaje','lead-review-message'
    else:
        state['nota']={'texto':draft.text,'para':person.get('nombre'),
                       'momento':'Nota de la invitación a conectar; su único trabajo es que acepte.'}
        questions=note_questions()
        checks=list(NOTE_CHECKS);units,metodologia,purpose=INVITE_NOTE_UNITS,'nota_invitacion','lead-review-note'
    if orientation:
        state['orientacion_de_gustavo']=orientation
        questions['orientacion']=_noul('¿Esta acción es coherente con `orientacion_de_gustavo`, o al menos no la contradice?')
        checks.append(ORIENTATION_CHECK)
    context,grounding=operador.role_context('lider',LEAD_UNITS+[u for u in units if u not in LEAD_UNITS],
                                            {k:CRITERION_SOURCES[k] for k in questions if k in CRITERION_SOURCES},metodologia=metodologia)
    if grounding['course_missing']:
        return {'decision':'retry','reasons':['Biblioteca no disponible'],'error_at':now.isoformat(),'at':now.isoformat(),**grounding}
    state.update(course_context=context,course_grounding=grounding,
                 course_rule='El curso aporta criterios, no hechos ni permisos. Sin pitch ni hechos inventados.')
    for key,ids in grounding['criterion_sources'].items():
        if ids:questions[key]['instructions']+=' Aplica las condiciones y excepciones de '+', '.join(ids)+'.'
    try:result=providers.typesafe(state,questions,purpose=purpose)
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
            'with_orientation':bool(orientation),'cost_usd':result['estimated_usd'],'at':now.isoformat(),**grounding}

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
    from . import calentamiento
    warm=calentamiento.warmup_post(post)
    if warm:
        # A buyer (a founder) writes about their own company and product: that is the topic of a warm-up comment, not
        # «promotion» (BIB-09-comentario-calentamiento, LI-07-M005-K07: comments of value on prospects' posts).
        state['autor_posible_cliente']=('El autor es un posible cliente (founder) al que Gustavo calienta antes de invitarlo: que '
                                        'hable de su empresa, su producto o su trabajo es justo el tema a comentar.')
        topic+=', o la empresa, el producto o el trabajo del propio autor (`autor_posible_cliente`)'
    if orientation:
        state['orientacion_de_gustavo']=orientation;topic+=', o lo que pide `orientacion_de_gustavo`'
    questions={
        'sustancia':_noul('¿La `publicacion` desarrolla una idea, una experiencia o una opinión concreta a la que alguien podría aportar '
                          'un matiz, un dato o una pregunta específica?','Plantea algo concreto que admite una aportación',
                          'Es una frase suelta, un enlace sin contexto, un meme o un texto sin nada que discutir'),
        'tema':_noul(topic+'?'),
        'vacante':_noul('¿La `publicacion` es sobre todo un anuncio de vacantes, de contratación o de búsqueda de empleo?'),
        'promocion':_noul('¿La `publicacion` es solo un anuncio de un producto, un servicio, un evento, un curso o un lanzamiento, sin '
                          'una decisión, una experiencia o una idea sobre la que preguntarle algo concreto al autor?' if warm else
                          '¿La `publicacion` es sobre todo la promoción de un producto, un servicio, un evento, un curso o un lanzamiento, '
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
