"""«Qué les funciona y qué no» (docs/plan-referentes-industria.md, Gustavo 17/11/2026): the posts of the industry
referents taken apart (topic, visual resource, hook, body, closing, length), each one compared with its own author's
usual post on every counter LinkedIn shows, and what repeats across posts, authors and weeks told apart from what is
only news this week.

«Analizar sus posts, qué les funciona y qué no, cómo lo hacen, qué estructura usan; descomponer sus temas y su
estructura»: the structure and the angle are copied, never the text. So everything here is a label of a fixed
vocabulary or a number; the only words that come from a post are names shared by several referents in the same week
(a product, a company, an event) when they make a current topic, and the link to each post, to look at it.

No paid call and no LinkedIn read: it works on what operador.observe already stored (its reading window and caps), with
fixed rules, so it costs USD 0. What a model would add (the kind of image, free-form topics) is listed in `limites`.

Two signals for the editorial, apart (estrategia.audience_signals, only with REFERENTES_ANALISIS on):
- `estructura_sostenida`: structures (hook · body format · closing) that did clearly better than their authors'
  norm in several posts, authors and weeks, leaving out posts driven by news; below the minimums they are hypotheses.
- `tema_en_tendencia`: what several referents are talking about right now, with the date it expires."""
from collections import Counter, defaultdict
from datetime import timedelta
import hashlib
import os
import re
import statistics

from django.utils import timezone

from . import modelos_crecimiento as mc
from .models import ObservedPost

RULE = 'analisis-v1'
USE = ('Reutilizar la estructura (gancho, formato del cuerpo, cierre) con material propio de Gustavo; nunca frases, '
       'cifras, historias ni ejemplos del referente.')


def enabled():
    """The editorial signals. Off (default): the editorial reads exactly what it read before."""
    return os.environ.get('REFERENTES_ANALISIS', 'false').strip().lower() in ('1', 'true', 'yes', 'si', 'sí', 'on')


def thresholds():
    """«Funcionó» is the growth models' rule (modelos_crecimiento.judge: ≥2x the author's median, robust z ≥3, ≥20
    interactions, ≥6 other posts of his as base). «No funcionó»: at most half his median, same base. A structure is
    «sostenida» with ≥3 posts that worked, from ≥2 authors, in ≥2 different weeks, not counting posts driven by news;
    a topic is «en tendencia» for 14 days after the last post of ≥2 referents about it."""
    t = mc.thresholds()
    return {'min_sample': t['min_sample'], 'min_lift': t['min_lift'], 'min_z': t['min_z'], 'min_interactions': t['min_interactions'],
            'base_days': t['base_days'], 'mature_hours': t['mature_hours'],
            'low': mc._number('REFERENTES_ANALISIS_VECES_BAJO', 0.5, float),
            'durable_posts': mc._number('REFERENTES_ANALISIS_MIN_POSTS', 3),
            'durable_authors': mc._number('REFERENTES_ANALISIS_MIN_AUTORES', 2),
            'durable_weeks': mc._number('REFERENTES_ANALISIS_MIN_SEMANAS', 2),
            'trend_days': mc._number('REFERENTES_ANALISIS_DIAS_TENDENCIA', 14),
            'trend_authors': mc._number('REFERENTES_ANALISIS_AUTORES_TENDENCIA', 2)}


# --------------------------------------------------------------------------- one post, taken apart (labels only)

# The topic taxonomy is the audience one (modelos_crecimiento.THEMES), each topic under one of Gustavo's pillars.
PILLAR_OF = {'contratar_equipo': 'business_to_product', 'costo': 'business_to_product', 'mvp_alcance': 'business_to_product',
             'financiacion': 'business_to_product', 'validacion': 'business_to_product', 'ia_en_producto': 'applied_ai',
             'plazos': 'architecture_delivery', 'calidad_deuda': 'architecture_delivery',
             'arquitectura_escala': 'architecture_delivery', 'liderazgo_tecnico': 'architecture_delivery'}
TOPICS = {**{key: label for key, (label, _) in mc.THEMES.items()}, 'otro': 'Otro tema'}
FORMATS = {'lista': 'Lista', 'historia': 'Historia', 'opinion_contraria': 'Opinión contraria', 'caso': 'Caso de cliente',
           'tutorial': 'Tutorial', 'datos': 'Datos', 'pregunta_abierta': 'Pregunta abierta', 'opinion': 'Opinión'}
