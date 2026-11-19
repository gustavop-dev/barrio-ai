"""«Del post viral al post propio: el molde» (moldes.py, docs/plan-referentes-industria.md, REFERENTES_MOLDE).

A referent post far above its own author's norm becomes a mold: labels (hook, body, closing, length range, angle), its
source (id, author, link, times his median) and an honest estado. The weekly plan stores it in a day, the daily brief
carries it, copywriter A writes variant A on it while B stays free, the piece records which one won and the weekly
summary compares posts with and without a mold. Off, every prompt and request is the one of before. The clock is fixed
(a Wednesday at 10:00 in Bogotá): nothing here depends on the hour the suite runs."""
import json
import os
import uuid
from contextlib import ExitStack
from datetime import date, datetime, timedelta, timezone as dt_timezone
from unittest.mock import patch

from django.apps import apps
from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from team_backend import editorial, estrategia, identidad, moldes, resumen_semanal
from team_backend.models import (ActionExecution, ActionProposal, ConnectorAccount, EditorialPiece, Member, ObservedPost,
                                 Organization, PostMetric, Referent, WeeklyPlan)
from team_backend.tests import test_identidad_prompts as pins
from team_backend.tests.test_estrategia import StrategyBase
from team_backend.tests.test_publicacion import answers

NOW = datetime(2026, 11, 18, 15, 0, tzinfo=dt_timezone.utc)  # Wednesday 18/11/2026, 10:00 in Bogotá
MONDAY = date(2026, 11, 16)
THURSDAY, FRIDAY, SATURDAY, SUNDAY = (MONDAY + timedelta(days=i) for i in (3, 4, 5, 6))

ANA_LIST = ('Five habits that keep a small product team shipping every single week.\n\n'
            '1. Write the decision down before opening the ticket.\n2. Demo on Fridays even when the build is ugly.\n'
            '3. Cut one feature from every sprint plan.\n4. Keep the backlog under thirty items.\n'
            '5. Ask a customer before adding any scope.\n\nWhich habit would your team drop first?')
ANA_OPINION = ('Unpopular view: a roadmap full of features is a wish list with deadlines attached.\n\n'
               'Teams promise outcomes they cannot control and then report output instead.\n\n'
               'Name the bets, the evidence that would kill each one and who decides.\n\nWhat would you remove from yours?')
ANA_STORY = ('Two years ago our biggest client walked away in a single afternoon.\n\n'
             'We had shipped everything on the contract and nothing they actually used.\n\n'
             'Since then every kickoff starts with one question about the decision behind the request.\n\n'
             'That habit has saved more projects than any framework we tried.')
ANA_NORM = 'Notes from a calm sprint review number {n}: small fixes merged, nothing dramatic, everyone home on time.'
BETO_BEST = ('Three questions I ask before quoting any software project:\n\n- Who decides with this tool?\n'
             '- What does a wrong call cost them?\n- How often do they face that call?\n\n'
             'The answers set the scope better than a feature list. What do you ask first?')
BETO_NORM = 'A short reflection on client calls, round {n}: listen twice as long as you talk and write it all down.'
TEXTS = [ANA_LIST, ANA_OPINION, ANA_STORY, ANA_NORM, BETO_BEST, BETO_NORM]


def windows(text, size=20):
    plain = ' '.join(text.split())
    return {plain[i:i + size] for i in range(len(plain) - size + 1)}


def leaks(value):
    """Every 20-character window of a referent's text found in `value`, dumped: none means no sentence of theirs."""
    dumped = json.dumps(value, ensure_ascii=False, default=str)
    dumped = ' '.join(dumped.replace('\\n', ' ').split())
    return sorted(w for text in TEXTS for w in windows(text.replace('{n}', '')) if w in dumped)


def frozen(stack, moment=NOW):
    """The world at `moment`: timezone.now and the models' default dates (Django binds those when models load)."""
    stack.enter_context(patch('django.utils.timezone.now', return_value=moment))
    for model in apps.get_app_config('team_backend').get_models():
        for field in model._meta.fields:
            if getattr(field.default, '__module__', '') == 'django.utils.timezone':
                stack.enter_context(patch.object(field, '_get_default', new=lambda: timezone.now()))


