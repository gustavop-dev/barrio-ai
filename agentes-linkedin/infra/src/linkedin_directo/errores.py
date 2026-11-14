"""What can go wrong talking to LinkedIn. No backend import: team_backend.connectors_directo maps these to the
connector's exceptions, and the navegador service (phase 2) raises the same ones."""


class LinkedInError(Exception):
    """Definite failure: LinkedIn did not apply the operation, or it never left. pause=True means LinkedIn pushed back
    or the session is gone (401/403/429/999, a redirect, a login or checkpoint page): the account stops until a human
    looks at it. `kind` is short and stable; a LinkedIn error code, when the answer has one, goes in it as
    `linkedin/<code>` so the network's limit rules can read it. kind='budget' is the navegador service's own budget
    per account, never LinkedIn's: nothing left, and `retry_after` says in how many seconds there is room again.
    kind='egress' is the service refusing to open the account by another internet exit: nothing left, and only an
    operator on the server clears it; `since` is when that refusal began (one moment per episode)."""

    def __init__(self, message, *, kind='error', status=None, pause=False, retry_after=None, since=None):
        super().__init__(message)
        self.kind, self.status, self.pause, self.retry_after, self.since = kind, status, pause, retry_after, since


class Uncertain(Exception):
    """A write may have reached LinkedIn (a timeout after sending, a 5xx, an unreadable answer): only a later read
    tells. Never retried."""


class NoteQuota(LinkedInError):
    """The invitation was refused for its note alone and the answer proves no invitation was created."""

    def __init__(self, message, status=None):
        super().__init__(message, kind='note_quota', status=status)