HOOKS = {'pregunta': 'Pregunta', 'lista_anunciada': 'Lista anunciada', 'historia': 'Historia', 'cifra': 'Cifra',
         'contraste': 'Contraste', 'primera_persona': 'Primera persona', 'afirmacion': 'Afirmación', 'sin_texto': 'Sin texto'}
CLOSINGS = {'pregunta': 'Pregunta', 'llamado': 'Llamado a la acción', 'enlace': 'Enlace', 'resumen': 'Resumen',
            'afirmacion': 'Afirmación', 'sin_texto': 'Sin texto'}
MEDIA = {'imagen': 'Imagen', 'imagenes': 'Varias imágenes', 'video': 'Video', 'documento': 'Documento (carrusel PDF)',
         'carrusel': 'Carrusel', 'encuesta': 'Encuesta', 'enlace': 'Enlace', 'evento': 'Evento', 'otro': 'Otro',
         'desconocido': 'No se sabe'}

NEWS = re.compile(r"\b(?:just (?:announced|launched|released|dropped)|announc(?:ed|es|ement)|launch(?:ed|es)|releas(?:ed|es)|"
                  r"breaking|acquir(?:ed|es)|acquisition|keynote|anunci(?:ó|o|a|aron)|lanz(?:ó|aron)|noticia\w*|adquiri\w+)\b", re.I)
WHEN = re.compile(r"\b(?:jan(?:uary)?|feb(?:ruary)?|march|april|june|july|aug(?:ust)?|sept?(?:ember)?|oct(?:ober)?|"
                  r"nov(?:ember)?|dec(?:ember)?|enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|"
                  r"diciembre)\s+\d{1,2}\b|\b\d{1,2}\s+de\s+(?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|"
                  r"noviembre|diciembre)\b|\b(?:this|last) week'?s?\b|\besta semana\b|\bQ[1-4]\s?20\d\d\b", re.I)
RELEASE = re.compile(r"\b(?:gpt-?\d[\w.]*|o\d-(?:mini|pro)|claude(?: \w+)? \d[\w.]*|gemini \d[\w.]*|llama ?\d[\w.]*|"
                     r"devday|wwdc|google i/o|re:invent|ces 20\d\d)\b", re.I)
# Capitalized names inside a sentence (the first word of a line or sentence is skipped), names with digits (GPT-5),
# at most three words. Common capitalized words are not names.
NAME = re.compile(r"(?<![\w@#])[A-Z][\w.+-]*\d[\w.+-]*|(?<![\w@#])[A-Z][a-zA-Z0-9+&.-]+(?:\s[A-Z][a-zA-Z0-9+&.-]+){0,2}")
NOT_NAMES = frozenset((
    'i im ive ill id ai ia ceo cto cfo coo cmo vp svp evp mvp mvps saas b2b b2c us usa eeuu uk eu latam linkedin founder founders '
    'startup startups the this that these those we our my you your if and but so or here what why how when where who most '
    'every no not yes ps tl dr dm api apis llm llms ux ui qa roi kpi okr pm seo crm erp sql html css js it its hr pr '
    'monday tuesday wednesday thursday friday saturday sunday lunes martes miércoles jueves viernes sábado domingo '
    'el la los las un una yo nosotros mi mis tu sus y pero si no').split())


def _names(text):
    """Names a referent mentions, lowercased. A Title Case line («Stop Building Features Nobody Wants») is a phrase,
    not names: its capitals say nothing, so it is skipped."""
    out = []
    for line in (text or '').splitlines():
        for sentence in re.split(r'(?<=[.!?:])\s+', mc.LIST_ITEM.sub('', line.strip(), count=1)):
            words = re.findall(r"[^\W\d_][\w'’-]*", sentence)
            if len(words) >= 3 and sum(w[0].isupper() for w in words) >= 0.8 * len(words):
                continue
            first = re.search(r'\w', sentence)
            for match in NAME.finditer(sentence):
                name = match.group(0).strip(' .-+&')
                if first and match.start() <= first.start() and not re.search(r'\d', name):
                    continue  # a sentence (or a list item) starts with a capital letter: that is not a name
                if len(name) < 2 or len(name) > 40 or name.lower().replace("'", '') in NOT_NAMES:
                    continue
                out.append(name)
    keys = []
    for name in out:
        key = name.lower()
        if key not in keys:
            keys.append(key)
    return keys[:8]


