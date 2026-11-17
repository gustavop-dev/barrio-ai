"""«Qué les funciona y qué no» to the industry referents (analisis_referentes.py): each post taken apart and cached, each
counter against its own author's median with the minimum sample, what works across posts, authors and weeks told apart
from what is news this week, the editorial's two signals without any sentence of a referent, the switch and the
endpoint. Synthetic posts only; no LinkedIn and no paid provider."""
from datetime import timedelta
from unittest.mock import patch
import json
import os

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from linkedin_directo import lectura
from team_backend import analisis_referentes as an, estrategia, modelos_crecimiento as mc, posicionamiento
from team_backend.models import ConnectorAccount, ObservedPost, Referent

BASE = 'Notes on our delivery process. We review every pull request the same day and deploy small changes.'
LIST = ('5 lessons from shipping {n} MVPs for founders:\n\n- Cut scope early\n- Ship weekly\n- Talk to users\n'
        '- Measure activation\n- Keep one payment provider\n\nWhich one would you add?')
NEWS = ('OpenAI just announced GPT-5 at DevDay, and most founders will rush to rebuild.\n\n'
        'We tested it on a client MVP before deciding.\n\nWhat would you test first?')
DEVDAY = 'Three notes from the DevDay keynote for teams that build products.\n\nScope stays the hard part.\n\nThat is my take.'
CONTRARIAN = 'Nobody tells you that agencies fail on handoffs.\n\nThe code is rarely the problem.\n\nThe handoff is.'
FLOP = 'Is remote work over for engineering teams?'
SUMMIT = 'We spoke at Acme Summit about delivery and review habits for small teams.'
TEXTS = [BASE, LIST.format(n=12), LIST.format(n=30), LIST.format(n=7), NEWS, DEVDAY, CONTRARIAN, FLOP, SUMMIT]
DURABLE = 'lista_anunciada·lista·pregunta'


def windows(text, size=20):
    plain = ' '.join(text.split())
    return {plain[i:i + size] for i in range(len(plain) - size + 1)}


def leaks(value):
    dumped = json.dumps(value, ensure_ascii=False)
    return sorted(w for text in TEXTS for w in windows(text) if w in dumped)


class AnalysisData:
    """Ana (industria): a norm of 45 interactions, two list posts far above it in different weeks, two one-line
    questions far below, a post about DevDay and a young one. Beto (industria): a norm of 30, a list post far above it,
    a news post far above it and a contrarian one far above it. Ciro (industria) has three posts only; Nico is a niche
    voice. Ana and Beto both named Acme Summit 40 days ago and DevDay two days ago."""

    def build(self):
        self.now = timezone.now()
        self.account = ConnectorAccount.objects.create(provider='fake', external_account_id='analisis-fake', label='Synthetic')
        self.ana, self.beto, self.ciro = (Referent.objects.create(account=self.account, public_identifier=slug, display_name=name,
                                                                  reason='Synthetic', kind='industria', provider_user_id='ACo' + slug)
                                          for slug, name in (('ana-test', 'Ana'), ('beto-test', 'Beto'), ('ciro-test', 'Ciro')))
        self.nico = Referent.objects.create(account=self.account, public_identifier='nico-test', display_name='Nico', reason='Synthetic',
                                            kind='nicho', provider_user_id='ACoNico')
        self.n = 0
        for d in range(20, 60, 5):
            self.post(self.ana, d, 40, 5, BASE, reposts=1)
            self.post(self.beto, d + 1, 25, 5, BASE)
        self.ana_summit, self.beto_summit = self.post(self.ana, 40.5, 40, 5, SUMMIT, reposts=1), self.post(self.beto, 40.2, 25, 5, SUMMIT)
        self.ana_list = self.post(self.ana, 3, 300, 40, LIST.format(n=12), reposts=12)
        self.ana_list2 = self.post(self.ana, 17, 300, 40, LIST.format(n=30), reposts=1)
        self.flops = [self.post(self.ana, d, 10, 0, FLOP, reposts=0) for d in (5, 8)]
        self.ana_devday = self.post(self.ana, 2.1, 40, 5, DEVDAY, reposts=1)
        self.young = self.post(self.ana, 0.5, 900, 90, LIST.format(n=7))
        self.beto_list = self.post(self.beto, 10, 200, 20, LIST.format(n=7))
        self.beto_news = self.post(self.beto, 2, 400, 60, NEWS)
        self.beto_contrarian = self.post(self.beto, 24, 150, 15, CONTRARIAN)
        self.ciro_posts = [self.post(self.ciro, d, 500, 50, LIST.format(n=d)) for d in (3, 10, 17)]
        self.nico_list = [self.post(self.nico, d, 900, 90, LIST.format(n=d)) for d in (4, 11, 18)]

    def post(self, referent, days, reactions, comments, text, reposts=None):
        self.n += 1
        return ObservedPost.objects.create(account=self.account, referent=referent, provider_post_id=f'activity:{self.n}',
            share_url=f'https://www.linkedin.com/feed/update/urn:li:activity:{self.n}', author_name=referent.display_name,
            author_provider_id=referent.provider_user_id, text=text, posted_at=self.now - timedelta(days=days),
            reactions_count=reactions, comments_count=comments, reposts_count=reposts)


