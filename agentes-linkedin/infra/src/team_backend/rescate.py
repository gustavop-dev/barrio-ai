"""EDI-23 · Gustavo ante un bloqueo: ve la razón y decide.

Una pieza que el verificador (texto o reglas), la imagen o el líder dejó fuera ofrece dos salidas en su detalle:

- «Pedir un cambio»: su comentario la rehace (retoque.run, con una versión base descartada que el retoque reclama);
  la versión nueva la revisa el líder en su modo suave para pedidos de Gustavo.
- «Desestimar el bloqueo»: sale tal cual con su aprobación, sin pasar por el líder. Si le falta imagen, el equipo la
  prepara primero (todo post sale con imagen). La aprobación queda ligada a ese texto exacto (verification.override):
  al publicar solo se comprueba lo que LinkedIn exige (longitud e imagen).

Una pieza detenida por presupuesto o por un ciclo detenido no ofrece nada: la rehace el piloto.
"""
from django.db import IntegrityError, transaction
from django.utils import timezone

from . import editorial, guardas, imagenes, operador, retoque
from .models import ActionProposal, CycleLedger, EditorialPiece, OPEN_PIECE_STATES

KIND_LABEL = {'verificador': 'el verificador', 'imagen': 'la imagen', 'lider': 'el líder'}


def blocked_by(piece):
    """'verificador', 'imagen' or 'lider' when Gustavo can act on the block; None otherwise."""
    if piece is None:
        return None
    if piece.state == EditorialPiece.State.BLOCKED:
        if editorial.budget_stopped(piece) or piece.note.startswith('Ciclo detenido') or _cycle_stopped(piece):
            return None
        if piece.proposals.filter(execution__isnull=False).exists():
            return None
        return 'verificador' if (piece.verification or {}).get('verdict') == 'blocked' else 'imagen'
    if piece.state == EditorialPiece.State.READY and retoque.discarded(piece) is not None:
        return 'lider'
    return None


def _cycle_stopped(piece):
    return CycleLedger.objects.filter(cycle='pieza_diaria', key=str(piece.id), state='stopped').exists()


def reasons(piece, kind=None):
    """Why it was blocked, in the words the detail shows."""
    kind = kind or blocked_by(piece)
    if kind == 'verificador':
        return list((piece.verification or {}).get('blocking_reasons') or []) or [piece.note]
    if kind == 'lider':
        last = retoque.discarded(piece)
        review = (last.review or {}) if last else {}
        return list(review.get('reasons') or []) or [last.decision_note if last else piece.note]
    return [piece.note] if piece.note else []


def options(piece, now=None):
    """What the detail offers: None, or {kind, override, change, why_not}."""
    kind = blocked_by(piece)
    if kind is None:
        return None
    now = now or timezone.now()
    why = ''
    if piece.scheduled_for <= now:
        why = 'Su hora ya pasó: ya no se puede publicar ni rehacer.'
    elif kind != 'lider' and EditorialPiece.objects.filter(slot_date=piece.slot_date, state__in=OPEN_PIECE_STATES).exclude(pk=piece.pk).exists():
        why = 'Ese día ya tiene otra pieza programada.'
    return {'kind': kind, 'override': not why, 'change': not why, 'why_not': why}


def _usable(piece, now=None):
    current = options(piece, now)
    if current is None:
        raise ValueError('La pieza ya no está bloqueada.')
    if current['why_not']:
        raise ValueError(current['why_not'])
    return current['kind']


def _image(piece):
    """Every post goes out with an image: the team prepares it when the block came before the visual step."""
    if piece.images.exists():
        return
    if piece.image_review:
        # His order repeats the image step that the block left half done (imagenes.prepare refuses a silent repeat).
        piece.image_review = {}
        piece.save(update_fields=['image_review', 'updated_at'])
    public, private = guardas.blocks()
    editorial._visual(piece, public, private)
    if not piece.images.exists():
        raise ValueError('El equipo no pudo preparar la imagen')


