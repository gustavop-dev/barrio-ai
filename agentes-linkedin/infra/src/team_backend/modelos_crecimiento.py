"""«What worked for them» (docs/plan-referentes-industria.md): the posts of a referent that did far better than that
same referent's usual post, described by their shape and by who answered them, never by their words.

Gustavo, 14/11/2026: «lo que les funcione a ellos lo copiemos». The weekly strategy copies structure and angle, never
text, so what this module keeps about a post is labels and numbers: `outlier` (how it did against its author's own
norm), `structure` (hook, length band, outline, closing… as labels) and `audience` (counts and de-identified themes of
its comments: no names, no sentences). And «no se trata de mí, se trata de la audiencia»: a model is ranked by how much
of the people who answered it are Gustavo's neighborhood, not only by its reach.

No paid call. Outliers and structure come from what operador.observe already read; the audience comes from comments
red.discover already read, plus at most MODELOS_LECTURAS_DIA comment reads a day for new outliers of industry
referents, counted by red._read inside the shared daily cap."""
from collections import Counter, defaultdict
from datetime import timedelta
import logging
import os
import re
import statistics

from django.utils import timezone

from . import ubicacion
from .models import AuditEvent, Contact, ObservedPost, PersonEvidence

logger = logging.getLogger(__name__)
RULE = 'atipico-v1'
STRUCTURE_RULE = 'estructura-v1'
AUDIENCE_RULE = 'audiencia-v1'
READ_EVENT = 'modelos.audience_read'
USE = ('Modelo de estructura y ángulo. Nunca copiar frases, cifras, historias ni ejemplos: adaptarlo a una experiencia '
       'real de Gustavo y a su audiencia.')


def _number(name, default, cast=int):
    try:
        return cast(os.environ.get(name, default))
    except (TypeError, ValueError):
        return cast(default)


def thresholds():
    """Defaults, why: 6 other posts is the smallest sample whose median is not one lucky post; 2x the median and a
    robust z of 3 are «clearly above their own norm», not noise; 20 interactions keeps tiny accounts out; 120 days
    of base is about a quarter of their posting; 45 days keeps a model current; 48 h is when a post's counters settle."""
    return {'min_sample': _number('MODELOS_MIN_MUESTRA', 6), 'min_lift': _number('MODELOS_MIN_VECES_MEDIANA', 2.0, float),
            'min_z': _number('MODELOS_MIN_Z', 3.0, float), 'min_interactions': _number('MODELOS_MIN_INTERACCIONES', 20),
            'base_days': _number('MODELOS_DIAS_BASE', 120), 'recent_days': _number('MODELOS_DIAS_RECIENTES', 45),
            'mature_hours': _number('MODELOS_HORAS_MADURO', 48), 'reads_per_day': _number('MODELOS_LECTURAS_DIA', 4),
            'min_classified': _number('MODELOS_MIN_CLASIFICADOS', 5)}


# --------------------------------------------------------------------------- outliers

def score(reactions, comments):
    """Interactions LinkedIn shows (reactions + comments); None when neither is known: a hidden counter is not zero."""
    if reactions is None and comments is None:
        return None
    return (reactions or 0) + (comments or 0)


def judge(value, baseline, t=None, mature=True):
    """Pure rule. `baseline`: scores of the author's OTHER mature original posts (leave-one-out, so one huge post does
    not raise its own bar). Median and MAD instead of mean and deviation: one viral post must not move the norm.
    With MAD 0 (many equal posts) only the ratio decides; with median 0 only the absolute floor does."""
    t = t or thresholds()
    out = {'score': value, 'sample': len(baseline), 'mature': mature, 'rule': RULE}
    if value is None:
        return dict(out, flag=False, reason='sin_contadores')
    if len(baseline) < t['min_sample']:
        return dict(out, flag=False, reason='muestra_insuficiente')
    median = statistics.median(baseline)
    mad = statistics.median(abs(x - median) for x in baseline)
    lift = round(value / median, 2) if median > 0 else None
    z = round((value - median) / (1.4826 * mad), 2) if mad > 0 else None
    out.update(median=median, mad=mad, lift=lift, z=z)
    reasons = []
    if value < t['min_interactions']:
        reasons.append('pocas_interacciones')
    if value <= median:
        reasons.append('no_supera_mediana')
    elif lift is not None and lift < t['min_lift']:
        reasons.append('poca_ventaja')
    if z is not None and z < t['min_z']:
        reasons.append('dentro_de_lo_normal')
    return dict(out, flag=not reasons, reason=reasons[0] if reasons else 'modelo')


