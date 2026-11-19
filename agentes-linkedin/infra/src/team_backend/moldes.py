"""«Del post viral al post propio: el molde» (docs/plan-referentes-industria.md, decisions of Gustavo 18/11/2026).

A mold is the shape of a referent post that did far better than its author's usual post, as labels of a fixed
vocabulary and numbers: hook type, body format and outline, closing, length range and angle, plus where it comes from
(the post's id, its author, its link and how many times its author's median it got). Never a sentence of the post:
every label comes from modelos_crecimiento.structure / analisis_referentes, which keep no span of the text.

- Offer (catalog/offer): each referent's own best original posts of the base window against his own norm, so the
  competitors with small numbers count, not only the Top Voice. A post below the strict thresholds of the growth
  models (atipico-v1, which stays as it is) is offered as a hypothesis that says what it lacks. One author fills at most
  MOLDES_POR_AUTOR places of the offer and MOLDES_MAX_AUTOR_SEMANA days of a week.
- Estado: «sostenida» only when its structure (hook · body format · closing) passes the analysis' minimums (≥3 posts,
  ≥2 authors, ≥2 weeks); otherwise «hipotesis». Molds are usable as hypotheses from now; the estado travels as it is.
- The weekly plan stores a mold in a day when the planner bases it on a referent post or picks one (estrategia._apply);
  the daily brief carries it (estrategia.finalize_brief); copywriter A writes variant A on it with the member's own
  material while variant B stays free, so the selection compares them; the piece records which one won (outcome) and
  the weekly summary compares the posts written on a mold with the ones without one (comparison).

Off (REFERENTES_MOLDE=false, the default) no agent reads anything of this: prompts and requests are the ones of before.
No paid call and no LinkedIn read: it works on what operador.observe already stored."""
from collections import Counter, defaultdict
from datetime import timedelta
import os
import statistics

from django.utils import timezone

from . import analisis_referentes as an
from . import modelos_crecimiento as mc
from .models import ObservedPost

RULE = 'molde-v1'
USE = ('Molde de estructura y ángulo: la variante A sigue el mismo tipo de gancho, el formato del cuerpo y el cierre, '
       'dentro de su rango de longitud, con material propio (sus hechos, sus casos, su criterio). Nunca frases, cifras, '
       'historias, ejemplos ni nombres del post de referencia.')
ANGLES = {'experiencia_propia': 'Experiencia propia', 'caso_cliente': 'Caso de cliente', 'contrario': 'A contracorriente',
          'tutorial': 'Tutorial', 'datos': 'Datos', 'tendencia': 'Tendencia', 'general': 'General'}
# The length band of the referent post (modelos_crecimiento.structure) as a range the writers can meet: their own rule
# is 600–1.800 characters, so a short referent post becomes the shortest post they may write.
LENGTHS = {'corto': (600, 800), 'medio': (600, 1300), 'largo': (1300, 1800)}
WINNERS = {'A': 'molde', 'B': 'libre', 'merge': 'fusion', 'discard': 'descartada'}
LIVE_PIECES = ('preparing', 'ready')


def enabled():
    """REFERENTES_MOLDE: off by default; off, the plan, the director and the writers read exactly what they read before."""
    return os.environ.get('REFERENTES_MOLDE', 'false').strip().lower() in ('1', 'true', 'yes', 'si', 'sí', 'on')


def thresholds():
    """Defaults, why: two posts per author keep one voice from filling the offer while each competitor still brings his
    best two; two days a week per author keep a week varied; 3 other posts are the least that make a norm for a small
    account (the strict rule asks 6); 1.5x his median is «clearly his best» without asking a viral number; 8 molds fit
    a week of seven days with a spare."""
    return {'per_author': mc._number('MOLDES_POR_AUTOR', 2), 'per_week': mc._number('MOLDES_MAX_AUTOR_SEMANA', 2),
            'min_sample': mc._number('MOLDES_MIN_MUESTRA', 3), 'min_lift': mc._number('MOLDES_MIN_VECES_MEDIANA', 1.5, float),
            'offer': mc._number('MOLDES_OFERTA', 8)}


# --------------------------------------------------------------------------- one post, as a mold (labels only)

