import argparse
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from team_backend import operador
from team_backend.jobs import enqueue_operation
from team_backend.models import ConnectorAccount

def miembros_lines():
    """Organizations, members and whose each account is: what to look at after migration 0055 (read only)."""
    from team_backend.models import Member, Organization
    lines=[]
    for organization in Organization.objects.order_by('created_at'):
        lines.append(f'{organization.name} ({organization.slug})')
        for member in Member.objects.filter(organization=organization).select_related('user'):
            flags=', '.join(filter(None,['activo' if member.active else 'inactivo','administrador' if member.is_admin else '']))
            lines.append(f'  {member.display_name} · {member.role or "sin rol"} · usuario {member.user.get_username()} · {flags}')
            for account in ConnectorAccount.objects.filter(member=member).order_by('created_at'):
                lines.append(f'    {account.provider}: {account.label} ({account.id})')
    orphans=ConnectorAccount.objects.filter(member__isnull=True).order_by('created_at')
    if orphans.exists():
        lines.append('Cuentas sin miembro (del único miembro activo mientras haya uno solo; de nadie con varios):')
        lines+=[f'  {a.provider}: {a.label} ({a.id})' for a in orphans]
    return lines or ['Sin organizaciones ni miembros: todo funciona como antes de las organizaciones.']

def _pairs(items):
    values={}
    for item in items:
        name,sep,value=item.partition('=')
        if not sep:raise CommandError(f'--fijar «{item}»: usa CAMPO=VALOR.')
        values[name.strip()]=value
    return values

def _shown(value):
    import json
    return value if isinstance(value,str) else json.dumps(value,ensure_ascii=False)

def perfil_lines(profile,fields,stored):
    """A profile as plain lines: each field with its value and whether it is stored or a default."""
    lines=[]
    for name,what in fields.items():
        origin='propio' if name in (stored or {}) else 'por defecto'
        lines.append(f'  {name} [{origin}]: {_shown(profile.get(name))}')
        lines.append(f'      ({what})')
    return lines