class DecompositionTests(SimpleTestCase):
    def test_a_post_is_taken_apart_in_labels_tied_to_gustavos_pillars(self):
        post = ObservedPost(text=LIST.format(n=12), media='documento')
        parts = an.decompose(post)
        self.assertEqual((parts['tema'], parts['pilar'], parts['firma']), ('mvp_alcance', 'business_to_product', DURABLE))
        self.assertEqual(parts['partes']['recurso_visual'], {'tipo': 'documento', 'detalle': 'no_disponible'})
        self.assertEqual(parts['partes']['gancho'], {'tipo': 'lista_anunciada', 'palabras': 8, 'linea_propia': True})
        self.assertEqual((parts['partes']['cuerpo']['formato'], parts['partes']['cuerpo']['items_lista']), ('lista', 5))
        self.assertEqual(parts['partes']['cierre'], {'tipo': 'pregunta', 'cta': True})
        self.assertEqual(parts['partes']['longitud']['banda'], 'corto')
        self.assertEqual((parts['senales_coyuntura'], parts['apto']), ([], True))
        self.assertEqual(leaks({k: v for k, v in parts.items() if k != 'nombres'}), [])
        self.assertLessEqual(set(an.PILLAR_OF.values()), set(posicionamiento.PILLARS))
        self.assertEqual(set(an.PILLAR_OF), set(mc.THEMES))

    def test_news_dates_and_releases_are_topical_signals_and_a_title_case_line_is_no_name(self):
        news = an.decompose(ObservedPost(text=NEWS))
        self.assertEqual(news['senales_coyuntura'], ['menciona_noticia', 'menciona_lanzamiento'])
        self.assertEqual(news['nombres'], ['gpt-5', 'devday'])
        self.assertEqual(an.decompose(ObservedPost(text='Our numbers for Q3 2026 and what changed this week.'))['senales_coyuntura'],
                         ['menciona_fecha'])
        self.assertEqual(an._names('Stop Building Features Nobody Wants\nWe met Acme Labs in Austin.'), ['acme labs', 'austin'])
        self.assertEqual(an.decompose(ObservedPost(text=FLOP))['firma'], 'pregunta·pregunta_abierta·pregunta')
        self.assertEqual(an.decompose(ObservedPost(text=CONTRARIAN))['partes']['cuerpo']['formato'], 'opinion_contraria')
        self.assertFalse(an.decompose(ObservedPost(text="We're hiring senior engineers. Apply now."))['apto'])

    def test_the_connector_names_the_media_it_recognizes_and_never_guesses_text_only(self):
        image = {'com.linkedin.voyager.feed.render.ImageComponent': {'images': [{}, {}]}}
        self.assertEqual(lectura.media({'content': image}), 'imagenes')
        self.assertEqual(lectura.media({'content': {'com.linkedin.voyager.feed.render.ImageComponent': {'images': [{}]}}}), 'imagen')
        self.assertEqual(lectura.media({'content': {'com.linkedin.voyager.feed.render.LinkedInVideoComponent': {}}}), 'video')
        self.assertEqual(lectura.media({'content': {'com.linkedin.voyager.feed.render.DocumentComponent': {}}}), 'documento')
        self.assertEqual(lectura.media({'content': {'$type': 'com.linkedin.voyager.feed.render.PollComponent'}}), 'encuesta')
        self.assertEqual(lectura.media({'content': {'com.linkedin.voyager.feed.render.SomethingNew': {}}}), 'otro')
        self.assertEqual(lectura.media({}), '')
        self.assertEqual(lectura.media({'content': None}), '')


