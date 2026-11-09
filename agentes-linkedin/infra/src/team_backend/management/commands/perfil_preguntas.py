from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from team_backend.models import ProfileProposal
from team_backend.preguntas import clean_profile_questions


class Command(BaseCommand):
    help='Retira preguntas pendientes de perfiles reemplazados/cancelados y duplicadas. Idempotente; conserva historial.'

    def handle(self,*args,**options):
        owners=get_user_model().objects.filter(pk__in=ProfileProposal.objects.values('owner_id'))
        count=sum(clean_profile_questions(owner) for owner in owners)
        self.stdout.write(f'Preguntas retiradas: {count}. Historial conservado.')
