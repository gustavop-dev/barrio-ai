"""Move a LinkedIn account between Unipile and directo on the same ConnectorAccount row (`operador cambiar-proveedor`),
so its contacts, posts, proposals and history stay attached (navegador-contrato.md «Cambiar de proveedor»).

The provider and external id it had are kept on the row (`previous_provider`), written in the same transaction as the
switch, and `--volver` swaps them back. Not read back from the audit log: that is a record of what happened, not
state to restore from. Every switch is audited as well.

What is not carried over: the two providers agree only on person ids (`ACo…`). Posts, comments and their threads,
invitations, chats and messages are stored with the id the provider gave them, and the other one cannot be assumed to
take it (directo refuses anything not shaped like LinkedIn's own, linkedin_directo/rutas.py; Unipile's post ids are
its own encoding). Nothing is translated here: the switch refuses while the account holds such rows unless told to go
on with them as they are (`keep_ids`). It also refuses with an execution in flight (its reconciliation needs the
provider that sent it) or a login from the app in progress. It pauses nothing; the account's status goes back to
unknown until the next check."""
import re

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .connectors_directo import ACCOUNT as DIRECTO_ACCOUNT
from .models import ActionProposal, BrowserLogin, ConnectorAccount, EditorialPiece, PostMetric
from .operador import _audit
from .permissions import require
from .respuestas import reader_account

# The external id each provider takes (connectors.UnipileConnector, connectors_directo.ACCOUNT).
EXTERNAL={'unipile':(re.compile(r'acc_[A-Za-z0-9_\-]+'),'el id de la cuenta en Unipile (acc_…)'),
          'directo':(DIRECTO_ACCOUNT,'el nombre de la cuenta en el servicio navegador (minúsculas, cifras, - y _)')}
IN_FLIGHT=(ActionProposal.State.EXECUTING,ActionProposal.State.SENT,ActionProposal.State.UNCERTAIN)
OPEN=(ActionProposal.State.PROPOSED,ActionProposal.State.APPROVED)
LOGIN_ACTIVE=(BrowserLogin.State.STARTING,BrowserLogin.State.WAITING)


class Refused(ValueError):
    """The switch did not happen; the message says why."""


def provider_ids(account):
    """The account's rows that hold ids of its current provider, by kind (only the kinds it has)."""
    counts={
        'publicaciones observadas':account.posts.count(),
        'comentarios en publicaciones propias':account.post_comments.count(),
        'conversaciones':account.conversations.count(),
        'invitaciones con su id':account.contacts.exclude(invitation_id='').count(),
        'propuestas abiertas sobre una publicación, un comentario o una invitación':account.proposals.filter(
            Q(post__isnull=False)|Q(comment__isnull=False)|Q(capability=ActionProposal.Capability.ACCEPT),state__in=OPEN).count(),
    }
    if reader_account()==account:  # own posts are read (metrics, replies) through the first LinkedIn account
        counts['publicaciones propias medidas']=(EditorialPiece.objects.filter(metrics__has_key='unipile_post_id').count()
                                                 +PostMetric.objects.exclude(provider_post_id='').count())
    return {kind:n for kind,n in counts.items() if n}


def _check(account,to,external,keep_ids):
    if account.provider not in EXTERNAL:
        raise Refused(f'Solo se cambia una cuenta de Unipile o directo; esta es «{account.provider}».')
    if to==account.provider:
        raise Refused(f'La cuenta ya es de {to}.')
    pattern,what=EXTERNAL[to]
    if not pattern.fullmatch(external or ''):
        raise Refused(f'Para {to} hace falta {what}.')
    other=ConnectorAccount.objects.filter(provider=to,external_account_id=external).exclude(pk=account.pk).first()
    if other:
        raise Refused(f'Ya hay otra cuenta de {to} con ese nombre: «{other.label}» ({other.id}). Usa otro nombre.')
    flying=account.proposals.filter(state__in=IN_FLIGHT).count()
    if flying:
        raise Refused(f'La cuenta tiene {flying} acción(es) en curso o por conciliar con {account.provider}. '
                      'Espera a que terminen (o concílialas) antes de cambiar.')
    if account.browser_logins.filter(state__in=LOGIN_ACTIVE).exists():
        raise Refused('Hay una conexión desde la app en curso para esta cuenta. Termínala o cancélala antes.')
    held=provider_ids(account)
    if held and not keep_ids:
        listed=', '.join(f'{n} {kind}' for kind,n in held.items())
        raise Refused(f'La cuenta guarda ids de {account.provider} que {to} puede no aceptar: {listed}. Nada los traduce: '
                      'quedan como historia, y lo que dependa de ellos falla o se repite (navegador-contrato.md '
                      '«Cambiar de proveedor»). Para cambiar igualmente: --aceptar-ids-viejos.')
    return held


def _switch(user,account_id,to,external,keep_ids,back):
    require(user,'manage_jobs')
    with transaction.atomic():
        account=ConnectorAccount.objects.select_for_update().get(pk=account_id)
        if back:
            previous=account.previous_provider or {}
            if not previous.get('provider'):
                raise Refused('Esta cuenta no tiene un proveedor anterior guardado.')
            to,external=previous['provider'],previous.get('external_account_id','')
        held=_check(account,to,external,keep_ids)
        before=account.provider
        account.previous_provider={'provider':before,'external_account_id':account.external_account_id,
                                   'until':timezone.now().isoformat(),'by':user.username}
        account.provider,account.external_account_id=to,external
        # The status was the old provider's; the next check (comprobar, the inbox read) asks the new one.
        account.status,account.is_locked,account.last_checked_at='unknown',False,None
        account.save(update_fields=['provider','external_account_id','previous_provider','status','is_locked',
                                    'last_checked_at'])
        _audit(user,'operator.account_provider_switched',account.id,from_provider=before,to_provider=to,back=back,
               kept_ids=held)
    return account


def switch(user,account,to,external,keep_ids=False):
    """`account` now goes through `to` (unipile|directo) as `external`; its current values are kept for switch_back."""
    return _switch(user,account.pk,to,external,keep_ids,back=False)


def switch_back(user,account,keep_ids=False):
    """The provider and external id the account had before its last switch, back (and the current ones kept)."""
    return _switch(user,account.pk,None,None,keep_ids,back=True)
