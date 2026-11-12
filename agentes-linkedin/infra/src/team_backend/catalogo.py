"""Library catalog: the course units by shelf (the task of one agent) and tier, versioned in the database.

Tiers inside a shelf: «nucleo» loads on every call of the agent, «consulta» is looked up when the task needs it and
«referencia» stays in the library without loading. The course is private and this repository public, so a catalog
arrives from a private file through `manage.py catalogo cargar` and lives only in the database. It points at units and
never changes them.

A version loads inactive. `catalogo activar` adopts it shelf by shelf, once the evaluator (`evaluar --catalogo`) has
compared it with the fixed lists. A shelf without an active version keeps its fixed list in code."""
import hashlib
import json
import re

from django.db import transaction

from .models import ActiveShelf, CatalogEntry, LibraryCatalog

SHELVES=('cliente','perfil','elegir','conectar','comentar','responder','privado','temas','redactar_post','editar','analizar')
TIERS=tuple(CatalogEntry.Tier.values)
REASONS=('','dup','fuera','caso','baja')
# The core loads on every call of the agent and the prompt cache rarely holds between calls: ~6–8 whole units.
CORE_TOKEN_BUDGET=16500
LOADABLE=re.compile(r'LI-0[1-6]-[A-Z0-9]+-K\d+')  # what operador.course_context can read
VERSION=re.compile(r'[a-z0-9][a-z0-9._-]{0,39}')


def core(shelf,version):
    """Core unit IDs of `shelf` in `version`, in the order they were chosen."""
    return list(CatalogEntry.objects.filter(catalog_id=version,shelf=shelf,tier=CatalogEntry.Tier.CORE)
                .order_by('core_rank','unit_id').values_list('unit_id',flat=True))


def units_for(shelf,fallback):
    """(unit IDs, origin) for one call of the agent of `shelf`: the active catalog's core, else the fixed list."""
    active=ActiveShelf.objects.filter(shelf=shelf).first()
    if active:
        ids=core(shelf,active.catalog_id)
        if ids:return ids,f'catalogo:{active.catalog_id}'
    return list(fallback),'lista_fija'


def _entries(data):
    """Validated catalog entries from the private file's JSON (see `manage.py catalogo cargar --help`)."""
    errors=[];entries=[]
    homes={uid:(info or {}).get('principal') for uid,info in (data.get('unidades') or {}).items()}
    levels=data.get('niveles')
    if not isinstance(levels,dict) or not levels:raise ValueError('El catálogo no trae «niveles» por estante.')
    for shelf,level in levels.items():
        if shelf not in SHELVES:errors.append(f'Estante desconocido: {shelf}');continue
        units=(level or {}).get('unidades') or {}
        order=list((level or {}).get('nucleo_orden') or [])
        cores={uid for uid,u in units.items() if (u or {}).get('nivel')=='nucleo'}
        if len(order)!=len(set(order)) or set(order)!=cores:
            errors.append(f'{shelf}: «nucleo_orden» no coincide con las unidades de nivel núcleo.')
        if not cores:errors.append(f'{shelf}: sin núcleo.')
        errors+=[f'{shelf}: {uid} no se puede cargar como núcleo' for uid in order if not LOADABLE.fullmatch(uid)]
        for uid,u in units.items():
            u=u or {}
            tier=u.get('nivel');reason=u.get('razon') or '';duplicate=u.get('duplica') or ''
            if tier not in TIERS:errors.append(f'{shelf}/{uid}: nivel inválido {tier!r}')
            if reason not in REASONS:errors.append(f'{shelf}/{uid}: razón inválida {reason!r}')
            if duplicate and duplicate not in units:errors.append(f'{shelf}/{uid}: duplica una unidad fuera del estante')
            score=u.get('puntaje')
            entries.append(CatalogEntry(unit_id=uid,shelf=shelf,home=homes.get(uid)==shelf,tier=tier,
                                        core_rank=order.index(uid)+1 if uid in order else None,
                                        score=float(score) if isinstance(score,(int,float)) else None,
                                        reason=reason,duplicate_of=duplicate))
    if errors:raise ValueError('Catálogo inválido:\n'+'\n'.join(errors[:20])+(f'\n… y {len(errors)-20} más' if len(errors)>20 else ''))
    return entries


