"""Phase 3 of organizations (docs/plan-organizaciones.md): the identity left the code, and Gustavo's texts did not move.

Every prompt, criterion, schema and drawn text that named him was built from constants before this phase. The hashes
below were taken from origin/main (before phase 3) with the code of then, the database patched out: 109 texts. Here
the same 109 are built with the new API for the installation's first member (Gustavo) and must hash the same, byte for
byte, in the three ways an installation can be:
- after migration 0058 (his profile and ProjectApp's stored, his first voice document confirmed);
- with his member but empty profiles (an installation that got its first member after the migration);
- without members at all (an installation of before organizations, its account without a member).
That keeps the provider prompt cache valid, posicionamiento's version and status, and the classifier's criterion_version.
The infographic's PNG is in the set (infografias.render): the name drawn at its foot is his."""
import hashlib
import importlib
import json
import os
from contextlib import nullcontext
from types import SimpleNamespace as NS
from unittest.mock import patch

from django.apps import apps as django_apps
from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from team_backend import (capturas, capture_intent, comunidad, connectors_images, conversaciones, editor_visual, editorial,
                          estrategia, identidad, imagenes, infografias, lider, mensajes_comprador, operador, perfil_contenido,
                          perfil_marca, perfil_visual, posicionamiento, projectapp, red, referentes_industria,
                          referentes_research, research, respuesta_comprador, respuestas, resumen_semanal, revision_mensual,
                          secuencia_comprador, voz)
from team_backend.models import ConnectorAccount, Member, Organization

