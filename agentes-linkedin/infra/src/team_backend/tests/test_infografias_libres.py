"""Infografías libres (18-19/11/2026): the new templates, the free canvas behind INFOGRAFIA_LIENZO, the rules that protect
the truth and the legibility (style is mended, never a discard), the fallbacks that keep the post's own content before
the brand card, the editor's layout choice, the image's own research behind INFOGRAFIA_INVESTIGACION and the
operator's redo of the brand cards. Every provider is a fake; the clock is frozen."""
import io
import json
import os
import socket
import subprocess
import threading
import uuid
from contextlib import nullcontext
from datetime import datetime, timedelta, timezone as dt_timezone
from decimal import Decimal
from unittest.mock import patch

from PIL import Image, ImageDraw
from django.core.management import call_command
from django.test import TestCase

from team_backend import (connectors_images, editor_visual, editorial, guardas, imagenes, infografias, lienzo, operador,
                          orquestacion, research, retoque)
from team_backend.connectors_images import FakeImageConnector
from team_backend.grafo import load_graph
from team_backend.models import ActionExecution, ActionProposal, AuditEvent, CycleLedger, EditorialPiece, ObservedPost
from team_backend.tests import test_imagenes as image_cases
from team_backend.tests.test_imagenes import png, slide
from team_backend.tests.test_publicacion import GOOD_POST, EditorialBase

FIXED = datetime(2026, 11, 19, 15, 0, tzinfo=dt_timezone.utc)
FACT = [{'key': 'fact', 'claim': 'A public record'}]
SOURCE = {'ref': 'fact', 'label': 'Public record', 'date': '2026', 'estimate': False}
NO_SOURCE = {'ref': '', 'label': '', 'date': '', 'estimate': False}
# A post with no line a card can carry on its own: every sentence has a figure or is too short.
NO_LINE_POST = 'In 2026, 70% of teams shipped 3x more. Wow. Really.'


def frozen(test):
    clock = patch('django.utils.timezone.now', return_value=FIXED)
    clock.start()
    test.addCleanup(clock.stop)


def table():
    return dict(slide('tabla'), title='Who decides what', columns=['Decision', 'Owner', 'Cadence'],
                rows=[{'label': 'Pricing', 'cells': ['Founder', 'Quarterly'], 'focus': True},
                      {'label': 'Roadmap', 'cells': ['Product lead', 'Monthly'], 'focus': False}])


def comparison():
    return dict(slide('comparacion'), title='Two ways to start', columns=['Feature first', 'Decision first'],
                highlight='Decision first',
                rows=[{'label': 'Starts from', 'cells': ['A dashboard', 'The decision behind it'], 'focus': False},
                      {'label': 'Scope', 'cells': ['Everything asked', 'What the call needs'], 'focus': False}])


def line():
    return dict(slide('linea'), title='Reviews grow each quarter', columns=['Q1', 'Q2', 'Q3', 'Q4'], source=SOURCE,
                series=[{'name': 'Reviews', 'values': [2, 4, 5, 8], 'focus': True}])


def listing():
    return dict(slide('lista'), title='Before the first line of code',
                steps=['Name the decision — who makes it', 'Price a wrong call', 'Check the outcome'])


NEW_TEMPLATES = {'tabla': table, 'comparacion': comparison, 'linea': line, 'lista': listing,
                 'cita': lambda: infografias.content_card(GOOD_POST)}


class NewTemplatesTests(TestCase):
    def setUp(self):
        frozen(self)

    def test_each_new_template_renders_a_valid_png_alone_and_in_a_carousel(self):
        for name, make in NEW_TEMPLATES.items():
            with self.subTest(template=name):
                data = infografias.validate({'slides': [make()]}, 'infografia', FACT)
                one = Image.open(io.BytesIO(infografias.render(data['slides'][0])))
                self.assertEqual((one.size, one.format), ((1080, 1080), 'PNG'))
                part = Image.open(io.BytesIO(infografias.render(data['slides'][0], 2, 3, True)))
                self.assertEqual(part.size, (1080, 1350))

    def test_each_new_template_rejects_what_it_cannot_draw_with_the_reason(self):
        bad = [
            ('tabla', dict(table(), columns=['Only one']), 'Tabla de 2 a 4 columnas'),
            ('tabla', dict(table(), rows=[{'label': 'Pricing', 'cells': ['Founder'], 'focus': False}]), 'Cada fila'),
            ('comparacion', dict(comparison(), columns=['A', 'B', 'C']), 'Comparación: dos encabezados'),
            ('comparacion', dict(comparison(), rows=[{'label': 'Scope', 'cells': ['Everything', ''], 'focus': False}]),
             'Cada fila compara dos textos'),
            ('linea', dict(line(), series=[{'name': 'Reviews', 'values': [2, 4], 'focus': True}]), 'un valor por cada etiqueta'),
            ('linea', dict(line(), series=[{'name': 'Reviews', 'values': [-2, 4, 5, 8], 'focus': True}]), 'desde cero'),
            ('linea', dict(line(), source=NO_SOURCE), 'Dato sin fuente'),
            ('lista', dict(listing(), steps=['Only one thing']), 'lista: de 2 a 6'),
            ('cita', dict(infografias.content_card(GOOD_POST), title=' '.join(['word'] * 25)), 'de 1 a 24 palabras'),
        ]
        for name, value, reason in bad:
            with self.subTest(template=name, reason=reason), self.assertRaisesMessage(ValueError, reason):
                infografias.validate({'slides': [value]}, 'infografia', FACT)

    def test_a_name_with_a_digit_is_not_a_figure_but_a_quantity_is(self):
        self.assertEqual(infografias.figures('GPT-5 and B2B teams in Q3 3D'), [])
        self.assertEqual(infografias.figures('70% of teams, 3x faster, $2M in 2026, 10-15 days'),
                         ['70%', '3x', '$2M', '2026', '10-15'])


