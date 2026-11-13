"""LinkedIn without Unipile (docs/plan-linkedin-directo.md): everything LinkedIn-specific in one place, with no Django
and no browser import, so the backend's connector and the navegador service (phase 2) share it.

- rutas: routes, query ids and request builders of both APIs LinkedIn's web app uses.
- permitidas: the allowlist every call passes before leaving (writes with their payload checked).
- transporte: Request, Answer, the Transport interface and how an answer is judged.
- lectura: answers read into the connector's shapes.
- cliente: the 21 operations (Cliente), with UnipileConnector's arguments and answers.
- servicio: ServiceTransport, the backend's HTTP client of the navegador service (imports httpx; not loaded here).
"""
from .cliente import Cliente
from .errores import LinkedInError, NoteQuota, Uncertain
from .transporte import Answer, Request, Transport

__all__ = ['Answer', 'Cliente', 'LinkedInError', 'NoteQuota', 'Request', 'Transport', 'Uncertain']