PINNED = {
    'capturas.event_details': 'b5c675a46aeffd141a7814ceaa95f872fff2c91b6e4ebc8d5abb263a233f2f54',
    'capturas.route': '7c2b2430c0974b4ea3a90df628b3554bfc4ffaad872683affa4f53adc0d59bf2',
    'capture_intent.guide': '09f07c9e6c3b911b1c44a6ecd5c73e1c263aa5a2d80cacfd7ab0f7a96753b0a5',
    'comunidad.analyst': 'ff330df288d2aca96bb8866170fe6ef79413156b0c532b408c466ef5cddc4076',
    'connectors_images.photo_check': 'adc15c2e201bfca6999e35bbaf0aa915253810c4cee89a87f0ca5de403de54c8',
    'conversaciones.lines': 'fdd6f3a4376ef84fb23416c33bde502a84ce7af83833c113e8969a9d28aff9bb',
    'editor_visual.system': 'a3c5556e4a6362be7f5d419bf68df50d9b5634948845f77617dc21b448244ec7',
    'editorial.direction': 'dc3c3fbddc3fd748b49547b62e27e05cffe331cae681be2d1dc5146dc4078995',
    'editorial.director': 'ff4e5dba11c291ba5e2672b6ed7c56b480d62db2c3d07e0ff6009f06b23b2c3b',
    'editorial.director_schema': '98d9be3296797ebac7ff0edcb3a51b9bb0fa498fdc5955059505aab9ce22ed15',
    'editorial.lectores': '64f07a6457997408b4611020dfaebe17ba7440fff54a71a50df67280a8197c85',
    'editorial.lectores_schema': '922eeeaa0e4b3549dc9f7195f1af09f34ee94d5a73dbd726285a5e53cb671f99',
    'editorial.redactor': '7f1f31084645dd4b4488d80da82856591a797f5f402ae037949277a1418d55f1',
    'editorial.redactor_schema': '42b076334c71bbc33d5221fed5d986b172dac688b98938462d1db36173310a7d',
    'editorial.reparacion': 'd237296b3f1592e6253ad367a4b73f049f08d8fa9783b2bc05428cb85a60fbd7',
    'editorial.reparacion_schema': 'f8d472cc82462c89847ebc1ea092da906d864a197e93f31160c87edcd562eac9',
    'editorial.retoque': 'ae7dd11b31adf4a3a8d47b5f1a58fb9688ee2014e555eeaf9a7fb60cd0f8984d',
    'editorial.retoque_schema': '8c14157789487ba2bceb466da0c1ccaf2f1dade55722c79d1e0ff64e8a646aec',
    'editorial.seleccion': '6cdc3386370bb00c9d45fecf9661e2eb9a82758fb749bf4a133502a3af64c55a',
    'editorial.seleccion_schema': '217c78cc6b2f139d00111f7a86ffc68f3e218705d32f0f6fc5486fd985845934',
    'editorial.verificador': '2b9be3d72af6d385a6c7428e9879f922f0a31a19143dff8ee9d718a4d5125d48',
    'editorial.verificador_schema': '3026c5bd78e45ac27edbeea1405dec44259baf26bddc6443fee49ec23b5f8a07',
    'estrategia.plan': 'ec72eb8713c3f2c7cf6663ed1895368994a198f6ea769186847fc771bbde7a43',
    'imagenes.design': 'a2486ac82758969e39d5024f988c01b8884e98ec7ce94d5607658366b84f410c',
    'imagenes.document_title': '8a65e945c99f1bf4e2e6bd1a17aabbc38841546050e1ea7428d3454724ae7f15',
    'infografias.author': 'ec29b76d468efbf702e33789d4bb8aa87239bd8615cbbaa1298f7763b7340f7d',
    'infografias.fallback': 'bf31be6dd0a05d363f88dc0df6b8ec6075454f41293d63429b966aee187bcc08',
    'infografias.render': 'bf16076806def655d26a56070dda506e6d2ad60295df753c20ef4f75c6301964',
    'lider.checks': 'f497c6c43100e3f2820d17b33bd89b24636fb86a9ca96f4555762314c0b856f1',
    'lider.criteria': 'af5c3d752e71f24c5ed8ee3c6e7b7852ede3e9e3120152617350449a6856d7d7',
    'lider.criteria_projectapp': 'bb5b27757e9ee0b7f66f5927efe46941a63997d642188727eee3e2d26bb74aa6',
    'lider.dm_questions': '279de258711a239afd8423c25201b7b8b3925219f3cccf9f03a68f18cf125737',
    'lider.dm_questions_recorrido': '6a2b12d35b3780e0b841358996dea4104be1dc8a1b91472a990163e727fd20ea',
    'lider.note_questions': '74602ffa204865f5b8e4fbc658bb99b0f1031a800d7c53a0622dcb882ebbed0f',
    'lider.reply_questions_interesado': 'a603eb64880e6d2164a1f5ca996fd4b9542c17e58bec835339a24f85ee3024ad',
    'lider.reply_questions_no_es_el_momento': '0bdd2a43db651ac98d97f495996639c5163345c0a0bf9029414e5b3f54ef7c3f',
    'lider.reply_questions_no_le_interesa': '0bdd2a43db651ac98d97f495996639c5163345c0a0bf9029414e5b3f54ef7c3f',
    'lider.reply_questions_otra_persona': 'c9cf7932e4f6769703b5a43cbc491b8a9e15480a690e6a6ab6134b8b9f62382c',
    'lider.reply_questions_pide_informacion': 'a603eb64880e6d2164a1f5ca996fd4b9542c17e58bec835339a24f85ee3024ad',
    'lider.review_comment_plain': '7ff2bea752bd1f397e56a38c35daa8223cdd9a62ce99307d25080aa61799c62f',
    'lider.review_comment_warm': '51264fc4bc115e3da7d4936108c8b0c4c4dced00d759d0453f4e34e0dc5febe8',
    'lider.review_invite_plain': 'b8c7372f0d6ac9618bd0f1918da27707dfcbee61e34350f19c0e8318b793c591',
    'lider.review_invite_projectapp': '1c261757322a8d2740879687006600dc94573f4778bd113d5fbfe66767491e62',
    'lider.review_post_asked': '7064dfe5ae1375256c314c7fc55931e92678a79120519d89d57860826a327574',
    'lider.review_post_plain': '490698fe6739909d46378d86401ec7f6ec015d194aaab08f7811342869681a8e',
    'lider.review_reply_closing': '42ef4a47cd434d49837fd5114c87f6dc963ca8f1747203cd82615449dc052141',
    'lider.review_reply_plain': '787e8136056aea406b787df1dbe1ad46fdb3e5157e6aaaf34d0b8169589fb625',
    'lider.role_meaning': '29b4b21cb0fd513ccd1ca318081e2fef3f6672614747f3c8ce14e08fe02cd65e',
    'lider.sequence_questions_2': '4f5f62f9538f107e2335965cb8716c8395c4fe18a4a572633a4755e6fbdbf765',
    'lider.sequence_questions_3': '117d8a4c9eb46bfb77f35fa58b222420eccabf94e9e55aed52c8019080d4bf9c',
    'lider.sequence_questions_4': 'd7988793295c06846ea05393ff71b93654405e9bf5151042a405277ea45ff8e0',
    'lider.typesafe_0_lead-review-message': '0f4240049f9dba3154573146a34a2a13c6fe7e5655e9690c8e5308e3c9423b8f',
    'lider.typesafe_1_lead-review-sequence': '2ecdc7765e9d65ea29e18db28a039c1c2c7be98a2a89643ffb0046471555cd50',
    'lider.typesafe_2_lead-review-note': '71165219fa5cef1e65f740f62cc4d6018a1985cf5c25da2e32b585153bee8100',
    'lider.typesafe_3_lead-review-reply': 'e6bafd59485104cb3def3b191aa3d7ab55b2fdc01a1c88b5899c790685b1abd5',
    'lider.typesafe_4_comment-prefilter': '527e5fb5eee1a36deb40e8971aa6fe58e480f14c0931b9432040410d936907bc',
    'lider.typesafe_5_comment-prefilter': '855531780cebdf52b0f2aabb8a802ed07867db80b9d260467839da960a30ddfd',
    'lider.warmup_questions': '2f4e8db4cf75e82210300b31f60d700fb9d39514934dd3201431be94c10d76ce',
    'mensajes_comprador.bridge_rules': '6b4a260b2201e5497459d5c77ee0a7c91a35aacc4187c6aa4adce2234853bd75',
    'mensajes_comprador.message': '429917492478c7a38412fe619100f7e317e004ad97bcd5e0bd8dc6d22ab7b68f',
    'mensajes_comprador.note': '4730eb7fb9c20c93e1944ee30541f79dfe23ca236c746429416b661a0a67a4a5',
    'mensajes_comprador.referral_rules': 'b6aca529ebf472960b1028460444133f2fb87f0bd296519078db17008336968d',
    'mensajes_comprador.return_rules': '8c125d3dec8efcecdda9a0afc74c85ba442ad88aedf2da53b6c935fd5216b5c7',
    'operador.comment': 'f7901102eb9ea9dd4c87b0f7dd4802ec967bfbdfaab5a480c7c45c992746e58f',
    'operador.comment_warm': 'af25212dcb6d07f897f48328187b0aaef6ebf45153046e5a9284b0004c44f883',
    'perfil.brand_version': '9674492f0b48543379927410cca1368245d882087b8616de5971ca3f285e1e1d',
    'perfil_contenido.review': '63fc779dbc27fc8f298f13b69cd80db0a3d89ba0e378514c69b333ee64315d03',
    'perfil_contenido.system': '59290948a120345797db19cd15fc452390602277b631b54825fecb3e23c53032',
    'pos.cases': '9fba009fcaaed1f34bfd47223ac9901d917a01bce30d9d85db50819d76b9e7e6',
    'pos.editorial_direction': '63f9198be2e3bd478f49658f3ae92b7a9fd8acd6979c5869c4f632b6f65bd02c',
    'pos.lead_criteria': 'af5c3d752e71f24c5ed8ee3c6e7b7852ede3e9e3120152617350449a6856d7d7',
    'pos.lead_criteria_projectapp': 'bb5b27757e9ee0b7f66f5927efe46941a63997d642188727eee3e2d26bb74aa6',
    'pos.network_criteria': 'cb8975fd47bfc36c6cd976973dab81f4fb5d24db8900dea0bdab12d04268250b',
    'pos.network_criteria_projectapp': '7725f3845d38fdf266fa6194edeaa96b35fdaceb728d3ced913901db6f9857e3',
    'pos.offer': '8ed732e4aaf01d1e146de7b3b10be92ba989c6b3fe1b83a5dbabf761387e4d07',
    'pos.offer_text': 'bc92f2a7701664716abe32ec05a9735ef1363b8d4160bcbc590e87709ba0bf81',
    'pos.pillars': '76db798c65372a0ba52c70eda21f45785eafd53c76cd98bb0618bafe09480edc',
    'pos.services': '6f80bd125e9185926084bba64d353bb0343a462c563cc5b31cd6ae6a00c4952e',
    'pos.status': '51171939a002b7adc27bcbbcc3168a261d2553390842b362ea57f36a318993bf',
    'pos.version': '03e55852ccb4735d264ef13cbfa30b7c3f04c4b3b432f0818a60daa26e8a1a55',
    'projectapp.case_questions': 'efc226be4c07e004ea2c38286755fa938ba6f1e38f5a1fb56dc8cf8d6fa8762b',
    'projectapp.case_rules': 'afc56d36ad33e061abe975e6bd7f2d4b9df61047a781126e729ae861911b973c',
    'projectapp.size_rule': '7725f714104915853b212e53d98637c6976155fa00af9a90e7346e749b39c837',
    'red.classify': 'ede1f6aef1133af04ee037577d81971cee3e260823160292182802bb39a4c61d',
    'red.classify_projectapp': '1161c529d33bd7fdcfe0887065b99a79ba0dbd26d426dc8532e64945d8abaeda',
    'red.criterion_version': 'e5184ba76a76c62998c033233ce252506557cb6da9ea841ec00595b35f3f088c',
    'red.criterion_version_projectapp': '3c74cbe771e87e8cbddea57e4ec6d9f3ece3805e73094e4c6c79a824a72d8f9b',
    'red.no_fit_rule': 'e19ecd5ebc3ff845c2b742d7741a54b8090355c99612d40e7010c792174b92f8',
    'red.stage': '8f2e44fc186827b75e6b59373ed3c35ea4ae012ee8356cd5d0d41cabd90f0af7',
    'red.stage_projectapp': 'cc05dbe8f14a00b2b7147acd94f02dd24c6aec3c7b2f08d2c5a3d7e73bba2448',
    'referentes_industria.criteria': 'a9cd7cabb38280aa3a6321e055959948581bfde6b5b4e6a6e974c75a541c3c32',
    'referentes_industria.system': '85feedce2ac790daa67edf4ca37948cbd4f55ab35d1c3ea01d91d43354811cef',
    'referentes_research.system': '62047932d29038023981a6ccea42f40b6b095363f79345583f76701ff2b84627',
    'research.intent_guide': 'ce9d6e744bd7501b3a1778b5296a79cb8994a7916cb65ec75bde36c7ecf03441',
    'research.system': '934c2ac331bcbab4aed77a78c1cefb49e36d0da99f96482fcc919410f7e17954',
    'respuesta_comprador.questions': 'bcbdd0480d309b4193fd8ae1af8bafadedaf2496a4e20c01c29863cf974beab7',
    'respuesta_comprador.system_interesado': 'd02ccc266b4c13f21cfe88634845cb72b876c5bd9a249dde79ff1a5fa41f0cb1',
    'respuesta_comprador.system_no_es_el_momento': '900f2d703dfa9d798e10f238a02c82fa0e7c3b020a26ac193e6c2db442d31f38',
    'respuesta_comprador.system_no_le_interesa': 'be4b8d42daebb7a599425949ba4f4b26fdd084245ce1e59b8ecfd9b26ce62d0d',
    'respuesta_comprador.system_otra_persona': '89d5c2a6384ce3fd5cbb979fe2b238ff756946088abba87c43e5295d3b302c47',
    'respuesta_comprador.system_pide_informacion': 'a72ee3db2d52246e5a7326da38172f9685370908c5c04a74ae093a0322b82012',
    'respuestas.reply': 'ea3245e44b576951f44380571443d0d350b1ee0ea065712af0257d7bde883dd9',
    'respuestas.reply_schema': 'dfeac25c3166f4955646d0fd75dd18cf126ea20607ae78fcea613206110b4ed9',
    'resumen_semanal.system': 'e81d65f11b8832f64a87e5707e098603ea51a83e44a09b4a550a803044837fc5',
    'revision_mensual.system': '4957a092b0f4dc2be135d4a8f9d53aee0251261d563ee6b1a306ac011da00d20',
    'secuencia_comprador.system_2': 'e342a465f8b5604db0741f16af1d1efbe4b6a6b1f05afe2169d61b1e0789722b',
    'secuencia_comprador.system_3': 'cbc007587c2b544df7ad540bc0f125684f582d2826d7cf0a319607ac1a56d000',
    'secuencia_comprador.system_4': 'c92f3075286c14cd97b6bcd0b5272f281e530dd09d21eacc31bbf757c7bec000',
    'voz.block': 'c8fc07c13f0825dc36591dd94d36312e1fa5981339b35ad9390849896f78e029',
}


