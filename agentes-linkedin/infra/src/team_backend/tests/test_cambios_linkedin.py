"""LinkedIn cambió la página (cambios_linkedin, 19/11/2026), the incident rebuilt: the post page writes the `<` of the
comment box's template as a JavaScript `\\x3C`, and the parser of before the fix (simulated: it reads no JavaScript
escape) cannot read any createComment template. The canary must find the comment writes broken without writing; Slack
must say it once, in plain words; the flows report must turn the comments flow red; a comment that fails for it in use
must make the other comments wait, approved, without another read; and a canary that passes again (the fix deployed)
must let them go and say «recuperado».

Every LinkedIn answer is an invented fixture (directo_fixtures.py); Slack is an httpx.MockTransport (SlackBase); the
clock is frozen (FlowsBase); nothing reaches a network or a provider."""
import io
import re
from unittest.mock import patch
from django.core.management import call_command
from linkedin_directo import rutas
from team_backend import autopiloto, cambios_linkedin, canario, connectors_directo, flujos, jobs, operador
from team_backend.models import ActionProposal, AuditEvent, ConnectorAccount, Job, ObservedPost
from team_backend.tests import directo_fixtures as F
from team_backend.tests.directo_fixtures import ANA, OWN, POST, ok
from team_backend.tests.test_alertas_slack import SUMMARY
from team_backend.tests.test_canario import routes
from team_backend.tests.test_estado_flujos import FlowsBase
from team_backend.tests.test_linkedin_directo import sdui
from team_backend.tests.test_ventana_lectura import at

PAGE = r'^/feed/update/urn:li:activity:\d+/$'
OLD_PARSER = re.compile(r'(?!x)x')  # rutas.JS_HEX before the fix of 19/11/2026: no `\xHH` escape is read
# Values of the fixtures that must never reach Slack, the report or the audit: ids, names, the account's label.
PRIVATE = (POST, F.OTHER_POST, F.COMMENT_A, OWN[0], OWN[1], ANA[0], 'Ana', 'Cuenta directa de prueba', 'secreto-ficticio')
TEXT = 'Evals are where most of the work hides. Which failure modes do you test first?'


def page_of_19_11():
    """The post page as LinkedIn began to write it on 19/11/2026: the `<` of optimisticKey as `\\x3C`."""
    return F.html(F.post_page(POST, (F.COMMENT_A,)).text.replace('<PrefixToExecutionId>', '\\x3CPrefixToExecutionId>'))


class ChangeBase(FlowsBase):
    def setUp(self):
        super().setUp()
        push = patch('team_backend.alerts.notify')
        push.start()
        self.addCleanup(push.stop)
        self.directo = ConnectorAccount.objects.create(provider='directo', external_account_id='cuenta-prueba',
                                                       label='Cuenta directa de prueba')
        written = F.comment_written(POST, F.snowflake(at(18), 9), TEXT)
        self.transport = F.FakeTransport(('GET', PAGE, page_of_19_11()), sdui(rutas.COMMENT, written),
                                         *routes(ok(F.profile_views(37))))
        fake = patch.object(connectors_directo, 'TRANSPORT', self.transport)
        fake.start()
        self.addCleanup(fake.stop)
        self.parser = patch.object(rutas, 'JS_HEX', OLD_PARSER)
        self.parser.start()
        self.fixed = False
        self.addCleanup(lambda: self.fixed or self.parser.stop())

    def fix(self):
        """#147 deployed: the parser reads the page's escapes. The page stays as LinkedIn writes it now."""
        self.parser.stop()
        self.fixed = True

    def changes(self):
        return AuditEvent.objects.filter(action=cambios_linkedin.CHANGED, target=str(self.directo.id))

    def found(self):
        """{flow: [its «LinkedIn cambió la página» findings]} of the report at the frozen clock."""
        results = flujos.informe(self.clock)
        self.report = {r.flujo.id: r for r in results}
        return {r.flujo.id: [h.texto for h in r.hallazgos if h.texto.startswith('LinkedIn cambió la página')]
                for r in results if any(h.texto.startswith('LinkedIn cambió la página') for h in r.hallazgos)}

    def new_alerts(self, now):
        """What a watcher round adds to the alerts channel (the flows report goes to its own channel)."""
        before = len(self.texts())
        self.watch(now)
        return self.texts()[before:]

    def private_never_shown(self):
        shown = '\n'.join(self.texts() + self.texts(SUMMARY)) + str(list(self.changes().values_list('metadata', flat=True)))
        for value in PRIVATE:
            self.assertNotIn(value, shown)