def _shape(post):
    return post.structure if (post.structure or {}).get('rule') == mc.STRUCTURE_RULE else mc.structure(post.text)


def _parts(post):
    """Its decomposition (analisis_referentes), the stored one when it is current; computed otherwise, never written."""
    stored = post.analysis or {}
    return stored if stored.get('key') == an._key(post) else an.decompose(post)


def _missing(strict, t):
    """What keeps a post below the strict growth-model rule, in words (none for a strict outlier)."""
    words = {'muestra_insuficiente': f"menos de {t['min_sample']} posts propios de base",
             'pocas_interacciones': f"menos de {t['min_interactions']} interacciones",
             'poca_ventaja': f"menos de {t['min_lift']:g}x su mediana", 'no_supera_mediana': 'no supera su mediana',
             'dentro_de_lo_normal': f"z robusto menor que {t['min_z']:g}", 'sin_contadores': 'sin contadores'}
    if strict.get('flag'):
        return []
    return [words.get(strict.get('reason'), strict.get('reason') or 'no es atípico')]


def build(post, perf, sustained=None):
    """The mold of one referent post: labels of a fixed vocabulary and numbers, plus its id, author and link."""
    shape, sustained = _shape(post), sustained or {}
    hook, closing, fmt = shape['hook']['type'], shape['closing'], an.body_format(shape)
    signature = f'{hook}·{fmt}·{closing}'
    low, high = LENGTHS.get(shape['length'], (600, 1800))
    durable = sustained.get(signature)
    return {
        'id': f'molde:{post.pk}', 'regla': RULE, 'estado': 'sostenida' if durable else 'hipotesis', 'firma': signature,
        'etiqueta': f"{an.HOOKS.get(hook, hook)} · {an.FORMATS.get(fmt, fmt)} · {an.CLOSINGS.get(closing, closing)}",
        'gancho': {'tipo': hook, 'etiqueta': an.HOOKS.get(hook, hook), 'palabras': shape['hook']['words'],
                   'linea_propia': shape['hook']['own_line']},
        'cuerpo': {'formato': fmt, 'etiqueta': an.FORMATS.get(fmt, fmt), 'esquema': list(shape['outline']),
                   'items_lista': shape['list_items']},
        'cierre': {'tipo': closing, 'etiqueta': an.CLOSINGS.get(closing, closing)},
        'longitud': {'banda': shape['length'], 'caracteres_min': low, 'caracteres_max': high,
                     'caracteres_referente': shape['chars']},
        'angulo': {'tipo': shape['angle'], 'etiqueta': ANGLES.get(shape['angle'], shape['angle'])},
        'fuente': {'post_id': str(post.pk), 'referente_id': str(post.referent_id),
                   'autor': (post.referent.display_name if post.referent_id else '') or post.author_name,
                   'url': post.share_url, 'publicado': post.posted_at.isoformat() if post.posted_at else None,
                   'veces_mediana': perf.get('lift'), 'interacciones': perf.get('score'),
                   'mediana_autor': perf.get('median'), 'muestra': perf.get('sample')},
        'atipico_estricto': bool(perf.get('strict')), 'faltan': list(perf.get('faltan') or []),
        **({'sostenida': {k: durable[k] for k in ('posts_que_funcionaron', 'autores', 'semanas')}} if durable else {}),
        'uso': USE}


def for_writer(mold):
    """What copywriter A reads: the shape and nothing that names or points at the referent (no author, no link, no id)."""
    return {'estado': mold['estado'],
            'gancho': {k: mold['gancho'][k] for k in ('tipo', 'etiqueta', 'palabras', 'linea_propia')},
            'cuerpo': {k: mold['cuerpo'][k] for k in ('formato', 'etiqueta', 'esquema', 'items_lista')},
            'cierre': dict(mold['cierre']),
            'longitud': {k: mold['longitud'][k] for k in ('banda', 'caracteres_min', 'caracteres_max')},
            'angulo': dict(mold['angulo']), 'uso': USE}


def summary(mold):
    """A mold in one line for the week's view and the plan's record: labels, its estado, the author and the link."""
    source = mold.get('fuente') or {}
    return {'id': mold['id'], 'etiqueta': mold['etiqueta'], 'estado': mold['estado'], 'autor': source.get('autor'),
            'url': source.get('url'), 'veces_mediana': source.get('veces_mediana')}


