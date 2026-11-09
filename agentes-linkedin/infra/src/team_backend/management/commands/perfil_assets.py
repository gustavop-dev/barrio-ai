from django.core.management.base import BaseCommand, CommandError
from team_backend import perfil_assets
from team_backend.exceptions import Conflict
from team_backend.models import ProfileProposal


class Command(BaseCommand):
    help='Encola solo fotos y banner de una propuesta existente, con su presupuesto original.'

    def add_arguments(self,parser):
        parser.add_argument('proposal_id',help='UUID completo o prefijo único (por ejemplo 8aa8c51c).')

    def handle(self,*args,**options):
        prefix=options['proposal_id'].lower().replace('-','')
        if not prefix or any(c not in '0123456789abcdef' for c in prefix):raise CommandError('Identificador inválido')
        matches=[p for p in ProfileProposal.objects.select_related('owner') if p.id.hex.startswith(prefix)]
        if len(matches)!=1:raise CommandError('El identificador debe señalar exactamente una propuesta')
        proposal=matches[0]
        try:job=perfil_assets.queue(proposal.owner,proposal.id)
        except (ValueError,Conflict) as exc:raise CommandError(str(exc)) from exc
        self.stdout.write(f'Propuesta {proposal.id}; job {job.id}; estado {job.state}. El worker procesa solo fotos y banner.')