def switch(on):
    return patch.dict(os.environ, {'REFERENTES_MOLDE': 'true' if on else 'false'})


class Referents:
    """Ana (industria) is the Top Voice: a norm of 40 interactions and three posts far above it, so the strict growth
    rule (atipico-v1) flags them. Beto (industria) is a small competitor: a norm of 4 to 5 and one post of 12, three
    times his own median but below every absolute threshold of the strict rule."""

    def referents(self, account):
        self.ana = self.referent(account, 'ana', 'Ana')
        self.beto = self.referent(account, 'beto', 'Beto')
        self.ana_list = self.post(account, self.ana, 'list', ANA_LIST, 400, 4)
        self.ana_opinion = self.post(account, self.ana, 'opinion', ANA_OPINION, 300, 6)
        self.ana_story = self.post(account, self.ana, 'story', ANA_STORY, 250, 9)
        for n in range(5):
            self.post(account, self.ana, f'norm{n}', ANA_NORM.format(n=n), 40, 10 + n)
        self.beto_best = self.post(account, self.beto, 'best', BETO_BEST, 12, 5)
        for n, score in enumerate((4, 5, 4)):
            self.post(account, self.beto, f'norm{n}', BETO_NORM.format(n=n), score, 7 + n)
        self.ids = {name: f'molde:{getattr(self, name).pk}' for name in ('ana_list', 'ana_opinion', 'ana_story', 'beto_best')}

    def referent(self, account, slug, name):
        return Referent.objects.create(account=account, public_identifier=slug, display_name=name, reason='Synthetic',
                                       kind='industria', provider_user_id='ACo' + slug)

    def post(self, account, referent, key, text, reactions, days_ago):
        slug = referent.public_identifier
        return ObservedPost.objects.create(
            account=account, referent=referent, provider_post_id=f'activity:{slug}:{key}',
            share_url=f'https://www.linkedin.com/feed/update/urn:li:activity:{slug}{key}', author_name=referent.display_name,
            author_provider_id=referent.provider_user_id, text=text, posted_at=NOW - timedelta(days=days_ago, hours=1),
            reactions_count=reactions, comments_count=0)