class Rows(list):
    def order_by(self, *a):
        return self


def _projectapp(on):
    return patch.dict(os.environ, {'NETWORK_PROJECTAPP_BUYER_ENABLED': 'true' if on else 'false'})


def capture(member, account):
    """The 109 texts of PINNED, built with the new API for `member` (None: an installation without members)."""
    ident = identidad.of(member)
    out = {}

    def put(name, value):
        out[name] = value if isinstance(value, (str, bytes)) else json.dumps(value, ensure_ascii=False, sort_keys=True,
                                                                            default=str)

    def criterion(system):  # red.criterion_version with fixed inputs; the prefix (evidencia.CRITERION_VERSION) is the same
        return red.criterion_version(system, 0.6, 'bib-v2', '').rsplit(':', 1)[1]

    with _projectapp(False):
        put('pos.editorial_direction', posicionamiento.editorial_direction(ident))
        put('pos.network_criteria', posicionamiento.network_criteria(ident))
        put('pos.network_criteria_projectapp', posicionamiento.network_criteria(ident, projectapp_buyer=True))
        put('pos.lead_criteria', posicionamiento.lead_criteria(ident))
        put('pos.lead_criteria_projectapp', posicionamiento.lead_criteria(ident, projectapp_buyer=True))
        put('pos.offer_text', posicionamiento.offer_text(ident))
        put('pos.version', posicionamiento.version(ident))
        put('pos.status', posicionamiento.status(ident))
        put('pos.services', posicionamiento.services(ident))
        put('pos.cases', posicionamiento.cases(ident))
        put('pos.offer', posicionamiento.offer(ident))
        put('pos.pillars', posicionamiento.pillars(ident))
        put('voz.block', voz.block(ident))
        put('operador.comment', operador.comment_system(False, ident))
        put('operador.comment_warm', operador.comment_system(True, ident))
        put('respuestas.reply', respuestas.reply_system(ident))
        put('respuestas.reply_schema', ident.keyed(respuestas.REPLY_SCHEMA))
        put('red.classify', red.classify_system(ident))
        put('red.criterion_version', criterion(red.classify_system(ident)))
        put('red.stage', red.stage_system(account))
        put('red.stage_projectapp', red.STAGE_SYSTEM_PROJECTAPP)  # names no one
        put('red.no_fit_rule', red.no_fit_rule(ident))
        for name in editorial.STAGES:
            put(f'editorial.{name}', editorial.stage_system(name, ident))
            put(f'editorial.{name}_schema', editorial.stage_schema(name, ident))
        put('editorial.direction', editorial.direction(ident))
        put('estrategia.plan', estrategia.plan_system(ident))
        put('capturas.route', capturas.route_system())
        put('capturas.event_details', capturas.event_details())
        put('resumen_semanal.system', resumen_semanal.system(ident))
        put('revision_mensual.system', revision_mensual.system(ident))
        with referentes_industria.for_account(account) if account else nullcontext():
            put('referentes_industria.system', referentes_industria.system())
            put('referentes_industria.criteria', referentes_industria.criteria())
        put('referentes_research.system', referentes_research.system(account))
        put('mensajes_comprador.message', mensajes_comprador.system_for(mensajes_comprador.MESSAGE, {}, 1, ident)[0])
        put('mensajes_comprador.note', mensajes_comprador.system_for(mensajes_comprador.NOTE, {}, 1, ident)[0])
        put('mensajes_comprador.bridge_rules', ident.render(mensajes_comprador.BRIDGE_RULES))
        put('mensajes_comprador.return_rules', ident.render(mensajes_comprador.RETURN_RULES))
        put('mensajes_comprador.referral_rules', ident.render(mensajes_comprador.REFERRAL_RULES))
        for n in (2, 3, 4):
            put(f'secuencia_comprador.system_{n}', mensajes_comprador.system_for(mensajes_comprador.MESSAGE, {}, n, ident)[0])
        for kind in respuesta_comprador.JOBS:
            put(f'respuesta_comprador.system_{kind}', respuesta_comprador.system_for(kind, False, ident))
        put('respuesta_comprador.questions', {k: (ident.render(q), t, f) for k, (q, t, f) in respuesta_comprador.QUESTIONS.items()})
        put('projectapp.size_rule', projectapp.size_rule(ident))
        put('projectapp.case_questions', projectapp.CASE_QUESTIONS)
        put('projectapp.case_rules', projectapp.CASE_RULES)
        put('lider.criteria', lider.criteria_del_barrio(ident))
        put('lider.checks', lider._render(ident, {
            'CHECKS': lider.CHECKS, 'ORIENTATION_CHECK': lider.ORIENTATION_CHECK, 'CASE_CHECK': lider.CASE_CHECK,
            'BUYER_MESSAGE_CHECKS': lider.BUYER_MESSAGE_CHECKS, 'NOTE_CHECKS': lider.NOTE_CHECKS,
            'SEQUENCE_COMMON': lider.SEQUENCE_COMMON, 'REPLY_COMMON': lider.REPLY_COMMON}))
        put('lider.role_meaning', {k: ident.render(v) for k, v in lider.ROLE_MEANING.items()})
        put('lider.warmup_questions', lider._render(ident, lider.warmup_questions()))
        put('lider.dm_questions', lider._render(ident, lider.dm_questions()))
        put('lider.dm_questions_recorrido', lider._render(ident, lider.dm_questions('recorrido')))
        put('lider.note_questions', lider._render(ident, lider.note_questions()))
        for n in (2, 3, 4):
            put(f'lider.sequence_questions_{n}', lider._render(ident, lider.sequence_questions(n)))
        for kind in ('interesado', 'pide_informacion', 'no_es_el_momento', 'no_le_interesa', 'otra_persona'):
            put(f'lider.reply_questions_{kind}', lider._render(ident, lider.reply_questions(kind)))
    with _projectapp(True):
        put('red.classify_projectapp', red.classify_system(ident))
        put('red.criterion_version_projectapp', criterion(red.classify_system(ident)))
        put('lider.criteria_projectapp', lider.criteria_del_barrio(ident))
    lead_reviews(put, account)
    put('editor_visual.system', editor_visual.system(ident))
    put('imagenes.design', imagenes.design_system(NS(account=account)) if account else imagenes.design_system())
    put('connectors_images.photo_check', connectors_images.photo_check(ident.name))
    put('perfil_contenido.system', perfil_contenido._render(perfil_contenido.SYSTEM))
    put('perfil_contenido.review', perfil_contenido._render(perfil_contenido.REVIEW_SYSTEM))
    put('perfil.brand_version', [perfil_marca.brand_version(ident), perfil_visual.brand_version(ident),
                                 perfil_contenido.brand_version(ident)])
    put('comunidad.analyst', ident.render(comunidad.ANALYST_SYSTEM))
    put('research.system', research.SYSTEM)
    put('research.intent_guide', ident.render(research.INTENT_GUIDE))
    put('capture_intent.guide', ident.render(capture_intent.GUIDE))
    put('conversaciones.lines', conversaciones.lines(ident))
    put('infografias.author', infografias.author(ident))
    put('infografias.fallback', infografias.fallback(ident.name))
    put('infografias.render', infografias.render(dict(infografias.fallback(ident.name)), name=ident.name))
    put('imagenes.document_title', imagenes.document_title(NS(image_spec={}, account=account)) if account else
        'Ideas · ' + ident.name)
    return out