def refresh(account, referent_ids=None, now=None):
    """Recompute `outlier` (and `structure` when missing) for the recent original posts of these referents. Counters
    change on every observation, so this runs after each one. Returns the flagged posts."""
    now = now or timezone.now()
    t = thresholds()
    rows = (ObservedPost.objects.select_related('referent')
            .filter(account=account, referent__isnull=False, is_repost=False, posted_at__gte=now - timedelta(days=t['base_days'])))
    if referent_ids is not None:
        rows = rows.filter(referent_id__in=list(referent_ids))
    by_referent = defaultdict(list)
    for post in rows:
        by_referent[post.referent_id].append(post)
    settled, recent, flagged = now - timedelta(hours=t['mature_hours']), now - timedelta(days=t['recent_days']), []
    for posts in by_referent.values():
        mature = {p.pk: score(p.reactions_count, p.comments_count) for p in posts if p.posted_at <= settled}
        mature = {pk: value for pk, value in mature.items() if value is not None}
        for post in posts:
            if post.posted_at < recent:
                continue
            # A young post can only gain interactions: it may already be flagged, marked as not mature.
            result = judge(score(post.reactions_count, post.comments_count),
                           [v for pk, v in mature.items() if pk != post.pk], t, mature=post.posted_at <= settled)
            result.update(reactions=post.reactions_count, comments=post.comments_count)
            fields = []
            if {k: v for k, v in post.outlier.items() if k != 'computed_at'} != result:
                post.outlier = dict(result, computed_at=now.isoformat())
                fields.append('outlier')
            if post.structure.get('rule') != STRUCTURE_RULE:
                post.structure = structure(post.text)
                fields.append('structure')
            if fields:
                post.save(update_fields=fields)
            if result['flag']:
                flagged.append(post)
    return flagged


# --------------------------------------------------------------------------- structure (labels, never text)

LIST_ITEM = re.compile(r'^\s*(?:[-–—•·*▪►→✅✔☑👉🔹🔸➡]|\d{1,2}[.)/]|[a-z][.)])\s*', re.I)
COUNTED = (r'\b\d+\s+(?:things|lessons|ways|mistakes|tips|reasons|steps|rules|signs|questions|cosas|lecciones|formas|'
           r'errores|consejos|razones|pasos|reglas|señales|preguntas)\b')
STORY = (r'^(?:last (?:week|month|year)|yesterday|today|this (?:morning|week)|in (?:19|20)\d\d|\d+ (?:years|months|weeks) ago|'
         r'years ago|when i|a (?:founder|client|ceo)|la semana pasada|ayer|hoy|esta (?:mañana|semana)|en (?:19|20)\d\d|hace|cuando|'
         r'un (?:founder|cliente))\b')
CONTRAST = (r"\b(?:unpopular opinion|hot take|stop|nobody|everyone|myth|wrong|never|don't|isn't|is not|is dead|overrated|"
            r'nadie|todos|mito|deja de|nunca|no es|sobrevalorad\w*)\b')