# --------------------------------------------------------------------------- the catalog (no paid call, no read)

def _author(post):
    return post.author_provider_id or str(post.referent_id)


class Catalog:
    """The referents' posts of the base window, each judged against its own author's OTHER mature posts (leave-one-out
    median, as modelos_crecimiento.judge) twice: with the relaxed rule of the offer (≥ min_sample other posts, ≥ min_lift
    his median, no absolute floor) and with the strict one, only to say what a hypothesis lacks. Built once per plan
    or per brief; it writes nothing of its own (analisis_referentes.report keeps its decomposition cache)."""

    def __init__(self, now=None):
        self.now = now or timezone.now()
        self.t, self.m = mc.thresholds(), thresholds()
        rows = (ObservedPost.objects.select_related('referent')
                .filter(referent__isnull=False, is_repost=False, posted_at__isnull=False,
                        posted_at__gte=self.now - timedelta(days=self.t['base_days'])).exclude(text=''))
        kept, posts, self.alias = {}, [], {}
        for post in rows.order_by('posted_at', 'id'):
            # A referent's post read by one member is copied to the others (referentes.share_posts): it counts once,
            # and a plan that cites a copy gets the mold of the kept one.
            if post.provider_post_id in kept:
                self.alias[str(post.pk)] = kept[post.provider_post_id]
                continue
            kept[post.provider_post_id] = str(post.pk)
            posts.append(post)
        self.posts = {str(p.pk): p for p in posts}
        try:
            durable = an.report(now=self.now)['estructuras_sostenidas']
        except Exception:  # the analysis is an aid: without it every mold is a hypothesis
            durable = []
        self.sustained = {s['firma']: s for s in durable if s['estado'] == 'sostenida'}
        verdicts = mc._prefilter(self.posts)
        settled = self.now - timedelta(hours=self.t['mature_hours'])
        by_author = defaultdict(list)
        for post in posts:
            by_author[_author(post)].append(post)
        relaxed = dict(self.t, min_sample=self.m['min_sample'], min_lift=self.m['min_lift'], min_z=0, min_interactions=0)
        self.perf, self.eligible, self.signature = {}, {}, {}
        for author, items in by_author.items():
            mature = {p.pk: mc.score(p.reactions_count, p.comments_count) for p in items if p.posted_at <= settled}
            mature = {pk: value for pk, value in mature.items() if value is not None}
            for post in items:
                if post.posted_at > settled:
                    continue  # a young post can still change: no mold until its counters settle
                value = mc.score(post.reactions_count, post.comments_count)
                base = [v for pk, v in mature.items() if pk != post.pk]
                loose, strict = mc.judge(value, base, relaxed), mc.judge(value, base, self.t)
                perf = {'score': value, 'median': loose.get('median'), 'lift': loose.get('lift'), 'sample': len(base),
                        'strict': strict['flag'], 'faltan': _missing(strict, self.t)}
                parts = _parts(post)
                topical = list(parts.get('senales_coyuntura') or [])
                if topical:
                    perf['faltan'].append('post de coyuntura (noticia, fecha o lanzamiento)')
                shape = _shape(post)
                apt, _ = mc.fit_as_model(shape, verdicts.get(str(post.pk)))
                perf['apt'] = apt is not False
                self.perf[str(post.pk)] = perf
                self.signature[str(post.pk)] = f"{shape['hook']['type']}·{an.body_format(shape)}·{shape['closing']}"
                # The offer: his post clearly above his own norm, a model of how to grow (no job ad, promotion or a
                # post the lead's prefilter skipped) and not carried by news.
                if loose['flag'] and loose.get('lift') is not None and perf['apt'] and not topical:
                    self.eligible[str(post.pk)] = author

    def mold(self, post_id):
        """The mold of any referent post of the window (the plan may base a day on a growth model that is not in the
        offer); None for a young post, one without counters or one that is no model of how to grow."""
        post_id = str(post_id or '')
        post_id = self.alias.get(post_id, post_id)
        post, perf = self.posts.get(post_id), self.perf.get(post_id)
        if post is None or perf is None or not perf['apt'] or perf.get('score') is None:
            return None
        return build(post, perf, self.sustained)

    def for_structure(self, structure_id, offer=()):
        """The mold of a «sostenida» structure the plan names (analisis_referentes' id, `estructura:<firma>`): its offered
        example, else its best post (strict outliers first). None when no post of the window has it."""
        signature = str(structure_id or '').removeprefix('estructura:')
        found = next((m for m in offer or [] if m.get('firma') == signature), None)
        if found:
            return found
        ids = sorted((i for i in self.eligible if self.signature[i] == signature),
                     key=lambda i: (not self.perf[i]['strict'], -(self.perf[i]['lift'] or 0), i))
        return self.mold(ids[0]) if ids else None

    def author_of(self, mold):
        post = self.posts.get(str((mold.get('fuente') or {}).get('post_id') or ''))
        return _author(post) if post else (mold.get('fuente') or {}).get('referente_id')

    def offer(self, taken=None, kinds=('industria',)):
        """The molds offered for a week: first one example of each «sostenida» structure, then each author's best posts
        in turns (everyone's best before anyone's second), at most `per_author` per author and `offer` in all. `taken`:
        {author: days of this week that already use one of his molds}; an author at MOLDES_MAX_AUTOR_SEMANA is left out.
        Industry referents first; with none of them, every observed referent (as estrategia.growth_models)."""
        taken = Counter(taken or {})
        ids = [i for i in self.eligible if self.posts[i].referent.kind in kinds] or list(self.eligible)
        ranked = sorted(ids, key=lambda i: (-(self.perf[i]['lift'] or 0), -(self.perf[i]['score'] or 0), i))
        per_author, chosen = Counter(), []

        def room(post_id):
            author = self.eligible[post_id]
            return (post_id not in chosen and per_author[author] < self.m['per_author']
                    and taken[author] < self.m['per_week'])

        def take(post_id):
            chosen.append(post_id)
            per_author[self.eligible[post_id]] += 1

        strict_first = sorted(ranked, key=lambda i: not self.perf[i]['strict'])  # stable: by lift inside each group
        for signature in self.sustained:
            example = next((i for i in strict_first if self.signature[i] == signature and room(i)), None)
            if example:
                take(example)
        turns = defaultdict(list)
        for post_id in ranked:
            turns[self.eligible[post_id]].append(post_id)
        order = sorted(turns, key=lambda a: ranked.index(turns[a][0]))
        for turn in range(self.m['per_author']):
            for author in order:
                options = [i for i in turns[author] if room(i)]
                if options and per_author[author] <= turn:
                    take(options[0])
        return [self.mold(i) for i in chosen[:self.m['offer']]]