class CanaryFindsTheChangeTests(ChangeBase):
    def test_the_canary_finds_the_comment_writes_broken_slack_says_it_once_the_flow_turns_red_and_then_recovers(self):
        self.clock = at(16)
        log = canario.run(self.directo, now=self.clock)
        self.assertEqual((log.state, log.calls, canario.failing(log)), ('roto', 17, ['create_comment', 'comment_in_thread']))
        self.assertFalse(any(r.write for r in self.transport.sent))  # it only read
        row = next(r for r in log.operations if r['operacion'] == 'create_comment')
        self.assertEqual({k: row['diagnostico'][k] for k in ('apariciones', 'leidas', 'error', 'campo')},
                         {'apariciones': 3, 'leidas': 0, 'error': 'Invalid \\escape', 'campo': 'optimisticKey'})
        # Slack, at once and in plain words: what cannot be done, what stops, that nothing was sent and how to retry.
        texts = self.texts()
        self.assertEqual(len(texts), 2)
        comment, reply = sorted(texts, key=lambda t: '(comment_in_thread)' in t)
        for part in ('Barrio · LinkedIn cambió la página: la prueba de LinkedIn de las 16:00 encontró que no se puede comentar '
                     'en un post (create_comment); si sigue así, no salen comentarios en posts de otros. La prueba no envió '
                     'nada.', 'campo «optimisticKey»', 'prueba-linkedin'):
            self.assertIn(part, comment)
        self.assertIn('no se puede responder un comentario (comment_in_thread); si sigue así, no salen respuestas a los '
                      'comentarios de tus posts', reply)
        # Once: the watcher, and the same broken canary later that day, say nothing new.
        self.assertEqual(self.new_alerts(at(16, 10)), [])
        [report] = self.texts(SUMMARY)  # the watcher's only message is the flows report, in its own channel, red
        self.assertIn('🔴 *Comentarios en referentes*: LinkedIn cambió la página: no se puede comentar en un post '
                      '(create_comment) desde las 16:00 (en la prueba de LinkedIn): no salen comentarios en posts de otros.',
                      report)
        self.assertIn('🔴 *Respuestas en tus posts*: LinkedIn cambió la página', report)
        self.clock = at(16, 30)
        canario.run(self.directo, now=self.clock)
        self.assertEqual((len(self.texts()), self.changes().filter(metadata__operacion='create_comment').count()), (2, 1))
        # The flows report: the comments and replies flows red with the plain reason; the day's canary line in «salud».
        self.clock = at(16, 40)
        found = self.found()
        self.assertEqual(found['comentarios'], ['LinkedIn cambió la página: no se puede comentar en un post (create_comment) '
                                                'desde las 16:00 (en la prueba de LinkedIn): no salen comentarios en posts de '
                                                'otros.'])
        self.assertEqual(self.report['comentarios'].estado, flujos.ROJO)
        self.assertEqual(set(found), {'comentarios', 'respuestas'})
        self.assertIn('Prueba de LinkedIn: rota a las 16:30 (create_comment, comment_in_thread)', self.report['salud'].notas)
        self.assertIn('LinkedIn cambió la página', flujos.texto(self.clock, list(self.report.values())))
        # Nothing waits on the canary's word alone: one odd page must not stop a whole day.
        self.assertEqual(cambios_linkedin.held_capabilities(self.directo, self.clock), {})
        # The fix deployed and the canary run again: «recuperado», once per operation; the flows are back.
        self.fix()
        self.clock = at(17)
        self.assertEqual(canario.run(self.directo, now=self.clock).state, 'ok')
        recovered = self.texts()[2:]
        self.assertEqual(sorted(recovered), sorted([
            'Barrio · LinkedIn recuperado: ya se puede comentar en un post (create_comment) otra vez; lo confirmó la prueba '
            'de LinkedIn a las 17:00. Lo aprobado que esperaba sale solo, a su ritmo.',
            'Barrio · LinkedIn recuperado: ya se puede responder un comentario (comment_in_thread) otra vez; lo confirmó la '
            'prueba de LinkedIn a las 17:00. Lo aprobado que esperaba sale solo, a su ritmo.']))
        self.clock = at(17, 5)
        self.assertEqual(self.found(), {})
        line = ('Prueba de LinkedIn: ok a las 17:00 (21 comprobaciones, 17 llamadas, ninguna escritura enviada; 3 escrituras '
                'solo se saben al escribir)')
        self.assertIn(line, self.report['salud'].notas)
        self.assertIn(line, self.report['salud'].clave)  # the daily «all fine» lives in the report, never alone in Slack
        self.assertEqual(self.new_alerts(at(17, 10)), [])
        self.clock = at(17, 30)
        canario.run(self.directo, now=self.clock)
        self.assertEqual(len(self.texts()), 4)
        self.private_never_shown()

    def test_a_page_that_breaks_again_after_recuperado_is_told_once_more_and_then_never_again_that_day(self):
        self.clock = at(16)
        canario.run(self.directo, now=self.clock)
        self.fix()
        self.clock = at(17)
        canario.run(self.directo, now=self.clock)
        self.parser.start()  # LinkedIn changes it back and forth
        self.fixed = False
        for hour in (18, 19):
            self.clock = at(hour)
            canario.run(self.directo, now=self.clock)
        create = [t for t in self.texts() if '(create_comment)' in t]
        self.assertEqual([t.split(':')[0] for t in create],
                         ['Barrio · LinkedIn cambió la página', 'Barrio · LinkedIn recuperado', 'Barrio · LinkedIn cambió la página'])
        self.assertTrue(create[-1].startswith('Barrio · LinkedIn cambió la página: la prueba de LinkedIn de las 18:00'))


