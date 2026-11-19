"""Gates that can stop a piece: severity, the scoped second review and the second attempt of the day (docs/compuertas.md).

Gustavo (2026-11-14): «el verificador es demasiado rígido… que no nos bloquee tanto, y si nos bloquea buscar una manera
de reintentar… no digo que lo quitemos… tampoco iteraciones infinitas: al menos que en la segunda revisión ya pase, de
haber corregido lo que bloqueó».

- Severity. Gustavo (2026-11-19): «el verificador es muy rígido… es un post… no tiene que ser tan estricto».
  HARD findings are only an invented fact about him, his company or his clients presented as real (invented
  experience, someone else's story told as his) and private material (private data, a leak of his private guidance):
  they get the one repair round, which fixes that sentence, and block if they survive it. Everything else is SOFT: a
  figure or quote attributed to a source the evidence does not hold, an unsupported claim, a selling tone, a hook the
  text does not deliver, a drift from the brief. Soft findings are notes for the repair round and observations of a
  piece that goes out, never a block. Minor findings never block. The deterministic form rules (CONT-09), the
  private-guidance guard and a figure about his work that his facts do not hold (guardas.invented_figures) stay hard;
  the rest of the first-person experience regex only points sentences out to the verifier (guardas.invented_experience)
  and the web-source checks are notes (research.source_issues).
- Second review. After the repair the verifier gets the first findings and the changes (second_review): it checks that
  each one was resolved and flags only new hard problems. Code blocks only on hard findings there.
- Second attempt. A day whose piece a content gate blocked while it was prepared gets ONE more attempt
  (EDITORIAL_DAY_ATTEMPTS=2) when there is time before its hour (EDITORIAL_RETRY_MIN_MINUTES); the director sees why the
  first one stopped. Money stops wait for budget and never count as an attempt; a skip or a failure is not retried.
- gate_policy(piece) is the one hook for what a post type may do that the default forbids. Without a policy in the
  brief everything behaves as before (no contact request at all). The weekly strategy (estrategia.finalize_brief) sets
  it with the day's type: one conversational call to action on a Sales post, none on the others.
- This file is the one severity table, the per-type findings of the strategy (estrategia.findings and notes) included:
  the hard ones stop the text before the verifier like any rule; the soft ones join the verifier's findings, get the
  repair round and, if they stay, go out as observations.
"""
import os
import re
from datetime import timedelta
from .models import EditorialPiece

HARD=('invented_experience','private_data','private_guidance_leak',
      # A founder's public story on a Personal post (estrategia.findings) told as Gustavo's: a fact about him invented.
      'first_person_appropriation')
SOFT=('hook_not_delivered','off_brief','other',
      # Attribution to a source (19/11/2026): the repair drops or softens the attribution, or turns a quote into a
      # paraphrase; if it cannot, the piece goes out with the note.
      'unsourced_figure','unsupported_claim','fabricated_quote','unsourced_third_party_story',
      # The verifier's reading of a selling tone; the deterministic pitch rule of CONT-09 (form_rules) still stops it.
      'aggressive_pitch',
      # What fits a GASP type (estrategia.findings and notes): how a post is shaped, never a safety problem.
      'cta_count','offer_in_growth','offer_in_personal','no_reader_need','repeated_story')
# The finding codes of the weekly strategy; an issue line of estrategia reads «code: detail».
STRATEGY_CODES=('unsourced_third_party_story','fabricated_quote','first_person_appropriation','cta_count','offer_in_growth',
                'offer_in_personal','no_reader_need','repeated_story')
# The piece's policy allows one conversational call to action (cta_max=1); the deterministic rule (form_rules) counts it.
DEFAULT_POLICY={'cta_max':0}
BLOCKED_BARE='El verificador emitió blocked'
LEAD_REDRAFT='Reescrito una vez con las razones del líder'  # risk of a comment redrafted after a lead discard

def lead_redraft():
    """A comment the lead discarded gets ONE redraft with its reasons (COMMENT_LEAD_REDRAFT, on by default)."""
    return os.environ.get('COMMENT_LEAD_REDRAFT','true').lower()=='true'