def catalog(now=None):
    return Catalog(now)


# --------------------------------------------------------------------------- a week: plan, director and the cap

def cap_week(slots, catalog):
    """At most MOLDES_MAX_AUTOR_SEMANA days of one week on molds of the same author: days Gustavo locked or that were
    already prepared keep theirs and count first, the rest in date order. Returns the warnings of the days that lost
    their mold; a day without its mold keeps its idea."""
    limit = catalog.m['per_week']
    counted, warnings = Counter(), []
    ordered = sorted(slots, key=lambda s: (not (s.get('owner_edited') or s.get('state') == 'used'), s['date']))
    for slot in ordered:
        mold = slot.get('molde')
        if not mold:
            continue
        author = catalog.author_of(mold)
        if counted[author] >= limit:
            slot.pop('molde', None)
            warnings.append(f"El día {slot['date']} va sin molde: ya hay {limit} días con moldes de "
                            f"{(mold.get('fuente') or {}).get('autor') or 'ese autor'} esta semana.")
            continue
        counted[author] += 1
    return warnings


def week_taken(catalog, plan, pieces, day):
    """{author: days of the week of `day` that already use one of his molds}: the pieces of another day prepared or
    being prepared with one, and the later days whose planned mold still waits (an earlier day that never got its
    piece did not use it)."""
    out = Counter()
    for slot in (plan.slots if plan else []):
        if slot['date'] > day.isoformat() and slot.get('molde') and slot.get('state', 'planned') == 'planned':
            out[catalog.author_of(slot['molde'])] += 1
    for piece in pieces:
        mold = (piece.brief or {}).get('molde')
        if piece.slot_date != day and isinstance(mold, dict) and piece.state in LIVE_PIECES:
            out[catalog.author_of(mold)] += 1
    return out


