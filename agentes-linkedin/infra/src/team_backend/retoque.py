"""A comment of Gustavo on a ready piece goes back to the team (cycle `retoque_pieza`).

When he comments a piece that is ready and has not gone out, that version does not publish: its proposal is
superseded first. The director reads the comment and decides: only an opinion (nothing changes), new text, a new
image, or both. A new text goes through the rules and the verifier again, with the usual repair round. A photo comment
becomes IMG's edit instruction, from the original photo, with the same visual check; if no edit passes, the director
has already decided whether the post stands with an infographic or is postponed. The package is bound again and a new
proposal goes to the policy gate (Jev) at the same hour when his veto window still fits, otherwise at the next free
slot. Nothing here approves or publishes; a failure never publishes the old version: the piece is blocked and his
ideas go back to the editorial table.

A ready piece whose last version the lead (or the policy) discarded is reworked too: his comment is an order, and the
discard only said that version does not go out. The photos and ideas the discard released are taken back first.
"""
import os
from datetime import timedelta
from decimal import Decimal

from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone

from . import capturas, editor_visual, editorial, guardas, imagenes, operador, orientacion, orquestacion, urgente
from .grafo import load_graph
from .models import ActionExecution, ActionProposal, Capture, ConnectorAccount, CycleLedger, EditorialPiece, GalleryPhoto, Job

CYCLE = 'retoque_pieza'
GATE_EDGE = 'pieza_diaria_gate_0'
OPEN = (ActionProposal.State.PROPOSED, ActionProposal.State.APPROVED)
FROZEN = ('primary_reader', 'modality', 'pillar', 'thesis', 'approach', 'format', 'reader_value', 'evidence',
          'success_criterion', 'avoid')
PHOTO_ATTEMPTS = 2


def min_usd():
    """A rework (director, verifier, one edit and its checks) reserves about this much."""
    return Decimal(os.environ.get('EDITORIAL_REWORK_MIN_USD', '1'))


def open_proposal(piece):
    return piece.proposals.filter(state__in=OPEN, execution__isnull=True).order_by('-created_at').first()


def discarded(piece):
    """The last version of the piece when the lead or the policy discarded it and no rework has claimed it yet."""
    last = piece.proposals.order_by('-created_at').first()
    if (last is None or last.state != ActionProposal.State.DISCARDED or (last.review or {}).get('reworked_by')
            or ActionExecution.objects.filter(proposal=last).exists()):
        return None
    return last


def eligible(piece, now=None):
    """The version his comment reworks on a ready piece that has not gone out yet (its open proposal, or the last one
    when the lead discarded it), or None: then the comment is only noted."""
    now = now or timezone.now()
    if piece is None or piece.state != EditorialPiece.State.READY or piece.scheduled_for <= now:
        return None
    return open_proposal(piece) or discarded(piece)


def gate_left(piece):
    """Leader reviews left in the piece's own cycle: each new version needs one."""
    row = CycleLedger.objects.filter(cycle='pieza_diaria', key=str(piece.id)).first()
    edge = next(e for e in load_graph()['edges'] if e['id'] == GATE_EDGE)
    if row is None:
        return edge['max_calls_per_cycle']  # legacy piece without a cycle: its gate runs without one
    if row.state == 'stopped':
        return 0
    used = sum(GATE_EDGE in call.get('edges', [call.get('edge')]) for call in row.progress_ledger.get('calls', {}).values())
    return edge['max_calls_per_cycle'] - used


def _clip(text, limit=300):
    text = ' '.join((text or '').split())
    return text if len(text) <= limit else text[:limit - 1] + '…'


def _record(capture, state, text, **extra):
    """The comment keeps its place (NOTED) and says what the team did with it."""
    capture.refresh_from_db()
    capture.routed_to = dict(capture.routed_to or {}, rework=dict(extra, state=state, at=timezone.now().isoformat()))
    capture.outcome = capturas._outcome('anotado', _clip(text, 500), f'/calendario/pieza/{capture.context_id}')
    capture.save(update_fields=['routed_to', 'outcome'])
    return capture


