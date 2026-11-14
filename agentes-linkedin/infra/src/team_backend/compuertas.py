"""Gates that can stop a piece: severity, the scoped second review and the second attempt of the day (docs/compuertas.md).

Gustavo (2026-11-14): «el verificador es demasiado rígido… que no nos bloquee tanto, y si nos bloquea buscar una manera
de reintentar… no digo que lo quitemos… tampoco iteraciones infinitas: al menos que en la segunda revisión ya pase, de
haber corregido lo que bloqueó».

- Severity. HARD findings (invented experience, figures or claims without support, private data, a leak of his private
  guidance, aggressive pitch) block at every review: they protect people, the truth and his privacy. SOFT findings
  (a hook the text does not deliver, a drift from the brief, other quality issues) trigger the one repair round and,
  whatever that round does, stay as observations on a piece that goes out. Minor findings never block. The
  deterministic rules and the web-source checks are always hard.
- Second review. After the repair the verifier gets the first findings and the changes (second_review): it checks that
  each one was resolved and flags only new hard problems. Code blocks only on hard findings there.
- Second attempt. A day whose piece a content gate blocked while it was prepared gets ONE more attempt
  (EDITORIAL_DAY_ATTEMPTS=2) when there is time before its hour (EDITORIAL_RETRY_MIN_MINUTES); the director sees why the
  first one stopped. Money stops wait for budget and never count as an attempt; a skip or a failure is not retried.
- gate_policy(piece) is the one hook for what a post type may do that the default forbids. Without a policy in the
  brief everything behaves as before (no contact request at all).
"""
import os
import re
from datetime import timedelta
from .models import EditorialPiece

HARD=('invented_experience','unsourced_figure','private_data','private_guidance_leak','unsupported_claim')
SOFT=('hook_not_delivered','off_brief','other')
# aggressive_pitch is hard unless the piece's policy allows one conversational call to action (then the verifier's
# finding is soft and the deterministic rule still stops hard selling).
DEFAULT_POLICY={'cta_max':0}
BLOCKED_BARE='El verificador emitió blocked'
LEAD_REDRAFT='Reescrito una vez con las razones del líder'  # risk of a comment redrafted after a lead discard

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
    hard=set(HARD)|extra
    if not (policy or DEFAULT_POLICY).get('cta_max'):hard.add('aggressive_pitch')
    return hard

def severity(issue,policy=None):
    return 'dura' if issue in hard_issues(policy) else 'blanda'

def split(review,policy=None):
    """(hard reasons, soft findings) of one verifier review. The reasons use the wording of editorial._blocking. A bare
    «blocked» without material findings or unsupported claims is hard: there is nothing concrete to keep as an observation."""
    review=review or {};hard=hard_issues(policy);reasons=[];soft=[]
    material=[f for f in review.get('findings',[]) if f.get('severity')=='material']
    unsupported=[c for c in review.get('checked_claims',[]) if c.get('status')=='unsupported']
    if review.get('verdict')!='ready_for_execution' and not material and not unsupported:reasons.append(BLOCKED_BARE)
    for f in material:
        if f.get('issue') in hard:reasons.append(f'Hallazgo material ({f.get("issue")}): {f.get("detail") or f.get("quote")}')
        else:soft.append({'issue':f.get('issue') or 'other','quote':f.get('quote') or '','detail':f.get('detail') or ''})
    reasons+=[f'Afirmación sin respaldo: {c.get("text")}' for c in unsupported]
    return reasons,soft

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
        if f.get('source')=='reglas':still=f.get('detail') in issues
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
    return (autopiloto.enabled() and autopiloto.autonomy('CONT-09')!='off' and not piece.second_of_day
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