# --------------------------------------------------------------------------- policy and severity

def gate_policy(piece=None):
    """What this piece may do beyond the default. brief['gate_policy'] (set by a post type, never by the model) can allow
    one conversational call to action ({'cta_max': 1}); anything else keeps the default."""
    raw=(getattr(piece,'brief',None) or {}).get('gate_policy') if piece is not None else None
    raw=raw if isinstance(raw,dict) else {}
    try:cta=int(raw.get('cta_max',0))
    except (TypeError,ValueError):cta=0
    return {'cta_max':max(0,min(cta,1))}

def custom(policy):
    return bool(policy) and policy!=DEFAULT_POLICY

def hard_issues(policy=None):
    """COMPUERTAS_DURAS (comma separated) makes more verifier issues hard, e.g. «other» if it proves too loose."""
    extra={i.strip() for i in os.environ.get('COMPUERTAS_DURAS','').split(',') if i.strip()}
    return set(HARD)|extra

def severity(issue,policy=None):
    return 'dura' if issue in hard_issues(policy) else 'blanda'

def split(review,policy=None):
    """(hard reasons, soft findings) of one verifier review. The reasons use the wording of editorial._blocking. Only a
    material finding of a hard issue blocks. An unsupported claim and a bare «blocked» without anything concrete are
    soft since 19/11/2026: a note for the repair and an observation, never a stop."""
    review=review or {};hard=hard_issues(policy);reasons=[];soft=[]
    material=[f for f in review.get('findings',[]) if f.get('severity')=='material']
    unsupported=[c for c in review.get('checked_claims',[]) if c.get('status')=='unsupported']
    for f in material:
        if f.get('issue') in hard:reasons.append(f'Hallazgo material ({f.get("issue")}): {f.get("detail") or f.get("quote")}')
        else:soft.append({'issue':f.get('issue') or 'other','quote':f.get('quote') or '','detail':f.get('detail') or ''})
    soft+=[{'issue':'unsupported_claim','quote':c.get('text') or '','detail':'Afirmación sin respaldo en la evidencia'}
           for c in unsupported]
    if review.get('verdict')!='ready_for_execution' and not material and not unsupported:
        soft.append({'issue':'other','quote':'','detail':BLOCKED_BARE+' sin hallazgos concretos'})
    return reasons,soft

def settled(reasons,review,policy=None):
    """(blocking reasons, observations) of the last review once the repair round had its chance: the hard findings,
    with the round's own note when it could not fix them, block; everything else goes out as an observation."""
    hard,soft=split(review,policy)
    if hard:return hard+[r for r in reasons if str(r).startswith('Ronda de reparación')],[]
    return [],soft

# --------------------------------------------------------------------------- the strategy's per-type findings

BY_CODE='codigo'  # a finding the code added to a review (estrategia.findings), never the model's

def strategy_code(issue):
    """The code of a strategy issue line («cta_count: …» → cta_count), or None for any other rule."""
    head=str(issue).split(':',1)[0].strip()
    return head if head in STRATEGY_CODES else None

def strategy_split(issues,policy=None):
    """(hard issue lines, soft issue lines) of estrategia.findings, by this table (COMPUERTAS_DURAS can harden one)."""
    hard=hard_issues(policy)
    return ([i for i in issues if strategy_code(i) in hard],[i for i in issues if strategy_code(i) not in hard])

def with_code_findings(review,issues):
    """The verifier's review plus the soft strategy findings of the same text as material findings marked by code: they
    get the one repair round and, if they stay, settle as observations. One the model already flagged is not doubled."""
    if not issues or review is None:return review
    flagged={f.get('issue') for f in review.get('findings',[]) if f.get('severity')=='material'}
    extra=[]
    for line in issues:
        code=strategy_code(line)
        if code in flagged:continue
        flagged.add(code)
        extra.append({'issue':code,'severity':'material','quote':'','detail':str(line).split(':',1)[1].strip(),'by':BY_CODE})
    return dict(review,findings=list(review.get('findings',[]))+extra) if extra else review