ANGLES = {
    'experiencia_propia': (r"\b(?:i built|i learned|i made|i was|i spent|i hired|i failed|we built|we shipped|we learned|"
                           r"we hired|my team|our team|i've|aprendí|construí|contraté|mi equipo|nuestro equipo|cometí)\b"),
    'caso_cliente': r'\b(?:clients?|customers?|a founder|a startup|cliente\w*|un founder|una startup)\b',
    'contrario': (r'\b(?:unpopular opinion|hot take|myth|overrated|stop doing|nobody tells|is dead|wrong|mito|'
                  r'sobrevalorad\w*|nadie te dice|deja de)\b'),
    'tutorial': r"\b(?:how to|step \d|here's how|guide|framework|playbook|checklist|cómo|paso \d|guía)\b",
    'datos': r'\d+(?:[.,]\d+)?\s?%|\$\s?\d|\b\d+(?:[.,]\d+)?\s?[kKmM]\b',
    'tendencia': r'\b(?:future of|in 202\d|trend\w*|next year|the shift|futuro|tendencia\w*)\b',
}
PILLAR_TERMS = {
    'business_to_product': (r'\b(?:product\w*|mvps?|roadmap|customers?|users?|business|founders?|market|producto\w*|'
                            r'negocio\w*|clientes?|usuarios?)\b'),
    'applied_ai': r'\b(?:ai|a\.i\.|llms?|gpt\w*|agents?|agentic|machine learning|genai|ia|inteligencia artificial|agentes?)\b',
    'architecture_delivery': (r'\b(?:architecture|deploy\w*|delivery|ship\w*|scal\w+|code|coding|engineer\w*|tech debt|'
                              r'infrastructure|arquitectura|entrega\w*|código|ingenier\w+|deuda técnica)\b'),
}
CTA = (r'\b(?:comment|follow|repost|share|dm me|save this|subscribe|join|sign up|book a|register|comenta|sígueme|comparte|'
       r'escríbeme|guarda|suscríbete|únete|agenda|regístrate)\b')
HIRING = r"\b(?:we'?re hiring|now hiring|job opening|open roles?|apply (?:now|here)|estamos contratando|vacante\w*)\b"
PROMOTION = (r'\b(?:register now|sign up|link in (?:the )?comments|webinar|enroll|discount|\d+% off|launch(?:ing)? today|'
             r'regístrate|inscríbete|descuento|link en (?:los )?comentarios)\b')
EN_WORDS = frozenset('the and to of a in is you that it for with this on are be your we i was have not but'.split())
ES_WORDS = frozenset('el la de que y en los las un una es por para con no se lo su tu más como pero fue'.split())
EMOJI = re.compile('[\U0001F300-\U0001FAFF☀-➿]')


def _language(words):
    en, es = sum(w in EN_WORDS for w in words), sum(w in ES_WORDS for w in words)
    if en + es < 5:
        return 'desconocido'
    return 'en' if en > 1.5 * es else 'es' if es > 1.5 * en else 'mixto'


def _hook(line):
    low = line.lower().strip()
    if low.endswith('?'):
        return 'pregunta'
    if re.search(COUNTED, low) or re.match(r'^(?:\d+|three|five|seven|ten|tres|cinco|siete|diez)\b', low):
        return 'lista_anunciada'
    if re.search(STORY, low):
        return 'historia'
    if re.search(r'\d', low):
        return 'cifra'
    if re.search(CONTRAST, low):
        return 'contraste'
    if re.match(r'^(?:i|we|my|our|yo|nosotros|mi|mis)\b', low):
        return 'primera_persona'
    return 'afirmacion'


def _block(lines):
    items = sum(bool(LIST_ITEM.match(line)) for line in lines)
    if items >= 2 and items >= len(lines) - 1:
        return 'lista'
    if lines[-1].rstrip().endswith('?'):
        return 'pregunta'
    if len(lines) == 1 and len(lines[0]) <= 60:
        return 'linea_corta'
    return 'parrafo'


def _closing(last):
    low = last.lower().strip()
    if 'http' in low or re.search(r'\b(?:link in|enlace)\b', low):
        return 'enlace'
    if low.endswith('?'):
        return 'pregunta'
    if re.search(CTA, low):
        return 'llamado'
    if re.match(r'^(?:p\.?s\.?|tl;?dr|bottom line|in short|en resumen|conclusión)', low):
        return 'resumen'
    return 'afirmacion'


def _top(patterns, low, default):
    hits = {key: len(re.findall(rx, low)) for key, rx in patterns.items()}
    best = max(hits, key=lambda key: hits[key]) if hits else None
    return best if best and hits[best] else default