class RulesTests(TestCase):
    """What protects the truth or the legibility stays hard in validate(); style is fix()'s (19/11/2026)."""

    def setUp(self):
        frozen(self)

    def test_the_three_real_rejections_are_mended_or_dropped_not_a_discard(self):
        # «El cierre es una pregunta» (a carousel whose closing is a statement): a note, the carousel stays.
        carousel = {'slides': [slide('portada'), slide(), dict(slide('cierre'), title='Decide before you build')]}
        fixed, notes = infografias.fix(carousel, 'carrusel')
        infografias.validate(fixed, 'carrusel')
        self.assertIn('El cierre suele devolver la pregunta del post', notes)
        # «Demasiadas palabras» (over the board's 40): the secondary text goes, the steps stay whole.
        wordy = {'slides': [dict(slide(), body=' '.join(['word'] * 60))]}
        fixed, notes = infografias.fix(wordy, 'infografia')
        self.assertEqual(infografias.validate(fixed, 'infografia')['slides'][0]['body'], '')
        self.assertEqual(fixed['slides'][0]['steps'], slide()['steps'])
        # «Dato sin fuente pública identificable y fecha»: the figure without a source is dropped, the rest stays.
        unsourced = {'slides': [dict(slide(), subtitle='Teams that decide first ship 70% faster')]}
        with self.assertRaisesMessage(ValueError, 'Dato sin fuente'):
            infografias.validate(unsourced, 'infografia')  # the truth rule itself stays hard
        fixed, notes = infografias.fix(unsourced, 'infografia')
        self.assertEqual(infografias.validate(fixed, 'infografia')['slides'][0]['subtitle'], '')
        self.assertIn('cifra sin fuente', ' '.join(notes))

    def test_what_cannot_be_mended_stays_hard(self):
        hard = [
            ({'slides': [dict(slide('numero'), source=NO_SOURCE)]}, 'Dato sin fuente'),  # the figure is the slide
            ({'slides': [dict(slide(), title='We grew 70% this year')]}, 'Dato sin fuente'),  # in the headline
            ({'slides': [dict(slide('numero'), source=dict(SOURCE, ref='unknown'))]}, 'Dato sin fuente'),  # unknown source
            ({'slides': [dict(slide('barras'), bars=[{'label': 'A', 'value': -1, 'focus': True}])]}, 'Barras desde cero'),
            ({'slides': [dict(slide(), steps=['Only one'])]}, 'pasos: de 2 a 6'),
        ]
        for design, reason in hard:
            with self.subTest(reason=reason), self.assertRaisesMessage(ValueError, reason):
                fixed, _ = infografias.fix(design, 'infografia', FACT)
                infografias.validate(fixed, 'infografia', FACT)

    def test_an_unknown_source_is_not_cited_and_an_estimate_says_so(self):
        design = {'slides': [dict(slide(), body='A public record says so.', source=dict(SOURCE, ref='made-up'))]}
        fixed, notes = infografias.fix(design, 'infografia', FACT)
        self.assertEqual(fixed['slides'][0]['source'], NO_SOURCE)
        estimate = {'slides': [dict(slide('numero'), source=dict(SOURCE, estimate=True))]}
        fixed, _ = infografias.fix(estimate, 'infografia', FACT)
        self.assertIn('estimate', infografias.validate(fixed, 'infografia', FACT)['slides'][0]['source']['label'])

    def test_a_carousel_drops_a_slide_whose_figure_has_no_source_while_two_remain(self):
        design = {'slides': [slide('portada'), dict(slide('numero'), source=NO_SOURCE), slide(), slide('cierre')]}
        fixed, notes = infografias.fix(design, 'carrusel', FACT)
        self.assertEqual([s['template'] for s in infografias.validate(fixed, 'carrusel', FACT)['slides']],
                         ['portada', 'pasos', 'cierre'])
        self.assertIn('fuera del carrusel', ' '.join(notes))

    def test_the_vision_check_discards_only_on_truth_legibility_or_topic(self):
        def verdict(*failed):
            return {'ok': not failed, 'reasons': [], 'checks': [{'point': n, 'ok': n not in failed, 'reason': f'p{n}'}
                                                                 for n in range(1, 11)]}
        for point in (2, 3, 6, 7, 10):
            with self.subTest(style=point):
                soft = connectors_images.soften(verdict(point))
                self.assertEqual((soft['ok'], soft['observations']), (True, [f'Punto {point}: p{point}']))
        for point in sorted(connectors_images.BLOCKING):
            with self.subTest(blocking=point):
                hard = connectors_images.soften(verdict(point, 3))
                self.assertEqual((hard['ok'], hard['reasons'], hard['observations']),
                                 (False, [f'Punto {point}: p{point}'], ['Punto 3: p3']))
        self.assertEqual(connectors_images.BLOCKING, frozenset((1, 4, 5, 8, 9)))

    def test_the_real_check_softens_infographics_and_keeps_photos_strict(self):
        style = {'ok': False, 'reasons': ['Titular largo'],
                 'checks': [{'point': n, 'ok': n != 3, 'reason': 'Titular largo' if n == 3 else 'Bien'} for n in range(1, 11)]}
        raw = png((1080, 1080))
        with patch('team_backend.connectors_images.available', return_value=True), \
                patch('knowledge.providers.claude', return_value={'text': json.dumps(style)}) as model:
            infographic = connectors_images.ImageConnector().check([raw], {'post': GOOD_POST, 'lienzo': True})
            photo = connectors_images.ImageConnector().check([raw], {'post': GOOD_POST}, original=raw, instruction='Más luz')
        self.assertEqual((infographic['ok'], infographic['observations']), (True, ['Punto 3: Titular largo']))
        self.assertIn('lienzo libre', model.call_args_list[0].args[0])  # the canvas' own points
        self.assertIn('Solo los puntos 1, 4, 5, 8 y 9', model.call_args_list[0].args[0])
        self.assertFalse(photo['ok'])


class ContentCardTests(TestCase):
    def setUp(self):
        frozen(self)

    def test_the_card_carries_the_posts_own_line_and_question_and_no_figure(self):
        statement, question = infografias.key_lines(GOOD_POST)
        self.assertTrue(statement.startswith('Founders often arrive with a solution in mind'))
        self.assertEqual(question, 'Which decision is your product helping someone make this week?')
        card = infografias.content_card(GOOD_POST)
        self.assertEqual((card['template'], card['title'], card['subtitle']), ('cita', statement, question))
        self.assertNotIn('A question worth exploring', json.dumps(card))
        infografias.validate({'slides': [card]}, 'infografia')
        self.assertIsNone(infografias.content_card(NO_LINE_POST))
        self.assertIsNone(infografias.content_card('Follow me for more. Like if you agree with this. https://x.example'))


# --------------------------------------------------------------------------- the free canvas