class ReportTests(AnalysisData, TestCase):
    def setUp(self):
        self.build()

    def test_each_counter_is_compared_with_its_own_authors_median_and_judged_only_with_a_sample(self):
        data = an.report(self.account, now=self.now)
        standout = {s['post_id']: s for s in data['destacados']}
        top = standout[str(self.ana_list.pk)]
        self.assertEqual(top['veredicto'], 'funciono')
        self.assertEqual(top['metricas']['reacciones'], {'valor': 300, 'mediana_autor': 40, 'veces': 7.5, 'muestra': 13})
        self.assertEqual(top['metricas']['comentarios'], {'valor': 40, 'mediana_autor': 5, 'veces': 8.0, 'muestra': 13})
        self.assertEqual(top['metricas']['compartidos'], {'valor': 12, 'mediana_autor': 1, 'veces': 12.0, 'muestra': 13})
        self.assertEqual(top['metricas']['interacciones']['mediana_autor'], 45)
        self.assertEqual(standout[str(self.flops[0].pk)]['veredicto'], 'no_funciono')
        self.assertEqual(standout[str(self.flops[0].pk)]['metricas']['interacciones']['veces'], 0.22)
        self.assertEqual(standout[str(self.beto_list.pk)]['metricas']['compartidos'], {'valor': None, 'mediana_autor': None,
                                                                                         'veces': None, 'muestra': 0})
        self.assertNotIn(str(self.young.pk), standout)  # 12 h old: not judged yet, however big
        rows = {r['nombre']: r for r in data['referentes']}
        self.assertEqual({k: rows['Ana'][k] for k in ('posts', 'funciono', 'no_funciono', 'sin_juicio')},
                         {'posts': 15, 'funciono': 2, 'no_funciono': 2, 'sin_juicio': 1})
        self.assertEqual((rows['Ciro']['sin_juicio'], rows['Ciro']['funciono'], rows['Ciro']['muestra_pequena']), (3, 0, True))
        self.assertNotIn('Nico', rows)
        self.assertEqual(data['umbrales']['min_posts_base'], 6)
        self.assertIn('≥2x su mediana', data['umbrales']['funciono'])

    def test_what_works_across_authors_and_weeks_is_durable_and_news_or_a_single_post_is_not(self):
        data = an.report(self.account, now=self.now)
        durable = {s['firma']: s for s in data['estructuras_sostenidas']}
        self.assertEqual({k: durable[DURABLE][k] for k in ('estado', 'posts_que_funcionaron', 'autores', 'semanas')},
                         {'estado': 'sostenida', 'posts_que_funcionaron': 3, 'autores': 2, 'semanas': 3})
        self.assertEqual(durable[DURABLE]['etiqueta'], 'Lista anunciada · Lista · Pregunta')
        once = durable['contraste·opinion_contraria·afirmacion']
        self.assertEqual(once['estado'], 'hipotesis')
        self.assertEqual(len(once['faltan']), 3)
        # The news post worked, but news did: its structure is not a model.
        self.assertNotIn(an.decompose(self.beto_news)['firma'], durable)
        news = next(s for s in data['destacados'] if s['post_id'] == str(self.beto_news.pk))
        self.assertEqual(news['coyuntura'], {'flag': True, 'referentes_misma_semana': 2,
                                             'senales': ['menciona_noticia', 'menciona_lanzamiento', 'varios_referentes_misma_semana']})
        below = {s['firma']: s for s in data['estructuras_por_debajo']}
        self.assertEqual((below['pregunta·pregunta_abierta·pregunta']['no_funciono'],
                          below['pregunta·pregunta_abierta·pregunta']['muestra_pequena']), (2, True))
        formats = {g['valor']: g for g in data['por_parte']['formato']}
        # Seven list posts; only three with a verdict (the young one and Ciro's lack a base).
        self.assertEqual((formats['lista']['funciono'], formats['lista']['posts'], formats['lista']['con_juicio']), (3, 7, 3))
        self.assertEqual((formats['opinion_contraria']['posts'], formats['opinion_contraria']['muestra_pequena']), (1, True))
        self.assertEqual({g['valor'] for g in data['por_parte']['recurso_visual']}, {'desconocido'})

    def test_a_topic_trends_while_several_referents_talk_about_it_and_then_expires(self):
        trends = {r['id']: r for r in an.report(self.account, now=self.now)['temas_en_tendencia']}
        devday = trends['tendencia:nombre:devday']
        self.assertEqual((devday['autores'], devday['posts'], devday['por']), (2, 2, 'varios_referentes_misma_semana'))
        self.assertEqual(devday['expira'], (self.beto_news.posted_at + timedelta(days=14)).isoformat())  # its last post
        # Acme Summit (40 days ago) expired; the topic of Beto's news post that worked is current.
        self.assertEqual(set(trends), {'tendencia:nombre:devday', 'tendencia:tema:mvp_alcance'})
        news = trends['tendencia:tema:mvp_alcance']
        self.assertEqual((news['por'], news['posts'], news['autores'], news['funcionaron']), ('coyuntura_que_funciono', 1, 1, 1))
        later = an.report(self.account, now=self.now + timedelta(days=15))['temas_en_tendencia']
        self.assertNotIn('tendencia:nombre:devday', {r['id'] for r in later})

    def test_the_decomposition_is_stored_once_per_text_and_redone_when_the_text_changes(self):
        with patch.object(an, 'decompose', wraps=an.decompose) as parts:
            an.report(self.account, now=self.now)
            first = parts.call_count
            an.report(self.account, now=self.now)
            self.assertEqual(parts.call_count, first)
            self.ana_list.text = LIST.format(n=13) + '\n\nP.S. Save this.'
            self.ana_list.save(update_fields=['text'])
            an.report(self.account, now=self.now)
            self.assertEqual(parts.call_count, first + 1)
        self.assertEqual(first, ObservedPost.objects.filter(referent__kind='industria').count())
        self.ana_list.refresh_from_db()
        self.assertEqual((self.ana_list.analysis['rule'], self.ana_list.analysis['tema']), (an.RULE, 'mvp_alcance'))
        self.assertEqual(ObservedPost.objects.get(pk=self.nico_list[0].pk).analysis, {})

    def test_the_report_carries_labels_numbers_and_links_never_a_sentence_of_a_post(self):
        data = an.report(self.account, now=self.now)
        self.assertEqual(leaks(data), [])
        urls = {s['post_id']: s['url'] for s in data['destacados']}
        self.assertEqual(urls[str(self.ana_list.pk)], self.ana_list.share_url)
        self.assertEqual(urls, {str(p.pk): p.share_url for p in ObservedPost.objects.filter(pk__in=list(urls))})