def topic(text):
    """(topic, every topic it touches): the theme of the fixed taxonomy with most mentions, ties by taxonomy order."""
    low = (text or '').lower()
    hits = {key: len(re.findall(rx, low, re.I)) for key, (_, rx) in mc.THEMES.items()}
    touched = [key for key in mc.THEMES if hits[key]]
    best = max(touched, key=lambda key: hits[key]) if touched else 'otro'
    return best, touched


def body_format(shape):
    form, angle = shape.get('form'), shape.get('angle')
    if form == 'lista':
        return 'lista'
    if form == 'historia' or angle == 'experiencia_propia':
        return 'historia'
    return {'contrario': 'opinion_contraria', 'caso_cliente': 'caso', 'tutorial': 'tutorial', 'datos': 'datos'}.get(
        angle, 'pregunta_abierta' if form == 'pregunta_abierta' else 'opinion')


def _key(post):
    return hashlib.sha256(f'{RULE}\n{post.media}\n{post.text}'.encode()).hexdigest()[:16]


def decompose(post):
    """The post's parts as labels and numbers, from its text and the media the connector saw. Pure: no write."""
    shape = (post.structure if (post.structure or {}).get('rule') == mc.STRUCTURE_RULE else mc.structure(post.text))
    main, touched = topic(post.text)
    hook, closing, fmt = shape['hook']['type'], shape['closing'], body_format(shape)
    signals = [label for label, rx in (('menciona_noticia', NEWS), ('menciona_fecha', WHEN), ('menciona_lanzamiento', RELEASE))
               if rx.search(post.text or '')]
    return {'rule': RULE, 'key': _key(post), 'tema': main, 'temas': touched, 'pilar': PILLAR_OF.get(main, 'otro'),
            'partes': {'recurso_visual': {'tipo': post.media or 'desconocido', 'detalle': 'no_disponible'},
                       'gancho': {'tipo': hook, 'palabras': shape['hook']['words'], 'linea_propia': shape['hook']['own_line']},
                       'cuerpo': {'tema': main, 'formato': fmt, 'angulo': shape['angle'], 'esquema': shape['outline'],
                                  'items_lista': shape['list_items']},
                       'cierre': {'tipo': closing, 'cta': closing in ('llamado', 'pregunta', 'enlace')},
                       'longitud': {'banda': shape['length'], 'palabras': shape['words'], 'lineas': shape['lines'],
                                    'lineas_cortas_pct': shape['short_lines_pct']}},
            'firma': f'{hook}·{fmt}·{closing}', 'senales_coyuntura': signals, 'nombres': _names(post.text),
            'apto': not (shape.get('hiring') or shape.get('promotion'))}


def cached(posts):
    """Each post's decomposition, computed once per text and media and kept in ObservedPost.analysis."""
    stale = []
    for post in posts:
        if (post.analysis or {}).get('key') != _key(post):
            post.analysis = decompose(post)
            stale.append(post)
    if stale:
        ObservedPost.objects.bulk_update(stale, ['analysis'])
    return {post.pk: post.analysis for post in posts}


# --------------------------------------------------------------------------- against its own author

METRICS = (('reacciones', 'reactions_count'), ('comentarios', 'comments_count'), ('compartidos', 'reposts_count'))


def _metric(value, base, t):
    base = [v for v in base if v is not None]
    median = statistics.median(base) if len(base) >= t['min_sample'] else None
    return {'valor': value, 'mediana_autor': median, 'veces': round(value / median, 2) if value is not None and median else None,
            'muestra': len(base)}


def performance(post, others, t, now):
    """The post against its author's OTHER mature original posts of the base window (leave-one-out median), counter by
    counter: value, author's median, multiple. The verdict is on interactions (reactions + comments), the growth models'
    rule. Views are not there: LinkedIn shows impressions only of one's own posts."""
    mature = post.posted_at <= now - timedelta(hours=t['mature_hours'])
    out = {name: _metric(getattr(post, field), [getattr(o, field) for o in others], t) for name, field in METRICS}
    value = mc.score(post.reactions_count, post.comments_count)
    base = [s for s in (mc.score(o.reactions_count, o.comments_count) for o in others) if s is not None]
    out['interacciones'] = _metric(value, base, t)
    judged = mc.judge(value, base, t, mature=mature)
    lift = judged.get('lift')
    if value is None:
        verdict, reason = 'sin_juicio', 'sin_contadores'
    elif len(base) < t['min_sample']:
        verdict, reason = 'sin_juicio', 'muestra_insuficiente'
    elif not mature:
        verdict, reason = 'sin_juicio', 'aun_madurando'
    elif judged['flag']:
        verdict, reason = 'funciono', 'muy_por_encima'
    elif lift is not None and lift <= t['low']:
        verdict, reason = 'no_funciono', 'muy_por_debajo'
    else:
        verdict, reason = 'normal', judged['reason']
    out.update(veredicto=verdict, motivo=reason, z=judged.get('z'))
    return out