def structure(text):
    """The post's shape as labels and numbers. Nothing here is a span of the post: every value is a count or comes
    from a fixed vocabulary, so the strategy can imitate the form without being able to reuse a sentence."""
    text = text or ''
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    blocks, current = [], []
    for raw in text.splitlines():
        if raw.strip():
            current.append(raw.strip())
        elif current:
            blocks.append(current)
            current = []
    if current:
        blocks.append(current)
    low = text.lower()
    words = re.findall(r"[a-záéíóúñü']+", low)
    items = sum(bool(LIST_ITEM.match(line)) for line in lines)
    hook = _hook(lines[0]) if lines else 'sin_texto'
    outline = ['gancho'] + [_block(b) for b in blocks[1:]] if blocks else []
    if len(blocks) > 1:
        outline[-1] = 'cierre_' + _closing(lines[-1])
    compact = []
    for kind in outline:
        if compact and compact[-1][0] == kind:
            compact[-1][1] += 1
        else:
            compact.append([kind, 1])
    closing = _closing(lines[-1]) if lines else 'sin_texto'
    form = ('lista' if items >= 3 else 'historia' if hook == 'historia' else
            'pregunta_abierta' if closing == 'pregunta' and len(lines) <= 6 else 'opinion')
    chars = len(' '.join(text.split()))
    return {'rule': STRUCTURE_RULE, 'language': _language(words), 'chars': chars, 'words': len(words),
            'length': 'corto' if chars < 600 else 'medio' if chars <= 1300 else 'largo',
            'lines': len(lines), 'paragraphs': len(blocks),
            'short_lines_pct': round(100 * sum(len(line) <= 60 for line in lines) / len(lines)) if lines else 0,
            'hook': {'type': hook, 'words': len(lines[0].split()) if lines else 0, 'own_line': len(blocks[0]) == 1 if blocks else False},
            'form': form, 'list_items': items,
            'outline': [f'{kind} x{n}' if n > 1 else kind for kind, n in compact][:12],
            'closing': closing, 'angle': _top(ANGLES, low, 'general'), 'pillar': _top(PILLAR_TERMS, low, 'otro'),
            'hashtags': len(re.findall(r'(?<!\w)#\w+', text)), 'mentions': len(re.findall(r'(?<!\w)@\w+', text)),
            'links': len(re.findall(r'https?://', text)), 'emojis': len(EMOJI.findall(text)),
            # The connector does not say whether there was an image, a video, a carousel or a document.
            'format': 'desconocido',
            'hiring': bool(re.search(HIRING, low)), 'promotion': bool(re.search(PROMOTION, low))}


# --------------------------------------------------------------------------- audience (counts and themes, no names)

THEMES = {
    'contratar_equipo': ('Contratar: equipo propio, agencia o freelance',
                         r'\b(?:hire|hiring|in-house|agenc(?:y|ies)|outsourc\w*|freelanc\w*|nearshore|offshore|contratar|equipo interno)\b'),
    'costo': ('Costo y presupuesto', r'\b(?:cost\w*|price\w*|pricing|budget\w*|expensive|cheap|rates?|costo\w*|precio\w*|presupuesto\w*)\b'),
    'plazos': ('Plazos y entrega', r'\b(?:deadlines?|timelines?|launch\w*|delays?|weeks|months|plazos?|entrega\w*|lanzamiento)\b'),
    'mvp_alcance': ('MVP y alcance', r'\b(?:mvps?|scope|features?|prototypes?|v1|alcance|prototipo\w*|funcionalidad\w*)\b'),
    'ia_en_producto': ('IA dentro del producto', r'\b(?:ai|llms?|gpt\w*|agents?|agentic|models?|ia|agentes?|modelos?)\b'),
    'calidad_deuda': ('Calidad y deuda técnica', r'\b(?:quality|bugs?|tech debt|refactor\w*|testing|tests|calidad|deuda técnica)\b'),
    'arquitectura_escala': ('Arquitectura y escala', r'\b(?:architecture|scal\w+|infra\w*|cloud|microservices?|arquitectura|escalar)\b'),
    'liderazgo_tecnico': ('Liderazgo técnico y CTO', r'\b(?:cto|tech lead|leadership|technical co-?founder|liderazgo|cofundador técnico)\b'),
    'financiacion': ('Financiación y rondas', r'\b(?:funding|raise|raising|seed|investors?|vcs?|rounds?|ronda\w*|inversion\w*|inversionistas?)\b'),
    'validacion': ('Validar con usuarios', r'\b(?:customers?|users?|feedback|validat\w*|product-market|pmf|clientes?|usuarios?|validar)\b'),
}
APPLAUSE = re.compile(r"^(?:great|congrats|congratulations|love (?:this|it)|well said|so true|amazing|awesome|thanks for "
                      r"sharing|spot on|100%|agreed?|nice|felicidades|felicitaciones|excelente|gracias por compartir|"
                      r"totalmente|genial)\b", re.I)