def lead_reviews(put, account):
    """lider._questions for each kind of proposal, review_buyer_draft and comment_worthy, as the baseline built them."""
    orientation = 'Más posts sobre arquitectura.'
    noop = lambda state, questions: {'course_missing': []}
    post = NS(author_name='Ana Autora', text='Un post sobre arquitectura de software.', account=account)
    piece = NS(brief={'thesis': 'Una tesis'}, final_text='El post publicado.')
    contact = NS(headline='Founder at Acme', display_name='Ana', evidence={'comment': 'Buen punto'}, classification={
        'role': 'comprador', 'reason': 'Fundó Acme', 'buyer': {'level': 'probable'}}, signals={'bio': 'bio'},
        location='Austin', network_distance='2', source='own_post', account=account)
    thread = Rows([NS(own=True, author_name='', text='Gracias'), NS(own=False, author_name='Ana', text='¿Y el costo?')])
    facts = ([{'key': 'k', 'version': 1, 'fact': 'Un hecho público'}], [])
    patches = [patch('team_backend.lider.ground_questions', noop),
               patch('knowledge.memory.confirmed_blocks', return_value=facts),
               patch('team_backend.respuestas._thread', return_value=thread),
               patch('team_backend.mensajes_comprador.approved_note', return_value=False),
               patch('team_backend.compuertas.gate_policy', return_value={})]
    for p in patches:
        p.start()
    try:
        for warm in (False, True):
            with patch('team_backend.calentamiento.warmup_post', return_value=warm):
                proposal = NS(capability='INT-03', post=post, payload={'text': 'Un comentario.'}, account=account)
                put(f'lider.review_comment_{"warm" if warm else "plain"}', lider._questions(proposal, orientation))
        for closing in (False, True):
            row = NS(piece=piece, decision={'turn': 2, 'closing': closing, 'dm_opener': 'Hola, seguimos.'}, contact_id=None,
                     author_name='Ana', text='¿Y el costo?')
            proposal = NS(capability='INT-04', comment=row, comment_id=1, payload={'text': 'Depende del alcance.'},
                          account=account)
            put(f'lider.review_reply_{"closing" if closing else "plain"}', lider._questions(proposal, orientation))
        for asked in ([], ['Quiero contar lo de la migración']):
            with patch('team_backend.lider.own_request', return_value=asked):
                proposal = NS(capability='CONT-09', piece_id=None, payload={'text': 'Post'}, account=account)
                put(f'lider.review_post_{"asked" if asked else "plain"}', lider._questions(proposal, orientation))
        for on in (False, True):
            with _projectapp(on):
                proposal = NS(capability='RED-02', contact=contact, payload={'note': 'Hola', 'note_reason': 'r'},
                              account=account)
                put(f'lider.review_invite_{"projectapp" if on else "plain"}', lider._questions(proposal, orientation))
        captured = []
        fake = lambda state, questions, purpose: captured.append((purpose, state, questions)) or {
            'answers': {}, 'model': 'm', 'estimated_usd': 0}
        grounding = {'course_missing': [], 'criterion_sources': {}}
        with patch('team_backend.operador.role_context', return_value=('ctx', grounding)), \
                patch('knowledge.providers.typesafe', side_effect=fake), \
                patch('team_backend.lider._orientation', return_value=orientation), _projectapp(False):
            person = {'nombre': 'Ana'}
            for kind, number, inputs in (('mensaje', 1, {}), ('mensaje', 2, {'seguimiento': {'trabajo': 't'}}), ('nota', 1, {}),
                                         ('respuesta', 1, {'clasificacion': {'tipo': 'interesado'}, 'mensaje': {'texto': 'Sí'}})):
                draft = NS(kind=kind, number=number, text='Texto', contact=NS(account=account),
                           inputs={'persona': person, 'hechos': [{'id': 'h1'}], **inputs})
                lider.review_buyer_draft(draft)
            for warm in (False, True):
                with patch('team_backend.calentamiento.warmup_post', return_value=warm), \
                        patch('team_backend.lider.ground_questions', return_value={'course_missing': []}):
                    lider.comment_worthy(NS(author_name='Ana', text='Post', account=account))
        for i, (purpose, state, questions) in enumerate(captured):
            state = {k: v for k, v in state.items() if k not in ('course_context', 'course_grounding')}
            put(f'lider.typesafe_{i}_{purpose}', {'state': state, 'questions': questions})
    finally:
        for p in patches:
            p.stop()