class CatalogTests(Referents, TestCase):
    """The offer: each referent's own best posts against his own norm, the small competitor included as a hypothesis,
    the dominant author capped; labels and a link, never a sentence."""

    def setUp(self):
        stack = ExitStack()
        self.addCleanup(stack.close)
        frozen(stack)
        stack.enter_context(switch(True))
        self.account = ConnectorAccount.objects.create(provider='fake', external_account_id='moldes-fake', label='Synthetic')
        self.referents(self.account)

    def test_each_author_brings_his_best_and_the_dominant_one_is_capped(self):
        catalog = moldes.catalog(NOW)
        offer = catalog.offer()
        self.assertEqual([m['id'] for m in offer], [self.ids['ana_list'], self.ids['beto_best'], self.ids['ana_opinion']])
        # Ana has three posts above her norm, all strict outliers: the offer keeps two (MOLDES_POR_AUTOR).
        self.assertTrue(all(catalog.perf[str(p.pk)]['strict'] for p in (self.ana_list, self.ana_opinion, self.ana_story)))
        self.assertIsNotNone(catalog.mold(self.ana_story.pk))
        with patch.dict(os.environ, {'MOLDES_POR_AUTOR': '1'}):
            self.assertEqual([m['id'] for m in moldes.catalog(NOW).offer()], [self.ids['ana_list'], self.ids['beto_best']])
        # An author whose molds already fill MOLDES_MAX_AUTOR_SEMANA days of the week is left out of that week's offer.
        self.assertEqual([m['id'] for m in catalog.offer({'ACoana': 2})], [self.ids['beto_best']])

    def test_the_small_competitor_brings_his_best_post_as_a_hypothesis_that_says_what_it_lacks(self):
        beto = next(m for m in moldes.catalog(NOW).offer() if m['id'] == self.ids['beto_best'])
        self.assertEqual((beto['estado'], beto['atipico_estricto']), ('hipotesis', False))
        self.assertEqual(beto['faltan'], ['menos de 6 posts propios de base'])
        self.assertEqual(beto['fuente'], {'post_id': str(self.beto_best.pk), 'referente_id': str(self.beto.pk), 'autor': 'Beto',
                                          'url': self.beto_best.share_url, 'publicado': self.beto_best.posted_at.isoformat(),
                                          'veces_mediana': 3.0, 'interacciones': 12, 'mediana_autor': 4, 'muestra': 3})
        self.assertEqual((beto['gancho']['tipo'], beto['cuerpo']['formato'], beto['cierre']['tipo']),
                         tuple(beto['firma'].split('·')))
        self.assertEqual((beto['longitud']['caracteres_min'], beto['longitud']['caracteres_max']), (600, 800))
        # His other posts are not above his norm: no mold for them, and none for a young post.
        self.assertEqual(len([m for m in moldes.catalog(NOW).offer() if m['fuente']['autor'] == 'Beto']), 1)
        young = self.post(self.account, self.beto, 'young', BETO_BEST.replace('Three', 'Four'), 90, 1)
        self.assertIsNone(moldes.catalog(NOW).mold(young.pk))
        # Strict outliers say nothing is missing; with the strict rule the small one stays out of growth models.
        ana = moldes.catalog(NOW).mold(self.ana_list.pk)
        self.assertEqual((ana['estado'], ana['atipico_estricto'], ana['faltan']), ('hipotesis', True, []))

    def test_a_structure_the_analysis_holds_as_sostenida_comes_first_and_says_so(self):
        firma = moldes.catalog(NOW).signature[str(self.ana_story.pk)]
        durable = {'firma': firma, 'estado': 'sostenida', 'posts_que_funcionaron': 4, 'autores': 2, 'semanas': 3}
        with patch.object(moldes.an, 'report', return_value={'estructuras_sostenidas': [durable]}):
            catalog = moldes.catalog(NOW)
            offer = catalog.offer()
            self.assertEqual(catalog.for_structure(f'estructura:{firma}'), offer[0])
        self.assertEqual(offer[0]['id'], self.ids['ana_story'])
        self.assertEqual((offer[0]['estado'], offer[0]['sostenida']),
                         ('sostenida', {'posts_que_funcionaron': 4, 'autores': 2, 'semanas': 3}))
        self.assertEqual([m['fuente']['autor'] for m in offer].count('Ana'), 2)  # still capped
        self.assertTrue(all(m['estado'] == 'hipotesis' for m in offer[1:]))

    def test_no_referent_text_reaches_a_writer_through_the_mold(self):
        self.assertTrue(leaks({'text': ANA_LIST}))  # the check finds a copied sentence
        catalog = moldes.catalog(NOW)
        offer = catalog.offer() + [catalog.mold(self.ana_story.pk)]
        self.assertEqual(leaks(offer), [])  # the whole mold: labels, numbers, author and link
        for mold in offer:
            writer = moldes.for_writer(mold)
            dumped = json.dumps(writer, ensure_ascii=False)
            self.assertEqual(leaks(writer), [])
            for value in (mold['fuente']['url'], mold['fuente']['autor'], mold['id'], str(mold['fuente']['post_id'])):
                self.assertNotIn(value, dumped)
            self.assertEqual(set(writer), {'estado', 'gancho', 'cuerpo', 'cierre', 'longitud', 'angulo', 'uso'})

    def test_the_brief_only_takes_a_mold_that_was_planned_or_offered(self):
        offer = moldes.catalog(NOW).offer()
        planned, other = offer[0], offer[1]
        strategy = {'extra': False, 'type': 'G', 'audience_signals': {}, 'planned': {'idea': 'x', 'molde': planned},
                    'moldes': offer}
        brief = lambda **pick: estrategia.finalize_brief(dict(pick), strategy)
        self.assertEqual(brief()['molde'], planned)  # no pick: the planned one
        self.assertEqual(brief(molde=other['id'])['molde'], other)  # another offered one
        # A «sostenida» structure's id: the first offered mold with that structure.
        self.assertEqual(brief(molde=f"estructura:{other['firma']}")['molde'],
                         next(m for m in offer if m['firma'] == other['firma']))
        self.assertNotIn('molde', brief(molde=''))  # none fits the day's topic
        self.assertNotIn('molde', brief(molde='molde:inventado'))  # never one the model made up
        without = {k: v for k, v in strategy.items() if k != 'moldes'}  # REFERENTES_MOLDE off: no offer in the input
        self.assertNotIn('molde', estrategia.finalize_brief({'molde': other['id']}, without))
        self.assertNotIn('molde', estrategia.finalize_brief({'molde': other['id']}, None))

    def test_a_week_keeps_at_most_two_days_on_one_author_and_his_locked_days_count_first(self):
        catalog = moldes.catalog(NOW)
        mold = {name: catalog.mold(getattr(self, name).pk) for name in ('ana_list', 'ana_opinion', 'ana_story', 'beto_best')}
        slots = [{'date': '2026-11-19', 'molde': mold['ana_list']}, {'date': '2026-11-20', 'molde': mold['beto_best']},
                 {'date': '2026-11-21', 'molde': mold['ana_opinion']},
                 {'date': '2026-11-22', 'molde': mold['ana_story'], 'owner_edited': True}]
        warnings = moldes.cap_week(slots, catalog)
        self.assertEqual([s.get('molde', {}).get('id') for s in slots],
                         [self.ids['ana_list'], self.ids['beto_best'], None, self.ids['ana_story']])
        self.assertEqual(warnings, ['El día 2026-11-21 va sin molde: ya hay 2 días con moldes de Ana esta semana.'])