def week_pieces(pieces, monday):
    """Her pieces of the week that starts on `monday` (`pieces`: her own queryset) that use or may use a mold."""
    return pieces.filter(slot_date__gte=monday, slot_date__lte=monday + timedelta(days=6), state__in=LIVE_PIECES)


MISSING = object()


def choose(pick, planned, offered):
    """The brief's mold: the director's pick when it is one of the offered or the planned one; an empty pick means
    none fits the day; no pick at all keeps the planned one. Never a mold that was not offered or planned."""
    if pick is MISSING or pick is None:
        return planned or None
    pick = str(pick).strip()
    if not pick:
        return None
    if planned and pick == planned.get('id'):
        return planned
    # Its id, or the id of the «sostenida» structure it is the offered example of (analisis_referentes).
    return next((m for m in offered or [] if pick in (m.get('id'), f"estructura:{m.get('firma')}")), None)


# --------------------------------------------------------------------------- measurement (data only)

def outcome(mold, selection):
    """What the piece records once the director chose: its mold, the variant written on it (A) and which one won."""
    decision = (selection or {}).get('decision')
    return {'id': mold['id'], 'estado': mold['estado'], 'variante': 'A', 'decision': decision,
            'ganadora': WINNERS.get(decision, 'sin_dato')}


def _figures(posts, thin=3):
    from .resultados import engagement_pct
    measured = [p.cuts['72h'] for p in posts if '72h' in p.cuts]
    impressions = [m.impressions for m in measured if m.impressions is not None]
    engagement = [v for v in (engagement_pct(m) for m in measured) if v is not None]
    median = lambda values, digits: round(float(statistics.median(values)), digits) if values else None
    return {'publicados': len(posts), 'medidos_72h': len(measured), 'mediana_impresiones_72h': median(impressions, 0),
            'mediana_interaccion_pct_72h': median(engagement, 1), 'muestra_pequena': len(measured) < thin}


def comparison(posts, thin=3):
    """«Con molde vs sin molde» on her own published posts (resultados.Post, with their 72 h cuts): the ones whose
    published text is the variant written on a mold, the ones without a mold, the days the free variant beat the mold
    and the merges; how each duel ended; and each mold's results. Data only, no model."""
    groups = {'con_molde': [], 'sin_molde': [], 'libre_le_gano_al_molde': [], 'fusion': []}
    duels, per_mold = Counter(), {}
    for post in posts:
        brief = post.piece.brief or {}
        mold = brief.get('molde') if isinstance(brief.get('molde'), dict) else None
        if not mold:
            groups['sin_molde'].append(post)
            continue
        won = ((post.piece.selection or {}).get('molde') or {}).get('ganadora') or 'sin_dato'
        duels[won] += 1
        key = {'molde': 'con_molde', 'libre': 'libre_le_gano_al_molde', 'fusion': 'fusion'}.get(won)
        if key:
            groups[key].append(post)
        entry = per_mold.setdefault(mold['id'], {'mold': mold, 'duels': Counter(), 'own_text': []})
        entry['duels'][won] += 1
        if won == 'molde':
            entry['own_text'].append(post)
    rows = [dict(summary(e['mold']), publicados=sum(e['duels'].values()), duelos=dict(e['duels']),
                 resultados_con_su_texto=_figures(e['own_text'], thin)) for e in per_mold.values()]
    rows.sort(key=lambda r: (-r['publicados'], r['id']))
    return {'disponible': True, 'grupos': {k: _figures(v, thin) for k, v in groups.items()},
            'ganadora': {k: duels.get(k, 0) for k in ('molde', 'libre', 'fusion', 'sin_dato')}, 'por_molde': rows,
            'regla': ('con_molde: el texto publicado es la variante escrita sobre el molde (A); libre_le_gano_al_molde: '
                      'había molde y ganó la variante libre (B); fusion: el director juntó las dos; sin_molde: ese día '
                      'no tenía molde. Medianas del corte de 72 h; muestra_pequena con menos de tres posts medidos.')}