# --------------------------------------------------------------------------- the report

def _week(moment):
    year, week, _ = moment.isocalendar()
    return f'{year}-W{week:02d}'


def _median(values):
    values = [v for v in values if v is not None]
    return round(statistics.median(values), 2) if values else None


def _group(rows, key, t):
    """Rows grouped by a part: posts, how many worked or not, the median multiple of their authors' norm."""
    acc = defaultdict(list)
    for row in rows:
        acc[key(row)].append(row)
    out = []
    for value, items in acc.items():
        judged = [r for r in items if r['veredicto'] in ('funciono', 'normal', 'no_funciono')]
        out.append({'valor': value, 'posts': len(items), 'con_juicio': len(judged),
                    'funciono': sum(r['veredicto'] == 'funciono' for r in items),
                    'no_funciono': sum(r['veredicto'] == 'no_funciono' for r in items),
                    'veces_mediana': _median(r['interacciones']['veces'] for r in judged),
                    'muestra_pequena': len(judged) < t['durable_posts']})
    out.sort(key=lambda g: (-(g['veces_mediana'] or 0), -g['posts'], str(g['valor'])))
    return out


def _parts(rows, t):
    return {'tema': _group(rows, lambda r: r['analisis']['tema'], t),
            'recurso_visual': _group(rows, lambda r: r['analisis']['partes']['recurso_visual']['tipo'], t),
            'gancho': _group(rows, lambda r: r['analisis']['partes']['gancho']['tipo'], t),
            'formato': _group(rows, lambda r: r['analisis']['partes']['cuerpo']['formato'], t),
            'cierre': _group(rows, lambda r: r['analisis']['partes']['cierre']['tipo'], t),
            'longitud': _group(rows, lambda r: r['analisis']['partes']['longitud']['banda'], t)}


def _shared_names(rows, t):
    """{(week, name): referents} for names used by ≥ trend_authors referents in the same ISO week."""
    acc = defaultdict(set)
    for row in rows:
        for name in row['analisis']['nombres']:
            acc[(row['semana'], name)].add(row['referent_id'])
    return {k: v for k, v in acc.items() if len(v) >= t['trend_authors']}


def _topical(row, shared):
    signals = list(row['analisis']['senales_coyuntura'])
    others = max((len(shared[(row['semana'], n)]) for n in row['analisis']['nombres'] if (row['semana'], n) in shared), default=0)
    if others:
        signals.append('varios_referentes_misma_semana')
    return {'flag': bool(signals), 'senales': signals, 'referentes_misma_semana': others or None}


def _structures(rows, t):
    """Durable structures: the signatures of posts that worked WITHOUT news behind them, with their spread."""
    acc = defaultdict(list)
    for row in rows:
        acc[row['analisis']['firma']].append(row)
    durable, below = [], []
    for signature, items in acc.items():
        judged = [r for r in items if r['veredicto'] in ('funciono', 'normal', 'no_funciono')]
        won = [r for r in items if r['veredicto'] == 'funciono' and not r['coyuntura']['flag'] and r['analisis']['apto']]
        hook, fmt, closing = signature.split('·')
        base = {'id': f'estructura:{signature}', 'firma': signature, 'gancho': hook, 'formato': fmt, 'cierre': closing,
                'etiqueta': f"{HOOKS.get(hook, hook)} · {FORMATS.get(fmt, fmt)} · {CLOSINGS.get(closing, closing)}",
                'posts': len(items), 'con_juicio': len(judged), 'veces_mediana': _median(r['interacciones']['veces'] for r in judged)}
        if won:
            spread = {'posts_que_funcionaron': len(won), 'autores': len({r['referent_id'] for r in won}),
                      'semanas': len({r['semana'] for r in won})}
            missing = [f'{need} {label}' for need, have, label in (
                (t['durable_posts'], spread['posts_que_funcionaron'], 'posts que funcionaron'),
                (t['durable_authors'], spread['autores'], 'autores'), (t['durable_weeks'], spread['semanas'], 'semanas'))
                if have < need]
            durable.append(dict(base, **spread, estado='hipotesis' if missing else 'sostenida',
                                faltan=[f'faltan: al menos {m}' for m in missing]))
        elif len(judged) >= 2 and sum(r['veredicto'] == 'no_funciono' for r in judged) * 2 >= len(judged):
            below.append(dict(base, no_funciono=sum(r['veredicto'] == 'no_funciono' for r in judged),
                              muestra_pequena=len(judged) < t['durable_posts']))
    durable.sort(key=lambda s: (s['estado'] != 'sostenida', -s['posts_que_funcionaron'], -s['autores'], -(s['veces_mediana'] or 0)))
    below.sort(key=lambda s: (s['veces_mediana'] or 0, -s['posts']))
    return durable, below


