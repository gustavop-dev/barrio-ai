"""Phase 3 of organizations: the identity of the installation, out of the code (docs/plan-organizaciones.md).

ProjectApp's profile and its first member's (the oldest member, as miembros.first_member_id) get exactly the texts the
code had before this phase (a frozen copy of recursos/identidad-inicial.json as of this migration), each with its first
IdentityRevision (source «migracion»), and her first voice document points to recursos/tono-de-voz.md with its hash.
Nothing is overwritten: a profile that already has values, or a member who already has voice documents, stays as it is.
Without members (a fresh installation) nothing is written; bootstrap_local does the same later (identidad.seed_first).
The reverse step removes only what this step wrote."""
import json

from django.db import migrations
from django.utils import timezone

SOURCE = 'migracion'
VOICE_SHA256 = '767dd3ee4c67a36771988490d8961e5394565e142bde3d4406f223246ef3931c'  # recursos/tono-de-voz.md, stripped
SEED = json.loads(r'''{
 "member": {
  "brand_version": "PerfilLinkedIn-gustavo-addenda-6-v1",
  "company_relation": "Fundó y lidera ProjectApp, un equipo de desarrollo de software a la medida.",
  "identity": "Gustavo es ingeniero de producto con criterio de negocio: convierte necesidades de negocio en software que funciona, lo evoluciona e integra IA cuando resuelve un problema concreto.",
  "limits": "humo y promesas; temas que Gustavo no domina; experiencias, clientes, cifras o resultados inventados; pitch agresivo; datos privados de cualquier persona",
  "name": "Gustavo",
  "personal_startups": true,
  "purposes": {}
 },
 "organization": {
  "cases": {
   "educacion_en_linea": "ProjectApp construyó una plataforma grande a la medida de educación en línea",
   "retail_ecommerce": "ProjectApp construyó una plataforma grande a la medida de retail"
  },
  "date": "2026-11-12",
  "language": "Publica en LinkedIn, en inglés.",
  "location": "el barrio se construye en EE. UU.: compradores (founders) y comunidad van primero si están allí; los de Latinoamérica también entran, después.",
  "modalities": {
   "alianzas": {
    "neighborhood": "estudios o agencias complementarios, freelancers senior, aceleradoras, inversores o comunidades que recomiendan talento o proveedores",
    "purpose": "relaciones con quienes recomiendan talento o proveedores"
   },
   "comunidad": {
    "neighborhood": "pares, divulgadores y líderes temáticos (producto, software, IA aplicada, startups) que sostienen la conversación del nicho",
    "purpose": "comunidad y autoridad temática en el nicho"
   },
   "personal_startups": {
    "neighborhood": "founders técnicos o de negocio de startups con ronda semilla o posterior, o con clientes que pagan, líderes técnicos y personas que recomiendan talento en startups",
    "purpose": "oportunidades de trabajo personal en startups"
   },
   "projectapp": {
    "neighborhood": "empresas tradicionales de 20 a 200 personas en EE. UU. que necesitan digitalizarse, o que ya tienen software y quieren ampliarlo: su dueño o CEO, o su líder de tecnología (CTO, VP, Head o Director de ingeniería o de TI, gerente de sistemas); founders u operadores de startups que necesitan una entrega externa, un proyecto definido o un equipo continuo; y agencias de marketing, diseño, consultoría o producto que subcontratan el desarrollo de software de sus clientes (partners: traen contratos, no compran para sí)",
    "purpose": "contratos para ProjectApp, el equipo que {nombre} lidera"
   }
  },
  "neighborhood_before": {
   "projectapp": "founders u operadores que necesitan una entrega externa, un proyecto definido o un equipo continuo"
  },
  "not_wanted": "No buscan vendedores ni reclutadores masivos.",
  "offer": {
   "argumento": "nearshore: buena calidad a menor costo",
   "equipo_dedicado": "un equipo dedicado, desde unos 20 millones de pesos colombianos al mes (unos 5.000 USD)",
   "proyecto": "un proyecto por requerimientos, desde unos 20 millones de pesos colombianos"
  },
  "pillars": {
   "applied_ai": "incorporar y evaluar IA en soluciones concretas",
   "architecture_delivery": "decisiones de arquitectura y de entrega al construir productos reales",
   "business_to_product": "traducir problemas de negocio en decisiones de producto y de software"
  },
  "services": {
   "ia_aplicada": {
    "label": "incorporar IA en soluciones concretas",
    "source": "IDENTITY, pilar applied_ai",
    "terms": [
     "applied ai",
     "ai development"
    ]
   },
   "liderazgo_tecnico": {
    "label": "liderazgo técnico en startups: decisiones de arquitectura y de entrega",
    "source": "modalidad personal_startups, pilar architecture_delivery",
    "terms": [
     "fractional cto",
     "technical leadership"
    ]
   },
   "producto": {
    "label": "convertir necesidades de negocio en un producto de software que funciona y evolucionarlo",
    "source": "IDENTITY, pilar business_to_product",
    "terms": [
     "product development",
     "mvp development"
    ]
   },
   "software_a_la_medida": {
    "label": "desarrollo de software a la medida (entrega externa, proyecto definido o equipo continuo)",
    "source": "PROJECTAPP, modalidad projectapp",
    "terms": [
     "custom software development",
     "software development agency"
    ]
   }
  },
  "status": "propuesta interna v2; {nombre} la supervisa",
  "version": "posicionamiento-v2"
 },
 "voice": {
  "guide": "Voz de Gustavo. Debajo está su documento «Tono de voz», escrito por él: es la referencia de cómo habla.\nLa voz decide CÓMO se dice algo; nunca QUÉ le pasó a Gustavo. Aplícala así en LinkedIn:\n\nQué se conserva siempre:\n- Ritmo de conversación por pequeñas entregas: una idea por línea o párrafo corto, y los saltos de línea como\n  pausas. Alterna una frase larga que explica (porque, entonces, pero) con un remate breve.\n- Pensar en voz alta y matizar: entrar en la idea, ajustar su alcance («sí, pero», «solo que», «o al menos a mí\n  me parece») y dejar visible la relación entre causas y consecuencias.\n- Empezar por algo concreto y aterrizar lo técnico enseguida («o sea», «básicamente») con una comparación cotidiana.\n- Curiosidad y reacción genuina a lo que dijo la otra persona; separar cosas que parecen iguales.\n- Cierre cotidiano y de baja intensidad en lugar de moraleja o llamada a la acción.\n\nRegistro público (la «versión cuidada» que describe el propio documento):\n- Publicaciones propias: soltura y cadencia, sin risas escritas, sin vocales alargadas, sin groserías, sin\n  deformaciones afectivas («sipi», «ño», «beshito») y sin el modo frustrado. Una o dos muletillas por pieza como\n  mucho: la voz está en la cadencia y los matices, no en acumular expresiones.\n- Comentarios: algo más de reacción («qué pro», «me dio curiosidad», «uy») y, si encaja con el hilo, una risa\n  ligera o un emoji. Nunca groserías ni sarcasmo hacia la persona.\n- En inglés: traslada la cadencia y los conectores con equivalentes naturales de un hablante real («I mean»,\n  «here's the thing», «basically», «honestly», «but yeah», «anyway»). No traduzcas modismos colombianos al pie de\n  la letra ni conviertas la voz en caricatura. Frases cortas, palabras corrientes, nada de jerga corporativa.\n- En español: el español colombiano natural del documento, con la misma moderación.\n\nLímites que la voz no cambia:\n- Una historia en primera persona («yo pensé que…», «y yo dije…», «me pasó que…») solo puede contar un hecho de\n  public_facts. Sin ese hecho no hay anécdota: la voz se expresa en opinión, reacción al texto presente, pregunta\n  o razonamiento, nunca en una escena inventada.\n- Las frases de ejemplo del documento muestran cadencia; no las copies.\n- Todas las demás reglas de tu tarea siguen vigentes: sin pitch, sin cifras sin fuente, longitud, hashtags y emojis.",
  "resource": "tono-de-voz.md"
 }
}''')