def canvas(html=None, **changes):
    html = html or ('<div class="t"><h1>Decide first</h1><p>Name the decision before the feature.</p></div>'
                    '<style>.t{display:flex;flex-direction:column;gap:24px}h1{font-size:72px;color:var(--acento)}</style>')
    spec = {'html': html, 'title': 'Decide first', 'fondo': 'papel', 'source': NO_SOURCE,
            'alt': 'A canvas that puts the decision before the feature.'}
    return dict(spec, **changes)


class FakeRenderer:
    """lienzo.Renderer's contract without WeasyPrint: a plain page with one text inside the content box."""

    def __init__(self, size=72.0):
        self.pages, self.size = [], size

    def render(self, page):
        self.pages.append(page)
        image = Image.new('RGB', (1080, 1080), infografias.PAPER)
        ImageDraw.Draw(image).rectangle((120, 120, 600, 200), fill=infografias.INK)
        out = io.BytesIO()
        image.save(out, format='PNG')
        text = {'tag': 'h1', 'text': 'Decide first', 'box': [120, 120, 600, 200], 'size': self.size,
                'color': infografias.INK, 'alpha': 1, 'background': infografias.PAPER}
        return out.getvalue(), {'pages': 1, 'background': infografias.PAPER, 'texts': [text], 'boxes': []}


class CanvasSanitizerTests(TestCase):
    def setUp(self):
        frozen(self)

    def test_the_document_is_rejected_with_its_reason_never_stripped_silently(self):
        cases = [
            ('<script>alert(1)</script><p>Hi</p>', 'Sin scripts'),
            ('<svg><script>alert(1)</script></svg>', 'Sin imágenes, svg'),
            ('<div onclick="steal()">Hi</div>', 'Sin manejadores de eventos'),
            ('<img src="https://evil.example/pixel.png">', 'Sin imágenes, svg'),
            ('<a href="https://evil.example">Hi</a>', 'Sin imágenes, svg'),
            ('<iframe src="https://evil.example"></iframe>', 'Sin iframes'),
            ('<object data="x.swf"></object>', 'Sin iframes'),
            ('<form action="https://evil.example"><input name="q"></form>', 'Sin formularios'),
            ('<link rel="stylesheet" href="https://evil.example/x.css">', 'Sin imágenes, svg'),
            ('<meta http-equiv="refresh" content="0;url=https://evil.example">', 'Solo <meta charset>'),
            ('<p style="color:javascript:alert(1)">Hi</p>', 'Sin imágenes, svg'),
            ('<p data-x="1">Hi</p>', 'Atributo no permitido'),
            ('<p id="lienzo">Hi</p>', 'Atributo no permitido'),
            ('<marquee>Hi</marquee>', 'Etiqueta no permitida'),
            ('<!DOCTYPE something>', 'Solo <!doctype html>'),
            ('<p>Hi</p><style>.a{color:red}', 'Un <style> sin cerrar'),
            ('', 'El lienzo está vacío'),
            ('<p>' + 'x' * 20_001 + '</p>', 'Lienzo demasiado grande'),
        ]
        for document, reason in cases:
            with self.subTest(document=document[:40]), self.assertRaisesMessage(ValueError, reason):
                lienzo.sanitize(document)

    def test_the_css_comes_from_the_palette_and_cannot_fetch_hide_or_add_text(self):
        cases = [
            ('.a{background:url(https://evil.example/x.png)}', 'Sin url()'),
            ('@import url(https://evil.example/x.css);', 'Sin @import'),
            ('@font-face{font-family:x;src:url(x.woff)}', 'Sin @font-face'),
            ('@media print{.a{color:#1E1E2B}}', 'Sin @media'),
            ('.a{color:red}', 'Colores solo de la paleta'),
            ('.a{color:#FF0000}', 'Color fuera de la paleta'),
            ('.a{color:rgb(255,0,0)}', 'función CSS no permitida: rgb()'),
            ('.a{background:linear-gradient(#F7F6F0,#1E1E2B)}', 'Sin degradados'),
            ('.a{box-shadow:0 0 4px #1E1E2B}', 'Sin sombras'),
            ('.a{opacity:.5}', 'Sin sombras, degradados, transparencias'),
            ('.a{color:var(--mine)}', 'var() solo con los colores de la paleta'),
            ('.a{--mine:#F7F6F0}', 'Sin variables propias'),
            ('.a{color:#1E1E2B !important}', 'Sin !important'),
            ('.a{font-size:20px}', 'Nada por debajo de 28 px'),
            ('.a{font-size:2em}', 'font-size en px'),
            ('.a{font-weight:700}', 'Ubuntu regular'),
            ('.a{overflow:hidden}', 'Sin overflow oculto'),
            ('.a{display:none}', 'Sin texto escondido'),
            ('.a{position:fixed}', 'position: static, relative o absolute'),
            ('.a{content:"x"}', 'Propiedad CSS no permitida: content'),
            ('.a::after{color:#1E1E2B}', 'Sin pseudo-elementos'),
            (':root{color:#1E1E2B}', 'Sin pseudo-elementos ni :root'),
            ('#lienzo{left:0}', 'Sin selectores de id'),
            ('body{background:#1E1E2B}', 'Sin selectores html ni body'),
        ]
        for css, reason in cases:
            with self.subTest(css=css), self.assertRaisesMessage(ValueError, reason):
                lienzo.sanitize(f'<style>{css}</style><p class="a">Hi</p>')

    def test_what_passes_is_rebuilt_escaped_and_the_code_imposes_the_page(self):
        body, css, texts = lienzo.sanitize('<p class="a">1 &lt; 2 <!-- hidden --><b>bold</b></p>'
                                           '<style>.a{color:var(--acento);font-family:Comic Sans}</style>')
        self.assertEqual(body, '<p class="a">1 &lt; 2 <b>bold</b></p>')
        self.assertEqual(css, '.a{color:var(--acento)}')  # the font is the code's
        self.assertEqual(texts, ['1 < 2 ', 'bold'])
        page = lienzo.validate(canvas())
        self.assertIn('#lienzo{position:absolute !important;left:96px', page)
        self.assertIn('font-family:Ubuntu !important', page)

    def test_a_figure_on_the_canvas_needs_its_source_like_on_a_template(self):
        figure = canvas('<h1>Decide first</h1><p>70% of teams decide later.</p>')
        with self.assertRaisesMessage(ValueError, 'Dato sin fuente'):
            lienzo.validate(figure)
        lienzo.validate(dict(figure, source=SOURCE), FACT)
        with self.assertRaisesMessage(ValueError, 'Demasiadas palabras'):
            lienzo.validate(canvas('<p>' + ' '.join(['word'] * 91) + '</p>'))
        with self.assertRaisesMessage(ValueError, 'Sin emojis'):
            lienzo.validate(canvas('<p>Decide first 🚀</p>'))

    def test_the_measured_layout_rules(self):
        ok = FakeRenderer().render('')[1]
        self.assertEqual(lienzo.layout_issues(ok), [])
        text = ok['texts'][0]
        cases = [
            (dict(ok, pages=2), 'más de una página'),
            (dict(ok, texts=[dict(text, size=20.0)]), 'por debajo de 28 px'),
            (dict(ok, texts=[dict(text, box=[40, 120, 600, 200])]), 'Texto fuera del área'),
            (dict(ok, texts=[dict(text, color='#FF0000')]), 'Color de texto fuera de la paleta'),
            (dict(ok, texts=[dict(text, color=infografias.LINE)]), 'Contraste por debajo de 4,5:1'),
            (dict(ok, texts=[text, dict(text, text='Another')]), 'Textos superpuestos'),
            (dict(ok, boxes=[{'box': [96, 96, 500, 300], 'background': '#FF0000', 'alpha': 1, 'borders': []}]), 'Fondo fuera'),
            (dict(ok, texts=[]), 'no tiene texto'),
        ]
        for facts, reason in cases:
            with self.subTest(reason=reason):
                self.assertIn(reason, ' '.join(lienzo.layout_issues(facts)))

    def test_one_render_at_a_time_a_time_limit_and_no_keys_in_the_child(self):
        with lienzo.exclusive(60):  # waits for a render of another test worker, if any (CI runs them in parallel)
            with self.assertRaisesMessage(ValueError, 'Otro render del lienzo en curso'):
                with lienzo.exclusive(0.2):
                    pass
        with patch('team_backend.lienzo.subprocess.run', side_effect=subprocess.TimeoutExpired('render', 45)):
            with self.assertRaisesMessage(ValueError, 'El render del lienzo superó'):
                lienzo.Renderer().render('<p>x</p>')
        answer = subprocess.CompletedProcess([], 0, json.dumps({'png': '', 'facts': {}}).encode(), b'')
        with patch.dict(os.environ, {'ANTHROPIC_API_KEY': 'sk-ant-secret', 'DATABASE_URL': 'postgresql://x'}), \
                patch('team_backend.lienzo.subprocess.run', return_value=answer) as run:
            lienzo.Renderer().render('<p>x</p>')
        env = run.call_args.kwargs['env']
        self.assertFalse({'ANTHROPIC_API_KEY', 'DATABASE_URL'} & set(env))
        self.assertEqual(run.call_args.args[0][1], '-I')  # isolated: no user site, no cwd on the path

    def test_a_drawing_outside_the_content_box_is_refused(self):
        raw, _ = FakeRenderer().render('')
        image = Image.open(io.BytesIO(raw)).convert('RGB')
        ImageDraw.Draw(image).rectangle((0, 0, 50, 50), fill=infografias.INK)
        out = io.BytesIO()
        image.save(out, format='PNG')
        with self.assertRaisesMessage(ValueError, 'El lienzo dibuja fuera de su área'):
            lienzo.finish(out.getvalue(), canvas())