def revision_lines(rows):
    return [f'  #{r.number} · {r.created_at:%Y-%m-%d %H:%M} · {r.source} · '
            f'{r.actor.get_username() if r.actor_id else "sistema"} · cambió: {", ".join(r.changed) or "—"}' for r in rows]

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
        tar=sub.add_parser('rehacer-tarjetas',help='Piezas cuya imagen es la tarjeta genérica de marca: las lista con el costo '
                           'estimado; con --confirmar rehace cada imagen (llamadas pagadas) y la nueva versión pasa por el líder. '
                           'Las ya publicadas no se pueden cambiar')
        tar.add_argument('--cuenta',required=True);tar.add_argument('--confirmar',action='store_true')
        resp=sub.add_parser('respaldos-imagen',help='Cómo salieron las imágenes (diseño o qué respaldo) y por qué, en los últimos días')
        resp.add_argument('--cuenta',required=True);resp.add_argument('--dias',type=int,default=30)
        reev=sub.add_parser('reevaluar-compradores',help='Compradores que salieron por la región, por falta de evidencia pública o que siguen sin nivel: los lista por puntaje con su nivel y motivo; sin --confirmar no cambia nada')
        reev.add_argument('--cuenta',required=True);reev.add_argument('--confirmar',action='store_true')
        sub.add_parser('preguntas-casos-projectapp',help='Encola en Tu turno las preguntas a Gustavo sobre los dos casos reales de '
                       'ProjectApp (educación en línea y retail); idempotente: repetirlo no crea preguntas nuevas')
        mie=sub.add_parser('miembro',help='Da de alta (o actualiza) un miembro de tu organización con su propio usuario de Django; '
                           'idempotente; nunca crea cuentas de LinkedIn. Solo el administrador de la organización')
        mie.add_argument('--nombre',required=True,help='Nombre para mostrar (p. ej. «Ana Pérez»)')
        mie.add_argument('--usuario-nuevo',required=True,dest='usuario_nuevo',help='Usuario de Django de la persona (se crea sin contraseña si no existe)')
        mie.add_argument('--rol',default='',help='Rol en texto libre (p. ej. «CTO»)')
        mie.add_argument('--activo',action=argparse.BooleanOptionalAction,default=None,
                         help='Activo o no; un miembro nuevo empieza inactivo hasta la fase 7 del plan de organizaciones')
        mie.add_argument('--admin',action=argparse.BooleanOptionalAction,default=None,help='Administrador de la organización o no')
        mie.add_argument('--grupo',action='append',default=[],help='Grupo de permisos que se le añade (lectura, operacion, revision); repetible')
        sub.add_parser('miembros',help='Lista las organizaciones, sus miembros y las cuentas de LinkedIn de cada uno (solo lectura)')
        alta=sub.add_parser('alta-miembro',help='Alta guiada de un miembro (fase 7): su usuario y su miembro INACTIVO, los ajustes '
                            'prudentes de una cuenta gratuita y dormida, su perfil mínimo y su voz provisional; al final, lo que '
                            'falta a mano. Idempotente; sin --confirmar es un ensayo que no cambia nada')
        alta.add_argument('--usuario-nuevo',required=True,dest='usuario_nuevo',help='Usuario de Django de la persona')
        alta.add_argument('--nombre',required=True,help='Nombre para mostrar (p. ej. «Ana Pérez»)')
        alta.add_argument('--rol',required=True,help='Rol (p. ej. «CTO»)')
        alta.add_argument('--relacion',default='',help='Su relación con la empresa (por defecto «Es <rol> de <organización>.»)')
        alta.add_argument('--presentacion',default='',help='Cómo se presenta, en una o dos frases (opcional; lo completa ella)')
        alta.add_argument('--cuenta-directo',default='',dest='cuenta_directo',help='Id de su cuenta en el servicio navegador (opcional)')
        alta.add_argument('--grupo',action='append',default=None,help='Grupos de permisos (por defecto operacion y revision)')
        alta.add_argument('--confirmar',action='store_true',help='Aplica el alta (sin esta opción, solo el ensayo)')
        act=sub.add_parser('activar-miembro',help='Activa a un miembro en alta SOLO si pasan todas las comprobaciones previas (sus '
                           'cuentas, su hora, su autonomía, su rampa, una pasada en seco y la memoria del servidor); sin '
                           '--confirmar solo comprueba')
        act.add_argument('--miembro',required=True,help='Usuario de Django del miembro')
        act.add_argument('--confirmar',action='store_true',help='Activa si todo pasa')
        des=sub.add_parser('desactivar-miembro',help='Detiene a un miembro: sus cuentas no leen ni escriben, sus trabajos en cola se '
                           'cancelan, sus datos quedan y nada de los demás cambia; reversible con activar-miembro. Sin '
                           '--confirmar solo cuenta lo que haría')
        des.add_argument('--miembro',required=True,help='Usuario de Django del miembro')
        des.add_argument('--motivo',required=True,help='Por qué (queda auditado)')
        des.add_argument('--sin-acceso',action='store_true',dest='sin_acceso',help='Además desactiva su usuario: no puede entrar')
        des.add_argument('--confirmar',action='store_true',help='Desactiva')
        aju=sub.add_parser('ajustes',help='El ritmo de LinkedIn de un miembro (tier, topes, rampa, lecturas de perfil, autonomía, hora del '
                           'post): sin --fijar ni --quitar solo lo muestra con su origen; fijar o quitar es del administrador (auditado)')
        aju.add_argument('--miembro',required=True,help='Usuario de Django del miembro')
        aju.add_argument('--fijar',action='append',default=[],metavar='VARIABLE=VALOR',
                         help='Fija una variable de su ritmo con el formato del .env (p. ej. OPERATOR_INVITE_RAMP_STAGES=5/25,8/40,10/50); repetible')
        aju.add_argument('--quitar',action='append',default=[],metavar='VARIABLE',help='Vuelve a la del .env; repetible')
        per=sub.add_parser('perfil',help='Perfil de identidad de un miembro (nombre, identidad, relación con la empresa, límites, '
                           'modalidad personal, propósitos, marca): sin --fijar ni --quitar solo lo muestra; cambiarlo es solo de '
                           'ella misma (validado y auditado, con su historial)')
        per.add_argument('--miembro',default=None,help='Usuario de Django del miembro (por defecto, el tuyo)')
        per.add_argument('--fijar',action='append',default=[],metavar='CAMPO=VALOR',
                         help='Fija un campo (p. ej. limits="..."; purposes.projectapp="..."; personal_startups=no); repetible')
        per.add_argument('--quitar',action='append',default=[],metavar='CAMPO',help='Vuelve al valor neutro; repetible')
        per.add_argument('--historial',action='store_true',help='Lista sus revisiones (quién, cuándo, qué cambió)')
        org=sub.add_parser('perfil-organizacion',help='Perfil de la organización (posicionamiento, pilares, servicios, oferta, casos, '
                           'modalidades): sin --fijar ni --quitar solo lo muestra; cambiarlo es solo del administrador (validado y auditado)')
        org.add_argument('--fijar',action='append',default=[],metavar='CAMPO=VALOR',
                         help='Fija un campo (p. ej. version=posicionamiento-v3; services.producto.label="..."; offer=\'{...}\'); repetible')
        org.add_argument('--quitar',action='append',default=[],metavar='CAMPO',help='Vuelve al valor inicial; repetible')
        org.add_argument('--historial',action='store_true',help='Lista sus revisiones (quién, cuándo, qué cambió)')
        voz=sub.add_parser('voz',help='La voz de un miembro: sin opciones muestra cuál usa y sus versiones; --senales registra sus '
                           'señales de estilo (sin copiarlas); --proponer pide UNA propuesta de pago (VOICE_LEARNING_ENABLED y '
                           'muestra mínima); --confirmar o --descartar decide ella misma')
        voz.add_argument('--miembro',default=None,help='Usuario de Django del miembro (por defecto, el tuyo)')
        accion=voz.add_mutually_exclusive_group()
        accion.add_argument('--senales',action='store_true',help='Registra y cuenta sus señales de estilo (gratis)')
        accion.add_argument('--proponer',action='store_true',help='Una propuesta de su documento de voz (una llamada de pago)')
        accion.add_argument('--confirmar',type=int,default=None,metavar='N',help='Ella confirma la versión N: pasa a ser su voz')
        accion.add_argument('--descartar',type=int,default=None,metavar='N',help='Ella descarta la propuesta N')
        accion.add_argument('--ver',type=int,default=None,metavar='N',help='Imprime el texto de la versión N')
        voz.add_argument('--nota',default='',help='Nota de por qué descarta (opcional)')
        emp=sub.add_parser('hecho-empresa',help='Hechos de la empresa: sin opciones los lista; --compartir CLAVE --miembro USUARIO '
                           'hace de un hecho confirmado de ese miembro un hecho de la empresa (lo usan todos los miembros como '
                           'empresa.CLAVE); --retirar CLAVE lo retira. Solo el administrador de la organización (auditado)')
        emp.add_argument('--miembro',default=None,help='Usuario de Django del miembro dueño del hecho (con --compartir)')
        hecho=emp.add_mutually_exclusive_group()
        hecho.add_argument('--compartir',default=None,metavar='CLAVE',help='Clave del hecho de ese miembro (p. ej. caso.retail.resultado)')
        hecho.add_argument('--retirar',default=None,metavar='CLAVE',help='Clave del hecho de la empresa que deja de usarse')
        emp.add_argument('--motivo',default='',help='Por qué se retira (opcional)')
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
            if o['accion']=='miembro':
                from team_backend import miembros
                member,user_created,created=miembros.save_member(user,o['usuario_nuevo'],o['nombre'],o['rol'],
                    make_admin=o['admin'],active=o['activo'],groups=o['grupo'])
                state='activo' if member.active else 'inactivo'
                self.stdout.write(('Miembro creado: ' if created else 'Miembro actualizado: ')+
                                  f'{member.display_name} ({member.user.get_username()}) · {member.role or "sin rol"} · {state}'+
                                  (' · administrador' if member.is_admin else '')+f' · {member.organization.name}.')
                if user_created:
                    self.stdout.write(f'Usuario nuevo sin contraseña: defínela con «manage.py changepassword {member.user.get_username()}».')
                self.stdout.write('No se creó ninguna cuenta de LinkedIn: cada miembro conecta las suyas.')
                return
            if o['accion']=='miembros':
                for line in miembros_lines():self.stdout.write(line)
                return
            if o['accion'] in ('alta-miembro','activar-miembro','desactivar-miembro'):
                self.onboarding(user,o)
                return
            if o['accion']=='ajustes':
                from team_backend import miembros
                from team_backend.models import Member
                member=Member.objects.select_related('organization').filter(user__username=o['miembro']).first()
                if member is None:raise CommandError(f'«{o["miembro"]}» no es miembro de ninguna organización.')
                values={}
                for item in o['fijar']:
                    name,sep,value=item.partition('=')
                    if not sep:raise CommandError(f'--fijar «{item}»: usa VARIABLE=VALOR.')
                    values[name.strip()]=value
                if values or o['quitar']:
                    member,changed=miembros.save_settings(user,member,values,o['quitar'])
                    self.stdout.write('Ritmo actualizado (auditado).' if changed else 'Sin cambios: ya tenía esos valores.')
                self.stdout.write(f'Ritmo de {member.display_name} ({o["miembro"]}) · {member.organization.name}:')
                for name,value,source in miembros.effective_settings(member):
                    self.stdout.write(f'  {name}={value}  [{source}]')
                return
            if o['accion'] in ('perfil','perfil-organizacion','voz'):
                self.identity(user,o)
                return
            if o['accion']=='hecho-empresa':
                self.company_facts(user,o)
                return
            if o['accion']=='preguntas-casos-projectapp':
                from team_backend import projectapp
                from team_backend import miembros as org
                created=projectapp.ask_case_questions(org.member_for(user))  # to whoever runs it (her answers are hers)
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
            elif o['accion']=='rehacer-tarjetas':
                from team_backend import editorial, retoque
                plan=retoque.redo_images(user,account,confirm=o['confirmar'])
                todo=[r for r in plan if r['action']=='rehacer']
                labels={'rehacer':'se rehace','omitir':'se omite','publicada':'publicada, no se puede cambiar',
                        'rehecha':'rehecha','fallida':'falló'}
                self.stdout.write(f'Piezas con la tarjeta genérica: {len(plan)}.')
                for row in plan:
                    piece=row['piece'];when=piece.scheduled_for.astimezone(operador.local_tz())
                    detail=f' · {row["why"]}' if row['why'] else ''
                    if row.get('scheduled_for'):detail+=f' · sale {row["scheduled_for"].astimezone(operador.local_tz()):%d/%m %H:%M}'
                    self.stdout.write(f'  {when:%Y-%m-%d %H:%M} pieza {piece.id}: {labels.get(row["action"],row["action"])}{detail}')
                if not o['confirmar']:
                    total=sum(r['estimate_usd'] for r in todo)
                    self.stdout.write(f'Costo estimado (reserva máxima de diseño y revisión visual): {total:.2f} USD para '
                                      f'{len(todo)} pieza(s); presupuesto de IA que queda: {editorial.budget_left():.2f} USD.')
                    self.stdout.write('Sin --confirmar no se cambia nada.')
                else:
                    self.stdout.write(f"Rehechas: {sum(r['action']=='rehecha' for r in plan)}; "
                                      f"fallidas: {sum(r['action']=='fallida' for r in plan)}.")
            elif o['accion']=='respaldos-imagen':
                from datetime import timedelta
                from django.utils import timezone
                from team_backend import imagenes
                since=(timezone.now()-timedelta(days=max(1,o['dias']))).date()
                counts=imagenes.fallback_counts(account,since)
                names={'diseño':'diseño propio','contenido':'tarjeta con la frase del post','foto':'foto de la galería',
                       'marca':'tarjeta genérica de marca','sin imagen':'sin imagen lista'}
                self.stdout.write(f"Imágenes desde {since:%Y-%m-%d}: {counts['total']}.")
                for level,n in sorted(counts['by_level'].items(),key=lambda x:-x[1]):
                    self.stdout.write(f'  {names.get(level,level)}: {n}')
                for reason,n in counts['reasons']:self.stdout.write(f'  · {n}× {reason}')
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

    def onboarding(self,user,o):
        """alta-miembro, activar-miembro and desactivar-miembro (organizaciones, phase 7: team_backend/alta.py)."""
        from team_backend import alta
        if o['accion']=='alta-miembro':
            groups=tuple(o['grupo']) if o['grupo'] else alta.GROUPS
            result=alta.alta(user,o['usuario_nuevo'],o['nombre'],o['rol'],company_relation=o['relacion'],
                             identity=o['presentacion'],directo=o['cuenta_directo'],groups=groups,confirm=o['confirmar'])
            self.stdout.write(('Alta aplicada' if result.confirmed else 'ENSAYO (nada cambió; repite con --confirmar)')+
                              f': {o["nombre"]} ({o["usuario_nuevo"]}), inactivo hasta activar-miembro.')
            for step in result.steps:
                self.stdout.write(f'  [{step.state}] {step.what}'+(f' — {step.detail}' if step.detail else ''))
            if result.confirmed:
                member=self._member(user,o['usuario_nuevo'])
                self.stdout.write('Lo que falta a mano:')
                for done,what in alta.checklist(member):
                    mark='x' if done else ' ' if done is False else '?'
                    self.stdout.write(f'  [{mark}] {what}')
            return
        member=self._member(user,o['miembro'])
        if o['accion']=='activar-miembro':
            activated,found=alta.activate(user,member,confirm=o['confirmar'])
            for check in found:
                self.stdout.write(f'  [{"ok" if check.ok else "FALLA"}] {check.label}'+(f' — {check.detail}' if check.detail else ''))
            failing=[c for c in found if not c.ok]
            if activated:
                self.stdout.write(f'{member.display_name} está activa: el autopiloto trabaja sus cuentas con su ritmo.')
            elif failing:
                raise CommandError(f'No se activa: fallan {len(failing)} comprobaciones ({", ".join(c.code for c in failing)}).')
            else:
                self.stdout.write('Todo pasa. Repite con --confirmar para activarla.')
            return
        summary=alta.deactivate(user,member,o['motivo'],confirm=o['confirmar'],block_access=o['sin_acceso'])
        verb='Desactivada' if o['confirmar'] else 'ENSAYO: se desactivaría'
        self.stdout.write(f'{verb}: {member.display_name}. Trabajos en cola cancelados: {summary["jobs"]}. Propuestas suyas que '
                          f'esperan (quedan como están): {summary["proposals"]}. '+('Puede seguir entrando.' if summary['access']
                          else 'Su usuario queda sin acceso.'))
        if o['confirmar']:
            self.stdout.write('Sus datos quedan. Para volver: activar-miembro (con sus comprobaciones). Su navegador sigue abierto '
                              'en el servicio hasta que se cierre o se reinicie el contenedor.')

    def _member(self,user,username):
        from team_backend import miembros
        from team_backend.models import Member
        if username is None:
            member=miembros.member_of_user(user)
            if member is None:raise CommandError('No eres miembro de ninguna organización: indica --miembro.')
            return member
        member=Member.objects.select_related('organization','user').filter(user__username=username).first()
        if member is None:raise CommandError(f'«{username}» no es miembro de ninguna organización.')
        return member

    def company_facts(self,user,o):
        """hecho-empresa (phase 4): what a member confirmed is hers; the admin makes one of her facts the company's."""
        from knowledge import memory
        from team_backend import hechos
        admin=self._member(user,None)
        organization=admin.organization
        if o['compartir']:
            if not o['miembro']:raise CommandError('--compartir necesita --miembro: de quién es el hecho.')
            member=self._member(user,o['miembro'])
            if member.organization_id!=organization.pk:raise CommandError(f'«{o["miembro"]}» no es de {organization.name}.')
            version=hechos.share(user,member,o['compartir'])
            self.stdout.write(f'«{o["compartir"]}» de {member.display_name} es un hecho de {organization.name} (versión {version}, '
                              f'auditado): todos sus miembros lo usan como {hechos.COMPANY_PREFIX}{o["compartir"]}.')
        elif o['retirar']:
            version=hechos.unshare(user,organization,o['retirar'],o['motivo'])
            self.stdout.write(f'«{o["retirar"]}» ya no es un hecho de {organization.name} (versión {version}, auditado).')
        rows=[r for r in hechos.company_rows(organization) if not memory.retired(r['value'])]
        self.stdout.write(f'Hechos de la empresa {organization.name}: {len(rows)}.')
        for row in sorted(rows,key=lambda r:r['key']):self.stdout.write(f'  {hechos.COMPANY_PREFIX}{row["key"]} · versión {row["version"]}')

    def identity(self,user,o):
        """perfil, perfil-organizacion and voz (phase 3): identity and voice out of the code."""
        from team_backend import identidad, miembros, voz
        try:
            if o['accion']=='perfil':
                member=self._member(user,o['miembro'])
                values=_pairs(o['fijar'])
                if values or o['quitar']:
                    _,revision=identidad.save_profile(user,member=member,values=values,remove=o['quitar'])
                    self.stdout.write(f'Perfil actualizado: revisión {revision.number} (auditada).' if revision else
                                      'Sin cambios: ya tenía esos valores.')
                    member.refresh_from_db()
                ident=identidad.of(member)
                self.stdout.write(f'Perfil de {ident.name} ({member.user.get_username()}) · {member.organization.name}'+
                                  (' · identidad inicial de la instalación' if ident.legacy and not member.profile else '')+':')
                for line in perfil_lines(ident.member_profile,identidad.MEMBER_FIELDS,member.profile):self.stdout.write(line)
                if o['historial']:
                    self.stdout.write('Historial:')
                    for line in revision_lines(identidad.revisions(member.organization,member)) or ['  (sin cambios)']:self.stdout.write(line)
                return
            if o['accion']=='perfil-organizacion':
                own=miembros.member_of_user(user)
                if own is None:raise CommandError('No eres miembro de ninguna organización.')
                organization=own.organization
                values=_pairs(o['fijar'])
                if values or o['quitar']:
                    _,revision=identidad.save_profile(user,organization=organization,values=values,remove=o['quitar'])
                    self.stdout.write(f'Perfil de la organización actualizado: revisión {revision.number} (auditada).' if revision else
                                      'Sin cambios: ya tenía esos valores.')
                    organization.refresh_from_db()
                self.stdout.write(f'Perfil de {organization.name} ({organization.slug}):')
                for line in perfil_lines(identidad.organization_profile(organization),identidad.ORGANIZATION_FIELDS,
                                         organization.profile):self.stdout.write(line)
                if o['historial']:
                    self.stdout.write('Historial:')
                    for line in revision_lines(identidad.revisions(organization)) or ['  (sin cambios)']:self.stdout.write(line)
                return
            member=self._member(user,o['miembro'])
            if o['senales']:
                if not identidad.can_edit(user,member=member) and not miembros.is_admin(user,member.organization):
                    raise PermissionError('Solo ella o el administrador de su organización registran sus señales.')
                found=voz.collect_signals(member);_,_,texts=voz.sample(member)
                kinds=', '.join(f'{k}: {n}' for k,n in sorted(found['por_tipo'].items())) or 'ninguna'
                self.stdout.write(f'Señales de {member.display_name}: {kinds} (nuevas ahora: {found["nuevas"]}). '
                                  f'Textos aprobados o editados: {texts} de {voz.min_texts()} para proponer.')
                return
            if o['proponer']:
                doc=voz.propose(user,member)
                self.stdout.write(f'Propuesta de voz {doc.number} lista ({doc.usage.get("texts")} textos, {doc.usage.get("signals")} '
                                  f'señales, ~{doc.usage.get("estimated_usd")} USD). No se usa hasta que ella la confirme: '
                                  f'«voz --confirmar {doc.number}» o «--descartar {doc.number}»; «--ver {doc.number}» la imprime.')
                return
            if o['confirmar'] is not None:
                doc=voz.confirm(user,member,o['confirmar'])
                self.stdout.write(f'Voz {doc.number} confirmada: desde ahora el equipo escribe con ella.')
                return
            if o['descartar'] is not None:
                doc=voz.discard(user,member,o['descartar'],o['nota'])
                self.stdout.write(f'Propuesta {doc.number} descartada. Sigue la voz que tenía.')
                return
            if o['ver'] is not None:
                doc=voz.documents(member).filter(number=o['ver']).first()
                if doc is None:raise CommandError(f'No hay una versión {o["ver"]} de su voz.')
                self.stdout.write(voz._text_of(doc))
                return
            current=voz.current(member)
            label={'inicial':'la inicial de la instalación','confirmada':f'la confirmada (versión {current.number})',
                   'provisional':'PROVISIONAL (neutra, sobria; sus borradores salen marcados «voz provisional»)'}[current.kind]
            self.stdout.write(f'Voz de {current.author}: {label}. Aprendizaje '+('encendido' if voz.enabled() else 'apagado')+
                              f' (VOICE_LEARNING_ENABLED); muestra mínima {voz.min_texts()} textos.')
            for doc in voz.documents(member):
                self.stdout.write(f'  #{doc.number} · {doc.get_state_display()} · {doc.source} · {doc.created_at:%Y-%m-%d}'+
                                  (f' · {doc.resource}' if doc.resource else '')+(f' · {doc.note}' if doc.note else ''))
        except (identidad.IdentidadInvalida,miembros.MiembroRequerido,PermissionError) as exc:raise CommandError(str(exc)) from None
        except ValueError as exc:raise CommandError(str(exc)) from None
        except Exception as exc:
            detail=getattr(exc,'detail',None)
            if detail:raise CommandError(str(detail)) from None
            raise
