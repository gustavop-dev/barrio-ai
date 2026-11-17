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
        cuenta.add_argument('--proveedor',default='directo',choices=['directo','fake'])
        sub.add_parser('comprobar').add_argument('--cuenta',required=True)
        ref=sub.add_parser('referente');ref.add_argument('--cuenta',required=True);ref.add_argument('--perfil',required=True,help='URL linkedin.com/in/... o identificador público')
        ref.add_argument('--motivo',required=True)
        ref.add_argument('--industria',action='store_true',help='Lo da de alta como referente de industria (sus posts atípicos pasan a modelos de crecimiento); sin la opción, voz del nicho')
        tipo=sub.add_parser('referente-tipo',help='Corrige si un referente existente es de industria o del nicho (auditado; sin --confirmar solo muestra el cambio)')
        tipo.add_argument('--cuenta',required=True);tipo.add_argument('--perfil',required=True,help='URL linkedin.com/in/... o identificador público')
        tipo.add_argument('--tipo',required=True,choices=['industria','nicho']);tipo.add_argument('--motivo',required=True)
        tipo.add_argument('--confirmar',action='store_true')
        obs=sub.add_parser('observar');obs.add_argument('--cuenta',required=True);obs.add_argument('--limite',type=int,default=5)
        sub.add_parser('referentes-extraordinaria',help='Revisión de referentes fuera del calendario mensual (decisión explícita)').add_argument('--cuenta',required=True)
        cola=sub.add_parser('reclasificar-cola',help='Devuelve al clasificador a las personas que siguen en cola (encajan, sin seguir ni invitar) clasificadas antes de una fecha; sin --confirmar solo cuenta')
        cola.add_argument('--cuenta',required=True);cola.add_argument('--antes',required=True,help='Fecha y hora ISO con zona, por ejemplo 2026-11-12T20:40:00+00:00')
        cola.add_argument('--confirmar',action='store_true')
        reev=sub.add_parser('reevaluar-compradores',help='Compradores que salieron por la región, por falta de evidencia pública o que siguen sin nivel: los lista por puntaje con su nivel y motivo; sin --confirmar no cambia nada')
        reev.add_argument('--cuenta',required=True);reev.add_argument('--confirmar',action='store_true')
        sub.add_parser('preguntas-casos-projectapp',help='Encola en Tu turno las preguntas a Gustavo sobre los dos casos reales de '
                       'ProjectApp (educación en línea y retail); idempotente: repetirlo no crea preguntas nuevas')
        ind=sub.add_parser('referentes-industria',help='Busca referentes grandes de tu industria en EE. UU. (de pago; imprime el costo y sin --confirmar no encola nada). Si la del mes terminó sin propuestas, se puede repetir')
        ind.add_argument('--cuenta',required=True);ind.add_argument('--confirmar',action='store_true',help='Encola la búsqueda tras mostrar el costo')
        ind.add_argument('--tope-usd',default=None,help='Tope duro en USD de esta búsqueda (por defecto REFERENTES_INDUSTRIA_TOPE_USD o 3)')
        ind.add_argument('--candidatos',type=int,default=6,help='Personas a medir en LinkedIn con sus posts (1-9)')
        ind.add_argument('--busquedas',type=int,default=5,help='Búsquedas de personas en LinkedIn (0-8), en el orden fijo de referentes_industria.QUERIES')
        ind.add_argument('--empresas',default='',help='Empresas semilla separadas por comas (p. ej. "Imagine Apps,Northwind Labs"): se buscan sus fundadores y van primero')
        ind.add_argument('--perfiles',default='',help='Perfiles semilla separados por comas (URL linkedin.com/in/... o identificador): se miden primero con los mismos criterios')
        ind.add_argument('--informe',action='store_true',help='Solo imprime el embudo de las búsquedas de industria de este mes (no encola nada)')

    def handle(self,**o):
        user=User.objects.filter(username=o['usuario'],is_active=True).first()
        if not user:raise CommandError('Usuario inexistente o inactivo')
        try:
            if o['accion']=='cuenta':
                account=operador.register_account(user,o['proveedor'],o['account_id'],o['etiqueta'])
                self.stdout.write(f'Cuenta {account.id} ({account.provider}). Ejecuta "comprobar" antes de operar.')
                return
            if o['accion']=='preguntas-casos-projectapp':
                from team_backend import projectapp
                created=projectapp.ask_case_questions()
                total=len(projectapp.CASE_SEGMENTS)*len(projectapp.CASE_QUESTIONS)
                self.stdout.write(f'Preguntas de los casos de ProjectApp creadas ahora: {len(created)} de {total}.')
                for item in created:self.stdout.write(f'  · {item.memory_key}: {item.question}')
                if len(created)<total:
                    self.stdout.write('Las demás ya estaban abiertas, respondidas, rechazadas o retiradas: no se repiten.')
                return
            account=ConnectorAccount.objects.filter(id=o['cuenta']).first()
            if not account:raise CommandError('Cuenta no registrada')
            if o['accion']=='comprobar':
                account=operador.check_account(account,user)
                self.stdout.write(f'Estado {account.status}; bloqueada={account.is_locked}; pausa={account.paused} {account.paused_reason}')
            elif o['accion']=='referente':
                kind='industria' if o['industria'] else 'nicho'
                referent,created=operador.add_referent(user,account,o['perfil'],o['motivo'],kind=kind)
                self.stdout.write(('Añadido: ' if created else 'Ya existía: ')+f'{referent.display_name} ({referent.id}), tipo {referent.kind}')
                if not created and referent.kind!=kind:
                    self.stdout.write(f'El tipo no cambia al volver a añadirlo; usa «referente-tipo --tipo {kind}» para corregirlo.')
            elif o['accion']=='referente-tipo':
                referent,previous,changed=operador.set_referent_kind(user,account,o['perfil'],o['tipo'],o['motivo'],confirm=o['confirmar'])
                if previous==o['tipo']:self.stdout.write(f'{referent.display_name} ya es {previous}; nada que cambiar.')
                elif changed:self.stdout.write(f'{referent.display_name}: {previous} → {referent.kind} (auditado, revisión {referent.revision}).')
                else:self.stdout.write(f'{referent.display_name}: {previous} → {o["tipo"]}. Sin --confirmar no se cambia nada.')
            elif o['accion']=='referentes-extraordinaria':
                from team_backend import referentes
                job=referentes.extraordinary(user,account)
                self.stdout.write(f'Revisión extraordinaria en cola: trabajo {job.id}. Las propuestas llegan a la Bandeja.')
            elif o['accion']=='reclasificar-cola':
                from datetime import datetime
                from team_backend import red
                try:before=datetime.fromisoformat(o['antes'])
                except ValueError:raise CommandError('--antes debe ser una fecha ISO') from None
                if before.tzinfo is None:raise CommandError('--antes debe llevar zona horaria, por ejemplo +00:00')
                result=red.requeue(user,account,before,confirm=o['confirmar'])
                self.stdout.write(f"En cola clasificadas antes de {before.isoformat()}: {result['found']}. "+
                                  (f"Devueltas al clasificador: {result['requeued']}." if o['confirmar'] else 'Con --confirmar vuelven al clasificador.'))
            elif o['accion']=='reevaluar-compradores':
                from team_backend import nivel_comprador
                result=nivel_comprador.reevaluate(user,account,confirm=o['confirmar'])
                groups=nivel_comprador.actions()
                counts=', '.join(f'{group} ({groups[group]}): {n}' for group,n in result['found'].items())
                self.stdout.write(f"Compradores a reevaluar: {result['total']}. {counts}.")
                for row in result['people']:
                    score='—' if row['score'] is None else f"{row['score']}{'*' if row['provisional'] else ''}"
                    line=f" · línea {row['line']}" if row.get('line') else ''
                    self.stdout.write(f"{score:>4}  {row['level'] or '—':<13} {row['action']:<12} {row['name']} · {row['group']}{line} · {row['reason']}")
                if any(row['provisional'] for row in result['people']):
                    self.stdout.write('* Puntaje provisional: lo fija el clasificador al volver a juzgarlo.')
                self.stdout.write(f"Aplicados: {result['applied']}." if o['confirmar'] else 'Sin --confirmar no se cambia nada.')
            elif o['accion']=='referentes-industria':
                from decimal import Decimal, InvalidOperation
                from team_backend import referentes_industria
                if o['informe']:
                    for line in referentes_industria.report_lines(account):self.stdout.write(line)
                    return
                try:tope=Decimal(o['tope_usd']) if o['tope_usd'] is not None else None
                except InvalidOperation:raise CommandError('--tope-usd debe ser un número') from None
                if tope is not None and not (tope.is_finite() and tope>0):raise CommandError('--tope-usd debe ser positivo')
                split=lambda value:[x.strip() for x in (value or '').split(',') if x.strip()]
                job,report=referentes_industria.enqueue(user,account,tope_usd=tope,candidatos=o['candidatos'],
                                                        busquedas=o['busquedas'],empresas=split(o['empresas']),
                                                        perfiles=split(o['perfiles']),confirm=o['confirmar'])
                est=report['estimate'];reads=est['reads']
                scope={'us':'EE. UU.','global':'sin filtro de lugar'}
                for name in report['empresas']:
                    self.stdout.write(f'Búsqueda de empresa semilla: {referentes_industria.COMPANY_QUERY.format(name)} (sin filtro de lugar)')
                for n,q in enumerate(report['queries'],1):
                    self.stdout.write(f"Búsqueda {n}: {q['keywords']} ({scope[q['scope']]}; {q['service']})")
                if report['perfiles']:self.stdout.write('Perfiles semilla: '+', '.join(report['perfiles']))
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
        except (ValueError,PermissionError) as exc:raise CommandError(str(exc)) from None
        except Exception as exc:
            detail=getattr(exc,'detail',None)
            if detail:raise CommandError(str(detail)) from None
            raise
