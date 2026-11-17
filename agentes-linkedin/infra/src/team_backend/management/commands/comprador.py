import json
from django.core.management.base import BaseCommand, CommandError
from team_backend import comprador
from team_backend.models import ConnectorAccount

class Command(BaseCommand):
    help='Recorrido del comprador (docs/plan-outbound.md, fase 1): reconstruir el estado por persona desde el historial o ver el embudo.'

    def add_arguments(self,parser):
        sub=parser.add_subparsers(dest='accion',required=True)
        rebuild=sub.add_parser('reconstruir',help='Rellena el estado de cada comprador desde lo que ya guarda Barrio; idempotente')
        rebuild.add_argument('--cuenta',default=None,help='Solo los contactos de esta cuenta (por defecto, todas)')
        rebuild.add_argument('--seco',action='store_true',help='Calcula y deshace: solo informa cuántos recorridos y toques crearía')
        funnel=sub.add_parser('embudo',help='Imprime el embudo del comprador en JSON (solo lectura)')
        funnel.add_argument('--semanas',type=int,default=8)

    def handle(self,**o):
        account=None
        if o.get('cuenta'):
            account=ConnectorAccount.objects.filter(id=o['cuenta']).first()
            if account is None:raise CommandError('Cuenta no registrada')
        if o['accion']=='reconstruir':
            result=comprador.rebuild(account,dry_run=o['seco'])
            self.stdout.write(('En seco (sin guardar): ' if o['seco'] else '')+
                              f"{result['personas']} personas leídas, {result['recorridos']} recorridos ({result['nuevos']} nuevos), "
                              f"{result['toques_nuevos']} toques nuevos, {result['fallos']} fallos, {result['segundos']} s.")
            for error in result['errores'][:20]:self.stderr.write(f"{error['persona']}: {error['error']}")
        else:
            self.stdout.write(json.dumps(comprador.funnel(o['semanas'],account=account),ensure_ascii=False,indent=1,default=str))
