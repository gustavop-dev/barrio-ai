"""Autonomy safeguards: one comment per person within the cooldown, and a budget stop does not cost the day's slot."""
import os
from datetime import timedelta
from unittest.mock import patch
from django.utils import timezone
from team_backend import autopiloto, editorial, operador
from team_backend.models import ActionProposal, EditorialPiece, Job
from team_backend.tests.test_operador import OperatorBase
from team_backend.tests.test_publicacion import EditorialBase

class AuthorCooldownTests(OperatorBase):
    def comment(self,post,text):
        return operador.create_proposal(self.gustavo,post,'INT-03',{'text':text},citations=['LI-03-M006-K02'],source='agent')

    def test_one_comment_per_person_within_the_cooldown(self):
        first_post,second_post=self.observed()
        first=autopiloto.policy_review(self.comment(first_post,'Evals are where the work hides. Which failure mode do you test first?'))
        first.refresh_from_db();self.assertEqual(first.state,'approved')
        second=autopiloto.policy_review(self.comment(second_post,'Another angle: which regressions do your evals catch before users do?'))
        second.refresh_from_db()
        self.assertEqual(second.state,'discarded');self.assertIn('Ya hay un comentario para Ana Referente en las últimas 48 h',second.risks)
        with patch.dict(os.environ,{'OPERATOR_AUTHOR_COOLDOWN_HOURS':'0'}):
            third=autopiloto.policy_review(self.comment(second_post,'With no cooldown a second comment for the same person passes the gate.'))
        third.refresh_from_db();self.assertEqual(third.state,'approved')

    def test_drafting_skips_people_who_already_have_a_comment(self):
        first_post,_=self.observed()
        self.comment(first_post,'Evals are where the work hides. Which failure mode do you test first?')
        from django.contrib.auth.models import User
        bot=User.objects.create_user('barrio-autopiloto')
        self.grant(bot,'access_knowledge','run_agents','use_paid_providers','operate_linkedin','execute_actions')
        autopiloto.tick(bot)
        self.assertFalse(Job.objects.filter(kind='propose_comment').exists())  # the other post is by the same referent

class BudgetRetryTests(EditorialBase):
    def test_a_budget_stop_is_retried_once_the_budget_renewed(self):
        today=timezone.now().astimezone(operador.local_tz()).date();slot=today+timedelta(days=1)
        piece=EditorialPiece.objects.create(account=self.official,slot_date=slot,scheduled_for=editorial.scheduled_for(slot),state='failed',
                                            note=editorial.BUDGET_STOP+' (EDITORIAL_DAILY_LLM_USD); no se gasta más hoy.')
        now=editorial.scheduled_for(slot)-timedelta(hours=2)
        with patch.dict(os.environ,{'EDITORIAL_LEAD_HOURS':'12'}):
            EditorialPiece.objects.filter(pk=piece.pk).update(created_at=now-timedelta(minutes=30))
            self.assertIsNone(editorial.next_slot(now))  # same day: the budget has not renewed yet
            EditorialPiece.objects.filter(pk=piece.pk).update(created_at=now-timedelta(days=1))
            self.assertEqual(editorial.next_slot(now),slot)
            EditorialPiece.objects.filter(pk=piece.pk).update(note='Error interno en la preparación; no se repite el gasto.')
            self.assertIsNone(editorial.next_slot(now))  # any other failure is not retried automatically