def _trends(rows, shared, now, t):
    """Current topics: a name several referents used in the same week, and the topic of a post driven by news that
    worked, in the last `trend_days`: each one expires `trend_days` after its last post."""
    since = now - timedelta(days=t['trend_days'])
    acc = {}
    for row in rows:
        if row['post'].posted_at < since:
            continue
        keys = [('nombre', n) for n in row['analisis']['nombres'] if (row['semana'], n) in shared]
        if row['veredicto'] == 'funciono' and row['coyuntura']['flag']:
            keys.append(('tema', row['analisis']['tema']))
        for kind, value in keys:
            item = acc.setdefault((kind, value), {'kind': kind, 'value': value, 'posts': set(), 'authors': set(), 'won': 0,
                                                  'last': row['post'].posted_at})
            item['posts'].add(row['post'].pk)
            item['authors'].add(row['referent_id'])
            item['won'] += row['veredicto'] == 'funciono'
            item['last'] = max(item['last'], row['post'].posted_at)
    out = []
    for item in acc.values():
        expires = item['last'] + timedelta(days=t['trend_days'])  # > now: only posts of the last trend_days count
        label = item['value'] if item['kind'] == 'nombre' else TOPICS.get(item['value'], item['value'])
        out.append({'id': f"tendencia:{item['kind']}:{item['value']}", 'tema': label, 'tipo': item['kind'],
                    'por': 'varios_referentes_misma_semana' if item['kind'] == 'nombre' else 'coyuntura_que_funciono',
                    'posts': len(item['posts']), 'autores': len(item['authors']), 'funcionaron': item['won'],
                    'ultimo_post': item['last'].isoformat(), 'expira': expires.isoformat()})
    out.sort(key=lambda r: (-r['autores'], -r['posts'], r['expira']))
    return out