def observation_risks(observations):
    """What the proposal (and the detail) say about a soft finding that did not stop the piece."""
    return [f'Conservada como observación ({o.get("issue")}): {o.get("detail") or o.get("quote")}' for o in observations]

def resolution(findings,review,issues):
    """Per first finding, whether the second look still sees it: a rule by its exact text, a verifier finding by its issue
    among the material findings (unsupported claims by their text). Deterministic, for the audit and the detail."""
    review=review or {}
    open_issues={f.get('issue') for f in review.get('findings',[]) if f.get('severity')=='material'}
    open_claims={c.get('text') for c in review.get('checked_claims',[]) if c.get('status')=='unsupported'}
    out=[]
    for f in findings:
        # A soft strategy finding that travelled with the rules is still open if the second review carries it.
        if f.get('source')=='reglas':still=f.get('detail') in issues or (strategy_code(f.get('detail')) or '') in open_issues
        elif f.get('issue')=='unsupported_claim':still=f.get('quote') in open_claims
        else:still=f.get('issue') in open_issues
        out.append({'source':f.get('source'),'issue':f.get('issue'),'resolved':not still})
    return out

# --------------------------------------------------------------------------- form rules shared by the circuit and the policy

def pitch(text,policy=None):
    """Hard selling always counts; conversational calls to action count beyond the policy's cta_max (default 0)."""
    from . import autopiloto
    if autopiloto.POST_SELL.search(text):return True
    return len(autopiloto.POST_CTA.findall(text))>(policy or DEFAULT_POLICY).get('cta_max',0)

def form_rules(text,policy=None):
    """The deterministic CONT-09 form rules (length, email, phone, links, pitch, hashtags). editorial.text_rules runs them
    before the verifier is paid and autopiloto.post_issues again as the final gate: one function, same verdict."""
    from . import autopiloto as p
    issues=[];low,high=p.POST_LENGTH
    if not low<=len(text)<=high:issues.append(f'Longitud fuera de {low}–{high} caracteres')
    for pattern,reason in ((p.EMAIL,'Contiene un correo'),(p.PHONE,'Contiene un número de teléfono'),(p.URL,'Contiene enlaces')):
        if pattern.search(text):issues.append(reason)
    if pitch(text,policy):issues.append('Contiene pitch agresivo o petición de contacto')
    if len(p.HASHTAG.findall(text))>p.POST_MAX_HASHTAGS:issues.append(f'Más de {p.POST_MAX_HASHTAGS} hashtags')
    return issues

# --------------------------------------------------------------------------- the second attempt of the day

def day_attempts():
    try:return max(1,int(os.environ.get('EDITORIAL_DAY_ATTEMPTS','2')))
    except ValueError:return 2

def retry_margin():
    """A preparation takes up to ~20 min and the veto window needs room: a retry closer than this to the hour waits."""
    try:return timedelta(minutes=max(0,int(os.environ.get('EDITORIAL_RETRY_MIN_MINUTES','90'))))
    except ValueError:return timedelta(minutes=90)

def gate_blocked(piece):
    """Blocked while it was prepared by a content gate (rules, verifier or the visual check): not by money, a stopped cycle
    or a failed rework of his comment (that one keeps his rule: the commented version never goes out without him)."""
    from . import editorial
    if piece.state!=EditorialPiece.State.BLOCKED or editorial.budget_stopped(piece):return False
    if piece.note.startswith(('Ciclo detenido','No se pudo aplicar el comentario','Preparación interrumpida')):return False
    return not (piece.verification or {}).get('rework')

def attempt_number(piece):
    """1 + the earlier pieces of the same day a content gate stopped (money stops are waits, not attempts)."""
    earlier=EditorialPiece.objects.filter(slot_date=piece.slot_date,second_of_day=piece.second_of_day,
                                          created_at__lt=piece.created_at).exclude(pk=piece.pk)
    return 1+sum(1 for p in earlier if gate_blocked(p))

