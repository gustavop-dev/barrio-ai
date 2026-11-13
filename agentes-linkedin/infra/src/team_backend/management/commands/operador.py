from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from team_backend import operador
from team_backend.jobs import enqueue_operation
from team_backend.models import ConnectorAccount

class Command(BaseCommand):
    help='Primer uso del operador: registrar cuenta, comprobarla, añadir referentes y encolar observación.'

    def add_arguments(self,parser):
        parser.add_argument('--usuario',required=True,help='Usuario humano que actúa (p. ej. el administrador)')
        sub=parser.add_subparsers(dest='accion',required=True)
        cuenta=sub.add_parser('cuenta');cuenta.add_argument('--account-id',required=True);cuenta.add_argument('--etiqueta',required=True)
        cuenta.add_argument('--proveedor',default='unipile',choices=['unipile','fake'])
        sub.add_parser('comprobar').add_argument('--cuenta',required=True)
        ref=sub.add_parser('referente');ref.add_argument('--cuenta',required=True);ref.add_argument('--perfil',required=True,help='URL linkedin.com/in/... o identificador público')
        ref.add_argument('--motivo',required=True)
        obs=sub.add_parser('observar');obs.add_argument('--cuenta',required=True);obs.add_argument('--limite',type=int,default=5)
        sub.add_parser('referentes-extraordinaria',help='Revisión de referentes fuera del calendario mensual (decisión explícita)').add_argument('--cuenta',required=True)

    def handle(self,**o):
        user=User.objects.filter(username=o['usuario'],is_active=True).first()
        if not user:raise CommandError('Usuario inexistente o inactivo')
        try:
            if o['accion']=='cuenta':
                account=operador.register_account(user,o['proveedor'],o['account_id'],o['etiqueta'])
                self.stdout.write(f'Cuenta {account.id} ({account.provider}). Ejecuta "comprobar" antes de operar.')
                return
            account=ConnectorAccount.objects.filter(id=o['cuenta']).first()
            if not account:raise CommandError('Cuenta no registrada')
            if o['accion']=='comprobar':
                account=operador.check_account(account,user)
                self.stdout.write(f'Estado {account.status}; bloqueada={account.is_locked}; pausa={account.paused} {account.paused_reason}')
            elif o['accion']=='referente':
                referent,created=operador.add_referent(user,account,o['perfil'],o['motivo'])
                self.stdout.write(('Añadido: ' if created else 'Ya existía: ')+f'{referent.display_name} ({referent.id})')
            elif o['accion']=='referentes-extraordinaria':
                from team_backend import referentes
                job=referentes.extraordinary(user,account)
                self.stdout.write(f'Revisión extraordinaria en cola: trabajo {job.id}. Las propuestas llegan a Tu turno.')
            elif o['accion']=='observar':
                job,_=enqueue_operation(user,'observe',{'account':str(account.id),'limit':o['limite'],'referents':[]})
                self.stdout.write(f'Observación en cola: trabajo {job.id}. El worker la procesará.')
        except (ValueError,PermissionError) as exc:raise CommandError(str(exc)) from None
        except Exception as exc:
            detail=getattr(exc,'detail',None)
            if detail:raise CommandError(str(detail)) from None
            raise