def _notice(kind, title, detail, piece, ref):
    from .notificaciones import avisar
    avisar(kind, title, detail[:300], link=f'/calendario/pieza/{piece.id}', ref=ref)


# --------------------------------------------------------------------------- entry point (job process_capture)

def run(capture):
    """After `capturas.process` routed a comment on a ready piece. Business outcomes never raise."""
    piece = EditorialPiece.objects.filter(id=capture.context_id).first()
    if capture.state != Capture.State.NOTED or (capture.routed_to or {}).get('rework') != 'pending':
        return capture
    old = eligible(piece)
    if old is None:
        busy = piece is not None and piece.state == EditorialPiece.State.READY and piece.scheduled_for > timezone.now()
        return _record(capture, 'sin_cambios', 'El equipo ya está rehaciendo esta pieza; tu comentario queda para el equipo.' if busy
                       else 'La pieza ya no estaba pendiente de publicar; queda como comentario para el equipo.')
    day = f'{piece.slot_date:%d/%m}'
    if gate_left(piece) < 1 or editorial.budget_left() < min_usd():
        why = ('ya no le quedan revisiones del líder en su ciclo' if gate_left(piece) < 1
               else 'no queda presupuesto de IA para rehacerla hoy')
        after = ('Esa versión ya no sale.' if old.state == ActionProposal.State.DISCARDED
                 else 'Si no quieres que salga así, vétala en su detalle.')
        _notice('piece_blocked', f'No pude rehacer la pieza del {day}', f'Tu comentario quedó anotado, pero {why}. {after}',
                piece, f'piece_rework:{capture.id}')
        return _record(capture, 'sin_retoque', f'Quedó anotado, pero {why}. {after}')
    if not _hold(old, capture):
        return _record(capture, 'sin_cambios', 'La pieza ya se estaba publicando; tu comentario queda para el equipo.')
    try:
        if old.state == ActionProposal.State.DISCARDED:
            _revive(piece)
        return _rework(capture, piece, old)
    except Exception as exc:
        reason = str(exc) if isinstance(exc, (ValueError, orquestacion.CycleStopped)) else 'error interno al rehacerla'
        _fail(capture, piece, reason)
        if not isinstance(exc, (ValueError, orquestacion.CycleStopped)):
            raise
        return capture


def _hold(old, capture):
    """The commented version never publishes: supersede it unless it is already being executed. A discarded version
    already does not publish: the rework only claims it, so a second comment does not start a second rework."""
    with transaction.atomic():
        proposal = ActionProposal.objects.select_for_update().get(pk=old.pk)
        if ActionExecution.objects.filter(proposal=proposal).exists():
            return False
        if proposal.state == ActionProposal.State.DISCARDED:
            if (proposal.review or {}).get('reworked_by') or proposal.piece.proposals.filter(created_at__gt=proposal.created_at).exists():
                return False
            proposal.review = dict(proposal.review or {}, reworked_by=str(capture.id))
            proposal.save(update_fields=['review'])
            operador._audit(None, 'editorial.rework_after_discard', proposal.id, capture=str(capture.id))
            return True
        if proposal.state not in OPEN:
            return False
        proposal.state = ActionProposal.State.SUPERSEDED
        proposal.decided_at = timezone.now()
        proposal.decision_note = 'Gustavo la comentó: el equipo la rehace antes de publicarla'
        proposal.save(update_fields=['state', 'decided_at', 'decision_note'])
        operador._audit(None, 'operator.superseded', proposal.id, reason='comment', capture=str(capture.id))
    return True