def reopen(piece):
    """The blocked piece becomes ready again with its image and what the block released (ideas and photos). Raises
    ValueError when it cannot (its hour passed, the day has another piece, no image, its photo went elsewhere)."""
    kind = _usable(piece)
    if kind == 'lider':
        retoque._revive(piece)
        return kind
    _image(piece)
    retoque._revive(piece)
    with transaction.atomic():
        locked = EditorialPiece.objects.select_for_update().get(pk=piece.pk)
        locked.state = EditorialPiece.State.READY
        try:
            with transaction.atomic():
                locked.save(update_fields=['state', 'updated_at'])
        except IntegrityError:
            raise ValueError('Ese día ya tiene otra pieza programada.') from None
    piece.refresh_from_db()
    return kind


def override(user, piece_id, note=''):
    """Job override_piece: the piece goes out as it is with Gustavo's approval (no leader). Returns the proposal."""
    piece = EditorialPiece.objects.get(pk=piece_id)
    kind = _usable(piece)
    why = reasons(piece, kind)
    old = retoque.discarded(piece) if kind == 'lider' else None
    try:
        reopen(piece)
    except ValueError as exc:
        _notice(piece, f'No pude desestimar el bloqueo de la pieza del {piece.slot_date:%d/%m}', str(exc))
        raise
    try:
        proposal = _approve(user, piece, kind, why, old, note)
    except Exception:
        if kind != 'lider':  # it was blocked: it does not stay ready without a publication
            EditorialPiece.objects.filter(pk=piece.pk, state=EditorialPiece.State.READY).update(state=EditorialPiece.State.BLOCKED)
        raise
    local = piece.scheduled_for.astimezone(operador.local_tz())
    _notice(piece, f'La pieza del {local:%d/%m} sale con tu aprobación', f'Desestimaste el bloqueo: sale el {local:%d/%m} a las {local:%H:%M}.',
            kind='piece_scheduled')
    proposal.refresh_from_db()
    return proposal


def _approve(user, piece, kind, why, old, note):
    now = timezone.now()
    with transaction.atomic():
        piece = EditorialPiece.objects.select_for_update().get(pk=piece.pk)
        piece.verification = dict(piece.verification or {}, override={
            'by': str(user.pk), 'at': now.isoformat(), 'kind': kind, 'reasons': [str(r)[:500] for r in why[:5]],
            'note': (note or '')[:500], 'text_sha256': editorial._sha(piece.final_text.strip())})  # the proposal stores it stripped
        piece.note = f'Gustavo desestimó el bloqueo de {KIND_LABEL[kind]}.'
        piece.save(update_fields=['verification', 'note', 'updated_at'])
        brief = piece.brief or {}
        risk = f'Gustavo desestimó el bloqueo de {KIND_LABEL[kind]}: ' + '; '.join(str(r) for r in why)
        proposal = operador.create_proposal(user, None, 'CONT-09', {'text': piece.final_text, 'media': imagenes.manifest(piece)},
            rationale=(old.rationale if old else brief.get('thesis') or '')[:4000], citations=piece.citations or (old.citations if old else []),
            risks=[risk[:1000]], source='human', previous=old, piece=piece)
        # Approved in the same transaction: the autopilot never sees it pending, so the leader does not review it.
        operador.approve(user, proposal.id, proposal.payload_hash, note='Gustavo desestimó el bloqueo' + (f': {note}' if note else ''))
        operador._audit(user, 'editorial.block_overridden', piece.id, kind=kind, proposal=str(proposal.id))
    return proposal


def base_for_change(piece, capture):
    """«Pedir un cambio» on a blocked piece: reopen it and leave a discarded base version for the rework to claim."""
    kind = reopen(piece)
    if kind == 'lider':
        return retoque.discarded(piece)
    brief = piece.brief or {}
    return operador.create_proposal(capture.created_by, None, 'CONT-09',
        {'text': piece.final_text, 'media': imagenes.manifest(piece)}, rationale=(brief.get('thesis') or '')[:4000],
        citations=piece.citations, risks=[f'Bloqueada por {KIND_LABEL[kind]}: ' + '; '.join(str(r) for r in reasons(piece, kind))[:900]],
        source='agent', piece=piece, state=ActionProposal.State.DISCARDED)


def _notice(piece, title, detail, kind='piece_blocked'):
    from .notificaciones import avisar
    avisar(kind, title, detail[:300], link=f'/calendario/pieza/{piece.id}', ref=f'piece_override:{piece.id}:{timezone.now():%Y%m%d%H%M}')