class UseFindsTheChangeTests(ChangeBase):
    def approved(self, post_id, text):
        post = ObservedPost.objects.create(account=self.directo, provider_post_id=post_id, author_provider_id=ANA[0],
                                           author_name='Ana Ficticia', text='Un post ajeno de prueba', observed_at=at(9))
        response = self.api.post('/api/v1/operador/actions', {'post': str(post.id), 'capability': 'INT-03',
                                                              'payload': {'text': text}}, format='json')
        self.assertEqual(response.status_code, 201, response.content)
        action = response.json()
        response = self.human.post(f'/api/v1/operador/actions/{action["id"]}/approve',
                                   {'expected_hash': action['payload_hash']}, format='json')
        self.assertEqual(response.status_code, 202, response.content)
        return ActionProposal.objects.get(id=action['id'])

    def test_a_comment_that_fails_for_the_page_waits_with_the_others_until_the_canary_passes(self):
        self.clock = at(18, 30)
        first = self.approved(POST, TEXT)
        second = self.approved(F.OTHER_POST, 'Tracing is the eval nobody budgets for. What do you log first?')
        jobs.process_one(self.worker)  # the first: /me, its comments, the post page… and no box to write in
        first.refresh_from_db()
        self.assertEqual((first.state, ActionProposal.objects.filter(pk=first.pk, execution__isnull=False).exists()),
                         ('approved', False))  # nothing was sent: it goes back to approved, not failed
        self.assertEqual([(r.operation, r.write) for r in self.transport.sent],
                         [('account_status', False), ('list_comments', False), ('create_comment', False)])
        [change] = self.changes()
        self.assertEqual({k: change.metadata[k] for k in ('operacion', 'kind', 'fuente')},
                         {'operacion': 'create_comment', 'kind': 'template_missing', 'fuente': 'uso'})
        self.assertEqual({k: change.metadata['diagnostico'][k] for k in ('apariciones', 'leidas', 'error', 'campo')},
                         {'apariciones': 3, 'leidas': 0, 'error': 'Invalid \\escape', 'campo': 'optimisticKey'})
        self.assertTrue(AuditEvent.objects.filter(action=operador.WRITE_HELD, target=str(self.directo.id),
                                                  metadata__operation='create_comment').exists())
        [text] = self.texts()  # both wait: the one that saw the change and the other one
        self.assertTrue(text.startswith(
            'Barrio · LinkedIn cambió la página: desde las 18:30 no se puede comentar en un post (create_comment): no salen '
            'comentarios en posts de otros. No se envió nada. 2 comentarios aprobados esperan sin perderse: sale solo cuando '
            'la prueba de LinkedIn vuelva a pasar, o mañana con un primer intento.'), text)
        self.assertIn('campo «optimisticKey»', text)
        # The second comment waits without reading anything: no page read, no write, still approved.
        jobs.process_one(self.worker)
        job = Job.objects.filter(kind='execute_action', params__proposal=str(second.id)).get()
        self.assertEqual((job.state, job.result_status), ('failed', 'blocked'))
        self.assertTrue(job.error.startswith('LinkedIn cambió la página: no se puede comentar en un post (create_comment) '
                                             'desde las 18:30.'), job.error)
        self.assertEqual(len(self.transport.sent), 3)
        second.refresh_from_db()
        self.assertEqual(second.state, 'approved')
        self.assertEqual(autopiloto._execute(self.bot, self.directo, self.clock), 0)  # the autopilot does not queue them
        self.assertEqual(set(cambios_linkedin.held_capabilities(self.directo, self.clock)), {'INT-03'})
        self.assertEqual(self.new_alerts(at(18, 40)), [])  # Slack once
        self.assertEqual(self.found()['comentarios'],
                         ['LinkedIn cambió la página: no se puede comentar en un post (create_comment) desde las 18:30 (en uso): '
                          'no salen comentarios en posts de otros.'])
        self.assertEqual(flujos.motivo(job.error), 'LinkedIn cambió la página')
        # The fix deployed; the operator runs the canary now: it clears, Slack says «recuperado», the comments go out.
        self.fix()
        self.clock = at(18, 45)
        out = io.StringIO()
        call_command('operador', '--usuario', self.gustavo.username, 'prueba-linkedin', stdout=out)
        printed = out.getvalue()
        self.assertIn('Cuenta directa de prueba: prueba ok · 17 llamadas a LinkedIn · ninguna escritura enviada', printed)
        self.assertIn('ok         escritura create_comment', printed)
        self.assertIn('sin_probar escritura send_invitation: solo se sabe al escribir', printed)
        self.assertIn('Vuelve a funcionar: create_comment.', printed)
        self.assertEqual(self.texts()[1], 'Barrio · LinkedIn recuperado: ya se puede comentar en un post (create_comment) '
                                          'otra vez; lo confirmó la prueba de LinkedIn a las 18:45. Lo aprobado que esperaba '
                                          'sale solo, a su ritmo.')
        self.assertEqual(cambios_linkedin.held_capabilities(self.directo, self.clock), {})
        self.assertEqual(autopiloto._execute(self.bot, self.directo, self.clock), 1)
        jobs.process_one(self.worker)
        writes = [r for r in self.transport.sent if r.write]
        self.assertEqual([(r.operation, r.path) for r in writes], [('create_comment', rutas.sdui(rutas.COMMENT))])
        first.refresh_from_db()
        self.assertIn(first.state, ('sent', 'confirmed'))
        self.assertEqual(len(self.texts()), 2)
        self.private_never_shown()

    def test_the_hold_ends_with_the_day_and_a_later_success_in_use_clears_it_too(self):
        self.clock = at(18, 30)
        cambios_linkedin.record_changed(self.directo, 'list_comments', 'unreadable', 'LinkedIn: respuesta con una forma '
                                        'inesperada.', {'lectura': 'comments', 'error': 'KeyError'}, now=self.clock)
        self.assertEqual(set(cambios_linkedin.held_capabilities(self.directo, self.clock)), {'INT-03'})
        self.assertEqual(cambios_linkedin.held_capabilities(self.directo, at(0, 5, days=1)), {})  # a new day probes again
        self.assertIn('Pista para quien ajuste el conector: falla la lectura comments (KeyError).', self.texts()[0])
        self.fix()
        connector = connectors_directo.DirectoConnector('cuenta-prueba')
        connector.list_comments(POST)  # the same read, fine again
        self.assertEqual(cambios_linkedin.held_capabilities(self.directo, self.clock), {})
        self.assertIn('lo confirmó una operación que salió bien', self.texts()[-1])
