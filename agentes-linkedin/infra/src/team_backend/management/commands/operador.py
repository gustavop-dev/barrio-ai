from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from team_backend import operador
from team_backend.jobs import enqueue_operation
from team_backend.models import ConnectorAccount

class Command(BaseCommand):
    help='Primer uso del operador: registrar cuenta, comprobarla, añadir referentes, encolar observación y cambiar de proveedor.'

    def add_arguments(self,parser):
        parser.add_argument('--usuario',required=True,help='Usuario humano que actúa (p. ej. el administrador)')
        sub=parser.add_subparsers(dest='accion',required=True)
        cuenta=sub.add_parser('cuenta');cuenta.add_argument('--account-id',required=True);cuenta.add_argument('--etiqueta',required=True)
        cuenta.add_argument('--proveedor',default='unipile',choices=['unipile','fake','directo'])
        sub.add_parser('comprobar').add_argument('--cuenta',required=True)
        ref=sub.add_parser('referente');ref.add_argument('--cuenta',required=True);ref.add_argument('--perfil',required=True,help='URL linkedin.com/in/... o identificador público')
        ref.add_argument('--motivo',required=True)
        obs=sub.add_parser('observar');obs.add_argument('--cuenta',required=True);obs.add_argument('--limite',type=int,default=5)
        sub.add_parser('referentes-extraordinaria',help='Revisión de referentes fuera del calendario mensual (decisión explícita)').add_argument('--cuenta',required=True)
        cambio=sub.add_parser('cambiar-proveedor',help='Pasar una cuenta entre Unipile y directo sin perder su historia, traduciendo sus ids (navegador-contrato.md «Cambiar de proveedor»)')
        cambio.add_argument('--cuenta',required=True);destino=cambio.add_mutually_exclusive_group(required=True)
        destino.add_argument('--a',choices=['unipile','directo']);destino.add_argument('--volver',action='store_true',help='El proveedor y el id que tenía antes del último cambio, con los ids originales')
        destino.add_argument('--olvidar-originales',action='store_true',help='Borrar los ids originales guardados por los cambios de esta cuenta')
        cambio.add_argument('--slug','--id-externo',dest='slug',default='',help='directo: el nombre de la cuenta en el servicio navegador; unipile: su id acc_…')
        cambio.add_argument('--prueba',action='store_true',help='Solo decir qué cambiaría, por tabla y campo, y qué no se puede traducir')
        cambio.add_argument('--aceptar-ids-viejos',action='store_true',help='Cambiar dejando como están los ids que no se pueden traducir (caducan las propuestas abiertas que dependen de ellos)')
        ind=sub.add_parser('referentes-industria',help='Busca referentes grandes de tu industria en EE. UU. (de pago; imprime el costo y sin --confirmar no encola nada)')
        ind.add_argument('--cuenta',required=True);ind.add_argument('--confirmar',action='store_true',help='Encola la búsqueda tras mostrar el costo')
        ind.add_argument('--tope-usd',default=None,help='Tope duro en USD de esta búsqueda (por defecto REFERENTES_INDUSTRIA_TOPE_USD o 3)')
        ind.add_argument('--candidatos',type=int,default=6,help='Personas a medir en LinkedIn (1-9)')
        ind.add_argument('--busquedas',type=int,default=4,help='Búsquedas de personas en LinkedIn (0-8)')

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
                self.stdout.write(f'Revisión extraordinaria en cola: trabajo {job.id}. Las propuestas llegan a la Bandeja.')
            elif o['accion']=='referentes-industria':
                from decimal import Decimal, InvalidOperation
                from team_backend import referentes_industria
                try:tope=Decimal(o['tope_usd']) if o['tope_usd'] is not None else None
                except InvalidOperation:raise CommandError('--tope-usd debe ser un número') from None
                if tope is not None and not (tope.is_finite() and tope>0):raise CommandError('--tope-usd debe ser positivo')
                job,report=referentes_industria.enqueue(user,account,tope_usd=tope,candidatos=o['candidatos'],
                                                        busquedas=o['busquedas'],confirm=o['confirmar'])
                est=report['estimate'];reads=est['reads']
                self.stdout.write(f"Costo máximo (reserva): {est['usd_max']} USD = {est['web_calls']} investigaciones web × "
                                  f"{est['web_call_usd']} + selección {est['selection_usd']}. El real suele ser menor.")
                self.stdout.write(f"Tope duro de esta búsqueda: {report['tope_usd']} USD. Quedan {report['cycle_left_usd']} USD "
                                  f"este mes en referentes y {report['team_left_usd']} USD del equipo hoy.")
                self.stdout.write(f"Lecturas de LinkedIn como máximo: {reads['search']} búsquedas, {reads['profile']} perfiles, "
                                  f"{reads['content']} lecturas de contenido (dentro de los topes diarios).")
                for line in report['warnings']:self.stdout.write('Aviso: '+line)
                if report['issues']:raise CommandError(' '.join(report['issues']))
                if job is None:
                    self.stdout.write('No se encoló nada. Repite con --confirmar para lanzar la búsqueda.')
                else:
                    self.stdout.write(f'Búsqueda de referentes de industria en cola: trabajo {job.id}. Las propuestas llegan a la Bandeja.')
            elif o['accion']=='observar':
                job,_=enqueue_operation(user,'observe',{'account':str(account.id),'limit':o['limite'],'referents':[]})
                self.stdout.write(f'Observación en cola: trabajo {job.id}. El worker la procesará.')
            elif o['accion']=='cambiar-proveedor':
                from team_backend import proveedor
                if o['olvidar_originales']:
                    self.stdout.write(f'Ids originales borrados: {proveedor.forget_originals(user,account)}.');return
                if o['prueba']:
                    self.stdout.write('\n'.join(proveedor.report(proveedor.preview(account,o['a'],o['slug'],o['volver']))));return
                before=account.provider
                account,plan=(proveedor.switch_back(user,account,o['aceptar_ids_viejos']) if o['volver']
                              else proveedor.switch(user,account,o['a'],o['slug'],o['aceptar_ids_viejos']))
                self.stdout.write('\n'.join(proveedor.report(plan)))
                self.stdout.write(f'Cuenta {account.id}: de {before} a {account.provider} ({account.external_account_id}). '
                                  'Sigue en pausa: ejecuta "comprobar" y reanúdala.')
        except (ValueError,PermissionError) as exc:raise CommandError(str(exc)) from None
        except Exception as exc:
            detail=getattr(exc,'detail',None)
            if detail:raise CommandError(str(detail)) from None
            raise
