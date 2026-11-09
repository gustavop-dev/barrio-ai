"""GAL-08 consent, provenance and publication exclusion. No paid calls."""
from django.db import transaction
from django.utils import timezone
from .models import GalleryPhoto, PieceImage
from . import imagenes, orquestacion
from .jobs import audit

CONSENT_VERSION='perfil-gustavo-6-v1'
CONSENT_TEXT=('Perfil autoriza dos retratos (A en grises y B en color) y un banner con micrófono, '
    'camiseta blanca oversized y gafas claras, conservando identidad y sonrisa. '
    'Las notas instruyen a Perfil. Los resultados requieren tu revisión. Estas fotos no se usan en posts.')


@transaction.atomic
def update(user,photo,data):
    photo=GalleryPhoto.objects.select_for_update().get(pk=photo.pk)
    before={k:getattr(photo,k) for k in ('category','profile_edit','profile_role','note','ai_edit')}
    if 'ai_edit' in data and 'allow_ai_edit' in data:raise ValueError('Envía solo ai_edit')
    for field in ('note','allow_ai_edit','ai_edit','category','profile_edit','profile_role'):
        if field in data:setattr(photo,field,data[field].strip() if field=='note' else data[field])
    if data.get('category')=='perfil' and 'profile_edit' not in data:
        photo.profile_edit=True  # Explicit category save carries the scoped explanation in both clients.
    if photo.category!='perfil':photo.profile_edit=False
    if 'note' in data:photo.instruction='';photo.instruction_kind=''
    after={k:getattr(photo,k) for k in before}
    if before!=after:
        photo.profile_version+=1
        if 'category' in data or 'profile_edit' in data:
            photo.profile_consent={'version':CONSENT_VERSION,'actor':user.pk,'at':timezone.now().isoformat(),
                                   'allowed':photo.profile_edit,'scope':'perfil'}
        photo.save()
        if photo.category=='perfil':
            # Sticky on derivatives, even after deleting the source or removing its category.
            PieceImage.objects.filter(source_photo=photo).update(profile_exclusive=True)
        audit(user,'gallery.profile_updated',photo.id,version=photo.profile_version,category=photo.category,
              profile_edit=photo.profile_edit,role=photo.profile_role)
    return photo


def references(owner):
    rows=GalleryPhoto.objects.filter(category='perfil',profile_edit=True,created_by=owner,profile_consent__allowed=True,
        profile_consent__version=CONSENT_VERSION,profile_consent__scope='perfil').order_by('profile_role','id')
    return [dict(id=str(p.id),version=p.profile_version,role=p.profile_role,note=p.note,
                 consent=p.profile_consent,sha256=imagenes.sha(imagenes.read(p.image))) for p in rows]


def stale(refs,owner):
    try:current={p['id']:p for p in references(owner)}
    except (OSError,ValueError):return True
    return any(current.get(p['id'])!=p for p in refs)


def roles(refs,needed=('01','02','03')):
    result={}
    for role in needed:
        matches=[p for p in refs if p['role']==role]
        if len(matches)!=1:raise ValueError(f'Perfil necesita exactamente una referencia activa con función {role}; revisa Galería.')
        result[role]=matches[0]
    return result


def raw_references(refs,owner):
    if stale(refs,owner):raise ValueError('Cambió una referencia, nota o autorización de Perfil; revisa la versión vigente.')
    return {p['role']:imagenes.read(GalleryPhoto.objects.get(pk=p['id']).image) for p in refs if p['role']}
