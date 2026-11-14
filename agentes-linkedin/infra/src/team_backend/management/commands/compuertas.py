import json

from django.core.management.base import BaseCommand, CommandError

from team_backend import auditoria_compuertas


class Command(BaseCommand):
    help=('Compuertas (docs/compuertas.md). «auditar» lee lo que ya está guardado (piezas, propuestas y eventos) y muestra, por '
          'compuerta, cuántas entraron, pasaron a la primera, pasaron tras reparar o reintentar, se pararon o esperan; sus '
          'motivos, los días sin post y lo que nadie reintentó. Solo lee: no llama a modelos ni escribe. Solo ids y categorías.')

    def add_arguments(self,parser):
        sub=parser.add_subparsers(dest='accion',required=True)
        audit=sub.add_parser('auditar',help='Auditoría de los últimos N días (hoy no cuenta como día sin post).')
        audit.add_argument('--dias',type=int,default=7)
        audit.add_argument('--json',action='store_true',help='Imprime el informe en JSON')

    def handle(self,**o):
        if o['dias']<1:raise CommandError('--dias debe ser al menos 1.')
        report=auditoria_compuertas.auditar(o['dias'])
        self.stdout.write(json.dumps(report,ensure_ascii=False,indent=2) if o['json'] else auditoria_compuertas.render(report))
