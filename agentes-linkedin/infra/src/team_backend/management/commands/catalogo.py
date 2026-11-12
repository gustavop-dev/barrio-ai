import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from team_backend import catalogo


class Command(BaseCommand):
    help=('Catálogo de la biblioteca: estantes y niveles de las unidades del curso, por versiones. «cargar» guarda una versión '
          'inactiva desde un archivo privado (el curso no va al repositorio); «activar» la adopta estante por estante; '
          '«desactivar» devuelve un estante a su lista fija; «estado» muestra conteos, nunca texto del curso.')

    def add_arguments(self,parser):
        sub=parser.add_subparsers(dest='accion',required=True)
        load=sub.add_parser('cargar',help='Guarda una versión nueva, inactiva. JSON con «version», «niveles» '
                            '({estante: {nucleo_orden: [IDs], unidades: {ID: {nivel, razon, puntaje, duplica}}}}) '
                            'y «unidades» ({ID: {principal: estante}}).')
        load.add_argument('ruta')
        on=sub.add_parser('activar',help='Los agentes de estos estantes cargan el núcleo de la versión desde su próxima llamada.')
        on.add_argument('version');on.add_argument('--estantes',required=True,help='Separados por comas, p. ej. comentar,responder')
        off=sub.add_parser('desactivar',help='Estos estantes vuelven a su lista fija del código.')
        off.add_argument('--estantes',required=True)
        state=sub.add_parser('estado');state.add_argument('--version')

    def handle(self,**o):
        shelves=[s.strip() for s in (o.get('estantes') or '').split(',') if s.strip()]
        try:
            if o['accion']=='cargar':
                try:data=json.loads(Path(o['ruta']).read_text(encoding='utf-8'))
                except (OSError,ValueError) as exc:raise ValueError(f'No se pudo leer el catálogo: {exc}') from None
                result=catalogo.load(data)
            elif o['accion']=='activar':result=catalogo.activate(o['version'],shelves)
            elif o['accion']=='desactivar':catalogo.deactivate(shelves);result=catalogo.summary()
            else:result=catalogo.summary(o.get('version'))
        except ValueError as exc:raise CommandError(str(exc)) from None
        self.stdout.write(json.dumps(result,ensure_ascii=False,indent=2))