def _revive(piece):
    """Take back what the discard released (capturas.release_ideas): the piece's photos (when another piece chose or
    published one meanwhile, the rework fails and the piece is postponed) and the ideas whose last attempt was this
    piece and that no other piece reserved since."""
    for row in piece.images.exclude(source_photo=None).select_related('source_photo'):
        photo = row.source_photo
        if photo.chosen_piece_id not in (None, piece.id) or photo.state == GalleryPhoto.State.PUBLISHED:
            raise ValueError('Su foto ya la usa otra pieza')
        if photo.chosen_piece_id is None:
            photo.state = GalleryPhoto.State.EDITED if row.edited else GalleryPhoto.State.CHOSEN
            photo.chosen_piece, photo.chosen_for = piece, piece.slot_date
            photo.save(update_fields=['state', 'chosen_piece', 'chosen_for'])
    pid = str(piece.id)
    for capture in Capture.objects.filter(state=Capture.State.IDEA, publish_asap_expected_slot__isnull=True,
                                          routed_to__intentos_en__contains=[pid]):
        routed = dict(capture.routed_to or {})
        if routed['intentos_en'][-1:] != [pid]:
            continue
        routed.update(intentos=max(routed.get('intentos', 1) - 1, 0), intentos_en=routed['intentos_en'][:-1])
        capture.routed_to = routed
        capture.save(update_fields=['routed_to'])
        capturas.mark_used([capture.id], piece)


def _fail(capture, piece, reason):
    """Nothing publishes: the piece is blocked and his ideas (and photos) go back to the table to be redone."""
    with transaction.atomic():
        piece = EditorialPiece.objects.select_for_update().get(pk=piece.pk)
        piece.state = EditorialPiece.State.BLOCKED
        piece.note = ('No se pudo aplicar el comentario de Gustavo: ' + reason)[:2000]
        piece.save(update_fields=['state', 'note', 'updated_at'])
        operador._audit(None, 'editorial.rework_failed', piece.id, capture=str(capture.id), reason=reason[:500])
    capturas.release_ideas(piece, 'no se pudo aplicar tu comentario')
    urgente.assign_slots()
    _notice('piece_blocked', f'No pude rehacer la pieza del {piece.slot_date:%d/%m}',
            f'{reason}. No sale así: tus ideas vuelven a la mesa editorial para rehacerla.', piece, f'piece_rework:{capture.id}')
    _record(capture, 'aplazada', f'No pude aplicarlo ({_clip(reason, 200)}); la pieza no sale así y tus ideas vuelven a la mesa.',
            reason=reason[:500])


def pending_comments(now=None):
    """Comments he left on a ready piece AFTER its current version was proposed, before this flow existed: they asked
    for a change that nobody applied (the director only read earlier ones as feedback)."""
    rows = []
    for capture in Capture.objects.filter(context_type='pieza', state=Capture.State.NOTED).order_by('created_at'):
        if 'rework' in (capture.routed_to or {}):
            continue
        piece = EditorialPiece.objects.filter(id=capture.context_id).first()
        proposal = eligible(piece, now)
        if proposal is not None and capture.created_at > proposal.created_at:
            rows.append((capture, piece, proposal))
    return rows


def apply_pending(now=None):
    """Ops (management command retocar_comentarios --aplicar): run the rework for each pending comment, oldest first."""
    done = []
    for capture, piece, _ in pending_comments(now):
        capture.routed_to = dict(capture.routed_to or {}, rework='pending')
        capture.save(update_fields=['routed_to'])
        done.append(run(capture))
    return done


# --------------------------------------------------------------------------- the rework

def _image_context(piece):
    photos = {p['id']: p for p in editor_visual.gallery(piece)}
    rows = list(piece.images.order_by('position'))
    return {'kind': piece.image_kind, 'reason': piece.image_reason,
            'images': [{'kind': r.kind, 'alt': r.alt, 'edited': r.edited, 'reason': r.reason,
                        'edit_instruction': (r.review or {}).get('instruction', '')} for r in rows],
            'photos': [{'id': str(r.source_photo_id), 'note': photos.get(str(r.source_photo_id), {}).get('note', ''),
                        'ai_edit': r.ai_edit} for r in rows if r.source_photo_id],
            'design': piece.image_spec or None}