def digests(texts):
    return {name: hashlib.sha256(value if isinstance(value, bytes) else value.encode()).hexdigest()
            for name, value in texts.items()}


class GustavoSinCambiosTests(TestCase):
    """The 109 pinned texts, rebuilt for Gustavo with the new API."""

    def setUp(self):
        for name in ('NETWORK_PROJECTAPP_BUYER_ENABLED', 'COMMENT_PREFILTER_THRESHOLD'):
            patcher = patch.dict(os.environ)
            patcher.start()
            self.addCleanup(patcher.stop)
            os.environ.pop(name, None)
        self.user = User.objects.create_user('gustavo-pins')
        self.organization = Organization.objects.create(name='ProjectApp', slug='projectapp')
        self.member = Member.objects.create(organization=self.organization, user=self.user, display_name='Gustavo',
                                            role='Fundador', is_admin=True,
                                            created_at=timezone.now() - timezone.timedelta(days=90))
        self.account = ConnectorAccount.objects.create(provider='fake', external_account_id='acc_pins', label='Gustavo',
                                                       member=self.member)

    def assertPinned(self, texts, names=None):
        names = sorted(names or PINNED)
        got = digests(texts)
        self.assertEqual(sorted(got), names)  # every pinned text was built, and nothing else
        changed = [name for name in names if got.get(name) != PINNED[name]]
        self.assertEqual(changed, [], 'Textos de Gustavo que cambiaron: ' + ', '.join(changed))

    def test_after_migration_0058_every_text_is_the_one_of_before(self):
        migration = importlib.import_module('team_backend.migrations.0058_identidad_inicial')
        migration.forwards(django_apps, None)
        self.member.refresh_from_db()
        self.organization.refresh_from_db()
        self.assertEqual((self.member.profile, self.organization.profile),
                         (migration.SEED['member'], migration.SEED['organization']))
        self.assertEqual(voz.current(self.member).kind, 'confirmada')  # his VoiceDocument 1: the same document
        self.assertPinned(capture(self.member, self.account))
        migration.backwards(django_apps, None)
        self.member.refresh_from_db()
        self.organization.refresh_from_db()
        self.assertEqual((self.member.profile, self.organization.profile, voz.documents(self.member).count()), ({}, {}, 0))

    def test_the_first_member_seeded_by_ensure_first_member_keeps_every_text(self):
        identidad.seed_first(self.member)
        self.member.refresh_from_db()
        self.assertEqual(self.member.profile['name'], 'Gustavo')
        self.assertPinned(capture(self.member, self.account))

    def test_with_empty_profiles_the_first_member_keeps_the_initial_identity(self):
        self.assertEqual((self.member.profile, self.organization.profile), ({}, {}))
        self.assertEqual(voz.current(self.member).kind, 'inicial')
        self.assertPinned(capture(self.member, self.account))

    def test_without_members_the_installation_reads_the_initial_identity(self):
        self.account.member = None  # an account of before organizations
        self.account.save(update_fields=['member'])
        Member.objects.all().delete()
        ident = identidad.of_account(self.account)
        self.assertEqual((ident.member, ident.legacy, ident.name), (None, True, 'Gustavo'))
        self.assertPinned(capture(None, self.account))

    def test_the_migration_copies_exactly_the_initial_identity(self):
        migration = importlib.import_module('team_backend.migrations.0058_identidad_inicial')
        self.assertEqual(migration.SEED, identidad.initial())
        self.assertEqual(migration.VOICE_SHA256, hashlib.sha256(voz.resource('tono-de-voz.md').encode()).hexdigest())

    def test_positioning_version_status_and_criterion_version_of_gustavo(self):
        identidad.seed_first(self.member)
        self.assertEqual(digests({'pos.version': posicionamiento.version(self.member),
                                  'pos.status': posicionamiento.status(self.member)}),
                         {'pos.version': PINNED['pos.version'], 'pos.status': PINNED['pos.status']})
        with _projectapp(False):
            version = red.criterion_version(red.classify_system(self.member), 0.6, 'bib-v2', '')
        self.assertEqual(hashlib.sha256(version.rsplit(':', 1)[1].encode()).hexdigest(), PINNED['red.criterion_version'])