def _check_units(entries):
    from knowledge import db
    ids=sorted({e.unit_id for e in entries}|{e.duplicate_of for e in entries if e.duplicate_of})
    with db.connect() as c:
        found={r['id'] for r in c.execute('SELECT id FROM units WHERE active AND id = ANY(%s)',(ids,)).fetchall()}
    unknown=[uid for uid in ids if uid not in found]
    if unknown:raise ValueError(f'{len(unknown)} unidades no existen o no están activas en esta biblioteca: '+', '.join(unknown[:10]))


def _check_core_budget(entries):
    from . import operador
    for shelf in sorted({e.shelf for e in entries}):
        ids=[e.unit_id for e in sorted((e for e in entries if e.shelf==shelf and e.tier=='nucleo'),key=lambda e:e.core_rank)]
        _,missing,omitted=operador.course_context(ids,CORE_TOKEN_BUDGET)
        if missing:raise ValueError(f'{shelf}: núcleo con unidades ilegibles: '+', '.join(missing))
        if omitted:raise ValueError(f'{shelf}: el núcleo supera {CORE_TOKEN_BUDGET} tokens; no cabrían '+', '.join(omitted))


def load(data):
    """Store a new catalog version, inactive. Versions are immutable: a change is a new version."""
    version=str(data.get('version') or '').strip()
    if not VERSION.fullmatch(version):raise ValueError('Versión del catálogo ausente o inválida (minúsculas, cifras, punto, guion).')
    if LibraryCatalog.objects.filter(version=version).exists():raise ValueError(f'La versión {version} ya está cargada; usa otra versión.')
    entries=_entries(data)
    _check_units(entries)
    _check_core_budget(entries)
    digest=hashlib.sha256(json.dumps(data,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    with transaction.atomic():
        catalog=LibraryCatalog.objects.create(version=version,sha256=digest,
                                              method=str(data.get('metodo_niveles') or data.get('metodo') or '')[:4000])
        for e in entries:e.catalog=catalog
        CatalogEntry.objects.bulk_create(entries)
    return summary(version)


def activate(version,shelves):
    """Adopt `version` for these shelves: their agents load its core from the next call."""
    if not LibraryCatalog.objects.filter(version=version).exists():raise ValueError(f'No hay catálogo {version}.')
    unknown=[s for s in shelves if s not in SHELVES]
    if unknown or not shelves:raise ValueError('Estantes inválidos: '+', '.join(unknown or ['(ninguno)']))
    empty=[s for s in shelves if not core(s,version)]
    if empty:raise ValueError(f'El catálogo {version} no tiene núcleo para: '+', '.join(empty))
    with transaction.atomic():
        for shelf in shelves:ActiveShelf.objects.update_or_create(shelf=shelf,defaults={'catalog_id':version})
    return summary(version)


def deactivate(shelves):
    """These shelves go back to their fixed lists."""
    ActiveShelf.objects.filter(shelf__in=shelves).delete()


def summary(version=None):
    """Counts only: unit IDs and tiers, never course text."""
    versions=[version] if version else list(LibraryCatalog.objects.values_list('version',flat=True))
    out={'activos':{a.shelf:a.catalog_id for a in ActiveShelf.objects.all()},'versiones':{}}
    for v in versions:
        shelves={}
        for e in CatalogEntry.objects.filter(catalog_id=v).values('shelf','tier'):
            shelves.setdefault(e['shelf'],{t:0 for t in TIERS})[e['tier']]+=1
        out['versiones'][v]={'estantes':shelves,'nucleos':{s:core(s,v) for s in sorted(shelves)}}
    return out
