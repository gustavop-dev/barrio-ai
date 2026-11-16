"""Qué clases del curso guarda la biblioteca y cuáles pueden leer hoy los agentes.

Son dos conceptos distintos y cada uno vive solo aquí:

- CLASES_BIBLIOTECA: lo que la biblioteca puede contener (ingesta, restricción CHECK, consulta por ID o
  por una búsqueda que pide esas clases de forma explícita).
- CLASES_AGENTES: lo que un agente recibe hoy (búsqueda por defecto, relaciones entre unidades, listas
  curadas, grafo, catálogo y evaluaciones).

La clase 07 abre el bloque outbound. Las clases 07–12 están en la biblioteca, pero ningún agente las lee
hasta que cada metodología de outbound se active con su evaluación. Ampliar CLASES_AGENTES es esa
activación, no un ajuste de configuración.
"""

CLASES_BIBLIOTECA=tuple(range(1,13))
CLASES_AGENTES=tuple(range(1,7))


def patron(clases):
    """Fragmento de regex que acepta el número de dos cifras de cada clase: «(?:01|02|…)»."""
    return '(?:'+'|'.join(f'{n:02}' for n in clases)+')'


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