OBJECTION = re.compile(r"\b(?:disagree|not sure|push back|however|but|depends|counterpoint|no estoy de acuerdo|depende|"
                       r"sin embargo|pero)\b", re.I)


def comment_summary(comments, author_id=''):
    """What a page of comments was like, as counts and theme tags of a fixed taxonomy: no names, ids or sentences."""
    rows = [c for c in comments or [] if not c.get('is_sender')]
    others = [c for c in rows if (c.get('author') or {}).get('id') != author_id]
    themes, asked, objected = Counter(), Counter(), Counter()
    out = {'rule': AUDIENCE_RULE, 'read': len(others), 'substantive': 0, 'questions': 0, 'applause': 0, 'objections': 0,
           'author_replies': len(rows) - len(others)}
    for comment in others:
        text = ' '.join((comment.get('text') or '').split())
        found = [key for key, (_, rx) in THEMES.items() if re.search(rx, text, re.I)]
        themes.update(found)
        if len(text) >= 80:
            out['substantive'] += 1
        if '?' in text:
            out['questions'] += 1
            asked.update(found)
        if len(text) < 60 and (APPLAUSE.search(text) or not re.search(r'[a-záéíóúñ]', text, re.I)):
            out['applause'] += 1
        elif OBJECTION.search(text):
            out['objections'] += 1
            objected.update(found)
    return dict(out, themes=dict(themes), question_themes=dict(asked), objection_themes=dict(objected))


def store_audience(post, comments, now=None, source='red.discover'):
    """Hooked where a step already read a post's comments: keeps the summary, never the comments."""
    if comments is None or not post.referent_id:
        return
    post.audience = dict(comment_summary(comments, post.author_provider_id), read_at=(now or timezone.now()).isoformat(),
                         source=source)
    post.save(update_fields=['audience'])


def overlap(account, provider_ids, min_classified=None):
    """How many of these people (commenters) are Gustavo's neighborhood, from contacts the classifier already judged.
    Commenters nobody classified are unknown, never «not neighborhood»: the share is None below `min_classified`."""
    min_classified = thresholds()['min_classified'] if min_classified is None else min_classified
    ids = {i for i in provider_ids if i}
    contacts = list(Contact.objects.filter(account=account, provider_user_id__in=ids).exclude(classification={})
                    .values('classification', 'location')) if ids else []
    fit = [c for c in contacts if c['classification'].get('fit') is True]
    return {'commenters': len(ids), 'classified': len(contacts), 'fit': len(fit),
            'us': sum(ubicacion.region(c['location']) == 'us' for c in fit),
            'roles': dict(Counter(c['classification'].get('role') for c in fit if c['classification'].get('role'))),
            'fit_share': round(len(fit) / len(contacts), 3) if contacts and len(contacts) >= min_classified else None}


def barrio(post, min_classified=None):
    """Overlap of a referent post's commenters, as the evidence layer recorded them (evidencia.referent_comments)."""
    ids = PersonEvidence.objects.filter(person__account=post.account, kind='referent_comment',
                                        post_id=post.provider_post_id).values_list('person__provider_user_id', flat=True)
    return overlap(post.account, set(ids), min_classified)


