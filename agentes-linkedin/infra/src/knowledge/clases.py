"""Qué clases del curso guarda la biblioteca y cuáles pueden leer hoy los agentes.

Son dos conceptos distintos y cada uno vive solo aquí:

- CLASES_BIBLIOTECA: lo que la biblioteca puede contener (ingesta, restricción CHECK, consulta por ID o
  por una búsqueda que pide esas clases de forma explícita).
- CLASES_AGENTES: lo que un agente recibe hoy (búsqueda por defecto, relaciones entre unidades, listas
  curadas, grafo, catálogo y evaluaciones).

La clase 07 abre el bloque outbound. Las clases 07–12 están en la biblioteca, pero ningún agente las lee
salvo las unidades de una metodología activada (METODOLOGIAS_ACTIVAS): cada metodología de outbound abre
solo su lista curada, con su evaluación y en los roles que la usan. CLASES_AGENTES no se amplía.
"""
import re

CLASES_BIBLIOTECA=tuple(range(1,13))
CLASES_AGENTES=tuple(range(1,7))


def patron(clases):
    """Fragmento de regex que acepta el número de dos cifras de cada clase: «(?:01|02|…)»."""
    return '(?:'+'|'.join(f'{n:02}' for n in clases)+')'


# Activación por metodología, no por clase. Cada entrada abre a los agentes solo esas unidades 07–12; cualquier otra
# unidad 07–12 sigue rechazada, y la búsqueda por defecto, las relaciones y el catálogo siguen en CLASES_AGENTES.
#   evaluacion: el caso de team_backend.evaluaciones.COURSE_CASES (misma clave) que la activa y la mide.
#   lista: la constante de las unidades, con la misma clave en course_lists de equipos/grafo.yaml.
#   roles: los nodos del grafo que la cargan; ningún otro nodo puede enlazar la lista.
#   unidades: la lista curada completa, en orden; se cargan enteras, sin búsqueda dinámica.
METODOLOGIAS_ACTIVAS={
    'primer_mensaje':{'evaluacion':'BIB-09-primer-mensaje','lista':'operador.FIRST_MESSAGE_UNITS',
                      'roles':('relaciones_comunidad','lider_jev'),
                      'unidades':('LI-09-M002-K04','LI-09-M002-K05','LI-09-M003-K02','LI-09-V011-K01',
                                  'LI-09-M003-K03','LI-09-M003-K04','LI-09-M004-K02')},
}
_DE_AGENTES=re.compile(rf'LI-{patron(CLASES_AGENTES)}-[A-Z0-9]+-K\d+')


def legible_por_agentes(uid,metodologia=None):
    """Si un agente puede cargar o citar `uid`: de las clases que leen hoy, o de la metodología activada que lo pide.
    Sin metodología, una unidad 07–12 nunca es legible, aunque esté activada para otra."""
    if isinstance(uid,str) and _DE_AGENTES.fullmatch(uid):return True
    activa=METODOLOGIAS_ACTIVAS.get(metodologia)
    return bool(activa) and uid in activa['unidades']


def rango(clases):
    """Rótulo legible, p. ej. «01–12»."""
    return f'{min(clases):02}–{max(clases):02}'


def validar(clases):
    """Tupla ordenada de clases pedidas explícitamente; falla con cualquier clase que la biblioteca no contiene."""
    if isinstance(clases,(str,bytes)) or not clases:raise ValueError('Clases inválidas')
    pedidas=tuple(sorted(set(clases)))
    if any(type(n) is not int or n not in CLASES_BIBLIOTECA for n in pedidas):
        raise ValueError(f'Clase fuera de la biblioteca ({rango(CLASES_BIBLIOTECA)})')
    return pedidas