class RealRenderTests(TestCase):
    """The real renderer (WeasyPrint in its child process). CI installs Pango, so it never skips there."""

    def setUp(self):
        frozen(self)

    def real(self, page):
        try:
            return lienzo.Renderer().render(page)
        except ValueError as exc:
            if os.environ.get('GITHUB_ACTIONS') or os.environ.get('CI'):
                raise
            self.skipTest(f'WeasyPrint o Pango no están instalados aquí: {exc}')

    def test_a_checked_canvas_renders_measures_and_gets_its_foot(self):
        spec = canvas('<div class="wrap"><h1>Small teams decide faster</h1><div class="grid">'
                      '<div class="card"><p class="big">3</p><p>people own the scope</p></div>'
                      '<div class="card"><p class="big">1</p><p>weekly decision meeting</p></div></div></div>'
                      '<style>.wrap{display:flex;flex-direction:column;gap:32px}h1{font-size:64px;line-height:1.1}'
                      '.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:24px}'
                      '.card{background:var(--tinta);color:var(--papel);padding:24px;border-top:6px solid var(--acento-tinta)}'
                      '.big{font-size:96px;color:var(--acento-tinta);line-height:1}</style>',
                      title='Small teams decide faster', source=SOURCE,
                      alt='Small teams decide faster: three people own the scope and one weekly meeting decides.')
        page = lienzo.validate(spec, FACT)
        raw, facts = self.real(page)
        self.assertEqual((facts['pages'], lienzo.layout_issues(facts)), (1, []))
        self.assertIn('Small teams decide faster', ' '.join(t['text'] for t in facts['texts']))
        final = Image.open(io.BytesIO(lienzo.finish(raw, spec, 'Gustavo')))
        self.assertEqual((final.size, final.format), ((1080, 1080), 'PNG'))

    def test_the_child_fetches_nothing_even_from_a_page_that_skipped_the_sanitizer(self):
        server = socket.socket()
        server.bind(('127.0.0.1', 0))
        server.listen(4)
        server.settimeout(0.5)
        port = server.getsockname()[1]
        hits = []

        def accept():
            try:
                hits.append(server.accept())
            except OSError:
                pass

        page = (f'<!doctype html><html><head><style>@import url(http://127.0.0.1:{port}/a.css);'
                f'body{{background:url(http://127.0.0.1:{port}/b.png)}}</style></head>'
                f'<body><p>Hello</p><img src="http://127.0.0.1:{port}/c.png"></body></html>')
        listener = threading.Thread(target=accept)
        listener.start()
        try:
            with self.assertRaises(ValueError) as refused:
                lienzo.Renderer().render(page)
        finally:
            listener.join()
            server.close()
        if 'URL no permitida' not in str(refused.exception) and not (os.environ.get('GITHUB_ACTIONS') or os.environ.get('CI')):
            self.skipTest(f'WeasyPrint o Pango no están instalados aquí: {refused.exception}')
        # The child refuses every URL but its own font, and fails the render instead of drawing a page without it.
        self.assertIn('URL no permitida en el lienzo', str(refused.exception))
        self.assertEqual(hits, [])


# --------------------------------------------------------------------------- the flow, with fakes