def after_observe(account, connector, referent_ids, now=None):
    """operador.observe, after storing posts: recompute outliers, then read the comments of up to MODELOS_LECTURAS_DIA
    new outliers of industry referents whose audience nobody read yet, the strongest first. Each read also feeds the
    evidence layer (who commented), which is what the neighborhood overlap is computed from."""
    from . import evidencia, operador, red
    from .connectors import ConnectorError
    now = now or timezone.now()
    t = thresholds()
    flagged = refresh(account, referent_ids, now)
    summary = {'outliers': len(flagged), 'audience_read': 0, 'stopped': ''}
    day, _ = operador.period_starts(now)
    room = t['reads_per_day'] - AuditEvent.objects.filter(action=READ_EVENT, target=str(account.id), created_at__gte=day).count()
    pending = sorted((p for p in flagged if p.referent.kind == 'industria' and p.referent.active and not p.audience),
                     key=lambda p: -(p.outlier.get('score') or 0))
    for post in pending[:max(0, room)]:
        try:
            red._read(account, 'comments')
            comments = connector.list_comments(post.provider_post_id, limit=50)
        except red.ReadCapReached as exc:
            summary['stopped'] = str(exc)
            break
        except ConnectorError as exc:
            red._pause_on(account, exc)
            summary['stopped'] = str(exc)
            break
        operador._audit(None, READ_EVENT, account.id, post=str(post.pk))
        evidencia.referent_comments(post, comments, now)
        store_audience(post, comments, now, source='modelos')
        summary['audience_read'] += 1
    return summary


def read_limit(referent, limit):
    """An industry referent with fewer stored posts than a sample reads 20 at once (still one read) to have a norm."""
    if referent.kind != 'industria' or limit >= 20:
        return limit
    stored = ObservedPost.objects.filter(referent=referent, is_repost=False).count()
    return 20 if stored <= thresholds()['min_sample'] else limit


# --------------------------------------------------------------------------- what the weekly strategy reads

def _pct(part, whole):
    return round(100 * part / whole) if whole else None


def _ranked(counts, limit):
    return [{'theme': key, 'label': THEMES[key][0], 'count': n}
            for key, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])) if key in THEMES][:limit]


def _prefilter(post_ids):
    from .autopiloto import PREFILTER_ACTION
    rows = AuditEvent.objects.filter(action=PREFILTER_ACTION, target__in=[str(i) for i in post_ids]).order_by('created_at')
    return {row.target: row.metadata for row in rows}


def fit_as_model(shape, verdict=None):
    """(apt, reasons): a job ad or a promotion that went viral is not a model of how to grow. apt None = not judged."""
    reasons = [label for flag, label in ((shape.get('hiring'), 'anuncio de vacantes'), (shape.get('promotion'), 'promoción'))
               if flag]
    if verdict and verdict.get('decision') == 'skip':
        reasons += list(verdict.get('reasons') or ['el prefiltro del líder lo descartó'])
    if reasons:
        return False, reasons
    return (True, []) if verdict and verdict.get('decision') == 'comment' else (None, [])