class MoldFlowTests(Referents, StrategyBase):
    """The week and the day with REFERENTES_MOLDE on and off, through the real plan, the real editorial circuit and the
    fake Claude (no paid call)."""

    def setUp(self):
        stack = ExitStack()
        self.addCleanup(stack.close)
        frozen(stack)
        stack.enter_context(patch.dict(os.environ, {'STRATEGY_WEEK_TEMPLATE': 'G,G,G,G,G,G,G', 'STRATEGY_SALES_DOUBLE_EVERY': '0'}))
        super().setUp()
        self.assertEqual((self.today, estrategia.week_start(self.today)), (date(2026, 11, 18), MONDAY))
        self.referents(self.official)

    def called(self, purpose):
        found = [(data, system) for p, data, system in self.calls if p == purpose]
        self.assertEqual(len(found), 1, purpose)
        return found[0]

    def week_answer(self):
        """The planner bases Thursday on Ana's list post (its growth-model evidence), writes Friday on Beto's mold and
        Saturday on Ana's opinion post, and bases Sunday on a third post of Ana's."""
        outlier = lambda post: {'kind': 'referent_outlier', 'ref': str(post.pk), 'note': 'Superó con claridad su mediana.'}
        options = {THURSDAY: dict(self.option('Hábitos de un equipo que entrega cada semana', outlier(self.ana_list)), molde=''),
                   FRIDAY: dict(self.option('Tres preguntas antes de cotizar'), molde=self.ids['beto_best']),
                   SATURDAY: dict(self.option('Un roadmap como lista de apuestas'), molde=self.ids['ana_opinion']),
                   SUNDAY: dict(self.option('El cliente que se fue en una tarde', outlier(self.ana_story)), molde='')}
        return {'days': [{'date': d.isoformat(), 'options': [o]} for d, o in options.items()],
                'summary': 'Una semana sobre alcance.', 'signals_read': []}

    def plan_week(self):
        with self.claude({'plan': self.week_answer()}):
            plan = estrategia.run(self.gustavo, MONDAY)
        return plan, self.calls[-1]

    def slot(self, plan, day):
        return next(s for s in plan.slots if s['date'] == day.isoformat())

    def test_a_referent_outlier_becomes_the_mold_of_the_day_variant_a_is_written_on_it_and_b_stays_free(self):
        with switch(True):
            plan, (_, request, system) = self.plan_week()
            # The plan: the offer goes to the planner as labels and links, never a sentence of a referent.
            self.assertEqual([m['id'] for m in request['moldes']['ofrecidos']],
                             [self.ids['ana_list'], self.ids['beto_best'], self.ids['ana_opinion']])
            self.assertEqual(leaks(request['moldes']), [])
            self.assertIn('Moldes (moldes.ofrecidos)', system)
            # Thursday was based on Ana's post: its mold is stored with its link; Friday and Saturday on the molds named.
            thursday = self.slot(plan, THURSDAY)['molde']
            self.assertEqual((thursday['id'], thursday['fuente']['url'], thursday['fuente']['autor']),
                             (self.ids['ana_list'], self.ana_list.share_url, 'Ana'))
            self.assertEqual(self.slot(plan, FRIDAY)['molde']['id'], self.ids['beto_best'])
            self.assertEqual(self.slot(plan, SATURDAY)['molde']['id'], self.ids['ana_opinion'])
            # Sunday would be Ana's third day: it keeps its idea and goes without a mold.
            self.assertNotIn('molde', self.slot(plan, SUNDAY))
            self.assertEqual(self.slot(plan, SUNDAY)['idea'], 'El cliente que se fue en una tarde')
            self.assertIn('El día 2026-11-22 va sin molde: ya hay 2 días con moldes de Ana esta semana.', plan.warnings)
            # plan.signals.used records each mold, and the weekly summary's «plan_siguiente» reads it.
            used = [u for u in plan.signals['used'] if u['kind'] == 'molde']
            self.assertEqual([(u['date'], u['ref'], u['url']) for u in used],
                             [(THURSDAY.isoformat(), self.ids['ana_list'], self.ana_list.share_url),
                              (FRIDAY.isoformat(), self.ids['beto_best'], self.beto_best.share_url),
                              (SATURDAY.isoformat(), self.ids['ana_opinion'], self.ana_opinion.share_url)])
            self.assertEqual(plan.signals['offered']['moldes'], 3)
            self.assertIn({'fecha': FRIDAY.isoformat(), 'tipo': 'G', 'senal': 'molde',
                           'nota': f"{self.slot(plan, FRIDAY)['molde']['etiqueta']} (hipotesis)"},
                          resumen_semanal.next_plan(MONDAY - timedelta(days=7))['senales_usadas'])
            day = next(d for d in estrategia.payload(plan)['days'] if d['date'] == THURSDAY)
            self.assertEqual(day['molde'], moldes.summary(thursday))
            # The day: Thursday's piece.
            self.calls.clear()
            piece = self.plan(answers())
        self.assertEqual((piece.slot_date, piece.state), (THURSDAY, 'ready'), piece.note)
        director, director_system = self.called('editorial-director')
        self.assertEqual(director['strategy']['planned']['molde'], thursday)
        self.assertEqual([m['id'] for m in director['strategy']['moldes']],
                         [self.ids['ana_list'], self.ids['beto_best'], self.ids['ana_opinion']])
        self.assertIn('strategy.moldes', director_system)
        self.assertEqual(piece.brief['molde'], thursday)  # the brief carries it whole, link included
        writer, writer_system = self.called('editorial-redactor')
        self.assertEqual(writer['molde_variante_a'], moldes.for_writer(thursday))
        self.assertEqual((writer['molde_variante_a']['gancho']['tipo'], writer['molde_variante_a']['cuerpo']['formato'],
                          writer['molde_variante_a']['cierre']['tipo']), tuple(thursday['firma'].split('·')))
        self.assertIn('variant_b no usa el molde', writer_system)
        # Variant B's inputs (the shared brief and sources) carry no mold; only A's field does. No referent text, link,
        # author or id reaches the writers.
        self.assertEqual(set(writer), {'public_facts', 'private_guidance', 'orientation', 'brief', 'sources', 'course_units',
                                       'molde_variante_a'})
        self.assertNotIn('molde', json.dumps({k: v for k, v in writer.items() if k != 'molde_variante_a'}, ensure_ascii=False))
        self.assertEqual(leaks(writer), [])
        dumped = json.dumps(writer, ensure_ascii=False)
        for value in (self.ana_list.share_url, '"Ana"', thursday['id']):
            self.assertNotIn(value, dumped)
        # (The brief's audience_evidence already cited the post's id before molds; the mold adds no id of its own.)
        self.assertNotIn(str(self.ana_list.pk), json.dumps(writer['molde_variante_a'], ensure_ascii=False))
        # Readers, selection and verifier judge the texts blind: none of them is told which variant follows a mold.
        for purpose in ('editorial-lectores', 'editorial-seleccion', 'editorial-verificador'):
            self.assertNotIn('molde', json.dumps(self.called(purpose)[0], ensure_ascii=False), purpose)
        # The piece records its mold and the winning variant (the fake selection chose A: the mold's).
        self.assertEqual(piece.selection['molde'], {'id': thursday['id'], 'estado': 'hipotesis', 'variante': 'A',
                                                    'decision': 'A', 'ganadora': 'molde'})

    def test_the_director_may_pick_an_offered_mold_on_a_day_whose_plan_has_none(self):
        director = answers()
        director['director']['molde'] = self.ids['beto_best']
        with switch(True):
            piece = self.plan(director)
        strategy = self.called('editorial-director')[0]['strategy']
        self.assertIsNone(strategy['planned'])  # the day has the template's type and no planned idea
        self.assertIn(self.ids['beto_best'], [m['id'] for m in strategy['moldes']])
        self.assertEqual(piece.brief['molde']['id'], self.ids['beto_best'])
        self.assertEqual(self.called('editorial-redactor')[0]['molde_variante_a'], moldes.for_writer(piece.brief['molde']))
        self.assertEqual(piece.selection['molde']['ganadora'], 'molde')

    def test_with_the_switch_off_the_plan_and_the_day_are_the_ones_of_before(self):
        with switch(False):
            plan, (_, off_request, off_system) = self.plan_week()
            off_schema = estrategia.plan_schema()
        self.assertNotIn('moldes', off_request)
        self.assertNotIn('Moldes', off_system)
        self.assertFalse(any('molde' in s for s in plan.slots))
        self.assertFalse(any(u['kind'] == 'molde' for u in plan.signals['used']))
        self.assertNotIn('moldes', plan.signals['offered'])
        self.assertTrue(all('molde' not in d for d in estrategia.payload(plan)['days']))
        # The same week planned with the switch on: the request and the instructions only add the molds.
        with switch(True):
            plan, (_, on_request, on_system) = self.plan_week()
            on_schema = estrategia.plan_schema()
        self.assertEqual({k: v for k, v in on_request.items() if k != 'moldes'}, off_request)
        self.assertTrue(on_system.startswith(off_system) and on_system != off_system)
        option = on_schema['properties']['days']['items']['properties']['options']['items']
        self.assertEqual(option['required'][-1], 'molde')
        option['required'].pop()
        option['properties'].pop('molde')
        self.assertEqual(on_schema, off_schema)
        self.assertEqual(self.slot(plan, THURSDAY)['molde']['id'], self.ids['ana_list'])
        with switch(False):
            self.assertTrue(all('molde' not in d for d in estrategia.payload(plan)['days']))  # stored, not shown
        # Thursday's plan now stores a mold, and the switch goes off: the day is prepared as before.
        self.calls.clear()
        with switch(False):
            piece = self.plan(answers())
            systems = {name: editorial.stage_system(name) for name in ('director', 'redactor')}
        self.assertEqual((piece.slot_date, piece.state), (THURSDAY, 'ready'), piece.note)
        director, director_system = self.called('editorial-director')
        self.assertNotIn('moldes', director['strategy'])
        self.assertNotIn('molde', director['strategy']['planned'])
        self.assertEqual(director_system, systems['director'])
        writer, writer_system = self.called('editorial-redactor')
        self.assertEqual(set(writer), {'public_facts', 'private_guidance', 'orientation', 'brief', 'sources', 'course_units'})
        self.assertEqual(writer_system, systems['redactor'])
        self.assertNotIn('molde', piece.brief)
        self.assertNotIn('molde', piece.selection)
        for purpose, data, system in self.calls:
            self.assertNotIn('molde', json.dumps(data, ensure_ascii=False), purpose)
            self.assertNotIn('Moldes', system, purpose)


    def test_a_mold_moves_with_its_idea_and_a_new_idea_never_keeps_the_old_one(self):
        with switch(True):
            self.plan_week()
            estrategia.swap(self.gustavo, THURSDAY, SUNDAY)  # Sunday had no mold (Ana's third)
            estrategia.change(self.gustavo, SATURDAY, discard=True)
            plan = WeeklyPlan.objects.get(week_start=MONDAY)
        self.assertEqual(self.slot(plan, SUNDAY)['molde']['id'], self.ids['ana_list'])
        self.assertNotIn('molde', self.slot(plan, THURSDAY))
        self.assertNotIn('molde', self.slot(plan, SATURDAY))
        self.assertEqual(self.slot(plan, FRIDAY)['molde']['id'], self.ids['beto_best'])
        # Planned again with the switch off: Friday gets a new idea and loses the mold; the days he moved keep theirs.
        with switch(False):
            plan, _ = self.plan_week()
        self.assertNotIn('molde', self.slot(plan, FRIDAY))
        self.assertEqual(self.slot(plan, SUNDAY)['molde']['id'], self.ids['ana_list'])