class Designer:
    """The designer's fake: answers in turn (the last one repeats) and keeps every request."""

    def __init__(self, *answers):
        self.answers = [json.dumps(a) for a in answers]
        self.calls = []

    def __call__(self, system, message, **kwargs):
        self.calls.append(dict(kwargs, system=system, payload=json.loads(message)))
        return {'text': self.answers[min(len(self.calls), len(self.answers)) - 1]}


class FlowBase(EditorialBase):
    piece_factory = image_cases.ImageWorkflowTests.piece
    photo = image_cases.ImageWorkflowTests.photo

    def setUp(self):
        frozen(self)
        super().setUp()

    def piece(self, kind='infografia', layout=None, text=None):
        piece = self.piece_factory(kind)
        if layout is not None:
            piece.brief = dict(piece.brief, image=dict(piece.brief['image'], layout=layout))
        if text is not None:
            piece.final_text = text
            piece.verification = {'verdict': 'ready_for_execution', 'text_sha256': imagenes.sha(text.encode())}
        piece.save()
        return piece

    def prepare(self, piece, designer, client=None):
        with patch('knowledge.providers.claude', side_effect=designer):
            imagenes.prepare(piece, client=client or FakeImageConnector())
        piece.refresh_from_db()
        return piece


class RealReasonsFlowTests(FlowBase):
    """The three reasons that sent 4 of 14 pieces out with the brand card (production, 19/11/2026) now end in a content
    image; only a post with nothing a card can carry still reaches the brand card, and every fallback is counted."""

    def test_a_closing_statement_no_longer_discards_the_carousel(self):
        piece = self.prepare(self.piece('carrusel'), Designer(
            {'slides': [slide('portada'), slide(), dict(slide('cierre'), title='Decide before you build')]}))
        self.assertEqual((piece.image_kind, piece.images.count()), ('carrusel', 3))
        self.assertNotIn('mode', piece.image_review)
        self.assertIn('El cierre suele devolver la pregunta del post', piece.image_review['attempts'][-1]['notes'])

    def test_too_many_words_trims_the_secondary_text_and_goes_out(self):
        designer = Designer({'slides': [dict(slide(), body=' '.join(['word'] * 60))]})
        piece = self.prepare(self.piece(), designer)
        row = piece.images.get()
        self.assertEqual((piece.image_kind, row.template, row.data['body']), ('infografia', 'pasos', ''))
        self.assertEqual(len(designer.calls), 1)

    def test_a_figure_without_a_source_is_dropped_and_the_image_goes_out(self):
        designer = Designer({'slides': [dict(slide(), body='Teams that decide first ship 70% faster.')]})
        piece = self.prepare(self.piece(), designer)
        row = piece.images.get()
        self.assertEqual((row.template, row.data['body']), ('pasos', ''))
        self.assertEqual(len(designer.calls), 1)

    def test_a_design_that_cannot_pass_ends_in_the_posts_key_line_not_the_brand_card(self):
        designer = Designer({'slides': [dict(slide('numero'), source=NO_SOURCE)]})
        piece = self.prepare(self.piece(), designer)
        self.assertEqual(len(designer.calls), 2)  # one correction, with the exact failure
        self.assertIn('Dato sin fuente', ' '.join(designer.calls[1]['payload']['findings']))
        row = piece.images.get()
        self.assertEqual((piece.image_kind, row.kind, row.template), ('infografia', 'infografia', 'cita'))
        self.assertEqual(piece.image_review['fallback'], {'level': 'contenido', 'reason': piece.image_review['fallback']['reason']})
        self.assertNotIn('A question worth exploring', json.dumps(row.data))
        self.assertEqual(imagenes.issues(piece, imagenes.manifest(piece)), [])

    def test_the_brand_card_is_the_last_resort_and_every_fallback_is_counted(self):
        content = self.prepare(self.piece(), Designer({'slides': [dict(slide('numero'), source=NO_SOURCE)]}))
        last = self.prepare(self.piece(text=NO_LINE_POST), Designer({'slides': [dict(slide('numero'), source=NO_SOURCE)]}))
        designed = self.prepare(self.piece(), Designer({'slides': [slide()]}))
        self.assertEqual((last.image_kind, last.image_review['mode']), ('tarjeta', 'fixed_brand_card'))
        self.assertEqual(last.image_review['fallback']['level'], 'marca')
        self.assertEqual(designed.image_kind, 'infografia')
        audits = AuditEvent.objects.filter(action='editorial.image_fallback').order_by('created_at', 'id')
        self.assertEqual(sorted((a.target, a.metadata['level']) for a in audits),
                         sorted([(str(content.id), 'contenido'), (str(last.id), 'marca')]))
        counts = imagenes.fallback_counts(self.official, (FIXED - timedelta(days=30)).date())
        self.assertEqual(counts['by_level'], {'contenido': 1, 'marca': 1, 'diseño': 1})
        self.assertEqual(counts['total'], 3)
        self.assertTrue(all('Dato sin fuente' in reason for reason, _ in counts['reasons']))
        out = io.StringIO()
        call_command('operador', '--usuario', self.gustavo.username, 'respaldos-imagen', '--cuenta', str(self.official.id),
                     stdout=out)
        self.assertIn('tarjeta con la frase del post: 1', out.getvalue())
        self.assertIn('tarjeta genérica de marca: 1', out.getvalue())

    def test_the_editors_photo_comes_before_the_brand_card(self):
        photo = self.photo()
        piece = self.piece(text=NO_LINE_POST)
        piece.brief = dict(piece.brief, image=dict(piece.brief['image'], photos=[image_cases.choice(photo)]),
                           gallery_offered=[str(photo.id)])
        piece.save()
        piece = self.prepare(piece, Designer({'slides': [dict(slide('numero'), source=NO_SOURCE)]}))
        self.assertEqual((piece.image_kind, piece.image_review['mode']), ('foto', 'foto_respaldo'))
        self.assertEqual(piece.images.get().source_photo_id, photo.id)