def report(account=None, *, now=None, kinds=('industria',), days=None, top=12):
    """Everything the endpoint shows. Returns {activo, umbrales, muestra, referentes, destacados, por_parte,
    estructuras_sostenidas, estructuras_por_debajo, temas_en_tendencia, limites}. Labels and numbers, plus each post's
    link; no sentence of any post."""
    now = now or timezone.now()
    t = thresholds()
    window = days or t['base_days']
    rows = (ObservedPost.objects.select_related('referent')
            .filter(referent__isnull=False, referent__kind__in=list(kinds), is_repost=False, posted_at__isnull=False,
                    posted_at__gte=now - timedelta(days=window)).exclude(text=''))
    if account is not None:
        rows = rows.filter(account=account)
    posts = list(rows.order_by('posted_at'))
    analyses = cached(posts)
    settled = now - timedelta(hours=t['mature_hours'])
    by_author = defaultdict(list)
    for post in posts:
        by_author[post.referent_id].append(post)
    table = []
    for post in posts:
        others = [o for o in by_author[post.referent_id] if o.pk != post.pk and o.posted_at <= settled]
        perf = performance(post, others, t, now)
        table.append({'post': post, 'referent_id': post.referent_id, 'semana': _week(post.posted_at),
                      'analisis': analyses[post.pk], 'veredicto': perf['veredicto'], 'interacciones': perf['interacciones'],
                      'rendimiento': perf})
    shared = _shared_names(table, t)
    for row in table:
        row['coyuntura'] = _topical(row, shared)
    durable, below = _structures(table, t)
    referents = []
    for referent_id, items in by_author.items():
        mine = [r for r in table if r['referent_id'] == referent_id]
        ref = items[0].referent
        verdicts = Counter(r['veredicto'] for r in mine)
        referents.append({'id': str(referent_id), 'nombre': ref.display_name, 'tipo': ref.kind,
                          'posts': len(mine), **{k: verdicts.get(k, 0) for k in ('funciono', 'normal', 'no_funciono', 'sin_juicio')},
                          'mediana_interacciones': _median(mc.score(p.reactions_count, p.comments_count) for p in items
                                                           if p.posted_at <= settled),
                          'muestra_pequena': len([r for r in mine if r['veredicto'] != 'sin_juicio']) < t['min_sample'],
                          'temas': _group(mine, lambda r: r['analisis']['tema'], t),
                          'estructuras': _group(mine, lambda r: r['analisis']['firma'], t)})
    referents.sort(key=lambda r: (-r['funciono'], r['nombre']))
    standouts = [r for r in table if r['veredicto'] in ('funciono', 'no_funciono')]
    standouts.sort(key=lambda r: (r['veredicto'] != 'funciono', -(r['interacciones']['veces'] or 0)))
    return {
        'activo': enabled(), 'regla': RULE,
        'umbrales': {'base': (f"mediana de los otros posts originales del mismo autor con ≥{t['mature_hours']} h, de los "
                              f"últimos {t['base_days']} días; sin contar el post juzgado"),
                     'funciono': (f"≥{t['min_lift']:g}x su mediana de interacciones, z robusto ≥{t['min_z']:g} y "
                                  f"≥{t['min_interactions']} interacciones"),
                     'no_funciono': f"≤{t['low']:g}x su mediana de interacciones",
                     'min_posts_base': t['min_sample'],
                     'sostenida': (f"≥{t['durable_posts']} posts que funcionaron sin coyuntura, de ≥{t['durable_authors']} "
                                   f"autores, en ≥{t['durable_weeks']} semanas; si no, hipótesis"),
                     'tendencia': (f"un nombre en posts de ≥{t['trend_authors']} referentes la misma semana, o el tema de "
                                   f"un post de coyuntura que funcionó; caduca {t['trend_days']} días después del último post")},
        'muestra': {'posts': len(table), 'referentes': len(by_author), 'dias': window,
                    'desde': posts[0].posted_at.isoformat() if posts else None,
                    'hasta': posts[-1].posted_at.isoformat() if posts else None},
        'referentes': referents,
        'destacados': [{'post_id': str(r['post'].pk), 'url': r['post'].share_url, 'publicado': r['post'].posted_at.isoformat(),
                        'referente': {'id': str(r['referent_id']), 'nombre': r['post'].referent.display_name},
                        'veredicto': r['veredicto'], 'metricas': {k: r['rendimiento'][k] for k in ('interacciones', 'reacciones',
                                                                                                    'comentarios', 'compartidos')},
                        'partes': r['analisis']['partes'], 'firma': r['analisis']['firma'], 'pilar': r['analisis']['pilar'],
                        'coyuntura': r['coyuntura'], 'apto_como_modelo': r['analisis']['apto']} for r in standouts[:top]],
        'por_parte': _parts(table, t),
        'estructuras_sostenidas': durable,
        'estructuras_por_debajo': below,
        'temas_en_tendencia': _trends(table, shared, now, t),
        'limites': ['Recurso visual: el tipo (imagen, video, documento…) solo cuando el conector lo reconoce; si es foto, '
                    'gráfico, captura o infografía exigiría leer la imagen (no se hace).',
                    'Vistas: LinkedIn no muestra impresiones de posts ajenos.',
                    'Compartidos: solo de posts observados desde que se guardan (antes, sin dato).',
                    'Reglas fijas sin modelo de IA (USD 0): temas de una taxonomía fija; la coyuntura se detecta por palabras '
                    'de noticia, fechas, lanzamientos y nombres compartidos entre referentes.'],
    }


def editorial_signals(now=None, account=None):
    """The two signals for the editorial: structures to reuse (durable first, hypotheses marked) and topics of right now
    with their expiry. Labels, counts and dates; no text of any referent."""
    data = report(account, now=now)
    keep = ('id', 'estado', 'etiqueta', 'gancho', 'formato', 'cierre', 'posts_que_funcionaron', 'autores', 'semanas', 'veces_mediana')
    structures = [dict({k: s[k] for k in keep}, uso=USE) for s in data['estructuras_sostenidas'][:5]]
    trends = [{k: r[k] for k in ('id', 'tema', 'autores', 'posts', 'expira')} |
              {'uso': 'Tema de coyuntura: solo si Gustavo tiene algo propio que decir antes de que caduque.'}
              for r in data['temas_en_tendencia'][:5]]
    return structures, trends