class SwitchPromptTests(TestCase):
    """Off, the plan's, the director's and the writers' instructions and schemas hash as pinned
    (test_identidad_prompts); on, only the director's, the writers' and the plan's gain their mold block."""
    CHANGED = {'editorial.director', 'editorial.director_schema', 'editorial.redactor', 'estrategia.plan'}

    def setUp(self):
        stack = ExitStack()
        self.addCleanup(stack.close)
        frozen(stack)
        user = User.objects.create_user('gustavo-moldes')
        organization = Organization.objects.create(name='ProjectApp', slug='projectapp')
        self.member = Member.objects.create(organization=organization, user=user, display_name='Gustavo', role='Fundador',
                                            is_admin=True, created_at=NOW - timedelta(days=90))

    def texts(self):
        ident = identidad.of(self.member)
        out = {'estrategia.plan': estrategia.plan_system(ident)}
        for name in editorial.STAGES:
            out[f'editorial.{name}'] = editorial.stage_system(name, ident)
            out[f'editorial.{name}_schema'] = json.dumps(editorial.stage_schema(name, ident), ensure_ascii=False,
                                                         sort_keys=True, default=str)
        return out

    def test_off_every_text_is_pinned_and_on_only_the_mold_blocks_are_added(self):
        with switch(False):
            off = self.texts()
        self.assertEqual({k: v for k, v in pins.digests(off).items()}, {k: pins.PINNED[k] for k in off})
        with switch(True):
            on = self.texts()
        self.assertEqual({k for k in on if on[k] != off[k]}, self.CHANGED)
        ident = identidad.of(self.member)
        self.assertEqual(on['editorial.director'].replace(ident.render(editorial.MOLD_DIRECTOR_RULES), '', 1),
                         off['editorial.director'])
        self.assertEqual(on['editorial.redactor'].replace(ident.render(editorial.MOLD_WRITER_RULES), '', 1),
                         off['editorial.redactor'])
        self.assertEqual(on['estrategia.plan'], off['estrategia.plan'] + ident.render(estrategia.MOLD_PLAN_RULES))
        schema = json.loads(on['editorial.director_schema'])
        self.assertEqual(schema['properties'].pop('molde'), {'type': 'string'})
        self.assertNotIn('molde', schema['required'])  # optional: a brief without it stays valid
        self.assertEqual(json.dumps(schema, ensure_ascii=False, sort_keys=True), off['editorial.director_schema'])