class CanvasFlowTests(FlowBase):
    def canvas_on(self, renderer):
        for patcher in (patch.dict(os.environ, {'INFOGRAFIA_LIENZO': 'true'}), patch.object(lienzo, 'RENDERER', renderer)):
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_a_canvas_that_passes_goes_out_after_the_same_visual_check(self):
        renderer = FakeRenderer()
        self.canvas_on(renderer)
        designer = Designer({'slides': [slide()], 'lienzo': canvas()})
        client = FakeImageConnector()
        piece = self.prepare(self.piece(layout='lienzo'), designer, client)
        row = piece.images.get()
        self.assertEqual((row.template, row.kind, piece.image_review.get('lienzo')), ('lienzo', 'infografia', True))
        self.assertEqual(len(renderer.pages), 1)
        call = designer.calls[0]
        self.assertIs(call['output_schema'], infografias.CANVAS_DESIGN_SCHEMA)
        self.assertEqual(call['max_tokens'], 8000)
        self.assertIn('Lienzo libre (lienzo)', call['system'])
        self.assertEqual([c[2].get('lienzo') for c in client.calls if c[0] == 'check'], [True])
        self.assertEqual(infografias.layout_of(piece.image_kind, piece.image_spec), 'lienzo')
        self.assertEqual(imagenes.issues(piece, imagenes.manifest(piece)), [])

    def test_a_canvas_that_fails_falls_back_to_the_template_of_the_same_answer(self):
        for name, spec, renderer, reason in (
                ('layout', canvas(), FakeRenderer(size=20.0), 'por debajo de 28 px'),
                ('security', canvas('<script>fetch("https://evil.example")</script>'), FakeRenderer(), 'Sin scripts')):
            with self.subTest(failure=name):
                with patch.dict(os.environ, {'INFOGRAFIA_LIENZO': 'true'}), patch.object(lienzo, 'RENDERER', renderer):
                    designer = Designer({'slides': [slide()], 'lienzo': spec})
                    piece = self.prepare(self.piece(layout='lienzo'), designer)
                self.assertEqual(len(designer.calls), 1)  # no second paid call: the template was in the same answer
                self.assertEqual(piece.images.get().template, 'pasos')
                first = piece.image_review['attempts'][0]
                self.assertEqual(first['stage'], 'lienzo')
                self.assertIn(reason, ' '.join(first['failures']))
                self.assertEqual(len(renderer.pages), 0 if name == 'security' else 1)

    def test_canvas_then_template_failing_ends_in_the_content_card(self):
        self.canvas_on(FakeRenderer(size=20.0))
        designer = Designer({'slides': [dict(slide('numero'), source=NO_SOURCE)], 'lienzo': canvas()},
                            {'slides': [dict(slide('numero'), source=NO_SOURCE)]})
        piece = self.prepare(self.piece(layout='lienzo'), designer)
        self.assertEqual(len(designer.calls), 2)
        self.assertIs(designer.calls[1]['output_schema'], infografias.TEMPLATE_DESIGN_SCHEMA)  # the correction is a template
        self.assertEqual((piece.images.get().template, piece.image_review['mode']), ('cita', 'tarjeta_contenido'))

    def test_with_the_switch_off_the_designer_request_is_the_template_one(self):
        renderer = FakeRenderer()
        requests = []
        with patch.dict(os.environ, {'INFOGRAFIA_LIENZO': 'false'}), patch.object(lienzo, 'RENDERER', renderer):
            for layout in ('lienzo', None):
                designer = Designer({'slides': [slide()]})
                piece = self.prepare(self.piece(layout=layout), designer)
                self.assertEqual(piece.images.get().template, 'pasos')
                requests.append((piece, designer.calls))
            # The editor's side: no canvas in its instructions nor among the layouts it may choose.
            self.assertNotIn('lienzo es otro layout', editor_visual.system())
            self.assertNotIn('lienzo', infografias.choice_schema(lienzo.enabled())['properties']['layout']['enum'])
        self.assertEqual(renderer.pages, [])
        (first, [one]), (second, [other]) = requests
        for call, piece in ((one, first), (other, second)):
            self.assertIs(call['output_schema'], infografias.TEMPLATE_DESIGN_SCHEMA)
            self.assertEqual((call['max_tokens'], call['purpose']), (5000, 'image-design'))
            self.assertEqual(call['system'], imagenes.design_system(piece))
            self.assertNotIn('Lienzo libre (lienzo)', call['system'])  # the canvas' own instructions
            self.assertEqual(set(call['payload']), {'kind', 'brief', 'post', 'public_facts', 'sources', 'findings',
                                                    'previous_design'})
        self.assertEqual(one['system'], other['system'])
        self.assertEqual({k: v for k, v in one['payload'].items() if k != 'brief'},
                         {k: v for k, v in other['payload'].items() if k != 'brief'})


class LayoutChoiceTests(FlowBase):
    def choice(self, layout, alternatives=(), kind='infografia'):
        return {'kind': kind, 'reason': 'Encaja con el post.', 'photos': [], 'layout': layout,
                'alternatives': list(alternatives)}

    def test_settle_layout_never_repeats_the_last_layout_when_another_fits(self):
        recent = [{'date': '2026-11-18', 'kind': 'infografia', 'layout': 'pasos'}]
        settled = editor_visual.settle_layout(self.choice('pasos', ['lista', 'preguntas']), recent)
        self.assertEqual((settled['layout'], settled['alternatives']), ('lista', ['pasos', 'preguntas']))
        self.assertIn('Se evita repetir pasos', settled['reason'])
        self.assertEqual(editor_visual.settle_layout(self.choice('pasos'), recent)['layout'], 'pasos')  # nothing else fits
        photo_last = [{'date': '2026-11-18', 'kind': 'foto', 'layout': 'foto'}]
        self.assertEqual(editor_visual.settle_layout(self.choice('pasos', ['lista']), photo_last)['layout'], 'pasos')
        self.assertEqual(editor_visual.settle_layout(self.choice('pasos', kind='foto'), recent)['layout'], '')
        off = editor_visual.settle_layout(self.choice('lienzo', ['tabla']), [], canvas=False)
        self.assertEqual(off['layout'], 'tabla')
        self.assertEqual(editor_visual.settle_layout(self.choice('lienzo', ['tabla']), [], canvas=True)['layout'], 'lienzo')

    def test_the_editor_sees_the_last_layouts_and_does_not_repeat_the_last_one(self):
        before = self.piece()
        before.state, before.image_kind = EditorialPiece.State.READY, 'infografia'
        before.image_spec = {'slides': [dict(slide(), columns=[], rows=[], series=[])]}
        before.save()
        piece = self.piece()
        self.assertEqual(editor_visual.recent_layouts(piece),
                         [{'date': before.slot_date.isoformat(), 'kind': 'infografia', 'layout': 'pasos'}])
        self.assertEqual(editor_visual.recent_layouts(before), [])  # only what came before
        public, private = guardas.blocks()
        request = editor_visual.request(piece, public, private)
        answer = {'text': json.dumps(self.choice('pasos', ['lista']))}
        with patch('team_backend.imagenes.connector.available', return_value=True), \
                patch('knowledge.providers.claude', return_value=answer) as model:
            proposal = editor_visual.propose(request)
        self.assertEqual(proposal['choice']['layout'], 'lista')
        self.assertIn('recent_layouts', model.call_args.args[1][0]['text'])
        self.assertNotIn('lienzo', model.call_args.kwargs['output_schema']['properties']['layout']['enum'])

    def test_the_referents_visual_resource_is_a_label_read_defensively(self):
        piece = self.piece()
        self.assertEqual(editor_visual.referent_visual(piece), '')
        post = ObservedPost.objects.create(account=self.official, provider_post_id='urn:li:activity:1', media='documento',
                                           text='A referent post')
        for brief in ({'referent_post': str(post.id)}, {'referent': {'id': 'urn:li:activity:1'}},
                      {'evidence': [{'kind': 'referent_outlier', 'ref': str(post.id)}]}):
            with self.subTest(brief=brief):
                piece.brief = dict(piece.brief, **brief)
                self.assertEqual(editor_visual.referent_visual(piece), 'documento')
                piece.brief = {k: v for k, v in piece.brief.items() if k not in brief}
        for brief in ({'referent_post': 'not-a-post'}, {'referent_post': 42}, {'evidence': 'garbage'},
                      {'referents': [None, {'id': None}]}):
            with self.subTest(odd=brief):
                piece.brief = dict(piece.brief, **brief)
                self.assertEqual(editor_visual.referent_visual(piece), '')
                piece.brief = {k: v for k, v in piece.brief.items() if k not in brief}