def growth_models(account=None, *, limit=8, now=None, kinds=('industria',), days=None):
    """Recent outliers of referents of `kinds`, best model first, for the weekly strategy (GASP). No text of the post:
    its link (to look at it), how it did against its author's norm, its shape and its audience.

    Returns [{post_id, provider_post_id, url, posted_at, referent: {id, name, kind, tier},
              performance: {score, reactions, comments, median, lift, z, sample, mature},
              structure: {language, length, hook, form, outline, closing, angle, pillar, …},
              audience: {measured, comments_read, comments_per_100_reactions, substantive_pct, questions_pct,
                         applause_pct, objections_pct, themes, questions, objections,
                         barrio: {commenters, classified, fit, us, roles, fit_share}},
              fit_as_model: {apt, reasons}, relevance, rule, use}]
    relevance = lift x audience weight; the weight is 0.5 + the neighborhood share of its classified commenters
    (0.5 to 1.5) or 1 when unknown, so a post that reached Gustavo's audience beats a bigger one that did not."""
    now = now or timezone.now()
    t = thresholds()
    rows = (ObservedPost.objects.select_related('referent', 'account')
            .filter(referent__isnull=False, referent__kind__in=list(kinds), is_repost=False, outlier__flag=True,
                    posted_at__gte=now - timedelta(days=days or t['recent_days'])))
    if account is not None:
        rows = rows.filter(account=account)
    rows = list(rows)
    verdicts = _prefilter(p.pk for p in rows)
    out = []
    for post in rows:
        perf, heard = post.outlier, post.audience or {}
        apt, why = fit_as_model(post.structure, verdicts.get(str(post.pk)))
        if apt is False:
            continue
        crowd = barrio(post, t['min_classified'])
        weight = 0.5 + crowd['fit_share'] if crowd['fit_share'] is not None else 1.0
        lift = perf.get('lift') or round((perf.get('score') or 0) / max(1, t['min_interactions']), 2)
        read = heard.get('read', 0)
        reactions, comments = perf.get('reactions'), perf.get('comments')
        out.append({
            'post_id': str(post.pk), 'provider_post_id': post.provider_post_id, 'url': post.share_url,
            'posted_at': post.posted_at.isoformat(),
            'referent': {'id': str(post.referent_id), 'name': post.referent.display_name, 'kind': post.referent.kind,
                         'tier': 'main' if post.referent.protected else 'variable'},
            'performance': {k: perf.get(k) for k in ('score', 'reactions', 'comments', 'median', 'lift', 'z', 'sample', 'mature')},
            'structure': {k: v for k, v in post.structure.items() if k != 'rule'},
            'audience': {'measured': bool(heard), 'comments_read': read,
                         'comments_per_100_reactions': round(100 * comments / reactions, 1) if reactions and comments is not None else None,
                         **{f'{k}_pct': _pct(heard.get(k, 0), read) for k in ('substantive', 'questions', 'applause', 'objections')},
                         'themes': _ranked(heard.get('themes', {}), 5), 'questions': _ranked(heard.get('question_themes', {}), 3),
                         'objections': _ranked(heard.get('objection_themes', {}), 3), 'barrio': crowd},
            'fit_as_model': {'apt': apt, 'reasons': why}, 'relevance': round(min(lift, 20) * weight, 2),
            'rule': (f"{RULE}: ≥{t['min_lift']:g}x su mediana, z robusto ≥{t['min_z']:g}, ≥{t['min_interactions']} "
                     f"interacciones, ≥{t['min_sample']} posts propios de base"),
            'use': USE})
    out.sort(key=lambda m: (m['relevance'], m['posted_at']), reverse=True)
    return out[:limit]


def audience_questions(account=None, *, days=60, kinds=('industria',), limit=10, top_only=True, now=None):
    """What the audience of these referents asks and objects to, by theme: the content of future posts should answer
    it. Counts over the comments already summarized; no sentence of anyone. `top_only`: only posts that worked.

    Returns [{theme, label, kind: 'pregunta'|'objecion', count, posts, referents}], most frequent first.
    Themes come from a fixed keyword taxonomy (THEMES). Grouping free-form questions with a model is not enabled: it
    would be one cheap model call per post read (≈ USD 0.0005 with Haiku) and needs Gustavo's go-ahead."""
    now = now or timezone.now()
    rows = (ObservedPost.objects.filter(referent__isnull=False, referent__kind__in=list(kinds), is_repost=False,
                                        posted_at__gte=now - timedelta(days=days)).exclude(audience={}))
    if account is not None:
        rows = rows.filter(account=account)
    if top_only:
        rows = rows.filter(outlier__flag=True)
    acc = {}
    for post in rows.only('id', 'referent_id', 'audience'):
        for kind, field in (('pregunta', 'question_themes'), ('objecion', 'objection_themes')):
            for theme, n in (post.audience.get(field) or {}).items():
                if theme not in THEMES:
                    continue
                row = acc.setdefault((theme, kind), {'theme': theme, 'label': THEMES[theme][0], 'kind': kind, 'count': 0,
                                                     'posts': set(), 'referents': set()})
                row['count'] += n
                row['posts'].add(post.pk)
                row['referents'].add(post.referent_id)
    out = [dict(row, posts=len(row['posts']), referents=len(row['referents'])) for row in acc.values()]
    out.sort(key=lambda r: (-r['count'], -r['posts'], r['theme'], r['kind']))
    return out[:limit]