def _rework(capture, piece, old):
    user = capture.created_by
    job = Job.objects.filter(id=capturas.job_id(capture)).first()
    runtime = orquestacion.Runtime.open(CYCLE, str(capture.id), user, job,
        facts={'piece': str(piece.id), 'capture': str(capture.id), 'proposal': str(old.id)},
        plan=['decidir', 'texto_si_hace_falta', 'verificar', 'imagen_si_hace_falta', 'reamarrar', 'propuesta'])
    with runtime.session():
        try:
            record = _apply(capture, piece, old)
        except ValueError as exc:
            runtime.finish({'state': 'failed', 'reason': str(exc)[:500]})
            raise
        runtime.finish(record)
    return _propose(capture, piece, old, record)


def _apply(capture, piece, old):
    public, private = guardas.blocks()
    memory = {'public_facts': public, 'private_guidance': private, 'orientation': orientacion.text()}
    frozen = {k: piece.brief.get(k) for k in FROZEN}
    claims = piece.verification.get('claims') or piece.selection.get('claims') or []
    decision, model = editorial._call_stage(piece, 'retoque', dict(memory, comment=capture.text, text=piece.final_text,
        brief=frozen, claims=claims, image=_image_context(piece), sources=piece.signals))
    kind = decision.get('decision')
    record = {'capture': str(capture.id), 'decision': kind, 'reason': decision.get('reason', ''),
              'changes': decision.get('changes') or [], 'summary': decision.get('summary_for_gustavo', ''), 'model': model,
              'previous_proposal': str(old.id), 'previous_text_sha256': editorial._sha(old.payload.get('text', '')),
              'previous_media': old.payload.get('media'), 'text_changed': False, 'image_changed': False}
    if kind in ('texto', 'ambos'):
        record['text_changed'] = _rewrite(piece, decision, memory, frozen, public, private, capture)
    route = decision.get('image_route') if kind in ('imagen', 'ambos') else 'ninguna'
    client = imagenes.connector.ImageConnector()
    instruction = (decision.get('image_instruction') or '').strip() or capture.text
    if route == 'editar_foto' and not piece.images.exclude(source_photo=None).exists():
        route = 'infografia'  # nothing to edit: the director's other image route
    if route == 'editar_foto':
        attempts = _edit_photos(piece, instruction, client, public, capture)
        record['photo_attempts'] = attempts
        if attempts[-1:] != ['ok']:
            if decision.get('if_image_fails') != 'infografia':
                raise ValueError('La edición de la foto no pasó la revisión visual (' + '; '.join(attempts)[:300] + ')')
            route = record['fallback'] = 'infografia'
        record['image_changed'] = True
    if route == 'infografia':
        _redesign(piece, public, private, client, [instruction])
        record['image_changed'] = True
    elif record['text_changed'] and piece.image_kind in ('infografia', 'carrusel'):
        record['design_recheck'] = _recheck_design(piece, public, private, client)
    if kind in ('imagen', 'ambos', 'texto') and not (record['text_changed'] or record['image_changed']):
        raise ValueError('El director no dejó un cambio que aplicar')
    editor_visual.bind(piece, public, private, rework=str(capture.id))
    problems = imagenes.issues(piece, imagenes.manifest(piece))
    if problems:
        raise ValueError('; '.join(problems))
    record['media'] = imagenes.manifest(piece)
    return record


def _rewrite(piece, decision, memory, frozen, public, private, capture):
    """His text change, through the same rules, verifier and single repair round as any final text."""
    new = (decision.get('final_text') or '').strip()
    if not new:
        raise ValueError('El director no dejó el texto nuevo')
    if new == piece.final_text:
        return False
    claims = decision.get('claims') or []
    review, reasons, issues = editorial._check(piece, memory, frozen, new, claims, public, private)
    repair = None
    if reasons and editorial.repair_enabled() and editorial._findings(review, issues):
        repair, new, claims, review, reasons, issues = editorial._repair_round(
            piece, memory, frozen, new, claims, review, reasons, issues, public, private)
    if reasons:
        raise ValueError('El texto nuevo no pasó la verificación: ' + '; '.join(reasons)[:400])
    piece.final_text = new
    piece.verification = dict(review or {}, model_verdict=(review or {}).get('verdict'), verdict='ready_for_execution',
        blocking_reasons=[], rules=issues, text_sha256=editorial._sha(new), claims=claims, rework=str(capture.id),
        **({'repair': repair} if repair else {}))
    piece.save(update_fields=['final_text', 'verification', 'updated_at'])
    return True