class ImageResearchTests(FlowBase):
    def result(self, request):
        return research.ResearchResult(
            question=request.public_question, status='complete', researched_at=FIXED.isoformat(),
            sources=(research.Source('web:1', 'https://example.org/report', 'Report', 'In 2026, 62% of teams reviewed weekly.',
                                     FIXED.isoformat()),),
            usage={'input_tokens': 1000})

    def piece_with_thesis(self):
        piece = self.piece()
        piece.brief = dict(piece.brief, thesis='Las decisiones de producto empiezan antes que el código')
        piece.save()
        return piece

    def test_off_by_default_and_never_without_its_switch(self):
        piece = self.piece_with_thesis()
        with patch('team_backend.research.research', side_effect=AssertionError('paid research')):
            self.assertIsNone(imagenes.research_for_image(piece))
        self.assertEqual((piece.research, piece.usage), ([], []))

    def test_one_bounded_research_feeds_the_image_with_a_sourced_datum(self):
        piece = self.piece_with_thesis()
        run = orquestacion.Runtime.open('pieza_diaria', str(piece.id), self.gustavo)
        with patch.dict(os.environ, {'INFOGRAFIA_INVESTIGACION': 'true'}), \
                patch('team_backend.editorial.budget_left', return_value=Decimal('50')), \
                patch('team_backend.research.research', side_effect=self.result) as web:
            with run.session():
                note = imagenes.research_for_image(piece)
            with run.session():  # a resumed cycle replays it: no second request, no duplicate
                imagenes.research_for_image(piece)
        web.assert_called_once()
        request = web.call_args.args[0]
        self.assertEqual((request.key, request.purpose, request.search), (f'piece:{piece.id}:imagen', 'editorial-web-research', True))
        self.assertIn('Las decisiones de producto', request.public_question)
        self.assertEqual((note['state'], note['sources']), ('complete', 1))
        self.assertEqual(len(piece.research), 1)
        self.assertEqual(imagenes._usable(research.editorial_sources(piece))[0]['id'], 'web:1')
        calls = CycleLedger.objects.get(pk=run.id).progress_ledger['calls']
        self.assertEqual(calls[imagenes.RESEARCH_KEY]['edge'], 'investigar_pieza')
        self.assertEqual([u['stage'] for u in piece.usage], ['investigacion_imagen'])

    def test_it_is_skipped_and_says_why_when_it_does_not_fit(self):
        cases = [
            # 9 USD: more than the whole cycle's cap (8) can still hold.
            ('no room in the cycle', Decimal('9'), Decimal('50'), 'no cabe en el presupuesto del ciclo'),
            ('no AI budget today', None, Decimal('0.5'), 'no queda presupuesto de IA hoy'),
        ]
        for name, estimate, left, why in cases:
            with self.subTest(name):
                piece = self.piece_with_thesis()
                run = orquestacion.Runtime.open('pieza_diaria', str(piece.id), self.gustavo)
                with patch.dict(os.environ, {'INFOGRAFIA_INVESTIGACION': 'true'}), \
                        patch('team_backend.editorial.budget_left', return_value=left), \
                        (patch.object(imagenes, 'research_estimate', return_value=estimate) if estimate else nullcontext()), \
                        patch('team_backend.research.research', side_effect=AssertionError('paid research')):
                    with run.session():
                        note = imagenes.research_for_image(piece)
                self.assertEqual(note['state'], 'omitida')
                self.assertIn(why, note['reason'])
                self.assertEqual(piece.usage[-1]['stage'], 'investigacion_imagen')
        # The piece's own research was used by the director: the image does not ask a second time.
        piece = self.piece_with_thesis()
        run = orquestacion.Runtime.open('pieza_diaria', str(piece.id), self.gustavo)
        with patch.dict(os.environ, {'INFOGRAFIA_INVESTIGACION': 'true'}), \
                patch('team_backend.editorial.budget_left', return_value=Decimal('50')), \
                patch('team_backend.research.research', side_effect=self.result) as web:
            with run.session():
                story = research.ResearchRequest(key=f'piece:{piece.id}', public_question='Product decisions before code',
                                                 search=True, purpose='editorial-web-research')
                orquestacion.call('investigar_pieza', story, lambda: research.research(story))
                note = imagenes.research_for_image(piece)
        self.assertEqual(web.call_count, 1)
        self.assertEqual(note, {'state': 'omitida', 'reason': 'la pieza ya usó su investigación'})
        # A piece that already carries a sourced datum needs none.
        piece = self.piece_with_thesis()
        piece.research = [self.result(research.ResearchRequest(key='x', public_question='q')).to_dict()]
        piece.save()
        with patch.dict(os.environ, {'INFOGRAFIA_INVESTIGACION': 'true'}):
            self.assertEqual(imagenes.research_for_image(piece)['reason'], 'la pieza ya tiene datos con fuente')

    def test_the_reservation_arithmetic_leaves_room_for_the_image_stage(self):
        # The research is only asked when it AND the image calls after it fit the cycle: it can never stop the cycle.
        need = imagenes.research_estimate() + imagenes.stage_estimate('infografia')
        cycle = next(c for c in load_graph()['cycles'] if c['id'] == 'pieza_diaria')
        self.assertLess(need, Decimal(str(cycle['limits']['cost_cap_usd'])))
        self.assertGreater(imagenes.research_estimate(), Decimal('0'))


