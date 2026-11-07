"""An execution job queued by one actor and stopped by a gate can be queued again by the other (Gustavo or the autopilot)."""
import os
from unittest.mock import patch
from django.contrib.auth.models import User
from team_backend import autopiloto, jobs, operador
from team_backend.models import ActionProposal, Job
from team_backend.tests.test_operador import OperatorBase


class CrossOwnerExecutionTests(OperatorBase):
    def setUp(self):
        super().setUp()
        self.bot=User.objects.create_user('barrio-autopiloto')
        self.grant(self.bot,'access_knowledge','run_agents','use_paid_providers','operate_linkedin','execute_actions')

    def test_the_autopilot_retries_what_gustavo_approved_and_a_gate_stopped(self):
        post,_=self.observed()
        action=self.proposal(post)
        with patch.dict(os.environ,{'OPERATOR_PAUSED':'true'}):  # a gate stops the job before any execution
            first=operador.approve(self.gustavo,action['id'],action['payload_hash'])
            jobs.process_one(self.worker)
        first.refresh_from_db()
        self.assertEqual((first.state,first.owner_id),('failed',self.gustavo.pk))
        report=autopiloto.tick(self.bot)  # used to raise NotFound and stop the whole tick
        self.assertEqual(report['execute'],1)
        retry=Job.objects.filter(kind='execute_action',owner=self.bot).get()
        self.assertNotEqual(retry.id,first.id)
        while jobs.process_one(self.worker):pass
        self.assertEqual(ActionProposal.objects.get(pk=action['id']).state,'confirmed')

    def test_a_pending_job_of_the_other_actor_is_never_duplicated(self):
        post,_=self.observed()
        action=self.proposal(post)
        queued=operador.approve(self.gustavo,action['id'],action['payload_hash'])
        proposal=ActionProposal.objects.get(pk=action['id'])
        self.assertEqual(operador.enqueue_execution(self.bot,proposal).id,queued.id)
        self.assertEqual(Job.objects.filter(kind='execute_action').count(),1)