def _edit_photos(piece, instruction, client, public, capture):
    """Edit each photo of the piece from its original with his instruction; the visual check decides. Returns the
    attempts (the last one is 'ok' when every photo passed)."""
    if not imagenes.can_edit(client):
        return ['edición no disponible (proveedores o claves)']
    rows = list(piece.images.exclude(source_photo=None).select_related('source_photo').order_by('position'))
    accepted, attempts = [], []
    for row in rows:
        raw = imagenes.read(row.source_photo.image)
        for n in range(1, PHOTO_ATTEMPTS + 1):
            try:
                candidate, review, size = imagenes.edit_photo(piece, row.source_photo, raw, instruction, client, public,
                                                              suffix=f':retoque:{capture.id}:{n}')
            except (ValueError, OSError) as exc:
                attempts.append(_clip(str(exc), 200))
                continue
            if review.get('ok') and review.get('sha256') == [imagenes.sha(candidate)]:
                accepted.append((row, candidate, review, size))
                break
            attempts.append(_clip('; '.join(review.get('reasons') or ['comprobación desfavorable']), 200))
        else:
            return attempts  # one photo did not pass: the piece does not go out half edited
    with transaction.atomic():
        for row, candidate, review, size in accepted:
            row.image.save('edicion.png', ContentFile(candidate), save=False)
            row.mime = 'image/png'
            row.width, row.height = size
            row.sha256 = imagenes.sha(candidate)
            row.edited = True
            row.review = dict(review, instruction=instruction)  # the next comment edits the original again: it keeps this
            row.reason = _clip('Comentario de Gustavo: ' + capture.text, 1000)
            row.save()
            row.source_photo.state = 'editada'
            row.source_photo.save(update_fields=['state'])
        piece.image_review = dict(piece.image_review, ok=True,
                                  sha256=list(piece.images.order_by('position').values_list('sha256', flat=True)))
        piece.save(update_fields=['image_review', 'updated_at'])
    return attempts + ['ok']


def _redesign(piece, public, private, client, findings):
    """A new infographic (or carousel) from the current text, with his comment as the designer's finding."""
    if not (isinstance(client, imagenes.connector.FakeImageConnector) or imagenes.connector.available('anthropic')):
        raise ValueError('Sin proveedor visual para rehacer la imagen')
    binding = piece.image_review.get('visual_binding', {})
    with transaction.atomic():
        imagenes.release(piece)  # a replaced photo goes back to the gallery
        piece.images.all().delete()
        if piece.image_kind not in ('infografia', 'carrusel'):
            piece.image_kind, piece.image_spec = 'infografia', {}
        piece.image_reason = _clip('Rehecha por un comentario de Gustavo', 500)
        piece.image_review = {'started': True, 'visual_binding': binding}
        piece.save(update_fields=['image_kind', 'image_spec', 'image_reason', 'image_review', 'updated_at'])
    result = imagenes.design(piece, public, private, client, findings=findings, previous=piece.image_spec or None)
    piece.image_review = dict(result, visual_binding=binding)
    piece.save(update_fields=['image_review', 'image_document', 'image_document_sha256', 'updated_at'])