# --------------------------------------------------------------------------- redo the brand cards (operator)

class RedoBrandCardsTests(FlowBase):
    def setUp(self):
        super().setUp()
        self.grant(self.gustavo, 'run_agents', 'use_paid_providers', 'operate_linkedin')

    def ready(self, at, brand=True):
        piece = self.piece()
        piece.scheduled_for = at
        piece.slot_date = at.astimezone(operador.local_tz()).date()
        piece.citations = ['LI-06-M002-K09']
        piece.save()
        if brand:
            imagenes.brand_card(piece, 'Infografía rechazada tras una corrección: El cierre es una pregunta')
        else:
            with patch('knowledge.providers.claude', side_effect=Designer({'slides': [slide()]})):
                imagenes.prepare(piece, client=FakeImageConnector())
        public, private = guardas.blocks()
        editor_visual.bind(piece, public, private)
        piece.state = EditorialPiece.State.READY
        piece.save()
        proposal = operador.create_proposal(self.autobot, None, 'CONT-09',
            {'text': piece.final_text, 'media': imagenes.manifest(piece)}, rationale='Tesis', citations=piece.citations,
            source='agent', piece=piece)
        ActionProposal.objects.filter(pk=proposal.pk).update(state='approved', approved_hash=proposal.payload_hash)
        proposal.refresh_from_db()
        return piece, proposal

    def command(self, *extra):
        out = io.StringIO()
        call_command('operador', '--usuario', self.gustavo.username, 'rehacer-tarjetas', '--cuenta', str(self.official.id),
                     *extra, stdout=out)
        return out.getvalue()

    def test_dry_run_lists_with_the_cost_and_confirm_redoes_only_what_can_change(self):
        day = editorial.scheduled_for((FIXED + timedelta(days=3)).astimezone(operador.local_tz()).date())
        eligible, old = self.ready(day)
        close, close_old = self.ready(FIXED + timedelta(minutes=20))
        published, published_old = self.ready(day + timedelta(days=1))
        ActionExecution.objects.create(proposal=published_old, idempotency_key=uuid.uuid4().hex, provider='linkedin_fake',
                                       state='confirmed', executed_by=self.gustavo)
        designed, _ = self.ready(day + timedelta(days=2), brand=False)

        plan = {row['piece'].id: row for row in retoque.redo_plan(self.official)}
        self.assertEqual({k: v['action'] for k, v in plan.items()},
                         {eligible.id: 'rehacer', close.id: 'omitir', published.id: 'publicada'})
        self.assertNotIn(designed.id, plan)
        self.assertIn('Demasiado cerca de su hora', plan[close.id]['why'])
        self.assertEqual(plan[eligible.id]['estimate_usd'], imagenes.stage_estimate('infografia'))

        with patch('team_backend.editorial.budget_left', return_value=Decimal('50')), \
                patch('knowledge.providers.claude', side_effect=AssertionError('paid call in a dry run')):
            text = self.command()
        self.assertIn('Piezas con la tarjeta genérica: 3.', text)
        self.assertIn(f'Costo estimado (reserva máxima de diseño y revisión visual): '
                      f'{imagenes.stage_estimate("infografia"):.2f} USD para 1 pieza(s)', text)
        self.assertIn('publicada, no se puede cambiar', text)
        self.assertIn('Demasiado cerca de su hora', text)
        self.assertIn('Sin --confirmar no se cambia nada.', text)
        old.refresh_from_db()
        self.assertEqual((old.state, eligible.proposals.count()), ('approved', 1))

        designer = Designer({'slides': [slide()]})
        with patch('team_backend.editorial.budget_left', return_value=Decimal('50')), \
                patch('knowledge.providers.claude', side_effect=designer), \
                patch('team_backend.connectors_images.ImageConnector', return_value=FakeImageConnector()):
            text = self.command('--confirmar')
        self.assertIn('Rehechas: 1; fallidas: 0.', text)
        self.assertEqual(len(designer.calls), 1)
        self.assertIn(retoque.REDO_FINDING, designer.calls[0]['payload']['findings'])
        self.assertIsNone(designer.calls[0]['payload']['previous_design'])  # the brand card is not a model to follow
        eligible.refresh_from_db()
        old.refresh_from_db()
        new = eligible.proposals.get(state='proposed')
        self.assertEqual((old.state, new.previous_id), ('superseded', old.id))
        self.assertEqual((eligible.image_kind, eligible.images.get().template), ('infografia', 'pasos'))
        self.assertEqual(new.payload['media'], imagenes.manifest(eligible))
        self.assertEqual(eligible.scheduled_for, day)  # same hour: the veto window still fits
        self.assertTrue(AuditEvent.objects.filter(action='editorial.image_redone', target=str(eligible.id)).exists())
        self.assertEqual(CycleLedger.objects.get(cycle='retoque_pieza', key=f'imagen:{eligible.id}:{old.id}').state, 'complete')
        for piece, proposal in ((close, close_old), (published, published_old)):
            proposal.refresh_from_db()
            piece.refresh_from_db()
            self.assertEqual((piece.image_kind, piece.proposals.count()), ('tarjeta', 1))
        self.assertEqual(close_old.state, 'approved')
        # Done once: the redone piece no longer carries the brand card.
        self.assertNotIn(eligible.id, {row['piece'].id for row in retoque.redo_plan(self.official)})

    def test_without_ai_budget_nothing_is_superseded(self):
        day = editorial.scheduled_for((FIXED + timedelta(days=3)).astimezone(operador.local_tz()).date())
        piece, old = self.ready(day)
        with patch('team_backend.editorial.budget_left', return_value=Decimal('0.01')), \
                patch('knowledge.providers.claude', side_effect=AssertionError('paid call')):
            text = self.command('--confirmar')
        self.assertIn('No queda presupuesto de IA para rehacerla hoy', text)
        old.refresh_from_db()
        self.assertEqual(old.state, 'approved')