def retry_left(piece,now):
    """Whether a block of this piece (still being closed) leaves one more attempt for its day: only the autopilot retries."""
    from . import autopiloto
    from . import operador
    return (autopiloto.enabled() and autopiloto.autonomy('CONT-09',operador.member_of(account=piece.account))!='off' and not piece.second_of_day
            and attempt_number(piece)<day_attempts() and piece.scheduled_for-now>=retry_margin())

def gate_retry(pieces,now,when):
    """Autopilot: a day whose latest piece a content gate blocked is free once more while attempts and time remain."""
    pieces=list(pieces)
    if not pieces or day_attempts()<2:return False
    closed=(EditorialPiece.State.BLOCKED,EditorialPiece.State.SKIPPED,EditorialPiece.State.FAILED)
    if any(p.state not in closed for p in pieces):return False
    if not gate_blocked(max(pieces,key=lambda p:p.created_at)):return False
    if sum(1 for p in pieces if gate_blocked(p))>=day_attempts():return False
    return when-now>=retry_margin()

def category(reason):
    """A short stable label for a stop reason: never the quote or detail it may carry (audit output is shareable)."""
    reason=str(reason)
    match=re.match(r'Hallazgo material \((\w+)\)',reason)
    if match:return match.group(1)
    match=re.search(r'\((\w+)=',reason)
    if reason.startswith(('Líder:','Prefiltro:')) and match:return match.group(1)
    for prefix,label in CATEGORIES:
        if reason.startswith(prefix):return label
    return 'otro'

CATEGORIES=(('Afirmación sin respaldo','unsupported_claim'),(BLOCKED_BARE,'veredicto_sin_hallazgos'),
            ('Afirmación web sin','fuente_web'),('El verificador citó una fuente web','fuente_web'),
            ('Longitud','longitud'),('Contiene un correo','correo'),('Contiene un número de teléfono','telefono'),
            ('Contiene enlaces','enlaces'),('Contiene pitch','pitch'),('Más de','hashtags'),
            ('Deja traslucir orientación privada','private_guidance_leak'),('Reproduce orientación privada','private_guidance_leak'),
            ('Atribuye','invented_experience'),('Cifra sobre el trabajo de Gustavo','invented_experience'),
            ('Ronda de reparación: sin presupuesto','reparacion_sin_presupuesto'),
            ('Ronda de reparación: el texto reparado no se pudo verificar','reparacion_sin_presupuesto'),
            ('Ronda de reparación: la descartó','reparacion_descartada'),('Ronda de reparación: no cambió','reparacion_sin_cambios'),
            ('Sin veredicto ready_for_execution','sin_veredicto'),('El veredicto del verificador no corresponde','texto_cambiado'),
            ('Incluye afirmaciones sin evidencia','afirmaciones_sin_evidencia'),('Sin fundamento citado','sin_citas'),
            ('Está en inglés','idioma'),('Ya hay un comentario para','enfriamiento_autor'),('Imagen','imagen'),
            ('Documento','imagen'),('Capacidad desactivada','no_contenido'),('Hash inconsistente','no_contenido'))

def previous_attempts(piece):
    """What the director needs to avoid on the day's second attempt: the earlier attempt's thesis and why a gate stopped it."""
    rows=[]
    earlier=EditorialPiece.objects.filter(slot_date=piece.slot_date,second_of_day=piece.second_of_day,
                                          created_at__lt=piece.created_at).exclude(pk=piece.pk).order_by('created_at')
    for p in earlier:
        if not gate_blocked(p):continue
        brief=p.brief or {};v=p.verification or {}
        reasons=list(v.get('blocking_reasons') or []) or ([p.note] if p.note else [])
        rows.append({'thesis':brief.get('thesis') or '','pillar':brief.get('pillar'),'approach':brief.get('approach'),
                     'blocked_by':'imagen' if v.get('verdict')=='ready_for_execution' else 'texto',
                     'categories':sorted({category(r) for r in reasons}),'reasons':[str(r)[:300] for r in reasons[:5]]})
    return rows