class ComparisonTests(StrategyBase):
    """Each piece records its mold and which variant won; the weekly summary compares the posts written on a mold
    with the ones without one, and each mold's results. Data only."""
    ANA = {'id': 'molde:ana', 'etiqueta': 'Lista anunciada · Lista · Pregunta', 'estado': 'hipotesis',
           'fuente': {'autor': 'Ana', 'url': 'https://www.linkedin.com/feed/update/urn:li:activity:ana', 'veces_mediana': 10.0}}
    BETO = {'id': 'molde:beto', 'etiqueta': 'Pregunta · Lista · Pregunta', 'estado': 'hipotesis',
            'fuente': {'autor': 'Beto', 'url': 'https://www.linkedin.com/feed/update/urn:li:activity:beto', 'veces_mediana': 3.0}}

    def setUp(self):
        stack = ExitStack()
        self.addCleanup(stack.close)
        frozen(stack)
        super().setUp()

    def published(self, day, mold=None, won=None, impressions=None):
        when = datetime(day.year, day.month, day.day, 13, 30, tzinfo=dt_timezone.utc)
        selection = {'decision': {'molde': 'A', 'libre': 'B', 'fusion': 'merge'}[won]} if mold else {'decision': 'A'}
        if mold:
            selection['molde'] = moldes.outcome(mold, selection)
        piece = EditorialPiece.objects.create(account=self.official, slot_date=day, scheduled_for=when, state='ready',
                                              final_text=f'Post {day}', brief={'molde': mold} if mold else {},
                                              selection=selection)
        proposal = ActionProposal.objects.create(account=self.official, piece=piece, capability='CONT-09',
                                                 payload={'text': piece.final_text}, payload_hash='0' * 64, state='confirmed')
        ActionExecution.objects.create(proposal=proposal, idempotency_key=uuid.uuid4().hex, provider='linkedin_fake',
                                       state='confirmed', executed_by=self.gustavo, started_at=when)
        if impressions is not None:
            PostMetric.objects.create(piece=piece, kind='72h', impressions=impressions, reactions=impressions // 50,
                                      comments=2, reposts=0, published_at=when)
        return piece

    def test_the_winning_variant_is_recorded_and_the_comparison_counts_it(self):
        self.assertEqual(moldes.outcome(self.ANA, {'decision': 'B'}),
                         {'id': 'molde:ana', 'estado': 'hipotesis', 'variante': 'A', 'decision': 'B', 'ganadora': 'libre'})
        self.published(date(2026, 10, 27), self.ANA, 'molde', 1000)
        self.published(date(2026, 11, 3), self.ANA, 'libre', 600)
        self.published(date(2026, 11, 10), self.BETO, 'molde', 1400)
        self.published(date(2026, 11, 12), self.ANA, 'fusion')  # its 72 h cut is not there yet
        self.published(date(2026, 11, 13), impressions=800)
        self.published(date(2026, 10, 20), self.BETO, 'molde', 9000)  # five weeks back: outside the comparison
        with switch(True):
            found = resumen_semanal.molds(MONDAY)
            stats = resumen_semanal.stats(MONDAY, now=NOW)
        self.assertEqual((found['desde'], found['hasta']), ('2026-10-26', '2026-11-22'))
        groups = found['grupos']
        self.assertEqual({k: (v['publicados'], v['medidos_72h'], v['mediana_impresiones_72h']) for k, v in groups.items()},
                         {'con_molde': (2, 2, 1200), 'libre_le_gano_al_molde': (1, 1, 600), 'fusion': (1, 0, None),
                          'sin_molde': (1, 1, 800)})
        self.assertTrue(all(v['muestra_pequena'] for v in groups.values()))  # fewer than three measured: a hint
        self.assertEqual(found['ganadora'], {'molde': 2, 'libre': 1, 'fusion': 1, 'sin_dato': 0})
        self.assertEqual([(r['id'], r['autor'], r['url'], r['publicados'], r['duelos'], r['resultados_con_su_texto']['publicados'],
                           r['resultados_con_su_texto']['mediana_impresiones_72h']) for r in found['por_molde']],
                         [('molde:ana', 'Ana', self.ANA['fuente']['url'], 3, {'molde': 1, 'libre': 1, 'fusion': 1}, 1, 1000),
                          ('molde:beto', 'Beto', self.BETO['fuente']['url'], 1, {'molde': 1}, 1, 1400)])
        self.assertEqual(stats['moldes'], found)
        with switch(False):
            self.assertNotIn('moldes', resumen_semanal.stats(MONDAY, now=NOW))
        self.assertEqual(resumen_semanal.molds(MONDAY + timedelta(days=70))['disponible'], False)