def forwards(apps, schema_editor):
    Organization = apps.get_model('team_backend', 'Organization')
    Member = apps.get_model('team_backend', 'Member')
    IdentityRevision = apps.get_model('team_backend', 'IdentityRevision')
    VoiceDocument = apps.get_model('team_backend', 'VoiceDocument')
    now = timezone.now()
    first = Member.objects.order_by('created_at', 'pk').select_related('organization').first()
    if first is None:
        return
    organization = first.organization
    if not organization.profile:
        organization.profile = SEED['organization']
        organization.save(update_fields=['profile'])
        IdentityRevision.objects.create(organization=organization, subject='organization', number=1,
                                        changed=sorted(SEED['organization']), before={}, after=SEED['organization'],
                                        source=SOURCE, created_at=now)
    if not first.profile:
        first.profile = SEED['member']
        first.save(update_fields=['profile'])
        IdentityRevision.objects.create(organization=organization, member=first, subject=f'member:{first.pk}', number=1,
                                        changed=sorted(SEED['member']), before={}, after=SEED['member'], source=SOURCE,
                                        created_at=now)
    if not VoiceDocument.objects.filter(member=first).exists():
        VoiceDocument.objects.create(member=first, number=1, state='confirmada', source='recurso',
                                     guide=SEED['voice']['guide'], resource=SEED['voice']['resource'], sha256=VOICE_SHA256,
                                     decided_at=now, note='Voz inicial de la instalación (migración 0058)')


def backwards(apps, schema_editor):
    IdentityRevision = apps.get_model('team_backend', 'IdentityRevision')
    VoiceDocument = apps.get_model('team_backend', 'VoiceDocument')
    Organization = apps.get_model('team_backend', 'Organization')
    Member = apps.get_model('team_backend', 'Member')
    for revision in IdentityRevision.objects.filter(source=SOURCE, number=1):
        if revision.member_id:
            Member.objects.filter(pk=revision.member_id, profile=revision.after).update(profile={})
        else:
            Organization.objects.filter(pk=revision.organization_id, profile=revision.after).update(profile={})
        revision.delete()
    VoiceDocument.objects.filter(number=1, source='recurso', note__endswith='(migración 0058)').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('team_backend', '0057_identidad'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
