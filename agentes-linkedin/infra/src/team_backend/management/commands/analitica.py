import json
import uuid
from datetime import date

from django.core.management.base import BaseCommand, CommandError

from team_backend import analitica
from team_backend.models import AnalyticsImport, ConnectorAccount


def day(value):
    try:return date.fromisoformat(value)
    except ValueError:raise CommandError(f'Fecha inválida: {value!r} (AAAA-MM-DD).') from None


def account(value):
    """A directo account by its id or by its name in the navegador service (external_account_id)."""
    accounts=ConnectorAccount.objects.filter(provider='directo')
    try:found=accounts.filter(id=uuid.UUID(value)).first()
    except ValueError:found=accounts.filter(external_account_id=value).first()
    if not found:raise CommandError(f'No hay una cuenta «directo» {value!r}.')
    return found


def summary(log):
    return {'desde':log.start.isoformat(),'hasta':log.end.isoformat(),'tipo':log.trigger,'estado':log.state,
            'filas':log.rows,'hojas':len(log.sheets),'error':log.error or None}


class Command(BaseCommand):
    help=('Analítica de LinkedIn de una cuenta «directo» (docs/metricas-resultados.md): una exportación por rango, leída por '
          'el servicio navegador y guardada por día, por post y por rango. Solo lee LinkedIn y respeta la pausa de la máquina '
          'y de la cuenta. «importar» trae un rango; «carga-inicial» va hacia atrás hasta el primer día que da LinkedIn; '
          '«estado» muestra las últimas importaciones, sin cifras.')

    def add_arguments(self,parser):
        sub=parser.add_subparsers(dest='accion',required=True)
        one=sub.add_parser('importar',help='Un rango: --desde y --hasta (días UTC, ambos incluidos) o --dias N (los N días '
                           'completos que terminan ayer).')
        one.add_argument('--cuenta',required=True,help='Id de la cuenta o su nombre en el servicio navegador.')
        one.add_argument('--desde');one.add_argument('--hasta');one.add_argument('--dias',type=int)
        back=sub.add_parser('carga-inicial',help='Desde ayer hacia atrás, en trozos, hasta --desde o el primer día de LinkedIn.')
        back.add_argument('--cuenta',required=True);back.add_argument('--desde')
        back.add_argument('--trozo',type=int,help='Días por exportación (por defecto ANALYTICS_CHUNK_DAYS, 365).')
        state=sub.add_parser('estado');state.add_argument('--cuenta')

    def handle(self,**o):
        try:
            if o['accion']=='importar':
                target=account(o['cuenta'])
                if o.get('dias') is not None:
                    if o.get('desde') or o.get('hasta'):raise CommandError('Usa --dias o --desde/--hasta, no ambos.')
                    if not 1<=o['dias']<=analitica.ANALYTICS_DAYS:raise CommandError(f'--dias va de 1 a {analitica.ANALYTICS_DAYS}.')
                    start,end=analitica.last_days(o['dias'])
                elif o.get('desde') and o.get('hasta'):start,end=day(o['desde']),day(o['hasta'])
                else:raise CommandError('Falta el rango: --desde y --hasta, o --dias.')
                result=[summary(analitica.import_range(target,start,end))]
            elif o['accion']=='carga-inicial':
                result=[summary(log) for log in analitica.backfill(account(o['cuenta']),day(o['desde']) if o.get('desde') else None,
                                                                    o.get('trozo'))]
            else:
                logs=AnalyticsImport.objects.all()
                if o.get('cuenta'):logs=logs.filter(account=account(o['cuenta']))
                result=[summary(log) for log in logs[:10]]
        except ValueError as exc:raise CommandError(str(exc)) from None
        self.stdout.write(json.dumps(result,ensure_ascii=False,indent=2))
        if any(r['estado']=='error' for r in result if o['accion']!='estado'):raise CommandError('La importación falló; ver «error».')