class EditorialSignalTests(AnalysisData, TestCase):
    def setUp(self):
        self.build()

    def test_with_the_switch_on_the_editorial_gets_durable_structures_and_current_topics_apart_without_text(self):
        with patch.dict(os.environ, {'REFERENTES_ANALISIS': 'true'}):
            signals = estrategia.audience_signals(self.now)
        structures, trends = signals['estructura_sostenida'], signals['tema_en_tendencia']
        self.assertEqual((structures[0]['id'], structures[0]['estado']), (f'estructura:{DURABLE}', 'sostenida'))
        self.assertIn('hipotesis', {s['estado'] for s in structures})
        self.assertIn('nunca frases', structures[0]['uso'])
        devday = next(t for t in trends if t['id'] == 'tendencia:nombre:devday')
        self.assertEqual(devday['expira'], (self.beto_news.posted_at + timedelta(days=14)).isoformat())
        self.assertEqual(leaks([structures, trends]), [])
        self.assertNotIn('estructura_sostenida', estrategia.EVIDENCE_KINDS)

    def test_with_the_switch_off_the_editorial_reads_what_it_read_before(self):
        with patch.dict(os.environ, {'REFERENTES_ANALISIS': ''}), \
             patch.object(an, 'report', side_effect=AssertionError('not with the switch off')):
            signals = estrategia.audience_signals(self.now)
        self.assertEqual(set(signals), {'referent_outlier', 'comment_question', 'owner_capture', 'results_by_type', 'audience_question'})
        self.assertFalse(ObservedPost.objects.exclude(analysis={}).exists())

    def test_a_failure_of_the_analysis_never_takes_the_editorial_signals_down(self):
        with patch.dict(os.environ, {'REFERENTES_ANALISIS': 'true'}), patch.object(an, 'report', side_effect=RuntimeError('boom')), \
             self.assertLogs('team_backend.estrategia', 'ERROR'):
            signals = estrategia.audience_signals(self.now)
        self.assertNotIn('estructura_sostenida', signals)
        self.assertIn('referent_outlier', signals)


@override_settings(REFERENTS_GUSTAVO_USERNAME='gustavo')
class EndpointTests(AnalysisData, TestCase):
    def setUp(self):
        self.build()
        self.client = APIClient()

    def test_gustavo_reads_the_analysis_and_bad_parameters_or_no_permission_are_refused(self):
        self.client.force_authenticate(get_user_model().objects.create_user('gustavo', is_superuser=True))
        answer = self.client.get('/api/v1/referentes/analisis', {'account': str(self.account.pk)})
        self.assertEqual(answer.status_code, 200)
        data = answer.json()
        self.assertEqual(set(data), {'activo', 'regla', 'umbrales', 'muestra', 'referentes', 'destacados', 'por_parte',
                                     'estructuras_sostenidas', 'estructuras_por_debajo', 'temas_en_tendencia', 'limites'})
        self.assertEqual((data['activo'], data['muestra']['referentes']), (False, 3))
        self.assertEqual(leaks(data), [])
        self.assertEqual(self.client.get('/api/v1/referentes/analisis', {'dias': '3'}).status_code, 400)
        self.assertEqual(self.client.get('/api/v1/referentes/analisis', {'account': 'no-es-uuid'}).status_code, 400)
        self.assertEqual(self.client.get('/api/v1/referentes/analisis', {'account': '00000000-0000-0000-0000-000000000000'}).status_code, 404)
        self.assertEqual(self.client.get('/api/v1/referentes/analisis', {'dias': '30'}).json()['muestra']['dias'], 30)
        self.client.force_authenticate(get_user_model().objects.create_user('sin-permiso'))
        self.assertEqual(self.client.get('/api/v1/referentes/analisis').status_code, 403)