def _recheck_design(piece, public, private, client):
    """The text changed and the infographic stays: the visual check reads it again against the new text."""
    from .research import editorial_sources
    if not (isinstance(client, imagenes.connector.FakeImageConnector) or imagenes.connector.available('anthropic')):
        raise ValueError('Sin revisión visual para la infografía con el texto nuevo')
    rows = list(piece.images.order_by('position'))
    images = [imagenes.read(r.image) for r in rows]
    review = imagenes._check_call(piece, images, {'post': piece.final_text, 'design': piece.image_spec,
        'public_facts': public, 'sources': editorial_sources(piece)}, client, key='check:retoque:texto')
    if review.get('ok') and review.get('sha256') == [r.sha256 for r in rows]:
        for row in rows:
            row.review = review
            row.save(update_fields=['review'])
        piece.image_review = dict(piece.image_review, ok=True, sha256=review['sha256'])
        piece.save(update_fields=['image_review', 'updated_at'])
        return 'ok'
    _redesign(piece, public, private, client, review.get('reasons') or ['La infografía no encaja con el texto nuevo'])
    return 'rediseñada'


# --------------------------------------------------------------------------- new version

def _when(piece, changed, now):
    """The same hour when his veto window still fits (any future hour if nothing changed), otherwise the next free slot."""
    margin = urgente.veto_window() if changed else timedelta(0)
    if piece.scheduled_for > now + margin and operador.within_window(piece.scheduled_for):
        return piece.scheduled_for, False
    when = urgente.free_slot(piece.account, now, exclude_piece=piece.id)
    if when is None:
        raise ValueError('No hay un hueco libre que respete tu plazo de veto en los próximos días')
    return when, True


def _propose(capture, piece, old, record):
    changed = record['text_changed'] or record['image_changed']
    now = timezone.now()
    with transaction.atomic():
        ConnectorAccount.objects.select_for_update().get(pk=piece.account_id)  # same lock as the slot assignment
        piece = EditorialPiece.objects.select_for_update().get(pk=piece.pk)
        when, moved = _when(piece, changed, now)
        if moved:
            piece.scheduled_for, piece.slot_date = when, urgente._local(when).date()
            piece.save(update_fields=['scheduled_for', 'slot_date', 'updated_at'])
            piece.gallery_photos.update(chosen_for=piece.slot_date)
            Capture.objects.filter(state=Capture.State.USED, routed_to__used_in=str(piece.id)).update(
                publish_asap_expected_slot=when, publish_asap_reason='Se movió para conservar tu plazo de veto tras rehacerla')
        summary = record['summary'] or record['reason']
        dropped = set((old.review or {}).get('reasons') or []) if old.state == ActionProposal.State.DISCARDED else set()
        risks = [r for r in old.risks if not str(r).startswith(('Rehecha por un comentario', 'Líder:')) and r not in dropped]
        if changed:
            risks.append(_clip('Rehecha por un comentario de Gustavo: ' + summary, 500))
        new = operador.create_proposal(old.created_by, None, 'CONT-09',
            {'text': piece.final_text, 'media': imagenes.manifest(piece)}, rationale=old.rationale,
            citations=piece.citations or old.citations, risks=risks, source='agent', origin_job=old.origin_job,
            model=record['model'] or old.model, previous=old, piece=piece)
        operador._audit(None, 'editorial.reworked', piece.id, capture=str(capture.id), proposal=str(new.id),
                        previous=str(old.id), decision=record['decision'], moved=moved)
    local = when.astimezone(operador.local_tz())
    hour = f'{local:%d/%m} a las {local:%H:%M}'
    if changed:
        _notice('piece_scheduled', f'Rehicimos la pieza con tu comentario ({local:%d/%m})',
                f'{summary} Sale el {hour} si el líder la aprueba' + ('; se movió para conservar tu plazo de veto.' if moved else '.'),
                piece, f'piece_rework:{capture.id}')
        text = f'Lo aplicamos: {summary} Sale el {hour}, tras la revisión del líder.'
    else:
        text = f'El director lo tuvo en cuenta sin cambiar la pieza: {record["reason"]} Sale el {hour}.'
    return _record(capture, 'rehecha' if changed else 'sin_cambios', text, decision=record['decision'],
                   proposal=str(new.id), scheduled_for=when.isoformat(), moved=moved)
